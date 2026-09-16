# NORTH STAR

日期：2026-05-07

## 为什么要单独放一份文档

这份文档建议**独立存在**，而不是只埋在某个 SPEC 里。

原因：

1. `SPEC` 解决的是“怎么做”
2. `Field Mapping` 解决的是“写到哪里”
3. `Workflow` 解决的是“按什么顺序执行”
4. `North Star` 解决的是“我们最终到底想把系统做成什么样”

后面不管我们改：

- 字段
- 排序
- OCR 分流
- draft 流程
- 自动化 heartbeat / cron

都应该先回看这份 North Star，避免系统越来越复杂，却偏离真正目标。

---

## 用户真正的需要

你的最终需要不是“再做一个 skill”，而是让系统逐步变成一个**可独立运转的 KOL reply operations agent**。

这个 agent 最终应该能够在日常工作中，基于：

- Gmail 插件
- 本地脚本
- 现有 skills
- 本地 master CSV

稳定完成下面这些事：

1. 每天自动扫描 Gmail inbox
2. 区分：
   - 正常办公邮件
   - 系统邮件 / 噪音
   - KOL 开发与谈价邮件
3. 把 KOL 相关 thread 同步回本地 master
4. 分析对方是否回复、是否报价、报价属于第几轮
5. 检测附件并进入 OCR 分流
6. 基于完整 thread 判断下一步回复策略
7. 生成 reply draft 并写回 Gmail 草稿箱
8. 更新价格表和进度表
9. 每天把总结汇报给 Steve

---

## 最终目标系统

### 一句话版本

> 每天自动扫描 Gmail，识别 KOL thread，更新本地 master，分析价格与进度，必要时 OCR 附件，生成合适的回复草稿，并给 Steve 一份可信的每日总结。

### 更完整版本

这个系统最终应该是一个：

- **以 Gmail 插件为读入口**
- **以 V3 master 为本地真相源**
- **以场景化 reply reference 为判断规则**
- **以 OCR 分流为价格证据补强**
- **以 reply draft 为输出动作**
- **以 daily summary 为管理界面**

的闭环系统。

---

## 系统边界

### 系统应该完成的

1. 自动扫描 inbox
2. 自动筛掉不相关邮件
3. 自动识别 KOL 开发 / 谈价 thread
4. 自动更新 master 中的 thread / price / progress
5. 自动生成 high-confidence reply draft
6. 自动标记 OCR pending / manual review
7. 自动输出 daily summary

### 系统不应该盲目完成的

1. 不应该在低置信度下自动发送邮件
2. 不应该在价格判断模糊时直接覆盖有效价格
3. 不应该在附件未审计前擅自结构化价格
4. 不应该把 quoted history 手工写进 reply body
5. 不应该为了自动化而牺牲主表可读性

---

## 北极星下的五个核心模块

### Module 1 — Inbox Intelligence

目标：

- 每日从 Gmail inbox 中抓出真正属于 KOL 开发与谈价的邮件

要求：

- 不是只靠 subject
- 要结合 thread context
- 要能区分 office mail / workstream / outreach reply / noise

### Module 2 — Master Truth

目标：

- 本地 CSV 永远是“当前最可信的运营总览”

要求：

- master 里能看出：
  - 是否已发出
  - 是否已回复
  - 是否已报价
  - 报价是第几轮
  - 当前有效价格
  - 是否有附件待 OCR
  - 下一步该做什么

### Module 3 — Pricing Intelligence

目标：

- 让系统不仅知道“有没有价格”，还知道“现在这条 thread 到了哪一轮谈价”

要求：

- 区分 `mail1` 价格 / `mail2+` 价格
- 区分首次报价 / requote / discounted quote
- 当前有效价格必须稳定落到 master

### Module 4 — Draft Intelligence

目标：

- 让回复草稿不是模板堆砌，而是 thread-aware 的商务动作

要求：

- 必须看完整 thread
- 必须先判价格轮次
- 必须先判对方意图
- 必须只写 clean reply body
- 超过两天默认加入 delay softener

### Module 5 — Daily Management Surface

目标：

- 让 Steve 每天看的是结果，而不是一堆过程文件

要求：

- 每日总结要告诉 Steve：
  - 新增多少封相关回复
  - 多少封有价格
  - 多少封进入 OCR
  - 多少封 draft ready
  - 多少封 manual review
  - 今日最重要的 3~5 条进展

---

## 自动化视角下的标准日循环

### Morning / Scheduled Run

1. 扫描最近 inbox
2. 找到新 KOL thread
3. 命中 master 或 bootstrap 进入 master
4. 更新：
   - reply block
   - last reply
   - stage
   - price state
5. 有附件则标记 OCR pending
6. 高置信 case 生成 reply draft
7. 输出 daily summary

### Human Review Layer

Steve 主要看：

1. 今天新增了哪些关键回复
2. 哪些人给了价格
3. 哪些价格到了第二轮
4. 哪些草稿值得直接发送
5. 哪些 case 需要人工判断

---

## 对自动化设计的硬要求

### Requirement 0. 判断归大模型，执行归脚本

这是这条新 skill 和旧系统最重要的分界线。

必须优先交给大模型判断的部分：

- 这是不是 KOL outreach reply
- 这是 `mail1` 还是 `mail2+`
- 对方有没有给出 usable rate
- 当前价格属于首轮报价、二轮报价、折扣价还是无价格
- 附件 OCR 结果能不能作为有效价格证据
- 当前下一步到底应该：
  - `request_rate`
  - `push_agency_rate`
  - `hold_warm`
  - `ocr_first`
  - `manual_review`

应该交给脚本执行的部分：

- 扫描邮箱时间窗口
- 下载附件
- 跑 OCR
- 写 review table / summary / shadow master
- 按已确认结论分发到：
  - draft queue
  - OCR queue
  - manual review queue
- 真的写入 Gmail draft / CSV / checkpoint

一句话原则：

- 只要问题是“这是什么意思”，优先交给大模型
- 只要问题是“把这个结果写到哪里”，交给脚本

### Requirement 1. 系统必须知道自己怎么填

也就是说：

- 字段定义必须清楚
- 写回时机必须清楚
- 枚举值必须清楚
- 什么情况下不写必须清楚

不能靠“临场猜”。

### Requirement 2. 系统必须让 Steve 一眼看懂

也就是说：

- master 不能只是技术字段堆积
- 排序必须符合运营直觉
- summary 必须能直接辅助决策

### Requirement 3. 自动化必须可保守

宁可：

- 留 `manual_review`
- 留 `ocr_pending`
- 留 `draft_ready`

也不要：

- 误写价格
- 误分轮次
- 误发邮件

### Requirement 4. 过程与真相分层

- `workbench` 放过程产物
- `master CSV` 放当前真相
- `Gmail draft` 放待发动作
- `daily summary` 放管理界面

不要混成一层。

---

## 未来所有设计都要回答的四个问题

后面每做一步，都必须回答：

1. 这一步是帮助系统更稳地扫描 inbox，还是只是增加复杂度？
2. 这一步写回 master 后，Steve 会不会更容易看懂？
3. 这一步会不会让价格判断更可信？
4. 这一步是否更接近“自动扫描 -> 自动更新 -> 自动起草 -> 每日汇报”的闭环？

如果答案不是更接近这个闭环，就不该优先做。

---

## 对旧系统失败原因的明确修正

旧系统最容易失败的地方，不是脚本不够多，而是：

- 让脚本承担了过多语义判断
- 试图用规则硬猜 reply intent 和 pricing round

新系统必须避免：

1. 用脚本单独决定 `mail1 / mail2+`
2. 用脚本单独决定价格是否 usable
3. 用脚本单独决定附件 OCR 是否可信
4. 用脚本单独决定是否进入草稿箱

这些结论必须由大模型主判，脚本只负责承接、落盘和执行。

---

## 当前阶段判断

现在这个系统还没有完成 North Star。

当前只完成了：

- plugin-first reply triage
- scenario-based draft reference
- 独立 skill 拆分
- V3 master upgrade 思路
- field mapping 设计

还没完成的关键部分是：

1. preview-only master writeback
2. OCR 分流接线
3. draft status 写回 master
4. daily summary 自动化

---

## 结论

这份 North Star 的意义是：

以后 `S3-codex-plugin-reply` 的每一次改动，都不是为了“多一个功能”，而是为了逐步逼近这个最终目标：

> 让 Codex 可以独立完成每天的邮件扫描、本地写入、邮件分析、回复草稿上传、价格表更新，以及每日总结汇报。

这就是后面所有设计的最高优先级。
