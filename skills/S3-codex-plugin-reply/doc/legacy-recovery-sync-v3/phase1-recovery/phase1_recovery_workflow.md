# Phase 1 Recovery Workflow

## 目标

Phase 1 只负责：

- 把 Gmail 回复线程可靠拉回本地
- 把正文和附件转成可读内容
- 把报价尽量结构化
- 把结果稳定写进 master

这一阶段不负责实际回邮件。

## 两种执行模式

### 模式 A：High-Throughput Recovery

适合：

- 需要先把大窗口 thread 全部拉回
- 用户优先要“先收齐数据”

推荐顺序：

1. thread index
2. 切 batch thread ids
3. full fetch
4. attachment inventory 落盘
5. attachment raw download
6. 统一做 text extraction
7. 统一做 pricing extraction
8. 出 review-ready table
9. 分批 sync master

### 模式 B：Deep Processing

适合：

- batch 较少
- 用户希望边跑边进 master

推荐顺序：

1. thread index
2. full fetch
3. attachment text extraction
4. pricing extraction
5. review-ready table
6. preview / audit
7. master sync

## 标准步骤

### Step 1. thread index

- 先拿 thread ids
- 不要一上来全量抓 body
- 默认先收敛到 `20 threads / batch`

### Step 2. small-batch validation

验证：

- `账号ID / 联系方式 / Gmail thread` 归因是否稳定
- 当前窗口是否有附件
- Gmail API 与代理是否稳定
- recent audit thread 是否属于 `Outreach` 还是 `Workstream`

### Step 3. full fetch

每个 batch 至少抓到：

- `thread_id`
- `message_id`
- `reply_at`
- `from_email`
- `subject`
- `body_text`
- `body_html`
- `attachment inventory`

正文必须单独落盘。

### Step 4. attachment extraction

硬规则：

- 所有附件都必须进入处理链
- 最低要求是拿到 `attachment inventory`
- 推荐要求是同日拉回 `raw file`
- 最终要求是全部产出文本提取结果

当前策略：

- PDF: `pdftotext`
- PDF 文本过短: OCR fallback
- image: `tesseract`
- doc/docx: `textutil`
- 其他类型: fallback

### Step 5. pricing extraction

价格提取优先级：

1. 正文明确报价
2. 正文不完整或明确指向附件，再看附件
3. 附件中的明确报价或 package 表
4. 如果没有明确价格，也要保留真实摘录

### Step 6. foreign language handling

外语回复不能跳过：

- 先保留原文证据
- 再补英文理解
- review table / master 入表内容只能是英文或中文
- 若正文、附件文本、OCR 文本为其他语言，必须先自动翻译成英文后再参与意图判断、价格抽取和写表
- 结构化价格字段以英文理解后的结论为准

### Step 7. review-ready table

review-ready table 是 Phase 1 的真相源。

master sync 只能从 review-ready table 写，不允许直接从 raw full messages 写。

### Step 7.5. reply stream classification

在把 recent capture 纳入 replied 主表前，必须先做：

- `Reply_Stream = Outreach / Workstream / Manual_Review`

硬规则：

- 回复 `Mail1 / Mail2 / Mail3` 的 = `Outreach`
- 回复日常交接/执行推进邮件的 = `Workstream`
- 判断不清的 = `Manual_Review`

不能只用 replied 主表命中与否决定是否纳入。

### Step 8. master sync

写 master 前必须：

1. 物理备份
2. 先出 preview
3. 再出 audit
4. 最后写 master
