# Phase 1 Reply Stream Spec

## 目标

Phase 1 在把 Gmail 最近窗口抓回后，不是先问“这个人是不是在某张 replied 表里”，而是先问：

- 这封回复是在回复哪一类 outbound 邮件

统一把回复分成三类：

- `Outreach`
- `Workstream`
- `Manual_Review`

---

## 三类定义

### `Outreach`

满足任一条件即可：

- 这封 inbound 明确是在回复 `Mail1 / Mail2 / Mail3`
- thread 中我方 outbound 邮件正文能命中已定义的 outreach 模板指纹

这类邮件：

- 必须纳入 replied 主表
- 后续继续进入 `Pipeline_Stage`

### `Workstream`

满足以下特征：

- 对象也可能在大名单中
- 但这封回复是在回复后续交接、执行推进、日常沟通邮件
- 不属于标准 `Mail1 / Mail2 / Mail3` 外联链路

这类邮件：

- 不纳入当前 reply pipeline
- 进入排除或单独 audit

### `Manual_Review`

适用：

- header 对不上
- thread 中也看不出明显 outbound 模板指纹
- 无法稳定判断是 `Outreach` 还是 `Workstream`

---

## 判定优先级

### 第一层：header / reply chain

优先看：

- `Latest_Inbound_InReplyTo`
- `Outbound_Message_IDs`

如果能明确对上：

- `mail1`
- `mail2`
- `mail3`

则直接判为：

- `Reply_Stream = Outreach`

### 第二层：outbound 模板指纹

如果 header 不够稳定，则在 thread 中查找我方 outbound 邮件正文。

如果正文命中标准 outreach 模板指纹，也判为：

- `Reply_Stream = Outreach`

### 第三层：工作交接兜底

如果 thread 中存在我方 outbound 邮件，但不命中 outreach 模板指纹：

- 判为 `Workstream`

### 第四层：人工

如果连 thread 内 outbound 都无法稳定提取：

- 判为 `Manual_Review`

---

## 最小模板指纹

下面这些短语可作为最小可用指纹。

### Mail1 / 首轮外联

- `I'm Annabel from Rockbase Agency.`
- `We are currently finalizing our Premium Creator Shortlist`
- `Links to all your active social channels`
- `Current rates for all channels`

### Mail2 / reply 模板

- `Thank you for sharing your rates.`
- `We do see strong alignment between your audience`
- `Would you be open to sharing your best agency rate`
- `At this stage, we are reviewing creators for upcoming AI/tech campaigns`
- `Budget can vary depending on the format`

### Mail3

Mail3 如果后面有固定模板，也应加入固定指纹。

---

## 现有 30 小时 audit 的处理规则

对于 recent capture audit：

1. 不能只看 replied 主表是否命中
2. 必须先做 `Reply_Stream` 分类
3. 只有 `Outreach` 才继续纳入 replied 主表
4. `Workstream` 排除
5. `Manual_Review` 留在人工队列

---

## 是否需要重新抓取

如果 audit 中已经有：

- `thread_id`
- `message_id`
- `from_email`

通常不需要重新抓整段时间窗口。

更稳的做法是：

- 直接基于现有 `thread_id` 回 Gmail 拉该 thread 的完整消息链
- 只补这批 audit thread 的 outbound 信息

也就是说：

- 不需要重跑整段 recent capture
- 只需要做 `thread enrichment`
