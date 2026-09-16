---
tags: [spec, instagram, kol, skill, discovery]
date: 2026-04-10
status: active
---

# S1 Inbox Instagram KOL Fuzzy Discovery Spec

## 0. Recommended Architecture Tree

与 YouTube / TikTok skill 同构：`SKILL.md / WF_Int.md / WF / docs / specs / src / tests`

## 1. Background & Problem

Instagram 的最大难点是缺乏 clean 的全站 hot feed。第一版必须把“search-first 的高信号 hashtag/topic content”与“平台级 trending”严格区分。

这里的主逻辑仍然是：

- 用户给一个领域角度
- skill 搜大量高信号内容
- 再把背后的 creator 聚合出来

## 2. Target Positioning

它是 Instagram KOL 模糊发现 skill，不是 Instagram 趋势榜聚合器。

## 3. User Inputs & Outputs

输入与共享 contract 一致，但当前默认 runtime 已更新为：

- `content-first`: `ScrapeCreators /v2/instagram/reels/search`
- `account-first`: `ScrapeCreators /v1/instagram/profile`
- `instaloader`: session-backed 补充线，不再是默认主路径

## 4. Core Workflow

1. Intake
2. Lock provider_plan
3. Run dual-channel L1
4. Aggregate matched content back to creators
5. Merge by `username`
6. `views gate`
7. Check `master`
8. Enrich to L2
7. Score to L3
8. Export S2

## 5. Key Modules

- `ScrapeCreators reels search`
- `ScrapeCreators profile`
- session-backed `Instaloader`
- high-signal content aggregation
- honest fallback handling

## 6. What Is Shared

- layer meanings
- field taxonomy
- spec structure
- L2/L3/S2 semantics

## 7. What Stays Platform-Specific In V1

- reels/topic-first L1
- `username` / `full_name` aliasing
- session-backed operator requirements
- profile/link extraction path
- `business_email -> bio regex -> contact crawl` 的 email 优先级

## 8. Decision Rules

- 默认 `dual_channel`
- `content-first` 默认走 `ScrapeCreators reels search`
- `account-first` 默认走 `ScrapeCreators profile`
- `Instaloader` 当前只作为 session-backed 补充线
- 不把 weak public probing 当成强 discover 成功
- `L2` 前必须查 `master`
- `联系方式` 只能映射 email

## 9. Evaluation / Validation

- reels/topic results can aggregate to creators
- weak global discover fails safely
- account-first profile lookup can carry enough fields into L2
- `business_email` 命中优先于 bio regex
- 项目级 `workbench/{YYYY-MM-DD}/Instagram/` 路由正确

## 10. Output Contract

沿用 shared L1 minimum evidence fields。

## 11. Migration / Upgrade Path

- 先用 `ScrapeCreators` 跑通 reels/profile 路线
- 再把 `Instaloader` 补成更稳的 session-backed hashtag/profile 路线
- 再评估 browser/session assisted fallback
- 暂不抽 shared runtime

## 12. Acceptance Criteria

- 双通道 L1 明确
- Instagram-specific limitation 写清楚
- alias 完整
- downstream shared contract 保持一致

## 13. Next Steps

1. 默认先用 `ScrapeCreators /v2/instagram/reels/search` 跑 `keyword content-first`
2. `L2` 前先和 `docs/instagram_kol_discovery_master.csv` 去重
3. `instaloader` 仅在 session 稳定时作为补充线
4. 再决定 browser-assisted fallback

## Appendix. Reference Projects & What To Borrow

- `instaloader`: hashtag/profile runtime
- `ScrapeCreators reels search`: 当前已验证可用的 keyword content-first 主入口
- existing X skill: downstream workflow shape
