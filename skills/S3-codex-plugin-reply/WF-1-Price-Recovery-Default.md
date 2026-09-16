# WF 1 — Price Recovery Default

日期：2026-05-20

## Purpose

这是 `S3-codex-plugin-reply` 的默认 workflow。

默认目标不是压价。

默认目标是：

1. 把所有 usable price 拉回本地
2. 如果还没拿到 usable price，就继续追问价格
3. 如果对方先问我们是谁、服务谁、公司情况、合作方式，就用最小充分信息回答
4. 让 thread 尽快进入“可写回价格”的状态

## Ownership In The Overall System

`WF-1` 在整套 skill 里的职责现在明确是：

- 自己完成从 capture evidence 到 `reply_needed_from_us` 的默认判断
- 完成 `WF-1` judgment
- 完成 `WF-1` reply drafting
- 产出可写回本地的价格与动作结论

如果你要问：

> `WF-1` 的情况下“前面怎么判断、怎么写回信”放在哪里？

答案是：

- 前面的业务判断，放在 `WF-1` 的 `Need-Reply Gate + Round-Depth Rule + Scenario Cards + Standard Judgment Order`
- 回信正文，放在 `WF-1` 的 `Default Reply Moves + Draft Quality Standard + Output Contract`

一句话：

> `WF-1` 既是默认判断层，也是默认起草层。

## End-To-End Contract

以后默认直接运行 `WF-1`。

`WF-1` 自己内部就包含完整顺序：

1. capture thread evidence
2. full-thread review
3. need-reply judgment
4. `WF-1` scenario routing
5. price extraction / structure completion
6. local writeback
7. draft decision
8. draft writing

一句话：

> `WF-1` 本身就是一条完整 workflow。

## Latest Pointer Rule

每次进入 `WF-1`，默认先看：

1. `output/wf1_latest_resume.md`
2. `output/wf1_latest_checkpoint.json`

而不是等用户提醒“上次跑到哪里”。

如果这两个指针文件存在：

- 先按它们给出的 `last_window_end_at -> now` 时间窗做最新增量扫描
- 先把当前 inbox 顶部直到最新时间窗边界内的 thread 全部扫到
- 只有最新时间窗扫完后，才允许继续历史 backfill / deeper page review
- 如果 checkpoint 里同时保存了历史 backfill cursor，它只是第二优先级，不得盖过最新时间窗扫描

只有在 pointer files 缺失或明显失真时，才允许人工回翻日期目录。

一句话：

> `WF-1` 的默认入口不是“继续翻旧页”，而是“先把上次结束时间到现在的最新回复全扫完”。 

## Script vs LLM Contract

这条 workflow 明确采用：

- `脚本 = 提供证据包，不替代判断`
- `LLM = 判断场景、决定动作、起草正文`

脚本可以做：

1. 拉完整 thread
2. 拉附件与历史上下文
3. 提供本地主表字段
4. 提供 writeback / draft manifest 容器
5. 执行本地主表写回与 Gmail draft 上传

脚本不应该做：

1. 用硬规则直接决定 `S1-S9`
2. 用 preview 先缩掉真实应回复 case
3. 代替 LLM 决定正文策略
4. 在价格结构未完整前直接决定 thread 已 closed

## Capture And OCR Gate

`WF-1` 现在自己携带 capture / OCR gate。

默认顺序：

1. 先抓完整 thread，而不是只看 snippet
2. 先确认最新整体消息来自谁
3. 如有附件，先判断是否 `ocr_first`

进入 `ocr_first` 的条件：

- 最新 inbound 或同 thread 更早 inbound 带 `pdf / image / rate card / media kit`
- 正文没有足够清晰的 usable quote
- 或正文明确说价格在附件里

硬规则：

- `ocr_first` 完成前，禁止直接起草
- 先恢复价格，再继续 `WF-1` 判断

## Resume Contract

以后每一批 `WF-1` inbox review 都必须同时落两层记录：

### Layer A. Dated Archive

- `workbench/{YYYY-MM-DD}/wf1_gmail_review/...`

### Layer B. Latest Pointer

- `output/wf1_latest_resume.md`
- `output/wf1_latest_checkpoint.json`

`wf1_latest_checkpoint.json` 至少要包含：

1. `workflow`
2. `run_date`
3. `tranche_id`
4. `scan_mode`
5. `last_window_start_at`
6. `last_window_end_at`
7. `candidate_threads_seen`
8. `wf1_threads_selected`
9. `processed_thread_ids`
10. `latest_inbound_message_ids`
11. `artifact_paths`

如果这一轮同时做了历史翻页 backfill，可以额外包含：

1. `page_cursor_before`
2. `page_cursor_after`
3. `backfill_scan_mode`

但这些历史 cursor 字段默认不再是 `WF-1` 的主入口。

去重规则固定为：

1. `Reply_Thread_ID` 是主键
2. `Latest_Inbound_Message_ID` 是刷新键
3. 同 thread + 同 latest inbound = duplicate
4. 同 thread + 更新的 latest inbound = refresh, not duplicate

## Incremental Scan Rule

`WF-1` 默认采用：

- `latest-first`
- `resume-boundary incremental sweep`
- `full-thread refresh before judgment`

标准顺序固定为：

1. 从 `wf1_latest_checkpoint.json` 读取：
   - `last_window_end_at`
   - `resume_boundary_lower_date` 或等价历史边界
   - `processed_thread_ids`
2. 先以 `last_window_end_at -> now` 扫最新增量
3. 然后继续从 inbox 顶部向下扫，直到命中“上一次已处理边界”
4. 这个边界默认表现为：
   - 到达 `resume_boundary_lower_date`
   - 或命中历史 checkpoint 对应的已处理 tranche/thread evidence
5. 对扫描范围内命中的 thread，必须读 full thread，再按最新 inbound 判断
6. 不允许因为“今天窗口扫完了”就提前停；只有命中上一次边界才允许停

首次运行或 checkpoint 缺失时：

1. 才允许使用配置起始时间
2. 或人工指定 `since`
3. 然后从这个起点一直扫到 `now`

硬规则：

- 不允许只靠旧的 `page_cursor` 就判断“这次已经续跑到了”
- 不允许因为在历史 backfill 里有 cursor，就跳过当前 inbox 顶部的新回复
- 不允许只看 snippet 就认定 thread 已不需要回复

## Coverage Proof Gate

以后 `WF-1` 在任何 writeback / draft 之前，必须先产出一层 `coverage proof`。

最低要求：

1. 明确打印本轮扫描窗口
   - `scan_window_top_at`
   - `boundary_target_from_checkpoint`
   - `lower_bound`
2. 明确说明扫描是否真的接上上一次 stop point
   - `connected_to_previous_stop = true / false`
   - 如为 `true`，必须给出至少一个 `boundary_hit_thread` 证据
3. 明确给出全量统计，而不是只报写回数
   - `thread_count`
   - `message_total_seen`
   - `price_signal_thread_count`
   - `new_price_thread_count`
   - `refreshed_price_thread_count`
   - `reply_needed_thread_count`
   - `existing_draft_thread_count`
   - `non_wf1_thread_count`
4. 明确落一份逐线程 triage 表
   - 每条 thread 至少要有：
     - `queue_name`
     - `action_bucket`
     - `in_master`
     - `is_refresh_vs_master`
     - `thread_has_draft`
     - `price_source`

硬规则：

- 没有 `coverage proof`，不得提前报“今天只有几个新价格”
- 没有 `connected_to_previous_stop` 证据，不得声称“已经接上头”
- `新价格` 与 `刷新旧价格` 不得混报成一个数字

## Dry Run Contract

`WF-1` 的 dry-run 是强制校验门，不是可选摘要。

推荐执行顺序改为两阶段：

1. `window gate dry-run`
   - 先做 metadata / inventory 级快扫
   - 先验证方向、边界、覆盖量
2. `full recovery dry-run`
   - 只在 gate 通过后，才进入 full-thread / OCR / writeback manifest 生成

dry-run 默认必须：

1. 读取当前 INBOX 顶部并向过去回扫
2. 扫到上一次 checkpoint 边界
3. 生成但不执行 writeback manifest
4. 生成但不覆盖 latest checkpoint

dry-run 最低产物：

- `wf1_resume_sweep_thread_inventory.csv`
- `wf1_resume_sweep_triage.csv`
- `wf1_resume_sweep_summary.json`
- `wf1_resume_sweep_summary.md`
- `wf1_resume_sweep_checkpoint_preview.json`
- `writeback_manifest_auto_resume.csv`

硬规则：

- dry-run 不得写 Gmail draft
- dry-run 不得写本地 master
- dry-run 不得写 Feishu
- dry-run 不得覆盖 `output/wf1_latest_checkpoint.json`

## Draft Skip Rule

`WF-1` 现在必须把“已有草稿 thread”当成一等状态处理。

默认顺序：

1. 扫 thread 时先检查是否已经存在 Gmail draft
2. 如已存在 draft：
   - 标记为 `pass_existing_draft`
   - 不再重复起草
   - 但如果发现更新的价格或 OCR 新价格，仍然允许本地 writeback
3. 如不存在 draft，才进入 `new_draft_candidate`

硬规则：

- `已有草稿 != 已完成 writeback`
- `已有草稿 != 已经不需要回复`
- `已有草稿` 只跳过重复 draft，不跳过价格恢复与本地同步

## Auto OCR And Auto Writeback Rule

以后 `WF-1` 对附件线程默认采用：

1. 自动抓附件 inventory
2. 自动执行 OCR
3. 自动抽取价格信号
4. 如果价格达到 `usable quote` 标准：
   - 自动生成本地 writeback manifest
   - 自动写回本地主表
5. 如果 OCR 后仍然没有 usable quote：
   - 进入 `draft_needed_no_price`
   - 或 `manual_review`

`usable quote` 的最低标准：

- 能识别出货币 + 数值
- 至少能对应一个 deliverable / package / placement
- 不是明显无效的 OCR 噪声

默认自动化优先级：

1. `body quote`
2. `OCR quote`
3. `new draft`
4. `manual review`

## Writeback-First Rule

`WF-1` 的核心规则是：

> `先把本地真相表更新完整，再决定推进动作。`

也就是说：

- 一旦拿到 usable quote，先准备写回本地
- 即使这一轮还没有马上发出去的回复，也不影响 `WF-1` 完成 capture / writeback

## When To Use

只要满足下面任一条件，优先走这条 workflow：

- 对方还没有给出 usable quote
- 对方只给了 media kit / links / generic interest
- 对方问：
  - 我们服务什么品牌
  - 我们是 agency 还是品牌方
  - campaign / brief / product category 是什么
- 对方给出的价格不完整，缺：
  - platform
  - deliverable
  - dedicated vs integration
  - usage
  - bundle breakdown
- 对方已经谈到可继续推进，但当前还停在：
  - 等我方内部确认
  - 等 brief / next step
  - 等我方回应 `any update`

## Non-Goal

这条 workflow 默认不做：

- 压 first-collab rate
- 直接砍价
- 讨论更激进的 agency discount

如果当前邮件的主目标已经明显是压价，改走：

- `WF-2-Price-Negotiation-Followup.md`

如果当前 thread 已明显进入执行 / review / invoicing / go-live 协调，优先改走：

- `workstream`

而不是继续当作 `WF-1` 普通拿价线程。

## Need-Reply Gate

进入 `WF-1` 之前，先判断这条 thread 是否真的需要回复。

这里的最终判断默认由 LLM 完成，不允许只凭旧脚本 preview 命中与否来决定。

### 明确需要回复

下面这些默认属于 `reply_needed_from_us`：

1. 我方发出一封，对方回了一封，而且还没有拿到 usable quote
2. 已经有一个来回，进入第二个来回，但价格仍未拿完整
3. 对方最新一封在问：
   - usage
   - formats
   - company / agency / brand background
   - budget
   - brief
4. 已经谈好大方向，但对方在追问：
   - `any update`
   - `just following up`
   - `checking in`
   - `did you have a chance`

### 默认不需要回复

下面这些默认先不进 `WF-1`：

1. 最新整体消息已经是我方发出
2. 对方只完成了信息投递：
   - 发来 rate card
   - 发来 media kit
   - 发来 channel links
   - 没有新的问题，也没有催进度
3. 自动回复 / OOO / bounce / admin routing
4. thread 已经多轮往返，并且明显进入执行或交付协同
5. thread 已经 8-9 轮以上，而且最新对方消息没有新的价格缺口、没有新的问题、也没有催进度

## Round-Depth Rule

`WF-1` 需要结合轮次深度判断。

### R1. Light Thread

定义：

- 1 个来回
- 或刚进入第 2 个来回

默认策略：

- 大概率继续回复
- 重点是尽快拿到 usable quote 或补齐价格结构

### R2. Active Pricing Thread

定义：

- 2-4 个来回
- 仍在 price recovery / scope clarification 阶段

默认策略：

- 继续回复
- 但必须很明确当前这一封的唯一目标

### R3. Mature Thread

定义：

- 5 轮以上
- 已经谈过价格、scope、next step

默认策略：

- 不再默认“有来信就回”
- 先判断 thread 当前到底卡在：
  - 价格未完整
  - 我方内部等待
  - 执行协调
  - 单纯 follow-up

### R4. Deep Multi-Round Thread

定义：

- 8-9 轮或以上

默认策略：

- 默认不再按普通拿价线程自动推进
- 除非最新 inbound 明确属于：
  - `any update`
  - `still waiting on your side`
  - `please confirm next step`
  - `need answer to blocking question`

否则先标：

- `closed_no_reply_needed`
- 或 `manual_review`
- 或 `workstream`

## Core Decision

### P0. No Usable Quote Yet

动作：

- 追问 usable quote
- 尽量一次性问齐结构

优先拉回这些字段：

- platform
- deliverable format
- dedicated / integration / shorts / repost
- usage rights
- bundle price vs single-unit price

### P1. Partial Quote Only

动作：

- 不急着压价
- 先补齐结构缺口
- 但如果当前已经是 usable quote，默认不要再发 broad re-quote 邮件
- 已有报价时，默认至少回一封简短确认型邮件，而不是继续泛化追问

典型缺口：

- 只给 bundle，不给 single option
- 只给一个大包价，不给 starter option
- 只给口头模糊范围，不给明确数字

如果已经满足：

- 报价可写回本地
- 没有新的关键问题需要我方回答
- 也没有明确阻塞当前判断的结构缺口

则默认改走：

- `quoted_confirm_standard`

而不是继续追问。

### P2. They Ask About Us First

动作：

- 用最小充分信息回答
- 立刻把对话拉回价格

回答原则：

- 不过度暴露 brand
- 不提前丢完整 brief
- 只提供足够让对方愿意报价的背景

## Default Reply Moves

### Move 1. Ask For Quote

适用于还没报价。

必须优先拿回：

- best current rates
- key formats
- recent media kit if needed

### Move 2. Ask For Breakdown

适用于已有模糊报价，但不够写回本地。

重点不是压价，而是让价格变得可落表。

### Move 3. Minimal Company Context

当对方问我们是谁时，可回答：

- Rockbase Agency
- 我们主要服务 AI / software / workflow 类 campaign
- 当前在先做 creator fit / shortlist / first-test review

然后立刻回到：

- current rates
- available formats
- any starter option

### Move 4. Quoted Confirm Standard

适用于：

- 对方已经给出 usable quote
- 本轮不需要继续压价
- 也不需要把平台和格式重新问宽

动作：

- 回一封统一确认型邮件
- 不复述具体价格
- 不加入价格分析
- 不追加 broad re-quote

统一模板：

```text
Hi [Name],

Thank you, that is very helpful.

I’ve noted this on my side and will keep it in our current review.

If there’s a strong fit for the next round, I’ll follow up with the relevant campaign context and next step.

Best regards,
Annabel
Rockbase Agency
```

## Scenario Cards

`WF-1` 默认按下面 `S1-S9` 来路由。

### S1. Interested But No Price

触发条件：

- 对方表达兴趣
- 没给任何 usable quote

回答原则：

- 不绕弯
- 直接索价
- 一次尽量问齐关键格式

继续要价问法：

- `Could you share your current rates for the most relevant formats?`
- `It would be especially helpful to see your current dedicated, integration, or short-form options if available.`

不该说的话：

- 不要先谈预算
- 不要先压价
- 不要只说 `would love to keep in touch`

### S2. Media Kit Or Link Without Clear Price

触发条件：

- 对方只发 media kit
- 或只发官网 / doc / rate deck link
- 但正文里没有清晰报价

回答原则：

- 不自己脑补 kit 里的价格
- 让对方确认当前有效报价

继续要价问法：

- `Could you confirm the most relevant current rates for this type of collaboration?`
- `If there is a specific current rate card you would want us to reference, feel free to share it directly here as well.`

不该说的话：

- 不要假设附件价格一定是 current effective price
- 不要直接进入谈价

### S3. Vague Price Range Only

触发条件：

- 对方只说 `starting from`
- 或 `depends`
- 或给很模糊的范围

回答原则：

- 先把价格具体化
- 不急着往下谈

继续要价问法：

- `Could you share the clearest current numbers you would want us to compare on our side?`
- `If the pricing varies by format, a simple breakdown by the main options would be very helpful.`

不该说的话：

- 不要把模糊范围直接当成本地正式价格
- 不要抢先进入砍价

### S4. Bundle Price Without Breakdown

触发条件：

- 给了 bundle
- 没给 single-unit option
- 或没拆平台 / deliverable

回答原则：

- 先补 breakdown
- 让价格变得可写回

继续要价问法：

- `Could you also break that out into the most relevant individual options?`
- `If there is a lighter single-format or single-video option, that would also help us compare more accurately.`

不该说的话：

- 不要直接问能不能更便宜
- 不要在价格结构没清前就进入 negotiation mode

### S5. Missing Usage / Cross-Post / Scope Details

触发条件：

- 给了数字
- 但不知道是否含 usage
- 或是否含 repost / cross-post / edits / whitelisting

回答原则：

- 先把 scope 补清
- 目标是拿完整 usable quote

继续要价问法：

- `Does that rate already include any usage or repost support, or would that be separate?`
- `If cross-posting or usage is handled separately, could you share how you normally structure that?`

不该说的话：

- 不要默认价格已含 usage
- 不要直接把 scope 不清的价格写成 final

### S6. Asks About Agency / Brand / Company First

触发条件：

- 对方先问我们是谁
- 问服务哪些品牌
- 问是什么 campaign

回答原则：

- 最小充分回答
- 不过度暴露 brand
- 结尾必须回拉到价格
- 默认不要主动提 `paid whitelisting` 或 `exclusivity`
- 平台口径默认放开，让对方按自己相关平台报价，尤其不要漏掉 `YouTube`

继续要价问法：

- `We are Rockbase Agency, and we mainly review AI / software / workflow collaborations.`
- `At this stage we are still reviewing creator fit and first-test options, so it would also be helpful to understand your current rates and available formats.`

不该说的话：

- 不要一上来给完整客户名单
- 不要一上来发完整 brief
- 不要只回答他们的问题却忘了继续索价

### S7. Asks About Budget First

触发条件：

- 对方反问预算
- 要求先给 budget range

回答原则：

- 不先亮底牌
- 把话题拉回 creator 当前报价

继续要价问法：

- `We are still comparing creator fit and current rate structures before narrowing final shortlist decisions.`
- `It would help first to see your current rates or strongest starting options for the most relevant formats.`

不该说的话：

- 不要直接报预算
- 不要让 thread 变成对方套预算

### S8. Wants Full Brief Before Pricing

触发条件：

- 对方要更完整 brief
- 要求先看 campaign details 才报价

回答原则：

- 可以给最小 brief context
- 但不提前给完整包
- 仍要把 thread 拉回价格
- 默认不要主动先限定成只有 `TikTok / Instagram`
- 如果对方有多个相关平台，默认允许对方一起报 `TikTok / Instagram / YouTube / LinkedIn` 等最相关平台价格

继续要价问法：

- `What I can share for now is that the category is AI / software rather than a broad consumer campaign.`
- `Based on that direction, could you share the most relevant current rates you would want us to review first?`

不该说的话：

- 不要把完整 brief 提前交出去
- 不要在没报价前就进入深度 campaign discussion

### S9. Agreed Direction, Waiting On Us, They Ask Any Update

触发条件：

- 价格或方向已经大致谈到位
- 对方最新 inbound 是 `any update / following up / checking in`
- 当前卡点在我方内部，而不是对方没给信息

回答原则：

- 这类不是压价
- 也不是继续追价
- 而是发一封短的安抚 / 承接 / 延迟软化邮件
- 让对方知道 thread 还活着

继续回复问法：

- `Thank you for following up, and sorry for the delay on our side.`
- `We are still reviewing the next-step fit internally, but I did not want to leave you without an update.`
- `I will come back to you as soon as I have a firmer next step to share.`

不该说的话：

- 不要假装马上会定
- 不要重新谈一遍价格
- 不要写成冷冰冰的 `noted`
- 不要把它误判成“不需要回”

## Standard Judgment Order

每次起草 `WF-1` 时，固定按这个顺序判断：

1. `thread 是否归 ReplyOps 管`
2. `最新整体消息是不是对方发的`
3. `这条 thread 现在需不需要回`
4. `是否应先进入 ocr_first`
5. `当前轮次深度属于 R1 / R2 / R3 / R4 哪一类`
6. `有没有 usable quote`
7. `这个价格能不能直接写回本地`
8. `如果不能，缺的是数字，还是缺结构`
9. `对方有没有先问我们问题`
10. `如果是 any update，是否应改走 S9`
11. `这封发出去后，能不能更接近 writeback-ready 或 keep-warm-safe`

这 `1-11` 步是 `WF-1` 的核心判断层。

硬规则：

- 这部分必须基于完整 thread
- 不能只基于 snippet
- 不能只基于旧 master 匹配
- 不能由脚本用窄路由提前代替

## Writeback Standard

一旦拿到 usable quote，就要准备写回：

- `latest_price_raw`
- `latest_price_normalized`
- `latest_price_basis`
- `current_price_summary`
- `Pricing_Round`
- `Current_Reply_Scenario`
- `Next_Reply_Action`

价格字段硬规则：

1. `latest_price_raw`
   - 直接保留正文或 OCR 中的原始报价行
   - 尽量保留原顺序、原货币、原 wording
   - 不允许把原文压成裸金额串
2. `latest_price_normalized`
   - 必须写成带平台 / 内容类型的结构化多行格式
   - 推荐格式：
     - `· Instagram: Reel = 2,200 USD`
     - `· TikTok: Integration = 250 USD`
     - `· Add-on / Usage Rights: 30-day whitelisting = 3,000 USD per platform`
   - 若平台不明确，必须显式写：
     - `· Unknown Platform: Short Form Video = 800 USD`
3. 禁止格式：
   - `300 USD | 300 | 450 USD | 450`
   - `THB 15,000 | 15,000 | 10,000 USD | ...`
4. 货币码必须标准化成合法形式：
   - `USD / GBP / EUR / THB`
   - OCR 误读如 `THP` 必须在 `latest_price_normalized` 中纠正成 `THB`
   - 但 `latest_price_raw` 仍保留原始证据文本

推荐状态：

- `Pricing_Round = no_quote / first_quote / partial_quote`
- `Current_Reply_Scenario = price_recovery_default`
- `Next_Reply_Action = request_rate / request_breakdown / writeback_complete_wait_next_round`

## Draft Quality Standard

这条 workflow 的正文应该像：

- 专业
- 简洁
- 明确
- 以拿价为中心
- 默认不主动提 `paid whitelisting / exclusivity`
- 默认允许对方按相关平台一起报价，尤其补上 `YouTube`
- 正文只写新的回复内容，不手动粘贴旧邮件引用
- 禁止在正文中出现 `On Tue ... wrote:`、整段历史抄送、或转发式引用块

## Draft Ownership

`WF-1` 的正文起草权归 LLM，不归脚本。

脚本最多只负责：

- 落 draft manifest
- 上传 Gmail draft
- 把 draft id 写回本地

正文策略必须由 LLM 根据下面信息综合决定：

1. `Scenario card`
2. `Round depth`
3. `usable quote status`
4. `latest inbound ask`
5. `writeback gap`

## Reply Format Rule

`WF-1` 默认使用干净的 top-posting 格式。

硬规则：

- 只写新的回复正文
- 不手动复制上一封邮件内容
- 不手动插入 `On ... wrote:` 引用头
- 不手动保留整段 quoted history

说明：

- Gmail 线程里如有系统自动挂载的历史引用，视为客户端行为
- 但 LLM 生成的正文部分必须在视觉上干净结束，不能把历史邮件继续写进正文

不应该像：

- 已经进入砍价
- 一边说在了解，一边突然压价
- 一边说不方便给 brief，一边又把谈价写得很重

## Output Contract

每封候选回复在正文前，至少先写：

1. `Thread Synopsis`
2. `Scenario Decision`
3. `Draft Plan`
4. `Reply Self-Check`

其中 `Scenario Decision` 必须明确写：

- `Workflow = price_recovery_default`
- `Why not negotiation yet = ...`
- `Scenario card = S1 / S2 / S3 / S4 / S5 / S6 / S7 / S8 / S9`
- `Round depth = R1 / R2 / R3 / R4`

并且建议补一行：

- `Judgment owner = LLM full-thread review`
