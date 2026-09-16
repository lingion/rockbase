# Recovery Case Notes

## 2026-03-16 Corestar Reply Recovery

本文件记录一次完整实战中踩过的坑和已固化的修复。

## 已验证有效的做法

### 1. 一个 skill，分两个 phase

`ag-gmail-reply-ops` 不拆 skill 名称，但内部强制分成：

- Phase 1: Recovery & Sync
- Phase 2: Reply Execution

### 2. canonical batch naming

必须统一为：

- `YYYY-MM-DD_batch-00X_*`

### 3. body-first pricing, attachment as supplement

价格判断顺序：

- 先看正文
- 正文不完整，或正文明确说价格在附件里，再看附件

### 4. all attachments must yield text

所有附件默认都要经过一次文本提取。

如果抽不到，也要生成占位文本，不能留空。

### 5. foreign language handling

外语回复必须进入英文理解层，目标是稳定价格和意图判断。

补充固化：

- 入表字段只允许英文或中文
- 非英文/中文正文、附件文本、OCR 价格证据，先自动翻成英文，再参与 review table 和 master 写回
- 原始外语全文继续保留在落盘 body / attachment text 文件中，便于追溯

### 6. pricing excerpt must be evidence-backed

`Reply_Pricing_Excerpt` 只在存在高置信价格证据时填写。

高置信价格证据要求：

- 同时出现“渠道词 / 合作形式 + 价格”
- 来源可以是正文，也可以是附件文本
- 优先正文，附件作为补充

如果没有明确价格，或者价格无法和任何渠道 / 形式建立稳定对应：

- `Reply_Pricing_Excerpt` 留空
- 不再默认写 `[No explicit pricing] ...`

### 7. do not parallel-write master

同一个 master CSV 的 sync 不能并行跑。

### 8. replied master can append from full master

- 已有行：更新
- 缺失行但 full master 能命中：补基础字段后追加
- full master 命不中：只进 audit
