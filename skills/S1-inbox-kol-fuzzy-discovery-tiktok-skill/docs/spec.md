---
tags: [spec, tiktok, kol, skill, discovery]
date: 2026-04-10
status: active
---

# S1 Inbox TikTok KOL Fuzzy Discovery Spec

## 0. Recommended Architecture Tree

与 YouTube skill 同构：`SKILL.md / WF_Int.md / WF / docs / specs / src / tests`

## 1. Background & Problem

TikTok 的核心难点不在后半段 workflow，而在 `L1` 的 search-first 热内容挖掘稳定性、anti-bot、session 和 proxy 成本。

这里的目标不是平台 discover 榜，而是：

- 用户给一个领域角度
- skill 搜大量高信号内容
- 再把背后的 creator 聚合出来

## 2. Target Positioning

它是 TikTok KOL 模糊发现 skill，不是 TikTok 全平台趋势产品。

## 3. User Inputs & Outputs

输入与共享 contract 相同，但 operator requirement 更重。

## 4. Core Workflow

1. Intake
2. Lock provider_plan
3. Run dual-channel L1
4. Aggregate matched content back to creators
5. Merge by `author_unique_id`
6. Enrich to L2
7. Score to L3
8. Export S2

## 5. Key Modules

- `ScrapeCreators` TikTok keyword search
- `ScrapeCreators` TikTok hashtag search
- `ScrapeCreators` TikTok search users / profile videos
- `TikTok-Api` account-first runtime
- profile lookup / user search
- blocker reporting
- heavier browser/session content collector
- escalation to `MediaCrawler`

## 6. What Is Shared

- layer meanings
- field taxonomy
- spec structure
- L2/L3/S2 output semantics

## 7. What Stays Platform-Specific In V1

- session/proxy requirements
- TikTok search/trending runtime
- author-level aggregation
- escalation path to browser/session collection

## 8. Decision Rules

- 默认 `dual_channel`
- `content-first` 当前默认入口应为 `ScrapeCreators`
- `account-first` 当前优先 `TikTok-Api` user lookup
- `TikTok-Api item search` 当前不应作为默认 `content-first`
- blocker 必须结构化输出
- 当 `content-first` 无法稳定返回 item/content rows 时，应升级到更重的 browser/session collector

## 9. Evaluation / Validation

- account-first yields creator rows with enough L2 fields
- content-first 必须返回真实内容证据行，不能只返回空响应或 blocker
- when blocked, result must explain what is missing

## 10. Output Contract

沿用 shared L1 minimum evidence fields。

## 11. Migration / Upgrade Path

- 先冻结当前已验证的 env / token / proxy
- `content-first` 默认切到 `ScrapeCreators`
- `account-first` 继续沿用 `TikTok-Api`
- `TikTok-Api` 保留为辅助/交叉验证入口
- 若 `ScrapeCreators` 质量不够，再转向更重的 browser/session collector 研究
- 不在 v1 抽 shared runtime

## 12. Acceptance Criteria

- 双通道 L1 明确
- blocker path 明确
- TikTok alias 定义完成
- downstream contract 与共享结构兼容

## 13. Next Steps

1. 保留当前已验证可用的 `ms_token + static proxy`
2. 用 `ScrapeCreators` 接 TikTok `content-first`
3. 用 `TikTok-Api` 继续承担 `account-first`
4. 用真实返回字段更新 `L1 field matrix`
5. 再评估 `MediaCrawler` escalation

## Appendix. Reference Projects & What To Borrow

- `ScrapeCreators`: current best default for TikTok `content-first`
- `davidteather/TikTok-Api`: verified for account-first / user search, not yet verified as stable content-first collector
- `NanmiCoder/MediaCrawler`: browser/session fallback pattern
- existing X skill: downstream workflow shape
