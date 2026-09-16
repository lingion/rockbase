---
name: s1-inbox-kol-fuzzy-discovery-tiktok-skill
description: 面向 Social Agency 的 TikTok KOL 模糊发现技能。默认采用 shared contract, separate runtime 架构，主流程为 L1 发现、L2 补全、L3 shortlist、S2 outreach export。
---

# S1 Inbox TikTok KOL Fuzzy Discovery Skill

本技能用于把一句模糊的 TikTok KOL 寻找需求，收口成一条可审计、可续跑、可交付的 `L1 -> L2 -> L3 -> S2` 工作流。

默认逻辑是：

`给一个领域角度 -> 搜大量高信号热视频 -> 聚合背后的 creator -> 进入 L2/L3/S2`

## 当前定位

- 这是 `3` 个新平台 skill 中的高摩擦平台
- 当前 spec 已 development-ready
- 但第一版 runtime 要故意收窄，不夸大 discover 稳定性

## 当前默认 L1 策略

- `dual_channel`
- `content-first`
  - 目标仍然是 search-first 的高信号内容搜索
  - 但 `TikTok-Api item search` 当前未验证为稳定主路径
- `account-first`
  - 当前已验证可用的是 `TikTok-Api` user/profile lookup
- fallback
  - 更重的 browser/session content collector
  - `MediaCrawler` 风格 path 仍保留为重要参考

## 先读什么

1. `BUILD_SPEC.md`
2. 本文件
3. `WF_Int.md`
4. `QUERY_LIBRARY.md`
5. `docs/spec.md`
6. `docs/l1-tool-research.md`
7. `docs/ms-token-setup.md`
8. `WF/L1-WF_tiktok_kol_discovery_csv.md`
9. `WF/Lx-Field-Matrix_tiktok_kol_csv.md`
10. `specs/_template.tiktok_kol_task.json`
11. `docs/operator-requirements.md`
12. `tests/README.md`

## 目录结构

```text
S1-inbox-kol-fuzzy-discovery-tiktok-skill/
├── SKILL.md
├── WF_Int.md
├── QUERY_LIBRARY.md
├── WF/
├── docs/
├── specs/
├── src/
└── tests/
```

## 执行原则

1. 明确标记 blocker，不假装 discover 全可用。
2. session / proxy requirement 是一等公民，不是隐藏实现细节。
3. 不因为高摩擦就放弃 shared contract。
4. 当前已冻结的认证层是 `skill-local ms_token + static proxy`，后续优先更换 collector，不优先重做认证层。
