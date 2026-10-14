"""Optional bridge to a local open-weight model.

Works with Ollama's native API (default http://127.0.0.1:11434) or any
OpenAI-compatible server (llama.cpp, vLLM, LM Studio, text-generation-webui).
If nothing is reachable, callers fall back to the deterministic offline engine.

Privacy is the point: the prompt (which contains vendor names and amounts)
is sent to a process running on localhost, never to a third-party API.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434"
#: gemma2 and llama3.2 are open-weight models served by Ollama out of the box.
DEFAULT_MODEL = "gemma2:2b"


class LocalModel:
    def __init__(self, url=None, model=None, timeout=20):
        self.url = (url or os.environ.get("LOCALLLM_URL") or DEFAULT_URL).rstrip("/")
        self.model = model or os.environ.get("LOCALLLM_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self._available = None
        self._mode = None  # "ollama" or "openai"

    def _probe(self):
        for suffix, mode in (("/api/tags", "ollama"), ("/v1/models", "openai")):
            try:
                req = urllib.request.Request(self.url + suffix,
                                             headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as r:
                    if r.status == 200:
                        return mode
            except Exception:
                continue
        return None

    def available(self):
        if self._available is None:
            self._mode = self._probe()
            self._available = self._mode is not None
        return self._available

    def summarize(self, prompt):
        try:
            if self._mode == "openai":
                payload = {"model": self.model, "temperature": 0.2,
                           "messages": [{"role": "user", "content": prompt}]}
                url = self.url + "/v1/chat/completions"
                body = json.dumps(payload).encode()
                req = urllib.request.Request(url, data=body, method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read())
                return (data["choices"][0]["message"]["content"] or "").strip() or None
            payload = {"model": self.model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.2}}
            body = json.dumps(payload).encode()
            req = urllib.request.Request(self.url + "/api/generate", data=body,
                                         method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
            return (data.get("response") or "").strip() or None
        except Exception:
            return None


def get_model(enabled=True):
    """Return a LocalModel (which may report itself unavailable) or None."""
    if not enabled:
        return None
    return LocalModel()
