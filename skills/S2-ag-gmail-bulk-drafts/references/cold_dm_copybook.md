# Cold DM Copybook

> 用途：集中管理 Cold DM 的模板、variant、固定语气和拼装规则。
> 这是一份策略资产库，不是执行 SOP。

## 1. Core Purpose

- 用于 X / Twitter 首次陌生私信
- 目标是先获得回应，再推进到 email / brief / rates
- 风格应短、自然、轻量，不像邮件
- 重点不是“一次讲完全部信息”，而是用最小阻力拿到下一步沟通机会

## 2. Messaging Principles

- 首句先让对方知道你是谁，但不要像正式 Email 开场一样沉重
- `Hook` 必须回答“为什么是你”，而不是泛泛夸赞
- 正文推进要分层：
  - `Open`
  - `Context Bridge`
  - `Intent Block`
  - `CTA`
- CTA 只保留一个主动作，不堆多个请求
- 默认不带链接、不带手机号、不带明显营销词

## 3. Core Structure

```text
Hi {Mail1_Greeting_Name},

{Open}

{Context Bridge}

{Intent Block}

{CTA}
```

规则：
- `Context Bridge` 常由 `Mail1_Hook` 驱动
- `Intent Block` 负责说明为什么现在联系对方
- `CTA` 负责把动作压缩成最轻的下一步
- 整体应控制在 DM 可读长度内，避免像邮件段落

## 4. Greeting Rule

- 真人名：直接叫名字
- 品牌 / 项目 / 组织：必要时可加 `Team`
- handle-like identity 若本身像个人品牌，可直接保留原名
- DM 比 Mail 更口语，但仍保持商务克制
- 宁可保守，也不要叫错名字

## 5. Angle Layer

这是过去 DM 资产里很有价值的一层，不必保留旧字段名，但策略上应保留。

常见 angle：
- `founder`
  - 适合创业、building in public、founder journey、brand-building 账号
- `builder`
  - 适合 dev tools、product build、software creation、maker 账号
- `operator`
  - 适合 growth、marketing、ops、ecom、business execution 账号
- `educator`
  - 适合教程、课程、解释型内容、专业教学账号
- `researcher`
  - 适合研究、science、robotics、frontier tech、deep analysis 账号
- `automation`
  - 适合 AI workflow、agents、automation、n8n、systems 账号
- `creator-tools`
  - 适合内容生产工具、design、creative workflow、creator systems 账号
- `ai-generalist`
  - 泛 AI / productivity / tech commentator

作用：
- angle 不必直接展示给对方
- 但它会影响：
  - 用哪类 `Open`
  - 用哪类 `Intent Block`
  - CTA 是偏“reply here”还是“continue over email”

## 6. Reusable Blocks

### 6.1 Open Blocks

#### O1 Rockbase Intro

- `I’m Annabel from Rockbase Agency.`
- 适用：
  - 想让对方知道是正式商务触达
  - 账号偏 founder / operator / educator

#### O2 Quick Note

- `Quick note — I’m Annabel, and I help AI products work with the right creators on X and beyond.`
- 适用：
  - 想降低压迫感
  - 账号偏 builder / creator-tools / ai-generalist

#### O3 Light Relevance Intro

- `I’m Annabel from Rockbase, and your content came to mind for a campaign lane we’re building out.`
- 适用：
  - 已有较强匹配证据
  - 想快速进入 relevance

### 6.2 Context Bridge Blocks

这里通常围绕 `Mail1_Hook` 做不同衔接。

#### C1 Direct Hook

- `{Mail1_Hook}`
- 适用：
  - Hook 已经够自然、够完整

#### C2 Reason Bridge

- `The reason I wanted to reach out is simple: {hook_lower}`
- 适用：
  - 想让商务触达显得更自然

#### C3 Audience Bridge

- `What stood out to me is that {hook_lower}`
- 适用：
  - 想强调 audience / content fit

### 6.3 Intent Blocks

#### I1 Soft Partnership Fit

- `We work with AI and tech products on creator partnerships, and I thought there could be a good fit here.`
- 适用：
  - 默认通用版

#### I2 Early Campaign Radar

- `We’re putting together a small group of creators for upcoming AI campaigns, and I wanted to put this on your radar early.`
- 适用：
  - 需要制造“现在联系”的合理性

#### I3 Fit-First Intent

- `Given your content style and audience, this feels like a stronger fit than a typical broad creator outreach.`
- 适用：
  - 内容证据强
  - 想强调不是 mass blast

### 6.4 CTA Blocks

#### T1 Reply Here

- `If you’re open, happy to share a quick brief here.`
- 适用：
  - 最轻 CTA

#### T2 Email Bridge

- `If this sounds relevant, I’d love to continue over email and send a brief.`
- 适用：
  - 目标是从 DM 平滑切到 email

#### T3 Soft Rates Bridge

- `If there’s interest on your side, we can also move to email and talk through format, fit, and rates.`
- 适用：
  - 已进入更深一层意向，但仍不宜直接压价

## 7. Variant Matrix

### A1_soft_intro

- 用途：首次破冰
- 结构建议：
  - `O2 + C1/C2 + I1 + T1`
- 风格：短、轻、自然
- CTA：先拿回应
- 不适合：
  - 你已经非常明确要切 email

### A2_soft_email_bridge

- 用途：目标是平滑切到 email
- 结构建议：
  - `O1/O2 + C2 + I2 + T2`
- 风格：先建立相关性，再问是否方便邮件沟通
- 适合：
  - creator 已有公开商务邮箱
  - 你想把 DM 只当作门口

### B1_creator_fit_soft

- 用途：已有较强内容匹配证据
- 结构建议：
  - `O3 + C3 + I3 + T2`
- 风格：强调内容 fit，但不强推
- 适合：
  - founder / educator / operator 这类内容逻辑明确的账号

### B2_creator_fit_direct

- 用途：匹配证据明确，希望更快推进
- 结构建议：
  - `O1/O3 + C2/C3 + I3 + T3`
- 风格：更直接，但仍保留 DM 的轻量感
- 不适合：
  - 初次接触且证据很弱的账号

## 8. Assembly Rules

- `Mail1_Hook` 必须基于账号资料
- 正文必须保留 DM 节奏，不允许像邮件一样大段展开
- 不默认使用外链
- 不默认使用手机号
- 不默认使用重营销词
- 同一条 DM 只保留一个主 CTA
- 默认顺序：
  - 自我介绍
  - 为什么找你
  - 为什么是现在
  - 最轻下一步

## 9. Do / Don't

Do:
- 快速说明为什么找到对方
- 让对方知道这是合作触达
- 给出轻量 next step
- 让 DM 像真人发出的商务消息

Don't:
- 上来发超长段落
- 复制邮件正文到 DM
- 初次就塞外链、手机号、重营销词
- 连续多个 CTA 堆叠
- 让语气像粉丝私信
- 一上来就谈报价和执行细节

## 10. Risk Language

谨慎使用：
- `limited spots`
- `exclusive`
- `launching next week`
- `WhatsApp me`
- 任何明显 pushy 的营销表达

原因：
- 这些内容不是绝对不能用
- 但非常容易让 DM 像营销脚本，而不是正常商务触达

## 11. Good Examples

### Example A1

```text
Hi {Mail1_Greeting_Name},

Quick note — I’m Annabel, and I help AI products work with the right creators on X and beyond.

{Mail1_Hook}

We work with AI and tech products on creator partnerships, and I thought there could be a good fit here.

If you’re open, happy to share a quick brief here.
```

### Example A2

```text
Hi {Mail1_Greeting_Name},

I’m Annabel from Rockbase Agency.

The reason I wanted to reach out is simple: {hook_lower}

We’re putting together a small group of creators for upcoming AI campaigns, and I wanted to put this on your radar early.

If this sounds relevant, I’d love to continue over email and send a brief.
```

### Example B1

```text
Hi {Mail1_Greeting_Name},

I’m Annabel from Rockbase, and your content came to mind for a campaign lane we’re building out.

What stood out to me is that {hook_lower}

Given your content style and audience, this feels like a stronger fit than a typical broad creator outreach.

If this sounds relevant, I’d love to continue over email and send a brief.
```

## 12. Bad Example

```text
Hi creator,

We are launching an amazing AI product next week with limited spots and think you are perfect. Please send your email and WhatsApp ASAP and I will share all details, links, pricing, and deadlines.
```

问题：
- 太像 mass blast
- 没有真实 `Hook`
- CTA 过多
- 风控风险高
