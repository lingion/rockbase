# SPEC — S3 Master Upgrade

日期：2026-05-07

## 背景

当前正式 S3 主表是：

- `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`

它原本更偏向：

- replied 主线
- 当前价格视图
- recovery / thread 跟踪

但现在新的目标已经扩大：

1. 不只看“已回复的人”
2. 还要跟踪“已发出但未回复的人”
3. 要明确区分：
   - `mail1` 价格
   - `mail2+` 价格
   - 当前有效价格
4. 要支持附件 OCR 分流
5. 要支持基于 Gmail 插件的智能回复 workflow

所以 V3 主表需要从 “replied master” 升级为 “outreach progress master”。

## 目标

升级后的主表要同时承担：

1. KOL 基础身份总览
2. 当前 thread / reply / price 跟踪
3. 外联进度管理
4. 自动回复 workflow 的落盘载体
5. OCR / 附件审计的回写落点

## 是否新起表

结论：

- **不建议新起第二张正式 master**
- **建议继续沿用现有 `【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`**
- 但要扩展它的入口定义与进度字段

原因：

1. 这张表已经有：
   - 基础信息
   - reply blocks
   - latest price
   - thread anchors
   - pipeline fields
2. 如果再新起一张平行表，会制造两个 truth source
3. 当前真正缺的是：
   - sent-but-not-replied 入口
   - pricing round tracking
   - attachment OCR status
   - next action management

## Part 1 / Part 2 / Part 3 的建议

### Part 1 — 基础身份区

保持基本稳定，不做大改。

继续保留：

- `Source_Tag`
- `账号ID`
- `频道/作者名称`
- `平台`
- `多平台标记`
- `账号链接`
- `语言`
- `Reply_Contact_Email`

### Part 2 — 回复与价格主视图

这是升级重点。

继续保留：

- `mail1_reply_block ~ mail5_reply_block`
- `latest_price_raw`
- `latest_price_normalized`
- `latest_price_basis`

建议补强：

- `Pricing_Effective_Wave`
- `Pricing_Change_Type`

建议新增：

- `Pricing_Round`
  - `no_quote`
  - `mail1_first_quote`
  - `mail2_requote`
  - `discounted_quote`
- `Current_Reply_Scenario`
  - 对应 `S3-codex-plugin-reply` 的场景 reference
- `Next_Reply_Action`
  - `request_rate`
  - `push_agency_rate`
  - `hold_warm`
  - `ocr_first`
  - `manual_review`

### Part 3 — 系统跟踪区

继续保留：

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

建议新增：

- `Attachment_OCR_Status`
  - `none`
  - `attachment_detected`
  - `ocr_pending`
  - `ocr_done`
  - `ocr_review_required`
- `Draft_Workflow_Status`
  - `not_started`
  - `draft_ready`
  - `drafted`
  - `sent`

## 排序目标

升级后的表格排序应符合 Steve 的直觉使用方式。

### 一级排序

先把“已经有报价的人”排到上面。

推荐分桶：

1. `quoted_mail2_or_later`
2. `quoted_mail1`
3. `replied_no_quote`
4. `sent_waiting`
5. `closed`

### 二级排序

每个桶内部按：

- `Reply_Last_At` 从近到远

### 这样带来的效果

你随时打开表时：

- 上面优先是已经有价格的人
- 下面才是还没价格的人
- 新价格一出现，就会自动被提到上面

## 是否要区分 Mail1 / Mail2

结论：**要区分。**

原因：

1. `mail1` 价格通常是第一次报价
2. `mail2+` 价格通常已经进入追价 / 压价 / 折扣阶段
3. 后续回复策略完全不同
4. 进度管理必须知道当前处于第几轮谈价

但区分方式应以：

- `Pricing_Effective_Wave`
- `Pricing_Round`
- `Mail1/2/3_Pricing_Excerpt`

来承载，而不是让主视图无限复杂。

## 新工作流如何映射到主表

### Flow A — 外联已发出

来自 S2 / bulk send 的人：

- 先 bootstrap 到 V3
- 标记为：
  - `Pipeline_Stage = sent_waiting`
  - `Draft_Workflow_Status = sent`

### Flow B — Gmail 插件扫描 inbox

当 inbox 扫到回复：

1. 判断是否命中 V3 既有 `Reply_Thread_ID`
2. 如未命中，再按邮箱 / source bootstrap
3. 更新 reply blocks
4. 更新 `Reply_Last_*`
5. 判断是否有价格
6. 更新 `Pricing_Round / latest_price_*`
7. 判断是否需要 OCR

### Flow C — 附件分流

当检测到附件：

1. 标记 `Attachment_OCR_Status = attachment_detected`
2. 拉回本地
3. OCR
4. 审计结果先落 `workbench`
5. 价格结论再回写到 master

### Flow D — Reply Draft

当准备起草回复：

1. 根据 thread + price round + scenario 判断动作
2. 生成 clean draft
3. 写回：
   - `Current_Reply_Scenario`
   - `Next_Reply_Action`
   - `Draft_Workflow_Status`

## Live Master 写入规范

### 核心原则

正式写入 live master 时，必须是**批次级写入**，不能一条 thread 写一次。

正确顺序：

1. 扫描邮件和 thread
2. 由大模型逐 thread 判断语义结果
3. 汇总成一份 `writeback manifest`
4. 对 live master 做一次批次级物理备份
5. 一次性应用整批 manifest
6. 输出写入后的 master 快照与 audit summary

### 为什么不能逐条写入

逐条写入会带来：

- 备份爆炸
- audit 噪音
- 中断后难以判断批次完整性
- 反复打开和写 CSV，增加编码与格式风险

如果一批有 1000 条，仍然只应该：

- 备份一次
- 写入一次
- 产出一份批次 audit

### 必须产出的批次文件

每次 live writeback 前后，必须在当天 `workbench/{YYYY-MM-DD}/` 产出：

- `writeback_manifest_*.csv`
- `pre_writeback_master_bak_*.csv`
- `post_writeback_master_snapshot_*.csv`
- `audit_live_writeback_*.csv`
- `summary_live_writeback_*.md`

同时仍要遵守项目全局红线，在：

- `Agency/list-bak/{YYYY-MM-DD}/`

保留一份正式灾备。

### Manifest 字段要求

`writeback_manifest` 至少要能说明：

- 是新增还是更新
- 匹配依据是什么
- 写入哪些价格字段
- 写入哪个 reply block
- 当前 `Pricing_Round`
- 当前 `Next_Reply_Action`
- 是否需要 OCR
- 是否允许进入 draft queue
- 是否需要 manual review

### 中断恢复

如果 live writeback 中断：

- 以批次 manifest 为准
- 不按单条历史补猜
- 用 pre-writeback backup 和 audit 进行恢复或重跑

### 与 shadow master 的关系

在规则尚未稳定前，仍优先写 shadow master。

当某一批经过 review 并决定进入 live master 时，才执行本节的批次级 live writeback。

## 结论

这次升级的关键不是再造一张新表，而是：

1. 继续使用现有 V3 作为唯一正式 master
2. 把它从 replied master 升级成 progress master
3. 让 Gmail 插件判断结果、附件 OCR 结果、reply draft 状态，都能稳定映射回这张表

这也是 `S3-codex-plugin-reply` 后续最重要的系统接线点。
