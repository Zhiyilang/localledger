# LocalLedger（本地账本）

**给自由职业者的离线发票与收据整理工具。**
把一堆收据丢给它，它**在你自己的电脑上**读完、自动分类每一笔、导出可导入记账软件的 CSV，
再写一份大白话的季度复盘，并列出「该问会计的问题」。**所有数据永不外传。**

为 [Hacktoberfest 2026 DEV 挑战赛](https://dev.to/challenges) Week 2「Side Hustle（副业）」而建。

> 传统记账工具要你的银行流水、收据，还要把 OCR 放到它的云上。对自由职业者来说，
> 这意味着客户名称、报价、银行信息离开本机，还要按月付费。LocalLedger 反过来做：
> 全部本地跑，靠开源权重模型，数据不动、每张收据成本为零。

---

## 为什么「开源 AI」在这里是关键（评委最关心的一点）

自由职业者手里是**别人的**财务数据。用闭源云端 OCR 会坏在三件事上：

1. **隐私**：客户发票含姓名、地址、金额。本地开源权重模型让它们留在磁盘上，无 API、无数据处理协议、无泄露面。
2. **成本**：云端文档 AI 按页计费。一年 400 张收据的自由职业者要么吃掉这笔利润，要么转嫁给客户。本地推理**每张文档边际成本为零**——这才让「每月 5–10 美元」的定价成立。
3. **贴合**：本地模型可用你自己的供应商名和分类做微调。通用 API 学不会「ACME DSGN 是你最大的客户」。

因此 LocalLedger 有**两套可互换引擎**：

| 引擎 | 何时启用 | 作用 |
|---|---|---|
| `deterministic-offline` | 永远可用 | 正则解析 + 关键词分类。**零配置**、不需要模型、不需要联网。 |
| `local-open-weight-model` | 本机 [Ollama](https://ollama.com)（或任意 OpenAI 兼容服务）可达时 | 用大白话写季度叙事。 |

解析与分类是**纯代码、不是模型**——模型只写文字。这让数字可审计，也让工具诚实：**绝不编造金额**。

---

## 快速开始

需要 **Python 3.8+**，无第三方依赖。

```bash
# 1. 扫描收据文件，生成 out/ledger.csv 与 out/quarterly-review.html
python -m localledger scan examples/receipts.txt --no-llm

# 2. 或启动本地网页控制台
python -m localledger serve --port 8780
#    然后打开 http://127.0.0.1:8780/
```

### 可选：启用本地模型

```bash
ollama pull gemma2:2b          # 一个开源权重模型
python -m localledger scan examples/receipts.txt
# engine: local-open-weight-model
```

可用 `LOCALLLM_URL` / `LOCALLLM_MODEL` 覆盖端点与模型（兼容 Ollama、llama.cpp、vLLM、LM Studio）。
若都不可达，会自动回退到确定性引擎——**在任何干净机器上都不会失败。**

---

## 你会得到

- **`out/ledger.csv`**：`date, vendor, amount, currency, category, note, source`，可直接导入记账。
- **`out/quarterly-review.html`**：按币种的合计、带条形图的分类占比、读过的每一张单据、以及会计问题清单。
- **会计问题**：由**你的数据**推导——餐饮抵扣比例、未分类项、最大单笔支出、多币种汇率等。

每一行都带 `evidence` 证据链（`<文件>:<行号> vendor=… / date=… / amount=…`），任何数字都能回溯到原始行。

## 测试

```bash
python eval.py     # 全部断言应通过
```

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
