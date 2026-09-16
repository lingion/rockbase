# REFERENCE — Smart Reply Scenarios

日期：2026-05-07

## Purpose

这份 reference 现在保留为 `legacy mixed-mode reference`。

它记录的是旧阶段的思路：

- 同一套逻辑里同时处理拿价、解释背景、压价

从 `2026-05-20` 起，新的正式设计已经拆成两条 workflow：

1. `WF-1-Price-Recovery-Default.md`
2. `WF-2-Price-Negotiation-Followup.md`

以及两份独立 reference：

- `REFERENCE-price-recovery-reply-framework-2026-05-20.md`
- `REFERENCE-price-negotiation-reply-framework-2026-05-20.md`

所以这份文档后续只作为旧设计参考，不再作为默认执行入口。

---

## Core Rules

### Rule 1. 先看完整 thread

至少要看清：

- 我方最初 outbound
- 对方当前 latest inbound
- 如果中间已经来回过，最近一轮价格 / brief / budget 交互

### Rule 2. 第一轮报价必须压价，不允许直接接受

如果对方只是第一次给出价格，不管价格高低，默认都要执行压价动作。

区别不在于“压不压”，而在于“怎么压”：

- `standard negotiation`
  - 用 Rockbase 既有的 first-test / agency-test 标准压价方式
  - 适用于大多数常规 first quote case
- `content-aware negotiation`
  - 基于 thread 里已经出现的 deliverables、bundle、usage、cross-post、performance、follow-up pressure、verification 等具体内容，做定制化压价
  - 适用于对方信息更完整、格式更多样、或已经给出一部分让步空间的 case

- 能不能继续压 `agency rate`
- 能不能拿到 `first-collab rate`
- 能不能把同价交付做大
- 能不能拆分出更细的 format pricing
- 能不能把对方已经给出的内容转成更适合我们 first test 的 starter option

禁止出现的错误：

- 第一轮报价后直接进入纯保温
- 第一轮报价后只说 `I've noted the rates on my side`
- 第一轮报价后只要数据、不做任何价格动作

允许的例外非常窄：

- 只有 thread 的真正目标根本不是价格推进，而是 verification / identity resolution / no-reply-needed，才可以暂不执行价格动作
- 一旦 thread 已进入真实 first quote 讨论，就必须压价

### Rule 3. 第二轮报价不能装作第一轮

如果 thread 里已经就价格来回一轮了，就不能再写成：

- “Thanks for sharing your rates”
- “I’ll keep you in mind”

这种太轻、太像第一次看到报价的回复。

### Rule 4. Reply body 只写新增内容

不要手工加入：

- `On ... wrote:`
- 对方原邮件复制
- 我方旧正文复制

thread history 应交给 Gmail reply thread 本身处理。

### Rule 5. 核心表达模块固定，措辞允许灵活

允许灵活的部分：

- `Sorry for the late reply`
- `Thank you for following up`
- `I’ve noted this on my side`
- `Happy to review`

不能漂移的部分：

- 本轮目标
- 价格动作
- 模板方向

### Rule 6. 超过两天未回复时，默认加入 delay softener

如果你当前准备写的 reply draft 时间，与对方上一封 inbound 邮件时间相比，已经超过 `2` 天：

- 默认加入：
  - `Sorry for the late reply`
  - `Thank you for your patience`
  - `Thank you for following up, and apologies for the delay`

这条默认适用于：

- 报价 follow-up
- chase / 催进度
- 需要重新承接对话的商务回复

这条不要求死板逐字一致，但语气上必须更客气、更有承接感。

如果未超过 `2` 天，则不用机械加入。

### Rule 7. 价格输出必须遵守固定三层结构

后续所有进入 master / preview 的价格信息，默认都按下面三层输出：

1. `latest_price_raw`
   - 保留作者原话
   - 尽量忠实，不做格式化改写
   - 可以是一句，也可以是一组最关键的原文价格表达

2. `latest_price_normalized`
   - 必须使用结构化多行格式
   - 每行前统一加 `·`
   - 若存在 `Bundle Package`，固定放最上方
   - 再按平台 / 形式分行，例如：
     - `· YouTube: dedicated $500 | integration $350`
     - `· Instagram: reel $450 | story $200`
     - `· X: quote post $1,500 | thread $2,000`
   - 货币统一用标准符号与千分位格式，例如 `$1,500`、`€750`、`₹900,000`
   - 若同一项同时保留当前有效价与原价参考价，必须显式区分：
     - `[effective]`
     - `[regular/original reference]`

3. `current_price_summary`
   - 给 CSV 快速扫表用
   - 保持单行、短摘要
   - 示例：
     - `X bundle $3,000 | quote $1,500 | thread $2,000`
     - `YouTube integration €750`
     - `IG Reel + TikTok/YT Shorts repost $2,500`

补充：

- `latest_price_basis` 继续保留，用来说明价格来自哪一轮 reply block，以及是否参考附件
- bonus / 免费附赠项默认不要硬塞进 `latest_price_normalized` 主价格结构，除非它本身已经构成清晰、稳定的价格方案；否则优先留在 `latest_price_raw` 或后续 notes 字段

### Rule 8. 联系人 / 达人 / manager 命名必须保守

生成回复时，如果 thread 中同时出现：

- manager / agency 联系人
- creator nickname
- creator real name
- channel name

不要在正文里贸然使用不确定的人名来指代报价，例如 `Jack's current rates`。

更安全的写法：

- `the current rates you shared`
- `InfiniteTech's current rates`
- `the rates for the creator`
- `the pricing you sent over`

除非完整 thread 明确显示该名字就是对方当前代表的 creator，并且不会造成混淆，否则优先使用“你分享的价格 / creator 的价格 / channel 的价格”。

价格来源也要在内部判断中区分：

- body quote：来自 Gmail thread 正文
- attachment/OCR quote：来自附件或 OCR
- mixed quote：正文 + 附件合并

例如 Infinite case 的 `$1,500 / $1,150 / $2,000` 来自 Danielle 早前 thread 正文，不是 OCR。

**结构化价格示例**

> · Bundle Package: X quote post + X thread: $3,000
> · X: quote post $1,500 | thread $2,000

> · Bundle Package: Instagram Reel + TikTok repost: $2,200
> · Instagram: reel $1,800 | usage rights (30 days) $800
> · TikTok: dedicated $900 | ad code (30 days) $400

> · YouTube: dedicated $850 [effective] | dedicated $1,000 [regular/original reference]
> · Instagram: reel $425 [effective] | reel $500 [regular/original reference]

---

## Decision Framework

### Step A. 先判断价格轮次

- `P0`：对方还没有给 usable rate
- `P1`：对方第一次给出 usable rate
- `P2`：已经围绕价格来回至少一轮
- `P3`：对方已经给折扣价 / 特价 / 明确说可谈

### Step B. 再判断对方意图

- `I1`：有兴趣，但没报价
- `I2`：发了 details / media kit，但没价格
- `I3`：先问我们预算
- `I4`：先要 brief / verification / campaign info
- `I5`：已经报价，等你下一步
- `I6`：来 follow up / 催你
- `I7`：联系人跳转 / admin reply
- `I8`：明确给了折扣或表示可灵活

### Step C. 再确定本轮 operator goal

- `G1`：继续索价
- `G2`：压 first-collab / agency rate
- `G3`：接受当前价格并保温
- `G4`：接受折扣价并保温
- `G5`：先收集更多条件
- `G6`：不进入 auto-reply

---

## Opening Modules

这些不是完整模板，是可以插拔的开头模块。

### `O1 | standard_thanks`

> Hi,
>
> Thank you for your reply.

### `O2 | late_reply_softener`

> Hi,
>
> Sorry for the late reply, and thank you for your patience.

### `O3 | follow_up_acknowledged`

> Hi,
>
> Thank you for following up, and apologies for the delay.

### `O4 | warm_acknowledgement`

> Hi,
>
> Thank you for sharing the details. This is very helpful.

### `O5 | delay_after_2_days`

> Hi,
>
> Thank you for your patience, and apologies for the delay.

---

## Negotiation Strategy Modules

这些模块用于补强 `RQ1 / Scenario 5 / Scenario 6` 的压价能力。

核心原则：不要把压价写成生硬的 “Can you lower the price?”。Rockbase 的谈判姿态应该是：

1. 认可 fit
2. 说明 first agency test 的预算机制
3. 给对方降价或扩包的台阶
4. 不承诺立即执行
5. 让对方知道这是进入 shortlist / confirmed brief 前的内部评估

如果本轮 operator goal 是 `G2 | 压 first-collab / agency rate`，回复里必须至少使用下面一个 negotiation module。对于 `P1 | 第一轮报价`，这条是强制规则。不能只写：

- clarify scope
- request stats
- keep in touch

### Mandatory Rule For P1

当 `price round = P1` 时：

- 必须压价
- 必须留下一个明确的价格动作
- 不允许只做礼貌确认

可接受的价格动作包括：

- 直接试探 first-collab flexibility
- 试探 agency-test rate
- 同价扩包
- 把高价 format 往 lighter starter format 下引
- 要求对方给出更适合 first test 的 option

不合格示例：

> Thank you for sharing the rates. I’ve noted them on my side.

合格示例：

> Thank you for sharing the rates. For a first AI / tech test, we would usually start with a tighter starter structure. If there is any first-collaboration flexibility, I’d be glad to review the most workable option.

### `N1 | first_test_budget_logic`

**Use when**

- 对方第一次给了 usable rate
- 价格不算离谱，但还想拿 first-collab / agency rate
- 想压价但不想伤关系

**What it does**

- 把压价理由包装成客户测试机制
- 不是说对方贵，而是说 first-time campaign 要先 test

**Language module**

> For first-time AI / tech collaborations, our clients usually start with a tighter test budget before expanding into larger placements.
>
> If there is any first-collaboration flexibility for an initial agency test, I’d be happy to review the most workable option on your side.

### `N2 | package_value_expand`

**Use when**

- 价格本身不高，不适合硬砍
- 但可以争取更多 deliverables
- 例如 TikTok + Instagram repost / YouTube Shorts repost / story add-on / link in bio

**What it does**

- 不直接压现金价，而是提高同价交付价值
- 适合 Jessy 这种 `$500 per sponsored video` 的低价或中低价 creator

**Language module**

> For the first agency test, would the quoted rate cover one platform only, or could it include a simple repost on another active channel as part of the same starter package?
>
> That would help us position the first collaboration more clearly when comparing creators internally.

**Jessy-style example**

> For the $500 sponsored video option, would that be one TikTok post only, or could it include Instagram reposting as part of the same first-test package?

### `N3 | best_rate_without_pressure`

**Use when**

- 想压价，但需要给对方保全面子
- 不确定对方是否能降
- 适合 first quote 和 second quote 的温和试探

**What it does**

- 明确允许对方说 no
- 让对方更容易给一个小折扣或更好 package

**Language module**

> If that is your standard rate, no problem at all. I just wanted to check whether there is any first-collaboration or agency-test flexibility before we close this review round.

### `N4 | high_price_soft_hold`

**Use when**

- 报价明显高于常规 test budget
- 不想直接拒绝
- 仍想保留未来合作可能

**What it does**

- 不硬砍到离谱价格
- 转向更小 format 或 future matching

**Language module**

> I’ve noted the rate on my side. For an initial test, this may be above what most of our current AI / tech briefs can start with, so the more realistic path may be a smaller format first, if you offer one.
>
> If not, I’ll still keep your profile in mind for briefs where the budget range is a better match.

### `N5 | budget_request_deflection`

**Use when**

- 对方问 “What is your budget?”
- thread 里已经或尚未出现价格
- 你不想先报预算被锚定

**What it does**

- 不先交出预算
- 把话题拉回 creator 的 lowest workable / first-test option

**Language module**

> Rather than locking a proposed budget too early, we are still matching this round of AI / tech briefs against creator fit, deliverables, and expected performance.
>
> Could you let me know the most flexible first-test option you would be open to reviewing?

### `N6 | second_round_final_check`

**Use when**

- 我方已经压过一轮
- 对方给了第二轮价格、更新报价，或说可以给 discount
- 不能再装作第一次看到报价

**What it does**

- 表示理解这是 revised / adjusted pricing
- 只做最后一次轻试探
- 如果已给明确折扣，应转入接受 / 保温，不继续机械压价

**Language module**

> I’ve noted the revised pricing on my side. Before we close this review round, I just wanted to check once more whether this is the best first-collaboration agency-test rate you can offer.
>
> If this is already the most flexible option, no problem at all. I’ll keep it noted for matching briefs.

### `N7 | discounted_quote_hold`

**Use when**

- 对方已经给出 discount / first-collab rate
- 继续压价会显得贪心或不专业
- 目标是接受折扣并保温

**What it does**

- 明确记录折扣
- 不继续砍
- 可提示更现实的 smaller format / first-test path

**Language module**

> Thank you for confirming the flexibility. I’ve noted the adjusted rate on my side.
>
> For a first test, we may start with the format that gives the cleanest audience-fit signal before expanding into larger placements, so I’ll keep this in mind when matching briefs internally.

### Strategy Selection Guide

- `P1 + price reasonable`：优先 `N1` + `N2` 或 `N3`
- `P1 + price high`：优先 `N1` + `N4`
- `P2 + already negotiated once`：优先 `N6`
- `P3 + discount offered`：优先 `N7`，不要继续机械压价
- `I3 + asks budget`：优先 `N5`
- `low / mid price creator`：优先扩包 `N2`，不一定硬砍现金价
- `high price creator`：优先 soft hold `N4`，必要时 manual review

### Stronger Jessy Example

原问题：只问清楚 `$500 sponsored video` 包什么，但没有形成谈判。

更好的方向：

> Hi Jessy,
>
> Sorry for the late reply, and thank you for your patience.
>
> Thank you for sharing your channels and rates. I’ve noted the UGC package at $1,000 for 30 videos and sponsored ads starting from $500 per video.
>
> For first-time AI / tech collaborations, our clients usually start with a tighter test budget before expanding into larger placements. If the $500 rate is your standard rate, no problem at all, but I wanted to check whether there is any first-collaboration flexibility for an initial agency test.
>
> Also, for the $500 sponsored video option, would that be one TikTok post only, or could it include Instagram reposting as part of the same first-test package?
>
> It would also be helpful if you could share recent average views or screenshots for the account you would recommend for a first collaboration.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 1 — P0 + Interested But No Rate

**Code idea**: `S1`

**When this applies**

- 对方明确有兴趣
- 但还没有给 usable rate
- 也没有发清晰的 pricing sheet

**Operator goal**

- `G1 | 继续索价`

**Best template direction**

- 对齐旧模板：`RI1 | interested_request_rate`

**Must say**

- acknowledge 兴趣
- 明确索要价格
- 最好拆 format

**Avoid**

- 太早发很多 brief
- 先报预算
- 只说 keep in touch

**Recommended draft**

> Hi,
>
> Thank you for your interest.
>
> To help us assess fit internally, could you please share your current rates for:
> - a dedicated placement
> - a sponsored integration
> - any other format you would recommend for a first collaboration
>
> Once we complete this round of evaluation, we will follow up with the most relevant creators for confirmed briefs.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 2 — P0 + Details Sent But No Price

**Code idea**: `S2`

**When this applies**

- 对方发了 media kit / channel links / audience info
- 但还是没给 usable rate

**Operator goal**

- `G1 | 继续索价`

**Best template direction**

- 对齐旧模板：`RI2 | interested_send_details_no_price`

**Must say**

- acknowledge 已收到 details
- 明确指出还缺价格
- 继续索要推荐 format 的 rate

**Avoid**

- 把 details 当作已经足够
- 忘了把价格问题拉回来

**Recommended draft**

> Hi,
>
> Thank you for sending the additional details. We’ve received them on our side.
>
> To help us continue the review efficiently, could you also share your current rates for the formats you would recommend for a first collaboration, especially:
> - dedicated placement
> - sponsored integration
> - short-form placement, if applicable
>
> Once we complete this review round, we will follow up with the best-fitting creators for confirmed opportunities.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 3 — P0 + Asks Budget First

**Code idea**: `S3`

**When this applies**

- 对方先问我们的预算
- 还没有主动给 standard rate

**Operator goal**

- `G1 | 继续索价`

**Best template direction**

- 对齐旧模板：`RI3 | ask_budget_first`

**Must say**

- 预算依 deliverables / fit 而变
- 当前先 mapping creator rates
- 请对方先给 standard starting rate
- 如果 thread 里已经有价格，则不要装作没价格；使用 `N5 | budget_request_deflection` 要对方给 lowest workable first-test option

**Avoid**

- 直接把预算先报出去
- 被对方带着走，忘记拿 rate
- 已经有价格时仍把场景写成 `no_price_budget_request`

**Recommended draft**

> Hi,
>
> Thank you for your reply.
>
> Budget can vary depending on format, deliverables, and campaign fit, so at this stage we are first mapping creator rates before locking final allocations.
>
> If possible, please share your standard starting rates for:
> - a dedicated placement
> - a sponsored integration
> - short-form placement, if applicable
>
> That will help us assess fit internally and decide whether to move forward with a more detailed brief.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 4 — P0 + Brief Gate / Verification Gate

**Code idea**: `S4`

**When this applies**

- 对方要求先看 brief
- 或先验证身份
- 或先看 campaign info 才愿意继续

**Operator goal**

- `G5 | 先收集更多条件`

**Best template direction**

- 对齐旧模板：`RI4 | verification_or_brief_gate`

**Must say**

- acknowledge 对方要求合理
- 不发半成品 brief
- 如果合适，顺手要 rates

**Avoid**

- 一上来发不完整 brief
- 忘记说明为什么现在不发

**Recommended draft**

> Hi,
>
> Thank you for your reply, and that makes complete sense.
>
> For now, I’d prefer not to send over partial materials too early while we’re still narrowing campaigns internally. I think it would be more useful to come back to you once I have a clearer fit and more concrete context to share.
>
> If useful for our internal review in the meantime, you’re also very welcome to share your current rates for the formats you’d usually recommend.
>
> I really appreciate your time, and I hope we get the chance to pick this up again when the right brief comes through.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 5 — P1 + First Quote Received

**Code idea**: `S5`

**When this applies**

- 这是对方第一次给出 usable rate
- thread 里还没有出现我方针对这个 price 的上一轮追问

**Operator goal**

- `G2 | 压 first-collab / agency rate`

**Best template direction**

- 优先对齐旧模板：`RQ1 | quoted_send_details`

**Must say**

- acknowledge 已收到报价
- 表达 fit
- 明确试探 agency / first-test / first-collab flexibility
- 至少使用一个 negotiation module：
  - `N1 | first_test_budget_logic`
  - `N2 | package_value_expand`
  - `N3 | best_rate_without_pressure`
  - `N4 | high_price_soft_hold`

**Avoid**

- 第一次报价就直接接受
- 太快进入纯保温
- 只问 scope / stats，却没有价格策略

**Recommended draft**

> Hi,
>
> Thank you for sharing your rates and the additional details.
>
> We do see a strong fit with the types of AI / tech campaigns we are currently reviewing. For first-time collaborations, our clients usually begin with tighter test budgets before expanding into larger placements.
>
> If there is any flexibility for an initial agency test, we would be glad to review:
> - your best dedicated rate
> - your best integration rate
> - any first-collaboration or agency rate you may be open to
>
> Once we complete this round of internal review, we will follow up with the most relevant creators for confirmed briefs.
>
> Best regards,  
> Annabel  
> Rockbase Agency

**Variant for X / thread creators**

> Hi,
>
> Thank you for sharing the pricing breakdown.
>
> We do see a strong fit with the types of AI / tech campaigns we are currently reviewing. For first-time collaborations, our clients usually begin with tighter test budgets before scaling into larger placements.
>
> If there is any flexibility for an initial agency test, we would be glad to review:
> - your best quote-post rate
> - your best thread rate
> - any first-collaboration or agency bundle rate you may be open to
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 6 — P2 + Second-Round Quote Or Requote

**Code idea**: `S6`

**When this applies**

- 我方已经追问过一轮价格
- 或已经要求拆分 format
- 对方现在给的是第二轮报价 / 更新报价 / requote

**Operator goal**

- `G2` 或 `G3`
- 重点是：不能再像第一次看到报价那样回复

**Best template direction**

- 优先还是 `RQ1`
- 如果已经不适合继续压了，再转 `RQ2`

**Must say**

- acknowledge updated / revised pricing
- 体现你知道这已经是第二轮
- 如果还压价，要更克制、更像最后一轮试探
- 如果继续压价，优先使用 `N6 | second_round_final_check`
- 如果对方已经给折扣，转入 `N7 | discounted_quote_hold`

**Avoid**

- 回到泛泛的 “thank you for sharing your rates”
- 假装没看到前一轮互动
- 已经拿到折扣后继续机械压价

**Recommended draft**

> Hi,
>
> Thank you for sending the updated pricing breakdown. This is helpful.
>
> I’ve noted the revised rates on my side. Before we close this review round, could you also let me know whether there is any final flexibility for a first-collaboration agency test rate?
>
> If not, no problem at all — I still wanted to check once more before we finish internal matching and shortlist decisions.
>
> Once we complete that review, I’ll come back with the most relevant confirmed opportunities.
>
> Best regards,  
> Annabel  
> Rockbase Agency

**When to switch away from this**

- 如果对方已经表现得非常 firm
- 或已经说明 prices are fixed
- 或你不打算再压了

这时应切到 `Scenario 7` 或 `Scenario 8`。

---

## Scenario 7 — P3 + Discounted / Flexible Quote

**Code idea**: `S7`

**When this applies**

- 对方已经给过折扣
- 或明确说对 first collab 可以灵活
- 或已经把 agency rate 放到桌上

**Operator goal**

- `G4 | 接受折扣价并保温`

**Best template direction**

- 对齐旧模板：`RQ3 | quoted_accept_discounted`

**Must say**

- acknowledge flexibility
- note discounted / adjusted pricing
- 保温，等待 matched brief

**Avoid**

- 继续反复压价
- 让对方觉得你还没看懂他已经让步

**Recommended draft**

> Hi,
>
> Thank you for sharing the adjusted rate for a first collaboration. I really appreciate the flexibility.
>
> I’ve noted everything on my side, and I do think there’s real potential for us to work together on the right AI / tech campaign.
>
> We may not move immediately from this thread, simply because the matching process can take a little time on our end, but when the right brief comes up, I’ll definitely come back to you.
>
> Thank you again for the time and openness. I’d honestly love to work with you on the right campaign.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 8 — Quoted, No More Negotiation For Now

**Code idea**: `S8`

**When this applies**

- 对方已给 usable rate
- 我方这轮不准备继续压价
- 目的是保温、保留 shortlist

**Operator goal**

- `G3 | 接受当前价格并保温`

**Best template direction**

- 对齐旧模板：`RQ2 | quoted_accept_standard`

**Must say**

- acknowledge 已收到价格
- note fit
- 说明 matching takes time

**Avoid**

- 假装马上推进
- 或完全不说明后续节奏

**Recommended draft**

> Hi,
>
> Thank you for sharing your rates. I really appreciate it.
>
> I’ve noted everything on my side, and I do think there’s real potential for us to work together on the right AI / tech campaign.
>
> We may not move immediately from this thread, simply because the matching process can take a little time on our end, but when the right brief comes up, I’ll definitely come back to you.
>
> Thank you again for the time and openness. I’d honestly love to work with you on the right campaign.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 9 — Follow-Up / Chase Message

**Code idea**: `S9`

**When this applies**

- 对方主动 follow up
- 问 `Any update?`
- 问 `Did you get a chance to review?`

**Operator goal**

- 先承接慢回复
- 再回到当前真实价格轮次

**Best practice**

这不是一个单独模板宇宙，而是：

- `Opening module` + 当前真实场景

最常用 opening：

> Hi,
>
> Thank you for following up, and apologies for the delay.

然后接：

- 如果对方已报价但你还想压价：接 `Scenario 5` 或 `Scenario 6`
- 如果对方已报价且你只想保温：接 `Scenario 8`
- 如果对方还没给价格：接 `Scenario 1 / 2 / 3 / 4`
- 如果对方是催回复且已报价：不要只道歉和保温，必须回到真实价格策略：
  - first quote：`N1` / `N2` / `N3`
  - second quote：`N6`
  - discount offered：`N7`
  - asks budget：`N5`

**Recommended draft for quoted follow-up**

> Hi,
>
> Thank you for following up, and apologies for the delay.
>
> I have your pricing noted on my side, and we are still matching the current briefs against audience fit, format, and budget, so I do not want to ask you to hold anything before we have a clear fit.
>
> Once we have a matching campaign, I will come back with the exact brief, timeline, deliverables, and budget range for your review.
>
> Best regards,  
> Annabel  
> Rockbase Agency

---

## Scenario 10 — Redirect / Admin / Contact Change

**Code idea**: `S10`

**When this applies**

- 助理接手
- 原联系人离职
- 让你联系新邮箱

**Operator goal**

- `G6 | 不进入标准 auto-reply`
- update contact

**Best template direction**

- 默认不 auto-draft
- 进入 manual handling / contact update

**Avoid**

- 对错误联系人继续套标准商务模板

**Action**

- 更新联系人
- 视情况重发或单独手工回复

---

## Scenario Mapping Back To Old Template Codes

- `S1` -> `RI1`
- `S2` -> `RI2`
- `S3` -> `RI3`
- `S4` -> `RI4`
- `S5` -> `RQ1`
- `S6` -> `RQ1` or `RQ2`
- `S7` -> `RQ3`
- `S8` -> `RQ2`
- `S9` -> depends on underlying real state
- `S10` -> `RX2` or manual handling

---

## Quick Operator Checklist

每次写 reply 前，先回答这 10 个问题：

1. 我看完整 thread 了吗？
2. 这是 `P0 / P1 / P2 / P3` 哪一档？
3. 对方当前意图是什么？
4. 我这一轮目标是索价、压价、接受、还是保温？
5. 这封邮件需要 `Sorry for the late reply` / `Thank you for following up` 吗？
6. 距离对方上一封邮件是否已经超过 `2` 天？如果是，我有没有加入更客气的 delay softener？
7. 我有没有把 quoted history 错写进 reply body？
8. 如果本轮目标是压价，我有没有至少使用一个 negotiation module，而不是只问 scope / stats？
9. 价格不高时，我是应该硬砍现金价，还是用 `N2 | package_value_expand` 争取更多交付？
10. 对方已经给折扣时，我有没有切到 `N7 | discounted_quote_hold`，避免继续机械压价？

如果第 2 和第 4 题答不清，就不要急着 auto-draft。
