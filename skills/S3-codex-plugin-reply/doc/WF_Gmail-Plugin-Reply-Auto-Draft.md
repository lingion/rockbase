# WF Gmail Plugin Reply Auto Draft

## 目的

把 Gmail 插件读信能力升级成一条更稳的 dispatcher-first workflow。

这个 workflow 不再假设“看到回复就起草”，而是固定先做：

`relevance -> ownership -> need_reply -> confidence -> draft`

并且在 draft 前，必须先分流到两条正式业务 workflow 之一：

- `WF-1-Price-Recovery-Default.md`
- `WF-2-Price-Negotiation-Followup.md`

批量场景下，默认执行顺序是：

`full-thread capture/writeback -> WF-1 or WF-2 judgment -> draft`

## Start Rule

每次运行这条 Gmail workflow，默认先读：

1. `output/wf1_latest_resume.md`
2. `output/wf1_latest_checkpoint.json`

如果 pointer files 存在：

- 先按 pointer 确认上次停在第几批
- 再决定是继续下一页，还是刷新同一 thread 的最新 inbound

不要等用户提醒“继续从前 100 后面跑”。

## 标准顺序

1. Gmail 插件搜索最近回复
2. 读取候选 thread 目录
3. 读完整 thread
4. 做 `relevance` 初筛
5. 做 `ownership` 判定
6. 做 `need_reply` 判定
7. 做 `ocr_queue` 判断
8. 先执行本地 capture/writeback
9. 把不该 auto-reply 的 thread 分流出去
10. 对真正需要回复的 case 写 `thread synopsis`
11. 再写 `scenario decision`
12. 判断当前属于 `price_recovery_default` 还是 `price_negotiation_followup`
13. 再写 `draft plan`
14. 生成 reply body
15. 执行 `reply self-check`
16. 建立 reply manifest
17. 先 1 封 sample
18. 再小批量 sample
19. 用户确认后再扩量写 draft

## Dispatcher Gates

### Gate 1. Relevance

必须先落：

- `A1_outreach_reply`
- `A2_workstream_execution`
- `A3_system_or_noise`
- `A4_unknown_manual_review`

只有 `A1_outreach_reply` 继续往下走。

### Gate 2. Ownership

必须再落：

- `auto_reply`
- `steve_handle`
- `workstream`
- `ignore`
- `manual_review`

若为 `steve_handle / workstream / ignore`，直接停止 draft 流程。

### Gate 3. Need Reply

必须显式判断：

- `reply_needed_from_us`
- `no_reply_needed_latest_outbound_ours`
- `contact_update_only`
- `closed_no_reply_needed`
- `unclear_manual_review`

若不是 `reply_needed_from_us`，不得进入 draft。

### Gate 4. Confidence / Action

动作层只允许落到：

- `draft_queue`
- `missed_reply_queue`
- `ocr_queue`
- `contact_update_queue`
- `manual_review`
- `excluded`

## Draft Gate

进入 draft 前，以下条件必须全部满足：

1. `Relevance = A1_outreach_reply`
2. `Ownership = auto_reply`
3. `Need_Reply_State = reply_needed_from_us`
4. 最新整体消息来自对方
5. 当前不属于：
   - `ocr_first`
   - `update_contact_only`
   - `manual_review`
   - `stale_thread_refresh_required`

第 5 条很重要：

- `stale_thread_refresh_required` 不再混进普通 manual review
- 它必须进入显式 `missed_reply_queue`

## Full Thread Gate

一旦准备进入 draft，仍然必须执行旧的 full-thread discipline：

1. 当前执行模型已经读完完整 thread
2. 已确认我方最初 outbound
3. 已确认最新 inbound 在问什么
4. 已确认中间有没有价格、brief、timeline 往返
5. 已确认当前是第几轮谈判
6. 已确认最新整体消息是谁发的
7. 已确认我方是否已经在其后回过

## 必要中间产物

每个 draft candidate 至少要留下：

1. `Thread Synopsis`
2. `Scenario Decision`
3. `Draft Plan`
4. `Reply Self-Check`

缺任一项，都不能上传 draft。

## Missed Reply Branch

这个 workflow 现在要求显式补捞漏回。

只要某条 thread 满足：

- `Ownership = auto_reply`
- 最新消息来自对方
- `Need_Reply_State = reply_needed_from_us`
- 但当前 draft 因 thread 变旧、队列断档、或 message id 过期而不能直接上传

则进入：

- `missed_reply_queue`

处理动作：

1. 刷新完整 thread
2. 用最新 inbound 重建 synopsis
3. 重新判断 scenario
4. 重建 draft

## 正文硬规则

1. 必须先决定 workflow 和模板，再写正文。
2. 必须先完成 Phase 1 writeback，再进入 Phase 2 draft。
3. 默认 workflow 是拿价，不是压价。
4. 只有已拿到 usable quote，才允许进入 negotiation workflow。
5. 第二轮报价不能按第一轮回。
6. reply body 只写新增内容。
7. 不手工加入 quoted history。
8. 超过 2 天默认加 delay softener。

## 自动化扩展

建议保留两条心跳：

### 高频 heartbeat

- 扫最近回复
- 发现新的 `draft_queue / missed_reply_queue / ocr_queue`

### 低频 unresolved sweep

- 专扫未闭环 thread
- 抓出“最新整体消息来自对方，但尚未被我们回复”的 case

## 推荐最小执行产物

至少保留这些文件或运行记录：

1. `review_table_daily_incremental_candidates.csv`
2. `queue_draft_ready.csv`
3. `queue_missed_reply.csv`
4. `queue_manual_review.csv`
5. `summary_daily_incremental_queues.md`
6. `capture_writeback_summary.md`
7. `output/wf1_latest_resume.md`
8. `output/wf1_latest_checkpoint.json`
