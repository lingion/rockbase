# S3 Reply Recovery Sync Upgrade Blueprint

## 总体业务目标

这次升级最终服务的不是一个孤立的 recovery skill，而是一整套长期邮件运营系统。

你的总目标是：

1. 给几千位 KOL 持续发邮件
2. 基于他们的回复，持续更新那几个核心报价表
3. 基于 `M1 / M2 / M3` 的状态以及他们各自的具体邮件内容，持续给出几类定制化回复方案

所以这份蓝图的定位不是“如何抓邮件”这么窄，而是：

- 如何把 Gmail 回复稳定拉回
- 如何把正文和附件中的报价 intelligence 稳定写回主表
- 如何让主表保持正确的 `M1 / M2 / M3` 波次状态
- 如何为后续 `reply drafting` 提供干净、稳定、可持续更新的数据底座

一句话说：

`S3-ag-reply-recovery-sync` 的升级目标，是成为整套“几千人外联 -> 回复回收 -> 报价更新 -> 状态推进 -> 后续定制化回复”系统中的 recovery intelligence 中枢。

## 目标

这份蓝图不是只解决一个 `hub` 的目录问题，而是定义 `S3-ag-reply-recovery-sync` 作为一个长期运营 skill 的整体升级方案。

目标是让这个 skill 最终能稳定完成以下事情：

1. 每次抓回来的回复，能准确落到 `M1 / M2 / M3` 对应状态链上
2. 抓取到的正文能正确写回，附件能识别价格后写回
3. 能基于最新抓取结果，自动更新涉及行的状态并支持重新排序
4. 能基于最新价格、最新回复波次、最新线程状态，持续更新主价格字段，并保留备注与证据
5. 能把 `Mail1 / Mail2 / Mail3` 各自的价格历史和 `Reply_*` 当前有效价格明确分层

这份蓝图覆盖：

- recovery / sync
- reply intelligence
- replied 主表字段管理
- M1 / M2 / M3 状态衔接
- workbench / hub 结构
- 旧资料迁移

这份蓝图不覆盖：

- Mail2 / Mail3 正文模板设计
- reply draft 创建与发送

---

## 新的匹配总原则

回复回收不能再只靠一个键。

- `M2 / M3` 回复：优先靠 `Reply_Thread_ID`
- 首轮 `M1` 回复：优先靠 `normalized subject + from_email`
- 如果 subject 唯一，但回信邮箱是团队别名 / 代理邮箱，允许 subject 主导 bootstrap
- 如果多条候选其实是同主体多平台重复行，要先做 `same-contact multi-platform collapse`
- `mailer-daemon` / `Delivery Status Notification` 这类退信不能进入 replied 主表

这意味着 `no_master_match` 不再是简单异常，而是一个 bootstrap 决策入口：

- `subject_email_unique` -> 自动 bootstrap
- `subject_unique` -> 自动 bootstrap
- `email_unique_only` -> 谨慎 bootstrap
- `same-contact multi-platform duplicate` -> 先归并，再 bootstrap
- 真正无法判断的 -> `Manual_Review`
- 退信 / bounce -> 独立排除，不进入建联 replied 表

---

## 一、升级后的能力目标

`S3-ag-reply-recovery-sync` 升级后应具备 4 个核心能力。

### 能力 A：波次识别

对每次最新抓回来的 inbound reply，能判断它回复的是：

- `Mail1`
- `Mail2`
- `Mail3`
- 或无法稳定判断，需要人工看

判断依据不是作者名，而是：

- `Latest_Inbound_InReplyTo`
- `Outbound_Message_IDs`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`

### 能力 B：正文与附件 intelligence

每次 recovery 后，至少能产出：

- 最新回复正文
- 正文文件路径
- 附件 inventory
- 附件 raw
- 附件 text / OCR
- 价格抽取结果
- 价格证据摘录

### 能力 C：状态推进

每次 recovery 后，能把当前行推进到正确状态：

- `Reply_Stage`
- 必要时初始化或刷新 `Pipeline_Stage`
- `Reply_Status`
- `Reply_Category`
- `Reply_Needs_Manual_Review`

### 能力 D：价格主字段更新

每次抓到新的正文或附件价格后：

- 刷新主价格字段
- 保留证据原文
- 保留人工备注 / ops 备注
- 不覆盖掉已有的重要人工结论

---

## 二、当前主表真实结构

当前真实主表是：

- `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL.csv`

它不是一个极简表，而是一张运行主表。当前字段分为 5 层：

### 1. 基础身份层

- `Source_Tag`
- `账号ID`
- `频道/作者名称`
- `平台`
- `账号链接`
- `语言`

### 2. recovery 定位层

- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Last_At`
- `Outbound_Message_IDs`
- `Latest_Inbound_Message_ID`
- `Latest_Inbound_InReplyTo`
- `Capture_Run_ID`
- `Capture_At`
- `Reply_Body_File`

### 3. intelligence 层

当前有效价格层：

- `Reply_Main_Dedicated_Rate`
- `Reply_Comprehensive_Pricing`
- `Reply_Pricing_Excerpt`
- `Pricing_Effective_Wave`
- `Pricing_Change_Type`
- `Reply_Analysis`
- `Reply_Needs_Manual_Review`

### 4. 波次执行层

- `Mail1_*`
- `Mail2_*`
- `Mail3_*`

其中每个波次还应有自己的价格历史块：

- `Mail1_Pricing_Excerpt`
- `Mail2_Pricing_Excerpt`
- `Mail3_Pricing_Excerpt`

### 5. 运营总控层

- `Pipeline_Stage`
- `Reply_Status`
- `Reply_Stage`
- `Owner`
- `Priority`
- `Final_Outcome`
- `Ops_Notes`

---

## 三、字段责任分工

升级时最重要的一件事，是先明确：

- 哪些字段由 recovery skill 写
- 哪些字段由 reply draft skill 写
- 哪些字段保留人工维护

### A. Recovery Skill 直接负责写的字段

`S3-ag-reply-recovery-sync` 应直接写：

- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Last_At`
- `Reply_Main_Dedicated_Rate`
- `Reply_Comprehensive_Pricing`
- `Reply_Pricing_Excerpt`
- `Mail1_Pricing_Excerpt`
- `Mail2_Pricing_Excerpt`
- `Mail3_Pricing_Excerpt`
- `Pricing_Effective_Wave`
- `Pricing_Change_Type`
- `Reply_Status`
- `Reply_Needs_Manual_Review`
- `Reply_Stream`
- `Reply_Body_File`
- `Reply_Stage`
- `Outbound_Message_IDs`
- `Latest_Inbound_Message_ID`
- `Latest_Inbound_InReplyTo`
- `Capture_Run_ID`
- `Capture_At`
- `Reply_Analysis`

### B. Recovery Skill 可初始化但不应重度维护的字段

- `Pipeline_Stage`

规则：

- recovery 可以根据最新回复波次给出初始建议
- 但不应强行覆盖后续 reply ops 已经人工调整过的 `Pipeline_Stage`

### C. Reply Draft Skill 负责写的字段

由 `S3-ag-reply-draft-ops` 维护：

- `Mail2_Reply_Template`
- `Mail2_Body_Final`
- `Mail2_Status`
- `Mail2_Draft_ID`
- `Mail2_Reply_*`
- `Mail3_*`

以及必要时：

- `Pipeline_Stage`

### D. 人工优先字段

这类字段后续 agent 默认不覆盖：

- `Owner`
- `Priority`
- `Final_Outcome`
- `Ops_Notes`

### E. 明确不由本 skill 维护的字段

这次升级后，以下能力明确不放在 `S3-ag-reply-recovery-sync`：

- reply 模板标签
- 下一封邮件建议
- Mail2 / Mail3 草稿内容生成
- 发送前的策略选择

这些由 `S3-ag-reply-draft-ops` 负责。

---

## 四、M1 / M2 / M3 的识别与衔接

### 第一层：recovery 识别波次

recovery 阶段要做的是：

- 看最新 inbound reply 回的是哪一波 outbound

核心依据：

- `Latest_Inbound_InReplyTo`
- `Outbound_Message_IDs`

如果命中：

- 回 `mail1` -> `Reply_Category = mail1_reply`
- 回 `mail2` -> `Reply_Category = mail2_reply`
- 回 `mail3` -> `Reply_Category = mail3_reply`
- 无法命中 -> `Reply_Category = manual_review`

### 第二层：recovery 维护 `Reply_Stage`

recovery 阶段建议维护以下 `Reply_Stage`：

- `mail1_waiting_reply`
- `mail1_replied_waiting_mail2`
- `mail2_waiting_reply`
- `mail2_replied`
- `mail3_waiting_reply`
- `mail3_replied`
- `closed`
- `manual_review`

### 第三层：reply ops 维护 `Pipeline_Stage`

更细的总控状态由 `Pipeline_Stage` 管：

- `M1_1_Drafted`
- `M1_2_Waiting`
- `M1_3_Replied_Review`
- `M2_1_Drafted`
- `M2_2_Waiting`
- `M2_3_Replied_Review`
- `M3_1_Drafted`
- `M3_2_Waiting`
- `M3_3_Replied_Review`
- `D1_Done`
- `D2_Stop`
- `Z_Manual_Review`

### 核心原则

- recovery skill 先负责“回的是哪一波”
- reply draft skill 再负责“现在总控阶段属于哪一格”

这能避免 recovery 和 drafting 同时争抢 `Pipeline_Stage`

---

## 五、正文与附件如何写入

### 正文

recovery 后必须至少产出：

- 最新 inbound 正文全文
- 对应 `Reply_Body_File`
- `Reply_Analysis`

写回规则：

- `Reply_Body_File` 只存相对路径或稳定路径
- 主表不直接塞整篇 raw body
- `Reply_Analysis` 保留：
  - `category=<...>`
  - `summary=<...>`
  - `next=<...>`

### 附件

附件处理分 3 层：

1. inventory
2. raw
3. text / OCR

价格写回规则：

- `Reply_Main_Dedicated_Rate`
  - 只放当前最关键的主平台 dedicated rate
- `Reply_Comprehensive_Pricing`
  - 放结构化综合报价摘要
- `Reply_Pricing_Excerpt`
  - 放原文证据或附件提取证据

### 备注处理

价格更新时，还需要落备注：

- `Reply_Analysis` 写“这次发生了什么”
- `Ops_Notes` 保留人工补充说明

规则：

- skill 可以追加 recovery 备注
- 不应清空人工已有的 `Ops_Notes`

---

## 六、状态自动更新与重新排序

升级后，recovery 不只是“抓回来”，还要做状态推进。

### 每次 recovery 结束后应自动更新

- `Reply_Status`
- `Reply_Category`
- `Reply_Stage`
- `Reply_Needs_Manual_Review`
- `Reply_Last_At`
- `Reply_Last_Message_ID`

### 关于排序

主表排序不应只靠时间，而应主要看：

1. `Pipeline_Stage`
2. `Priority`
3. `Reply_Last_At`

建议后续在 sync 阶段产出一份排序后的 preview，而不是一开始就强写主表顺序。

---

## 七、价格字段的持续更新策略

你特别关心的是：

- 最新价格抓回来后，如何持续更新核心价格字段
- 而且还要加备注

这里建议采用“主值 + 证据 + 备注”三层。

### 主值层

- `Reply_Main_Dedicated_Rate`

### 证据层

- `Reply_Pricing_Excerpt`
- `Reply_Comprehensive_Pricing`

### 备注层

- `Reply_Analysis`
- `Ops_Notes`

### 更新原则

1. 正文有明确价格，优先正文
2. 正文没有明确价格，再看附件
3. 如果新价格比旧价格更新，主值字段允许刷新
4. 不管主值是否刷新，证据层都应更新为最新证据
5. 人工备注不直接覆盖

---

## 八、长期工作台结构

旧的 `workbench/{date}/{project-slug}` 适合一次性项目，不适合长期 recovery。

升级后建议引入长期入口：

```text
workbench/reply-recovery-hub/
├── 00-state/
├── 01-runs/
├── 02-review-ready/
├── 03-master-sync/
├── 04-bodies/
├── 05-attachments/
├── 06-ledgers/
└── README.md
```

### `00-state/`

- `reply_recovery_checkpoint.json`
- `reply_capture_config.json`

### `01-runs/`

每次执行是一轮 run：

```text
01-runs/
├── 2026-03-19_run-001/
├── 2026-03-19_run-002/
└── 2026-03-20_run-001/
```

run 内放：

- thread ids
- full messages csv
- recent capture preview
- run audit
- run summary

### `02-review-ready/`

长期保留：

- review table
- pricing review table
- reply-ready table

### `03-master-sync/`

只放：

- sync preview
- sync audit
- sync summary

### `04-bodies/`

- `{message_id}.txt`

### `05-attachments/`

```text
05-attachments/
├── raw/
├── text/
└── ocr/
```

### `06-ledgers/`

- `reply_message_ledger.csv`
- `reply_thread_ledger.csv`
- `attachment_ledger.csv`

---

## 九、增量拉取策略

当前旧 skill 主要靠：

- `过去 N 小时`

这不足以支持长期接力。

升级后建议采用：

### 1. checkpoint

`00-state/reply_recovery_checkpoint.json` 记录：

- `last_run_id`
- `last_sync_started_at`
- `last_sync_completed_at`
- `last_success_reply_at`
- `last_success_message_id`
- `last_success_thread_id`

### 2. overlap

下次默认从：

- `last_success_reply_at - 6h`

开始拉。

### 3. ledger 去重

真正去重靠：

- `message_id`
- `thread_id`

### 4. 首次运行 fallback

没有 checkpoint 时：

- 默认抓 `过去 36h`

---

## 十、旧资料如何迁移

### 旧文档

保留并继续引用：

- `phase1_recovery_workflow.md`
- `phase1_output_tables.md`
- `phase1_reply_stream_spec.md`
- `recovery_case_notes.md`

### 旧 run 产物

后续迁移到：

- 旧 `full_messages.csv` -> `01-runs/`
- 旧 review table -> `02-review-ready/`
- 旧 sync preview/audit -> `03-master-sync/`
- 旧 bodies -> `04-bodies/`
- 旧 attachments -> `05-attachments/`

### 旧去重方式

从“主表 latest inbound 去重”升级为：

- `06-ledgers/reply_message_ledger.csv`
- `06-ledgers/reply_thread_ledger.csv`

---

## 十一、脚本升级方向

### `capture_recent_reply_window.py`

升级后要：

1. 先读 checkpoint
2. 自动算 overlap window
3. 写 run 目录
4. bodies 写到 `04-bodies/`
5. 新 message 写入 `reply_message_ledger.csv`
6. 只在 sync 成功后提交 checkpoint
7. 初始化 `Reply_Stage`、`Reply_Category`
8. 只谨慎初始化 `Pipeline_Stage`

### `fetch_reply_batch_full.py`

升级后：

- 对齐 run 目录与命名规则

### `download_and_extract_attachments.py`

升级后：

- 对齐 `raw / text / ocr`
- 写 `attachment_ledger.csv`

### `sync_reply_recovery_to_master.py`

升级后：

- 明确字段责任边界
- 生成 preview / audit / summary
- 只从 canonical review-ready table 回写
- 不覆盖人工维护字段

---

## 十二、推荐实施顺序

### Phase A：字段治理

先完成：

- recovery 写哪些列
- drafting 写哪些列
- 人工维护哪些列
- `Reply_Stage` 和 `Pipeline_Stage` 的衔接规则

### Phase B：hub 落地

引入：

- `reply-recovery-hub`
- `00-state`
- `01-runs`
- `06-ledgers`

### Phase C：脚本增量升级

先升级：

- checkpoint
- overlap
- ledger 去重

### Phase D：状态推进升级

让 recovery 能稳定：

- 命中 M1 / M2 / M3
- 更新 `Reply_Stage`
- 初始化 `Pipeline_Stage`
- 刷新主价格字段和备注

### Phase E：后续再考虑更强增量同步

例如：

- Gmail History API

---

## 十三、最终原则

1. recovery skill 先解决“拉回、理解、写表”
2. drafting skill 再解决“怎么回”
3. 主表是运行主表，不是原始仓
4. `Reply_Stage` 和 `Pipeline_Stage` 必须分层管理
5. 价格字段必须采用“主值 + 证据 + 备注”三层更新
6. 长期运营必须靠 `hub + checkpoint + ledger`，不能只靠 `过去 N 小时`

---

## 十四、一句话总结

这次升级不是只做一个新文件夹，而是把 `S3-ag-reply-recovery-sync` 从一个“临时拉回邮件”的脚本集合，升级成一套可以长期承载几千封回复、持续更新主表状态、价格和波次阶段的 recovery operating system。
