# REFERENCE — Price Recovery Reply Framework

日期：2026-05-20

## Purpose

这份 reference 只服务于：

- `WF-1-Price-Recovery-Default.md`

它的目标很单一：

> 拿回 usable quote，并把价格结构拉到可写回本地的程度。

它不是独立 workflow。

它是：

- `WF-1-Price-Recovery-Default.md` 的 reply judgment reference
- 用来给 `WF-1` 补 scenario card 和 wording 原则

换句话说：

- capture
- resume
- dedupe
- writeback-first

这些执行顺序以 `WF-1` 正文为准；

这份 reference 只补：

- 怎么判断 reply angle
- 不同 `WF-1` 类型该怎么回

## Core Principles

1. 默认不压价。
2. 默认先把价格拿完整。
3. 如果对方先问我们是谁，可以回答，但回答必须最小充分。
4. 每一封回复都要把对话尽量拉回价格。
5. 但不是所有 thread 都要继续回，先判断 `need reply` 和 `round depth`。
6. 默认不要主动提 `paid whitelisting / exclusivity`，除非对方先问或当前 thread 明确需要。
7. 平台默认不要收得过窄；只要对方有多个相关平台，优先允许其一起报最相关平台价格，尤其不要漏掉 `YouTube`。
8. 正文默认保持干净，不手动带上旧邮件引用或 `On ... wrote:` 历史头。
9. 这份 reference 不替代 `WF-1` 的 latest pointer / checkpoint / dedupe 规则。

## Need-Reply Gate

### 通常要回

- 一封 outbound 后对方第一次回信
- 第二个来回以内，价格还没拿完整
- 对方最新 inbound 在问 scope / budget / brief / usage
- 已谈到一定程度，但对方在追 `any update`

### 通常先不回

- 最新整体消息已经是我方
- 对方只是发来价格或 kit，没有新的 ask
- OOO / bounce / admin routing
- 8-9 轮以上且没有新的问题、没有新的缺口、没有催进度

## Round-Depth Rule

- `R1`：1 个来回或刚进入第 2 个来回，默认继续
- `R2`：2-4 个来回，继续但目标必须单一
- `R3`：5 轮以上，先看 thread 当前卡点
- `R4`：8-9 轮以上，默认不自动推进，除非是 blocking ask 或 `any update`

## Main Scenarios

### S1. Interested But No Price

触发：

- 有兴趣
- 无 usable quote

回复目标：

- 直接把 thread 推到报价

标准问法：

- `Could you share your current rates for the most relevant formats?`
- `If available, dedicated, integration, and short-form options across your most relevant platforms would be especially helpful.`

### S2. Media Kit Without Clear Price

触发：

- 发了 media kit / doc / link
- 正文没给清晰价格

回复目标：

- 让对方确认当前有效价格

标准问法：

- `Could you confirm the most relevant current rates for this type of collaboration?`

### S3. Vague Price Range Only

触发：

- 只有范围
- 没有明确数字

回复目标：

- 把价格具体化

标准问法：

- `Could you share the clearest current numbers you would want us to compare on our side?`

### S4. Bundle Price Without Breakdown

触发：

- 只有 bundle
- 没有单项

回复目标：

- 补 breakdown

标准问法：

- `Could you also break that out into the most relevant individual options?`

### S5. Missing Usage / Scope Detail

触发：

- 有价格
- 但 usage / repost / cross-post / scope 不清

回复目标：

- 把 usable quote 补完整

标准问法：

- `Does that rate already include any usage or repost support, or would that be separate?`

### S6. Asks About Our Company / Brand / Brief

触发：

- 先问 Rockbase / brand / campaign

回复目标：

- 最小充分回答后，立刻回到价格

标准问法：

- `We are Rockbase Agency, and we mainly review AI / software / workflow collaborations.`
- `It would also help to understand your current rates and available formats across the most relevant platforms on your side.`

### S10. Quote Received And Confirm Only

触发：

- 对方已经给出 usable quote
- 价格已能写回本地
- 当前不需要继续压价
- 当前也不需要继续 broad re-quote

回复目标：

- 确认已收到
- 保持线程温度
- 不复述具体价格
- 不加入价格分析

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

### S7. Asks About Budget First

触发：

- 对方先套 budget

回复目标：

- 不亮底牌
- 先让对方给 creator-side pricing

标准问法：

- `We are still comparing creator fit and current rate structures first, so it would help to see your current rates or strongest starting options.`

### S8. Wants Full Brief Before Pricing

触发：

- 先要 full brief

回复目标：

- 给最小 brief context
- 仍然先拿价格

标准问法：

- `What I can share for now is that the category is AI / software rather than a broad consumer campaign.`
- `Based on that direction, could you share the most relevant current rates you would want us to review first?`

### S9. Agreed Direction, Waiting On Us, They Ask Any Update

触发：

- 已经谈过几轮
- 最新 inbound 是 follow-up / `any update`
- 当前不是继续索价，而是我方内部待确认

回复目标：

- 安抚
- 承接
- 维持 thread 温度

标准问法：

- `Thank you for following up, and sorry for the delay on our side.`
- `We are still reviewing the next-step fit internally, but I did not want to leave you without an update.`
- `I will come back to you as soon as I have a firmer next step to share.`

## Minimal Company Context

当对方问我们是谁时，优先使用这种量级的信息：

- Rockbase Agency
- 我们主要看 AI / software / workflow 类合作
- 当前在做 creator fit review / shortlist / first-test evaluation
- 默认不主动补充 `paid whitelisting / exclusivity`
- 默认不把平台先缩成只有 `TikTok / Instagram`，如果对方有 `YouTube` 等相关平台，也可以一起报价

避免：

- 一上来给完整客户清单
- 一上来给完整 brief
- 一上来进入压价语境

## Ask Blocks

### Block A. Request Current Rates

重点词：

- current rates
- best rates
- available formats
- dedicated / integration / shorts

### Block B. Request Breakdown

重点词：

- breakdown
- starter option
- single format
- usage included or separate

### Block C. Redirect Back To Price

适用于先答了对方问题后，马上把 thread 拉回价格。

## Do Not Say

在 `WF-1` 里，默认避免这些方向：

- 不先压价
- 不先报预算
- 不先发完整 brief
- 不把模糊价格直接当 final
- 不发只有礼貌但没有推进动作的保温信
- 不把 `any update` 误判成“不需要回复”
- 不把 8-9 轮以上的成熟线程继续当成普通追价线程
- 不把上一封邮件正文手动复制进这封回复
- 不在正文里写 `On Tue ... wrote:` 这种引用头
- 不在确认型邮件里复述具体报价
- 不在确认型邮件里加入价格分析

## Format Guardrail

默认使用干净的 top-posting：

- 新正文单独成立
- 结尾在签名处自然结束
- 不手动附带 quoted history

如果 Gmail 客户端在 threaded reply 中自动显示历史引用，视为客户端层行为，不算正文的一部分；但模型生成内容本身不能包含那段引用。

## North Star

`WF-1` 的 north star 不是“写一封看起来很会聊的邮件”。

而是：

> 每一封发出去，都要让 thread 更接近 `price writeback ready`。

## Self-Check

正文完成后必须确认：

- 这封的主目标是不是拿价
- 有没有不必要地提前进入压价
- 对方如果问了我们背景，是否只给了最小充分回答
- 这封发出去后，是否更有利于本地 writeback
- 当前场景是否已明确落在 `S1-S9` 之一
- 当前轮次是否已明确判断为 `R1 / R2 / R3 / R4`
