# Live Backfill Lessons

日期：2026-05-08

## 定位

这份 reference 记录 `s3_codex_backfill_batch_001` 到 `batch_004` 的 live master 回补经验。

它不是新的独立 skill，也不是一次性复盘。它是后续历史回补、daily incremental、draft queue 生成时必须参考的运行规则。

## 当前稳定判断

截至 `batch_004`，以下链路已经基本稳定：

1. Gmail connector 读取候选 message / thread
2. 大模型判断是否为 KOL outreach reply
3. 大模型判断价格轮次、有效价格、draft gate、manual review
4. 先生成 `writeback_manifest.csv`
5. 每个 live writeback batch 只备份一次 master
6. 脚本批量写入 live master
7. 输出 `audit_live_writeback.csv`
8. 输出 `queue_draft_ready.csv` / `queue_manual_review.csv` / `queue_ocr_first.csv`
9. 写 handoff，记录下一批 resume point

当前仍不应视为完全无人值守：

- Gmail connector 的输出可能被长 thread 截断
- 执行/QC/payment thread 容易混入候选
- 附件解析有时可由 Gmail connector 直接完成，有时仍需 OCR
- 价格冲突必须进入 manual review

## 核心经验

### 1. 不要边扫边写草稿

历史回补阶段只做：

- Gmail scan
- thread judgment
- manifest
- live master writeback
- queue output

不要在同一批里直接写 Gmail 草稿。

原因：

- 价格和阶段可能还没有完整落盘
- 同一联系人可能存在旧 thread / 新 thread / 执行 thread
- draft 依赖 `latest_price_normalized`、`Pricing_Round`、`Next_Reply_Action`
- 先写草稿会把错误判断放大

正确顺序：

```text
scan -> judge -> manifest -> backup -> live master writeback -> queue -> draft later
```

### 2. Manifest 是语义判断和脚本写入之间的边界

大模型负责：

- 是否 relevant
- 是否 workstream / execution
- 是否 system noise
- `mail1` / `mail2_plus`
- latest usable price
- draft gate
- manual review reason
- OCR/attachment status

脚本负责：

- 读 CSV
- 去重
- 备份
- 批量写入
- 排序
- audit
- queue split

禁止让脚本硬猜语义，也禁止让大模型直接手改 CSV。

### 3. 执行/QC/payment thread 必须排除出 ReplyOps 回补

以下类型不进入当前 reply-price backfill：

- 已经在改脚本
- 已经在看 rough cut / draft video
- 已经在确认 caption / posting
- 已经在收 invoice / PayPal
- 已经在执行付款 / release / affiliate link

这类 thread 应进入 execution/workstream 管理，而不是 outreach reply pipeline。

典型例子：

- Kelly Sun: Ticnote 已进入发布、invoice、collaborator tag
- BRIVVY: Freebeat 已进入 script / video QC / caption

### 4. 附件优先走 connector parse，失败再 OCR

附件处理顺序：

```text
Gmail connector attachment parse -> local parse summary -> OCR-first only if unclear
```

如果 Gmail connector 已经清楚解析出 PDF media kit 的价格页，可以写：

- `Attachment_OCR_Status = completed_connector_pdf_parse`
- `latest_price_basis` 指向本地 parse summary
- `queue_ocr_first.csv` 不需要包含该 row

典型例子：

- Alain Semevo: PDF media kit 被 Gmail connector 解析出 YouTube dedicated €3,500、YouTube integration €1,000、TikTok video €1,000。

如果 connector 只拿到附件但价格页不清楚，则写：

- `Attachment_OCR_Status = needs_ocr`
- `Draft_Workflow_Status = ocr_first`
- 不进入 `draft_ready`

### 5. 有价格冲突必须 manual review

如果同一 thread 中出现前后价格不一致，尤其是“best rate”比旧价格更高，必须：

- 写入 master
- 保留 latest quote
- 在 `latest_price_basis` 说明冲突
- `Reply_Needs_Manual_Review = yes`
- `Draft_Workflow_Status = manual_review`

典型例子：

- Anderson: 旧 quote 是 `$350` cross-post，后续 “best first-project rate” 是 `$400`，应写 master，但不能自动起草。

### 6. No-price 也可以进 master，但要沉底或 gated

如果是相关 KOL 回复但没有价格：

- 明确有兴趣：`Sort_Bucket = 2_replied_no_quote`
- 明确拒绝：`Sort_Bucket = 4_closed`
- 外部 media kit link 但未读价格：`manual_review` 或 `external_drive_link_pending`

无价格并不等于无价值。它有助于：

- 防止重复触达
- 记录 pipeline 状态
- 后续生成 ask-price draft

### 7. 每批必须写 handoff

每批结束后必须写：

- 当前 master row count
- append/update 数
- duplicate thread count
- draft/manual/OCR queue counts
- skipped count
- resume point
- 下一批 message ids 或 next page token

handoff 进入：

```text
workbench/handoff/
```

同时更新：

```text
workbench/handoff/LATEST.md
```

## Batch 001-004 经验快照

- Batch 001：shadow 11 条写入 live master，验证批量写入机制。
- Batch 002：真实 Gmail connector thread 样本写入，确认 duplicate skip 和 manual review gate。
- Batch 003：确认 execution/QC、system noise、decline、no-price lead 的分流规则。
- Batch 004：确认 PDF media kit 可由 Gmail connector parse 后直接写价；价格冲突进入 manual review。

## 后续升级方向

先继续跑 2-3 个 batch，观察以下规则是否仍稳定：

- execution/QC 排除是否足够准
- no-price 是否应 draft-ready 或 manual-review 的边界
- connector PDF parse 是否可稳定替代 OCR
- `Sort_Bucket` 是否能稳定实现“有价格浮上来，无价格沉底”

如果继续稳定，再把本 reference 中最核心的 5-8 条压缩进 `SKILL.md` 的 `Core Rules`。

## Batch 016-019 Bridge + OCR Merge Lessons

日期：2026-05-08

### 1. 旧线路接轨判断

`2026-03-28 ~ 2026-04-07` bridge window 已经证明新 Codex backfill 和旧 master 线路接上。

判断依据不是“扫到某个日期”，而是：

- 大量命中旧 `Capture_Run_ID`：`2026-03-19_run-002`、`2026-03-27_7d_segmented_recovery`、`2026-03-30_run-001`、`phase1_recent_20260318_103843_30h`
- batch 016-018 以 update old master 为主，而不是无控制 append
- batch 019 出现 0 行 safe writeback，说明 relevant KOL reply 大多已被旧 master 或新版 Codex batch 覆盖
- `Reply_Thread_ID` duplicate count 保持 0

### 2. OCR-first 不等于一直卡住

`ocr_first` 完成后必须明确退出：

- 如果 OCR/PDF extraction 找到价格：写回 `latest_price_raw`、`latest_price_normalized`、`latest_price_basis`，并把 `Draft_Workflow_Status` 改为 `draft_ready` 或 `manual_review`
- 如果 OCR/PDF extraction 没找到价格：写 `latest_price_normalized = no_price_media_kit_reviewed` 或同类表达，并进入 ask-price draft queue
- 不允许长期保留 `needs_ocr_*`，否则 daily loop 会反复处理同一附件

### 3. 附件必须 thread-aware

Gmail latest message 没有附件，不代表 thread 没有附件。

Preston Labs 的附件在较早 inbound message 上，latest reply 只有 “15% discount”。正确处理方式：

- 读取完整 thread
- 找到早先 PDF rate card
- OCR/解析 base rates
- 再结合 latest message 的 discount，写入当前有效价格

### 3.1 Thread freshness 不能只看 inbound

只校验“最新 inbound”还不够，必须同时校验“整条 thread 的最新整体消息”。

- 如果 thread 最后一封已经是我方 outbound，而且时间晚于对方最近 inbound，则不应再创建 reply draft
- 这类情况应把 `Draft_Workflow_Status` 标为 `no_draft_latest_outbound_already_replied`
- `Reply_Status` 应标为 `no_reply_needed_latest_outbound_ours`

典型例子：

- Tim Explains：对方最新 inbound 停在 `2026-03-12`，但我方已在 `2026-03-17` 发过回复，因此后续再起草属于 false positive，必须删除草稿并改回 no-reply-needed

### 4. Gmail connector 和本地 OAuth 分工

当前 Gmail connector 合理用于：

- 搜索 inbox/thread
- 读取正文
- 读取附件 metadata
- 快速判断是否需要 OCR

但它不提供稳定的附件 bytes 下载能力。附件下载仍应走本地 Gmail OAuth 脚本：

```text
Gmail connector metadata -> attachment_inventory.csv -> OAuth attachment download -> local extract/OCR -> manifest -> live master batch writeback
```

### 5. ag-ocr 的实际升级点

本轮修正了 `ag-ocr` 的调用路径问题：

- `.env` 从 skill root 读取，不依赖当前工作目录
- PDF 渲染脚本从 skill root 定位，不依赖当前工作目录
- PaddleOCR provider 从 skill root 找 `.venv/bin/paddleocr`

这保证 Social Agency workflow 可以从项目根目录直接调用 `ag-ocr`，不必先切换到 `ag-ocr` 目录。

### 6. 真实 OCR case 结果

- VKWeb：PDF 原生文本提取成功，写回 package rates，进入 `draft_ready`
- Preston Labs：原生 PDF 文本为空，但 `ag-ocr` PDF-to-image + tesseract 成功读出 rate card；结合 latest 15% discount 写回 master，进入 `draft_ready`
- Suhaib：PDF 提取成功但无价格；标记 `completed_pdf_text_extract_no_price_found`，进入 ask-price `draft_ready`

## Draft Queue + Preview Lessons

日期：2026-05-09

### 1. Consolidated draft queue 必须再次 gate OCR

`Draft_Workflow_Status = draft_ready` 不能单独作为上传 Gmail 草稿的依据。

队列生成时必须再次挡住：

- `Attachment_OCR_Status` 以 `needs_ocr` / `ocr_pending` / `ocr_review` 开头
- `Attachment_OCR_Status` 包含 `ocr_required`
- `Next_Reply_Action` 是 `manual_review` / `ocr_first` / `no_auto_reply`
- `Reply_Needs_Manual_Review = yes`

本次修正后，合并草稿队列从 `44` 条降到 `40` 条，避免未完成附件处理的 case 误进自动草稿。

### 2. 生成 Gmail 草稿前必须抽读完整 thread

预览 batch 001 验证了一个关键问题：master 里的结构化字段可能压缩了上下文。

例如 `Infinite` 当前 master 中显示为 `no_price_budget_request`，但完整 Gmail thread 中早已有：

- YouTube Short：`$1,500`
- TikTok：`$1,150`
- Cross Platform：`$2,000`

所以生成真实 reply draft 前必须读完整 thread，并允许生成 `master_correction_needed` 标记，而不是盲信当前 master 摘要。

### 3. 草稿预览先于 Gmail 写入

当前推荐顺序：

```text
live master -> consolidated draft queue -> Gmail full thread read -> local draft preview -> QA / correction manifest -> Gmail draft upload
```

不要从 queue 直接上传 Gmail draft。先落本地 preview，可以检查：

- 是否误用第一轮报价模板
- 是否忘记价格策略
- 是否需要 `Sorry for the late reply`
- 是否错误拼入 quoted history
- 是否需要先修 master price fields

### 4. 折扣价场景不要继续机械压价

如果对方已经给出 first-collab / agency-test / discount：

- 回复应 acknowledgement + keep warm
- 可以提“更现实的 first-test format”
- 不要再用第一轮报价模板继续索要 best rate

这类 case 包括 Preston Labs 和 Niyi Omotoso。

## Gmail Draft Upload Lessons

日期：2026-05-09

### 1. Gmail draft upload 前必须补齐 thread id

`gmail_create_reply_draft` 需要：

- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- recipient
- subject
- clean body

历史 master 中有些行只有 latest message id，没有 thread id。上传前应先用 Gmail plugin full-thread read 回填 `Reply_Thread_ID`，否则 local OAuth draft writer 无法稳定挂到原 thread。

### 2. 正确 token 路径

旧 draft 脚本默认 token 路径已经过期：

```text
AG-Skills-Hub/02 💼 Office/ag-google-workspace/auth/<YOUR_ACCOUNT_EMAIL>
```

当前可用 token 为：

```text
AG-Skills-Hub/02 💼 Office/ag-google-workspace/auth/<YOUR_ACCOUNT_EMAIL>
```

后续脚本应显式传 `--token-file`，不要依赖旧默认值。

### 3. Gmail 草稿创建后必须回写 master

成功创建 Gmail draft 后，master 至少应更新：

- `Draft_Workflow_Status = drafted`
- `Gmail_Draft_ID`
- `Gmail_Draft_Created_At`
- `Gmail_Draft_Job_ID`

这样 consolidated queue 会自动排除已写草稿的行，避免重复创建草稿。

### 4. Batch 001 实测结果

`draft_preview_batch_001` 的 8 封已成功写入 Gmail drafts，未发送：

- Preston Labs
- VKWeb France
- Suhaib Tamimi
- Niyi Omotoso
- mohamed_rivo
- Jessy Kigen
- Wander Pereira / minutotechpro
- Infinite

随后 live master 写回 `drafted` 状态，master 仍为 `465` 行，`Reply_Thread_ID` duplicate count 仍为 `0`。

## Remaining Draft Upload Lessons

日期：2026-05-09

### 1. Draft upload manifest 必须优先使用 queue row 的 thread/message

同一个 manager 邮箱可能代表多个 creator，同一个 creator 也可能在历史 master 中出现多个 thread。

因此生成 Gmail draft upload manifest 时，匹配优先级必须是：

1. 当前 queue row 的 `Reply_Thread_ID`
2. 当前 queue row 的 `Reply_Last_Message_ID`
3. 只有在上面缺失时，才回退到 master lookup

不要用 `Reply_Contact_Email + 频道/作者名称` 作为优先来源来取 thread id。

本轮 Damiano 出现过这个边界 case：同名同邮箱有旧 thread 和当前 thread。错误旧 draft 已删除，当前 thread draft 已补建。

### 2. Mixed price fields 不能被 `no_price` 字样误判

有些 rows 同时包含：

- 已知价格，例如 `$4,000 / $3,500`
- 以及 `dedicated_video: updated_available_no_price_shared`

这种不应进入 no-price ask-rate 模板。只要字段中存在有效金额，就应按报价场景处理，再根据金额高低选择：

- `N4 | high_price_soft_hold`
- `N6 | second_round_final_check`
- `N7 | discounted_quote_hold`

Bryan Low 是本轮修正案例。

### 3. 本轮结果

- 前 8 封用户确认已手动发送，master 标记为 `sent`
- 剩余 32 封已写入 Gmail drafts，未发送
- 最终 consolidated draft queue：`draft_ready = 0`
- master 行数仍为 `465`
- `Reply_Thread_ID` duplicate count 仍为 `0`

## Pre-Draft Thread Freshness Lesson

日期：2026-05-09

### 1. 不能只依赖 master/queue 的 latest message id

本轮暴露出一个关键漏洞：生成草稿时使用了 master / queue 中保存的 `Reply_Last_Message_ID`，但某些 thread 在 master 回补之后又出现了新的 inbound。

这会导致草稿基于旧内容写出，即使语气和谈判策略正确，也会错过最新上下文。

典型案例：

- Damiano：草稿按早期 `€1,100` / generic follow-up 写，但 thread 后续已经进入 TicNote 具体项目谈判，对方最新在 `2026-04-25` follow up 之前已提出 `€700 for 1 video including cross-posting`
- Bharti Mittal：旧 follow-up 之后，`2026-05-08` 又有新的 `Any update on this?`
- Frallo Tech：旧 budget 问题后，`2026-04-16` 又有新的 reconnect/flexibility follow-up

### 2. 正确上传顺序必须增加 freshness gate

以后 Gmail draft upload 前必须执行：

```text
queue row -> Gmail full-thread refresh -> find latest non-draft inbound -> compare with queue/master Reply_Last_Message_ID -> rebuild draft from latest inbound -> upload
```

如果不一致：

- 不允许直接上传
- 标记 `stale_thread_refresh_required`
- 更新 master 的 latest inbound metadata
- 用最新 inbound 重新生成 reply draft

### 3. Thread 内容判断必须以“最新 inbound 语义”为准

如果 latest inbound 已经进入具体项目 / 具体价格谈判，不允许再用早期 generic outreach 模板。

例如 Damiano / TechConNick 这种情况，应该按：

- 已有产品：TicNote Cloud
- 我方已报价：`€500`
- 对方最新可接受方向：`€700 for 1 video including cross-posting`
- 目标：继续谈当前项目是否能在 `€500-€700` 间成交

而不是重新问 generic first-test package。
