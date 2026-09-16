# Phase 2 Reply Templates

## Purpose

This is the shared reply template library for all `M1 / M2 / M3` follow-up drafting.

The template system is shared across waves.
Do not maintain separate template universes for `Mail2` and `Mail3`.

## Storage Rule

In the table, the template field should primarily store:

```text
RQ2 | quoted_accept_standard
```

The wording lives here.

## Default Greeting

All templates default to:

```text
Hi,
```

No `Greeting_Name` dependency is required.

## Code Table

| 编号 | English | 中文解释 |
| --- | --- | --- |
| `RQ1` | `quoted_send_details` | 已拿到报价，但当前仍希望继续压价、继续试探 agency rate |
| `RQ2` | `quoted_accept_standard` | 我方接受对方当前报价，即使没有降价，也先保留合作并等待合适项目推进 |
| `RQ3` | `quoted_accept_discounted` | 我方接受对方已经给出的折扣价 / 首次合作优惠价 |
| `RI1` | `interested_request_rate` | 对方有兴趣，但还没有给出可用报价，需要继续索要 rate |
| `RI2` | `interested_send_details_no_price` | 对方发了 media kit / details，但仍未给出清晰价格 |
| `RI3` | `ask_budget_first` | 对方先问我们的预算 / offer |
| `RI4` | `verification_or_brief_gate` | 对方要求先验证身份、先看 brief 或先看 campaign info |
| `RX1` | `no_reply_decline` | 对方明确不合作或当前无需继续回复 |
| `RX2` | `manual_review_required` | 信息混杂或判断不稳，需要人工审核 |

## RQ Templates

### `RQ1 | quoted_send_details`

Use when:

- creator already quoted
- we still want a better first-test / agency rate
- reply should keep the relationship warm while pushing for one more improvement

```text
Hi,

Thank you for sharing your rates and the additional details.

We do see a strong fit with the types of AI / tech campaigns we are currently reviewing. For first-time collaborations, our clients usually begin with tighter test budgets before expanding into larger placements.

If there is any flexibility for an initial agency test, we would be glad to review:
- your best dedicated rate
- your best integration rate
- any first-collaboration or agency rate you may be open to

Once we complete this round of internal review, we will follow up with the most relevant creators for confirmed briefs.

Best regards,
Annabel
Rockbase Agency
```

### `RQ2 | quoted_accept_standard`

Use when:

- creator has given a usable rate
- no discount is required for now
- we want to acknowledge the quote and keep the creator warm for upcoming briefs
- do not restate the exact numbers in the reply
- do not add price analysis in the reply

```text
Hi,

Thank you, that is very helpful.

I’ve noted this on my side and will keep it in our current review.

If there’s a strong fit for the next round, I’ll follow up with the relevant campaign context and next step.

Best regards,
Annabel
Rockbase Agency
```

### `RQ3 | quoted_accept_discounted`

Use when:

- creator has already offered a discounted / introductory rate
- we accept that rate as workable
- we want to hold warm until the matching brief is ready
- do not restate the exact numbers in the reply
- do not add price analysis in the reply

```text
Hi,

Thank you, that is very helpful.

I’ve noted this on my side and will keep it in our current review.

If there’s a strong fit for the next round, I’ll follow up with the relevant campaign context and next step.

Best regards,
Annabel
Rockbase Agency
```

## RI Templates

### `RI1 | interested_request_rate`

Use when:

- creator is interested
- but has not yet given a usable rate

```text
Hi,

Thank you for your interest.

To help us assess fit internally, could you please share your current rates for:
- a dedicated video
- a sponsored integration
- any other format you would recommend for a first collaboration

Once we complete this round of evaluation, we will follow up with the most relevant creators for confirmed briefs.

Best regards,
Annabel
Rockbase Agency
```

### `RI2 | interested_send_details_no_price`

Use when:

- creator sent media kit / links / audience info
- but still did not provide a usable rate

```text
Hi,

Thank you for sending the additional details. We’ve received them on our side.

To help us continue the review efficiently, could you also share your current rates for the formats you would recommend for a first collaboration, especially:
- dedicated video
- sponsored integration
- short-form placement, if applicable

Once we complete this review round, we will follow up with the best-fitting creators for confirmed opportunities.

Best regards,
Annabel
Rockbase Agency
```

### `RI3 | ask_budget_first`

Use when:

- creator asks our budget first

```text
Hi,

Thank you for your reply.

Budget can vary depending on format, deliverables, and campaign fit, so at this stage we are first mapping creator rates before locking final allocations.

If possible, please share your standard starting rates for:
- a dedicated video
- a sponsored integration
- short-form placement, if applicable

That will help us assess fit internally and decide whether to move forward with a more detailed brief.

Best regards,
Annabel
Rockbase Agency
```

### `RI4 | verification_or_brief_gate`

Use when:

- creator asks for verification
- or asks for brief / campaign details first

```text
Hi,

Thank you for your reply, and that makes complete sense.

For now, I’d prefer not to send over partial materials too early while we’re still narrowing campaigns internally. I think it would be more useful to come back to you once I have a clearer fit and more concrete context to share.

If useful for our internal review in the meantime, you’re also very welcome to share your current rates for the formats you’d usually recommend.

I really appreciate your time, and I hope we get the chance to pick this up again when the right brief comes through.

Best regards,
Annabel
Rockbase Agency
```

## RX Templates

### `RX1 | no_reply_decline`

Use when:

- creator clearly declines
- or no useful reply should be sent

Action:

- do not draft

### `RX2 | manual_review_required`

Use when:

- confidence is not high enough
- reply intent is mixed
- operator should decide manually

Action:

- do not auto-draft
- keep the template field as:

```text
RX2 | manual_review_required
```
