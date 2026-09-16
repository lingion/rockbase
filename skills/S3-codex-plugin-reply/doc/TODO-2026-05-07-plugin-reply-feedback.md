# TODO — Plugin Reply Feedback Fixes

日期：2026-05-07

## 背景

2026-05-06 的 plugin-first reply draft sample 已经证明：

- Gmail 插件可以直接读真实 inbox / thread
- 本地 OAuth 路线可以把 reply 写入 Gmail 草稿箱

但这轮 sample 暴露出几个关键质量问题，必须先修，再继续扩大自动化范围。

## 用户反馈

### 1. 总是忘记谈价格

现象：

- 回复虽然看起来礼貌，但没有严格按照 `references/reply_templates.md` 的价格策略执行
- 对于 `RQ1 / RI1 / RI2 / RI3` 这类本来就应该继续索价 / 压价 / 收集 rate 的 case，没有把价格问题放在正文中心

用户要求：

- 必须学习并严格对齐：
  - `.agent/skills/S3-ag-reply-draft-ops/references/reply_templates.md`
- 必须先判断需求分类，再决定回复
- 必须看过去我和这个 KOL 的全部对话，而不是只看最后一封

解决思路：

1. 生成 draft 前，强制先读完整 thread，而不是只读 latest message
2. 先输出结构化判断：
   - `pricing_state`
   - `reply_intent`
   - `template_code`
   - `why_this_template`
3. 若模板是：
   - `RQ1`：正文必须出现“继续压 agency test rate / first-collab rate”
   - `RI1`：正文必须明确索要 rate
   - `RI2`：正文必须明确“已收到 details，但还缺价格”
   - `RI3`：正文必须回避直接先报预算，同时把对方拉回标准 rate card
4. `RQ2 / RQ3` 才允许以“先保持温度、等待合适 brief”为主
5. 如果 thread 中已经出现过我方对价格的上一轮追问，新的回复必须考虑这段上下文，不能回到过于泛的模板

### 2. 回复正文里不应手工加入 quoted history

现象：

- 草稿正文里人工写入了：
  - `On Fri, ... wrote:`
  - 对方原邮件大段引用
- 这让正文变得又长又脏

用户判断：

- 这种引用不需要人工写进正文

解决思路：

1. Reply draft 的正文只保留“新增回复内容”
2. 不要把 thread history 手工拼进 `body`
3. Gmail reply draft 本身已经依赖：
   - `threadId`
   - `In-Reply-To`
   - `References`
4. quoted history 应交给 Gmail 界面 / thread 机制处理，而不是写进新正文
5. 后续要检查：
   - 是不是我们当前 preview 文档为了展示把历史也拼进去了
   - 或者是脚本在 draft body 层误拼了 quoted text

## 新的硬规则

### Rule A. 先读完整 thread

每个 candidate 在 draft 前必须至少读取：

- 原始 outbound
- 当前 latest inbound
- 若中间已经来回沟通过，必须看清最近一轮价格与 brief 交互

### Rule B. 先做模板判定，再写正文

不允许先凭感觉写 reply。

必须先落：

- `template_code`
- `pricing_state`
- `intent_summary`
- `operator_goal`

再生成正文。

### Rule C. 价格字段必须显式检查

每个 candidate 在写 draft 前必须回答：

1. 对方是否已经给出 usable rate？
2. 这个 rate 是：
   - 标准价
   - 折扣价
   - 模糊价
   - 还没给价
3. 当前目标是：
   - 继续索价
   - 压 first-test / agency rate
   - 接受当前价格并保温
   - 先发 brief / details
   - 暂不回复

### Rule D. Reply body 只写新增内容

不允许在生成正文时人工加入：

- `On ... wrote:`
- 对方原文复制
- 我方历史邮件复制

preview 文档可以单独展示 thread context，但 draft body 本身必须干净。

## 下一步修复任务

1. 重写 plugin-first drafting prompt，使其强制以 `reply_templates.md` 为唯一模板依据。
2. 增加 thread-level context summary，避免只读最后一封造成误判。
3. 修正 preview / manifest / draft body 的边界，禁止把 quoted history 混入 reply body。
4. 回看昨天写入的 8 封草稿，逐封复核：
   - 是否模板选对
   - 是否价格逻辑正确
   - 是否混入 quoted history
5. 基于复核结果，再决定是：
   - 更新现有 draft
   - 删除后重建
   - 保留个别正确版本

## 暂不继续放大的原因

在“价格策略”和“quoted history”两个问题修好之前，不应该继续扩大自动起草规模。

因为这两个问题都属于系统性问题，不是个别文案瑕疵。
