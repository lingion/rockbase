# V3 Field Mapping

日期：2026-05-07

## Purpose

这份文档把三件事对齐：

1. 当前 live master：
   - `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`
2. 旧系统：
   - `S3-ag-reply-recovery-sync-v3`
   - `S3-ag-reply-draft-ops`
3. 新系统：
   - `S3-codex-plugin-reply`

目标是明确：

- 现有字段哪些已经够用
- 新 workflow 要写回哪些字段
- 哪些字段建议新增
- 哪些字段不该再承担新职责

---

## 当前 Live Master 快照

当前 live V3 表共 `62` 列，核心字段如下：

### 身份与基础信息

- `Source_Tag`
- `账号ID`
- `频道/作者名称`
- `平台`
- `多平台标记`
- `账号链接`
- `语言`
- `博主国家`
- `粉丝数`

### 回复与价格主视图

- `Reply_Contact_Email`
- `mail1_reply_block`
- `mail2_reply_block`
- `mail3_reply_block`
- `mail4_reply_block`
- `mail5_reply_block`
- `latest_price_raw`
- `latest_price_normalized`
- `latest_price_basis`

### 系统跟踪

- `Sort_Bucket`
- `Reply_Count`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Last_At`
- `Outbound_Message_IDs`
- `Latest_Inbound_Message_ID`
- `Latest_Inbound_InReplyTo`
- `Reply_Stage`
- `Reply_Stream`
- `Pipeline_Stage`
- `Capture_Run_ID`
- `Capture_At`
- `Reply_Body_File`

### 审计与人工 review

- `Reply_Status`
- `Reply_Needs_Manual_Review`
- `Reply_Analysis`
- `Manual_Review_Reason`
- `Manual_Review_Focus`

---

## Mapping Principles

### Principle 1. 主表只保留“当前最有用的真相”

主表不应该承载所有过程文件。

主表重点保留：

- 当前 thread 锚点
- 当前有效价格
- 当前所处阶段
- 下一步该做什么

### Principle 2. 历史波次保留在波次字段，不把主视图搞乱

- `mail1_reply_block ~ mail5_reply_block` 继续保留
- 价格历史证据继续按 wave 存
- 但主视图只突出：
  - `latest_price_*`
  - `Pricing_Effective_Wave`
  - `Pricing_Round`

### Principle 3. 新 workflow 尽量复用旧字段

优先复用现有列。

只有当一个新概念在当前表里没有稳定落点时，才新增字段。

---

## Part 1 Mapping — 身份与基础信息

这些字段当前已经足够稳定，建议继续沿用。

| 字段 | 当前状态 | 新系统动作 | 备注 |
| --- | --- | --- | --- |
| `Source_Tag` | 现有可用 | 继续写 | 用于标记来自哪个 source / batch / workflow |
| `账号ID` | 现有可用 | 继续作为 person 主键 | 最核心锚点，不替换 |
| `频道/作者名称` | 现有可用 | 继续沿用 | 人工识别主字段 |
| `平台` | 现有可用 | 继续沿用 | 主平台 |
| `多平台标记` | 现有可用 | 继续写 | 由新系统按价格语义补充 |
| `账号链接` | 现有可用 | 继续沿用 | 不动 |
| `语言` | 现有可用 | 继续沿用 | 不动 |
| `Reply_Contact_Email` | 现有可用 | 继续更新 | 当前实际回复邮箱 |

结论：

- Part 1 不需要重构
- 只需要确保新 workflow 能稳定更新 `Reply_Contact_Email` 和 `多平台标记`

---

## Part 2 Mapping — 回复与价格主视图

这是新系统最关键的映射区。

### A. 现有字段继续保留

| 字段 | 当前状态 | 新系统动作 | 备注 |
| --- | --- | --- | --- |
| `mail1_reply_block` | 现有可用 | 继续写 | inbound-only |
| `mail2_reply_block` | 现有可用 | 继续写 | inbound-only |
| `mail3_reply_block` | 现有可用 | 继续写 | inbound-only |
| `mail4_reply_block` | 现有可用 | 继续写 | inbound-only |
| `mail5_reply_block` | 现有可用 | 继续写 | inbound-only |
| `latest_price_raw` | 现有可用 | 继续写 | 原始表达 |
| `latest_price_normalized` | 现有可用 | 继续写 | 当前有效价格规范化 |
| `latest_price_basis` | 现有可用 | 继续写 | 说明 price 来自哪些 wave / attachment |

### B. 现有系统概念，但当前 live 表里还没落出来

这些概念已经在旧设计里出现过，建议重新启用到 live master：

| 字段 | 来源 | 建议 |
| --- | --- | --- |
| `Pricing_Effective_Wave` | 旧 V3 recovery 设计 | 应加入 live master |
| `Pricing_Change_Type` | 旧 V3 recovery 设计 | 应加入 live master |

### C. 建议新增字段

| 字段 | 作用 | 为什么需要 |
| --- | --- | --- |
| `Capture_Status` | capture 层状态 | 把“拿到什么信息”与“要不要回复”拆开 |
| `current_price_summary` | 单行价格摘要 | 方便 Steve 在 CSV 第一屏快速扫表 |
| `Pricing_Round` | 当前价格轮次 | 明确区分 `mail1_first_quote / mail2_requote / discounted_quote / no_quote` |
| `Current_Reply_Scenario` | 当前回复场景 | 对应新 skill 的 `S1 ~ S10` |
| `Next_Reply_Action` | 下一步动作 | 例如 `request_rate / push_agency_rate / hold_warm / ocr_first / manual_review` |
| `Reply_Ownership` | thread 归属 | 区分 `auto_reply / steve_handle / workstream / ignore / manual_review` |
| `Need_Reply_State` | 是否真实需要回复 | 防止把“最新 outbound 是我方”的 thread 误起草 |
| `Latest_Thread_Speaker` | thread 最新发言方 | 给 need-reply 判断一个稳定锚点 |

### C1. 价格输出格式协议

新系统后续写价格时，统一按四层处理：

1. `latest_price_raw`
   - 证据层
   - 保留对方原文价格表达

2. `latest_price_normalized`
   - 正式价格层
   - 必须使用结构化多行格式
   - 每行前统一 `·`
   - `Bundle Package` 若存在，固定放在最上方
   - 之后按平台分行，例如：
     - `· YouTube: dedicated $500 | integration $350`
     - `· Instagram: reel $450 | story $200`
     - `· X: quote post $1,500 | thread $2,000`

3. `current_price_summary`
   - 快速浏览层
   - 单行摘要，用于 CSV 扫表与排序辅助
   - 示例：`X bundle $3,000 | quote $1,500 | thread $2,000`

4. `latest_price_basis`
   - 判断依据层
   - 说明价格来自哪一轮 reply block，以及是否用了附件

补充规范：

- 金额统一使用标准货币符号 + 千分位分隔
- 若同时保留当前有效价与 regular/original 参考价，必须显式使用：
  - `[effective]`
  - `[regular/original reference]`
- bonus / 免费附赠项默认不写入 `latest_price_normalized` 主价格结构，除非已经构成清晰、稳定的价格方案
- 不要让 `latest_price_normalized` 同时承担“主价格展示”和“扫表摘要”两种职责；两者应分别落在 `latest_price_normalized` 与 `current_price_summary`

### D. 新系统如何写 Part 2

先加一条总原则：

- `Phase 1 = capture and writeback`
- `Phase 2 = reply selection and drafting`

也就是说：

- 只要 thread 里已经拿到可用价格，就先写回本地
- 回复动作是第二阶段，不绑定在价格写回动作上

#### Flow 1 — 扫到 reply，但没价格

写：

- `mailN_reply_block`
- `Capture_Status = no_price`
- `Reply_Last_*`
- `Reply_Count`
- `Pricing_Round = no_quote`
- `Current_Reply_Scenario = S1/S2/S3/S4`
- `Next_Reply_Action = request_rate / send_details / manual_review`

#### Flow 2 — 第一次报价

写：

- `mailN_reply_block`
- `Capture_Status = price_captured`
- `latest_price_raw`
- `latest_price_normalized`
- `latest_price_basis`
- `Pricing_Effective_Wave = mail1`
- `Pricing_Round = mail1_first_quote`
- `Current_Reply_Scenario = S4/S5`
- `Next_Reply_Action = writeback_complete_wait_reply_selection`

#### Flow 3 — 第二轮报价 / 更新报价

写：

- 更新 `mail2_reply_block` 或更高波次
- `Capture_Status = price_captured`
- 更新 `latest_price_*`
- `Pricing_Effective_Wave = mail2` 或更高
- `Pricing_Round = mail2_requote`
- `Current_Reply_Scenario = S6`
- `Next_Reply_Action = writeback_complete_wait_reply_selection`

#### Flow 4 — 折扣价 / first-collab flexibility

写：

- `Capture_Status = price_captured`
- 更新 `latest_price_*`
- `Pricing_Round = discounted_quote`
- `Current_Reply_Scenario = S7`
- `Next_Reply_Action = writeback_complete_wait_reply_selection`

---

## Part 3 Mapping — 系统跟踪区

### A. 现有字段继续保留

| 字段 | 当前状态 | 新系统动作 | 备注 |
| --- | --- | --- | --- |
| `Sort_Bucket` | 现有可用 | 继续写，但规则升级 | 控制表格排序 |
| `Reply_Count` | 现有可用 | 继续写 | 有效回复轮次 |

### B. 新调度字段职责

`S3-codex-plugin-reply` 升级后，系统跟踪区不再只记录“回复到了第几轮”，还必须记录：

1. 这条 thread 归谁
2. 这条 thread 当前是否真的需要回复
3. 这条 thread 最新整体消息是谁发的

最小职责建议：

| 字段 | 建议值 | 说明 |
| --- | --- | --- |
| `Reply_Ownership` | `auto_reply / steve_handle / workstream / ignore / manual_review` | 决定 thread 是否进入自动处理链 |
| `Need_Reply_State` | `reply_needed_from_us / no_reply_needed_latest_outbound_ours / contact_update_only / closed_no_reply_needed / unclear_manual_review` | 决定 thread 是否值得继续推进 |
| `Latest_Thread_Speaker` | `them / us / mixed / unknown` | 为 need-reply 与 missed-reply 队列提供锚点 |

### C. 队列层建议

shadow / review 产物建议至少能落出这些队列：

- `draft_queue`
- `missed_reply_queue`
- `ocr_queue`
- `contact_update_queue`
- `manual_review`

其中：

- `missed_reply_queue` 用来显式承接“应该回复但因 stale thread / refresh 缺失而暂不能直接起草”的 case
- `contact_update_queue` 用来承接“只需要同步联系人或邮箱，不需要正式商务回复”的 case
| `Reply_Thread_ID` | 现有可用 | 继续写 | thread 主键 |
| `Reply_Last_Message_ID` | 现有可用 | 继续写 | 最新有效消息 |
| `Reply_Last_Subject` | 现有可用 | 继续写 | 最近主题 |
| `Reply_Last_At` | 现有可用 | 继续写 | 最近回复时间 |
| `Outbound_Message_IDs` | 现有可用 | 继续写 | wave 映射锚点 |
| `Latest_Inbound_Message_ID` | 现有可用 | 继续写 | 去重锚点 |
| `Latest_Inbound_InReplyTo` | 现有可用 | 继续写 | 判断波次 |
| `Reply_Stage` | 现有可用 | 继续写 | 细阶段 |
| `Reply_Stream` | 现有可用 | 继续写 | Outreach / Workstream / Noise |
| `Pipeline_Stage` | 现有可用 | 继续写，但规则升级 | 主流程阶段 |
| `Capture_Run_ID` | 现有可用 | 继续写 | run 追踪 |
| `Capture_At` | 现有可用 | 继续写 | 最近抓取时间 |
| `Reply_Body_File` | 现有可用 | 继续写 | 本地正文证据 |

### B. 建议新增字段

| 字段 | 作用 | 为什么需要 |
| --- | --- | --- |
| `Attachment_OCR_Status` | 附件状态 | 让 OCR 分流显式落盘 |
| `Draft_Workflow_Status` | 草稿进度 | 让 reply drafting 状态显式落盘 |

### C. 建议升级的排序规则

`Sort_Bucket` 推荐新分桶：

1. `quoted_mail2_or_later`
2. `quoted_mail1`
3. `replied_no_quote`
4. `sent_waiting`
5. `ocr_review_required`
6. `closed`

然后每个 bucket 内按：

- `Reply_Last_At` 从近到远

### D. Pipeline_Stage 推荐新值

建议收敛成下面这些主状态：

- `sent_waiting`
- `replied_no_quote`
- `replied_mail1_quote`
- `replied_mail2_quote`
- `attachment_ocr_pending`
- `draft_ready`
- `drafted`
- `closed`

---

## Attachment / OCR Mapping

新系统遇到附件时，不要直接把价格硬写死。

推荐写法：

### 当发现附件

写：

- `Attachment_OCR_Status = attachment_detected`
- `Next_Reply_Action = ocr_first`

### 当 OCR 已跑但还没确认

写：

- `Attachment_OCR_Status = ocr_pending` 或 `ocr_review_required`

### 当 OCR 已确认价格

写：

- `Attachment_OCR_Status = ocr_done`
- 更新：
  - `latest_price_raw`
  - `latest_price_normalized`
  - `latest_price_basis`
  - `Pricing_Round`
  - `Pricing_Effective_Wave`

附件审计文件继续优先落：

- `workbench/rockbase-gmail-reply-recovery-v3/`

主表只收最终状态和最终有效结论。

---

## Reply Draft Mapping

新系统在生成 reply draft 时，建议这样写回：

| 动作 | 写回字段 |
| --- | --- |
| 判断出当前场景 | `Current_Reply_Scenario` |
| 判断出下一步 | `Next_Reply_Action` |
| 已生成 draft preview | `Draft_Workflow_Status = draft_ready` |
| 已写入 Gmail draft | `Draft_Workflow_Status = drafted` |
| 已发送 | `Draft_Workflow_Status = sent` |

说明：

- 旧系统中的 `Mail2_Draft_ID / Mail3_Draft_ID` 等细粒度字段，可以继续保留在 legacy 系统或后续扩展层里
- 但新主表第一阶段先不急着恢复所有细列
- 先保证“能稳定知道当前 draft 进度”

### Draft Gate Decision Table

为了避免“什么时候进草稿箱”继续靠临场判断，后续统一按 `Next_Reply_Action` 做 gate：

| `Next_Reply_Action` | 是否允许进入 Gmail draft | 默认 `Draft_Workflow_Status` | 说明 |
| --- | --- | --- | --- |
| `request_rate` | 是 | `draft_ready` | 无价格但 thread 清楚，可以起草索价回复 |
| `send_details` | 是 | `draft_ready` | 对方需要 brief / details，可起草补信息回复 |
| `push_agency_rate` | 是 | `draft_ready` | 典型首轮或二轮报价后的压价回复 |
| `hold_warm` | 是 | `draft_ready` | 暂不成交但需要保温，可起草保持联系 |
| `draft_from_body_quote` | 是 | `draft_ready` | 附件无有效信号，允许以正文价格为主真相起草 |
| `manual_review` | 否 | `blocked_manual_review` | 需要人判断，禁止自动起草 |
| `ocr_first` | 否 | `blocked_ocr_first` | 附件价格或关键信息未确认，禁止自动起草 |
| `update_contact_only` | 否 | `blocked_contact_update` | 先更新联系人，不进标准草稿流 |
| `no_reply` | 否 | `not_applicable` | 不属于 reply draft 流程 |

补充硬规则：

1. 只有同时满足以下条件，才允许真正写入 Gmail draft：
   - `Next_Reply_Action` 属于可 draft 集合
   - `Reply_Needs_Manual_Review != yes`
   - `Attachment_OCR_Status` 不处于 `attachment_detected / ocr_pending / ocr_review_required`
   - thread 已完整读取，不是只看 latest message

2. `draft_ready` 只表示“允许起草”，不等于“已经写进 Gmail”。

3. 真正写入 Gmail 后，才改成：
   - `Draft_Workflow_Status = drafted`

4. 如果后续又发现：
   - 新附件
   - 新价格冲突
   - 新的 manual review 风险

   则应允许从 `draft_ready` 或 `drafted` 回退到：
   - `blocked_ocr_first`
   - `blocked_manual_review`

---

## What Not To Do

1. 不要新起第二张正式 master。
2. 不要把所有过程文件都塞进主表。
3. 不要让 `latest_price_normalized` 同时承担“历史价格日志”和“当前有效价格”两种职责。
4. 不要只靠脚本粗略猜 `mail1 / mail2`，应优先用 thread context + Gmail 插件判断。
5. 不要把附件 OCR 结果在未审计前直接覆盖有效价格。

---

## Recommended Build Order

### Step 1

先在新 skill 内定义新增字段和枚举值，不动旧 skill。

### Step 2

先做一个 preview-only mapping workflow：

- 扫 inbox
- 命中 master
- 生成拟写回字段 preview
- 不直接改 live master

### Step 3

确认 preview 稳定后，再做 writeback script。

### Step 4

再把 OCR 和 draft status 接进来。

---

## Bottom Line

这张 V3 表现在已经足够做新系统的正式总览表。

真正需要做的不是换表，而是：

1. 明确字段职责
2. 补齐价格轮次字段
3. 补齐 OCR / draft 状态字段
4. 让新 plugin-first workflow 稳定写回这些字段

这样你后面看到的就会是：

- 上面：已经有报价的人
- 中间：已回复但还没价格的人
- 下面：已发出但还没回的人

而且还能看出：

- 这是 `mail1` 价格还是 `mail2` 价格
- 附件有没有待 OCR
- 下一步该不该起草 / 追价 / 保温
