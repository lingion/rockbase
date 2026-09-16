# Cold Mail Run

> 用途：当任务是批量补齐 `Mail1_*` 邮件字段时，使用本工作流。
> 本文档只定义执行流程，不承载正文模板与 variant 细节。
> 文案资产统一放在 `references/cold_mail_copybook.md`。

## 1. Scope

- 适用场景：
  - 首次陌生邮件触达
  - Creator intake
  - 索取 media kit / channel links / rates
- 不适用场景：
  - X / Twitter DM
  - X / Twitter DM 输入执行

## 2. Required Inputs

- 源表至少应具备：
  - `频道/作者名称`
  - `联系方式`
  - `账号简介` 或 `账号简介__平台抓取`
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
  - `Mail1_Subject`
  - `Mail1_Content V1`
- 若存在以下控制字段，应复用：
  - `Mail1_Mode`
  - `Mail1_Variant`
  - `Mail1_Reason`

### 2.2 Mail1 Candidate Gate

- 只对 `联系方式` 为合法邮箱的行写入 `Mail1`
- `联系方式` 为空、无效、或明显不是邮箱的行，自动跳过
- `Mail1_Variant` 只在通过候选门槛的行里写入
- 没有邮箱的行不写 `Mail1_Greeting_Name / Mail1_Hook / Mail1_Subject / Mail1_Content V1 / Mail1_Content V2`

## 2.1 Canonical Script

- Gmail-native `Mail1` 生成入口：
  - `scripts/gmail/fill_mail1_with_codex.py`
- 默认机器配置：
  - `references/cold_mail_workflow_config.json`

## 3. Field Ownership

- 必须由 `LLM` 逐行判断：
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
  - `Mail1_Reason`
- 应优先由规则模板生成，必要时允许 `LLM` 轻量修正：
  - `Mail1_Subject`
- 必须由脚本按 copybook 规则拼装：
  - `Mail1_Content V1`
  - `Mail1_Content V2`
- 必须显式写入控制列：
  - `Mail1_Mode`
  - `Mail1_Variant`

## 4. Workflow

1. 先物理备份源表。
2. 只选“有合法邮箱且允许进入后续邮件”的行。
3. 小批量试跑 `5-10` 行。
4. 由 `LLM` 生成 `Greeting / Hook / Reason`。
5. 按 `references/cold_mail_copybook.md` 决定 `Variant`、`Subject`、正文拼装。
6. 人工抽查：
   - 名字是否叫对
   - 是否错误加了 `Team`
   - Hook 是否空泛
   - Subject 是否像群发
   - 正文是否保留真实换行
7. 先做“防串稿抽查”。
8. 小样通过后再全量写回。

## 5. Execution Rules

- 默认只处理有合法邮箱的行。
- `Greeting` 不允许用首词截断、正则清洗、关键词表替代 `LLM`。
- `Hook` 不允许统一句式硬刷。
- `Content V1 / V2` 不允许整封自由生成。
- 没有合法邮箱的行必须自动跳过，不得强行补写 `Mail1`。
- 如果人工已修改 `Mail1_Greeting_Name` 或 `Mail1_Hook`，重跑时必须同步刷新 `Subject / Content / Reason`。
- 若人工指定了 `Mail1_Variant`，脚本必须尊重人工值。
- sample 阶段未完成“防串稿抽查”前，不得直接进入全量写回。

## 6. QC Checklist

- `Mail1_Greeting_Name` 是否基于真人/组织做了正确判断
- `Mail1_Hook` 是否基于行内证据，而不是空泛夸赞
- `Mail1_Subject` 是否保持商务语气
- `Mail1_Content V1` 是否符合 copybook 的固定结构
- `Mail1_Content V1 / V2` 是否保留真实换行
- `Mail1_Reason` 是否足够短、可审计
- `Mail1_Variant` 是否只在合法邮箱行上写入

## 7. Anti-Mixup Review

### 7.1 Purpose

- 防止出现“串稿”
- 所谓串稿，是指以下字段来自不同对象，互相不匹配：
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
  - `Mail1_Subject`
  - `Mail1_Content V1`
  - 当前行的 `频道/作者名称 / 账号简介 / 联系方式`

### 7.2 When Required

- 每次 `Mail1` 首轮 sample 写入后，必须做
- 默认 sample 检查范围：
  - 先写 `5` 行
  - 检查这 `5` 行全部通过后，才允许继续全量
- 全量完成后，还应追加随机 spot check

### 7.3 Manual Review Items

每条 sample 至少检查：

- `Mail1_Greeting_Name` 是否与 `频道/作者名称` 对应
- 正文第一行是否严格等于 `Hi {Mail1_Greeting_Name},`
- `Mail1_Hook` 是否与当前行资料匹配，而不是别人的描述
- `Mail1_Hook` 是否真实出现在 `Mail1_Content V1` 中
- `Mail1_Subject` 是否和当前对象对应
- `Mail1_Content V1` 是否整体属于同一个人，而不是 `Greeting / Hook / Body` 来自不同对象

### 7.4 Machine Gate

- 在进入 manifest 前，必须通过：
  - `scripts/gmail/prepare_jobs.py`
- 该脚本默认会执行 Mail1 coherence check，至少校验：
  - 正文首行 greeting 是否匹配
  - hook 是否存在于正文中
  - subject / body / greeting 是否非空
- 未通过 coherence check 的行，不允许进入 manifest

### 7.5 Pass Criteria

- sample 行全部通过人工抽查
- sample 行全部通过 machine coherence gate
- 无以下情况：
  - greeting 对不上人
  - hook 属于别的账号
  - body 首行与 greeting 不一致
  - subject / body / hook 彼此错位

## 8. Output Contract

- 本阶段完成后，源表应至少具备：
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
  - `Mail1_Subject`
  - `Mail1_Content V1`
- 若项目启用完整控制字段，还应具备：
  - `Mail1_Mode`
  - `Mail1_Variant`
  - `Mail1_Reason`

## 9. Draft Run

### 8.1 Candidate Gate

- 只从 `Mail1发出状态` 为空的行里选
- 排除：
  - `drafted`
  - `sent`
  - `skip_same_contact`
- `联系方式`、`Mail1_Greeting_Name`、`Mail1_Subject`、`Mail1_Content V1` 必须完整

### 8.2 Recipient Cleaning

- `联系方式` 在进入 manifest 前必须先清洗
- 能提取合法邮箱就提取
- 清洗后仍不是合法邮箱就排除

### 8.3 Manifest

- manifest 必须写到当天 `workbench/{YYYY-MM-DD}/`
- 先生成候选表，再生成 `draft_jobs.csv`
- 生成后先向 Steve 汇报今日待发总数
- 默认使用：
  - `scripts/gmail/prepare_jobs.py`

### 8.4 Sample

1. 先跑 `1` 封
2. 再跑 `5` 封
3. Steve 确认后再跑全量

默认使用：
- `scripts/gmail/sample_send.py`

### 8.5 Bulk Run

- 全量只基于 manifest 跑
- 成功创建草稿后，manifest 标记为 `done`
- sample 保留 `sampled`

默认使用：
- `scripts/gmail/bulk_send.py`

### 8.5A Preflight Before Bulk Continuation

当任务不是“第一次全量”，而是“继续后面的 300 / 500 / 全部写完”时，进入 bulk 前必须先检查：

1. 当前候选行必须满足：
   - `status = pending`
   - `draft_id` 为空
2. 当前候选批次与历史 `done / sent` 的邮箱不能重叠
3. 当前候选批次内部邮箱不能重复
4. 若云端已有大批量草稿，至少先比较：
   - 本地 manifest `done`
   - 云端 Gmail `DRAFT` count
5. 若两者差值 `> 1`，先停，回到：
   - `reconcile`
   - `dedupe`
   - 必要时做云端 draft snapshot

一句话：

- **续写 bulk draft 不是直接接着跑，必须先过预检。**

### 8.6 Source Writeback

- Gmail draft 创建成功后，源表 `Mail1发出状态` 回写为 `drafted`
- 只有真正发出后，才把源表改成 `sent`

### 8.7 Failure Repair

- 失败先看 `manifest error`
- 若是脏邮箱，先修源表，再修 manifest，再单补
- 补发成功后，重新 `reconcile`
- 对账与修复默认使用：
  - `scripts/gmail/reconcile_drafts.py`
  - `scripts/gmail/dedupe_drafts.py`

### 8.8 Post-Bulk Reconcile

当发生以下任一情况时，bulk draft run 后必须马上做对账：

- 脚本被中断
- 用户怀疑有重复草稿
- 云端 `DRAFT` count 与本地 `done` 不一致
- 同一天内做了多轮 `继续后面的 300`

默认顺序：

1. 先跑 `reconcile`
2. 优先使用精确 key：
   - `to + subject + body_hash`
3. 若发现 exact duplicate：
   - 每组只保留 `1` 封
   - 其余删除
4. 删除后回读云端 `DRAFT` count

### 8.9 Cloud-vs-Local Drift Rule

- `云端 DRAFT = 本地 done`：正常
- `云端 DRAFT = 本地 done ± 1`：可接受，小漂移，先记账，不必立刻停机
- `差值 > 1`：异常，先停 bulk run，先对账和去重

## 10. References

- 文案资产：
  - `references/cold_mail_copybook.md`
- 机器配置：
  - `references/cold_mail_workflow_config.json`
