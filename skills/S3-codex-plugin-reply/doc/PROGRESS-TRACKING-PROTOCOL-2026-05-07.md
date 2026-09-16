# Progress Tracking Protocol

日期：2026-05-07

## 为什么必须有这个协议

`S3-codex-plugin-reply` 如果要走向自动化，就不能每次都靠“重新扫过去一周”来工作。

否则会出现：

1. 每次扫描窗口都重复过大
2. 同一批邮件被反复 triage
3. progress 无法连续
4. daily summary 无法稳定衔接
5. master writeback 容易重复判断或覆盖

所以这个 skill 必须有一套明确的 **stateful progress tracking**。

---

## 核心原则

### Principle 1. 扫描要续跑，不要每次重刷全量

系统默认应该：

- 从上一次成功扫描的时间点继续往后扫

而不是：

- 每次都重新扫过去 7 天

### Principle 2. 允许少量 overlap，避免漏信

为了避免：

- Gmail 时间边界误差
- 时区问题
- 自动化中断

每次新扫描应允许一个小 overlap。

建议默认 overlap：

- `24h`

也就是说：

- 正常逻辑是“从上次 checkpoint 往后”
- 但实际搜索可以允许带一个回看窗口做去重

### Principle 3. 进度状态要机器可读，也要人可读

所以需要两层：

1. **机器状态**
   - 供脚本和自动化续跑
2. **人工状态**
   - 供 Steve / Codex 理解目前跑到哪了

---

## 建议的状态文件

### 1. 机器状态文件

放在：

- `output/automation_checkpoint.json`

作用：

- 记录自动化上一次成功跑到哪里

### 2. 人工状态说明

放在：

- `doc/PROGRESS-TRACKING-PROTOCOL-2026-05-07.md`
- 或未来的 handoff / summary 中引用

作用：

- 告诉人当前系统应该如何续跑

---

## automation_checkpoint.json 应至少包含的字段

### Scan State

- `last_successful_scan_completed_at`
  - 上一次成功完成 inbox scan 的时间
- `last_scan_mode`
  - `sample_24h / full_72h / full_7d / incremental`
- `last_scan_scope`
  - 说明当时扫的是哪些邮件范围
- `next_scan_strategy`
  - 例如：
    - `incremental_from_checkpoint_with_overlap`

### Process State

- `last_review_table`
  - 上一次 review table 的位置
- `last_summary_file`
  - 上一次 summary 的位置
- `last_manifest_file`
  - 上一次 draft / writeback manifest 的位置

### Master State

- `master_csv_path`
  - 当前正式 master 路径
- `master_mode`
  - `preview_only` 或 `writeback_enabled`

### Draft State

- `last_draft_batch_completed_at`
  - 最近一次写草稿完成时间
- `draft_policy_version`
  - 当前 draft 参考体系版本

### OCR State

- `last_ocr_batch_completed_at`
  - 最近一次 OCR 批次时间
- `ocr_pending_count`
  - 当前待 OCR 数量（如果已知）

---

## 扫描模式

这个 skill 后续要明确区分两种模式：

### Mode A. `master_backfill_from_now_backward`

适用于当前阶段。

目标：

- 从现在这一刻往过去扫
- 补建和修正 master
- 把：
  - 是否已回复
  - 是否已报价
  - 价格属于 `mail1 / mail2+`
  - 是否有附件待 OCR
  - 下一步动作

写成一份稳定的主表预览

说明：

- 这不是普通的日常巡检
- 这是一次“为了建立可信 master 基线”的历史回补

### Mode B. `daily_incremental_from_checkpoint`

适用于未来。

目标：

- 从上一次成功状态往现在推进
- 只处理新增邮件和新增 thread 变化

说明：

- 只有当 `master_backfill_from_now_backward` 做到足够稳定后，才切换到这个模式

## 扫描续跑规则

### Rule A. 当前阶段优先使用 backfill 模式

当前阶段默认：

- `master_backfill_from_now_backward`

也就是：

- 不是简单接着上次时间点往后扫
- 而是从当前时刻出发，往过去补历史
- 目标是把 master 建完整

### Rule B. 有 checkpoint 后

有 checkpoint 后，仍然要先看当前 `scan_mode`：

- 如果是 `master_backfill_from_now_backward`
  - 继续往更早历史推进
- 如果是 `daily_incremental_from_checkpoint`
  - 再按增量模式运行

### Rule C. daily incremental 的正式规则

进入日常模式后：

1. 从 `last_successful_scan_completed_at` 往后看
2. 带 `24h overlap`
3. 对命中的 message / thread 做去重

### Rule D. full backfill 只作为特殊动作

只有在这些情况下才重新全量扫：

- 明确要求回补历史
- checkpoint 丢失
- 系统停跑太久
- 需要重新做规则升级验证

---

## 与 daily summary 的关系

daily summary 不应该自己重新定义时间窗口。

它应该依赖 checkpoint：

1. 当前这次扫描新增发现了哪些有效邮件
2. 哪些进入了 master preview
3. 哪些进入了 OCR
4. 哪些进入了 draft
5. 哪些留给 manual review

也就是说：

- **checkpoint 决定“今天该看哪些增量”**
- **summary 只是汇总这些增量**

---

## 与 master writeback 的关系

progress tracking 不是独立于 master 的。

它应该明确知道：

1. 当前是否只在做 `preview_only`
2. 当前是否允许真正 `writeback`
3. 上一次 preview 对应的是哪份 review table
4. 哪一批邮件已经被判断过，哪些还没进 master

否则会发生：

- preview 一直做，但永远不知道是否已接入 master

---

## 当前建议

当前阶段建议状态是：

- `master_mode = preview_only`

原因：

1. 新 skill 刚刚独立
2. field mapping 刚刚明确
3. reply logic 正在升级
4. 还没做第一轮 preview-only writeback 验证

所以现在最合理的阶段不是直接写 live master，而是：

- 先把 checkpoint 建起来
- 先让增量扫描能接上
- 先把 preview-only writeback 跑通

---

## 当前已知历史进度

截至目前，已经完成过：

- `24h inbox triage`
- `72h inbox triage`
- `7d inbox triage`
- `7d sample reply drafts`

这说明：

- triage 层的历史 backfill 已做过一轮
- 但 master writeback 层还没有真正完成
- 所以当前还不能切到正式 `daily_incremental`

---

## 结论

以后这个 skill 的默认思维应该变成：

> 当前不是“普通增量续跑”，而是“从现在往过去补 master 基线”；等基线稳定后，才切到日常增量模式。

这就是后面自动化真正能接上头的前提。
