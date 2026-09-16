---
name: s1-inbox-kol-fuzzy-discovery-instagram-skill
description: 面向 Social Agency 的 Instagram KOL 模糊发现技能。默认采用 content-first 的 ScrapeCreators Reels Search，主流程为 L1 搜内容、L2 补全、L3 shortlist、S2 outreach export。
---

# S1 Inbox Instagram KOL Fuzzy Discovery Skill

本技能用于把一句模糊的 Instagram KOL 寻找需求，收口成一条可审计、可续跑、可交付的 `L1 -> L2 -> L3 -> S2` 工作流。

默认逻辑是：

`给一个领域角度 -> 搜大量高信号内容 -> 聚合背后的 creator -> 进入 L2/L3/S2`

## 当前定位

- Instagram 第一版是保守设计
- 重点不是“全站热榜”，而是“高信号 hashtag/topic content -> creator”
- shared contract 与其他平台保持一致

## 当前默认 L1 策略

- `dual_channel`
- `content-first`
  - 主路径是 `ScrapeCreators /v2/instagram/reels/search`
  - 先从 keyword content 搜起，再聚合回 creator
- `account-first`
  - `ScrapeCreators /v1/instagram/profile`
  - `Instaloader` session-backed profile / hashtag 作为补充线
- fallback
  - later browser/session assisted path

## 先读什么

1. `BUILD_SPEC.md`
2. 本文件
3. `WF_Int.md`
4. `QUERY_LIBRARY.md`
5. `docs/spec.md`
6. `WF/L1-WF_instagram_kol_discovery_csv.md`
7. `WF/Lx-Field-Matrix_instagram_kol_csv.md`
8. `specs/_template.instagram_kol_task.json`
9. `docs/operator-requirements.md`

## 目录结构

```text
S1-inbox-kol-fuzzy-discovery-instagram-skill/
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

1. `workbench` 过程文件统一进项目级 `Social Agency/workbench/{YYYY-MM-DD}/Instagram/`。
2. `deliverables` 只放 skill 内最终交付 CSV。
3. `master` 固定放在 `docs/instagram_kol_discovery_master.csv`，并在 `L2` 前去重。
4. 不把 hashtag / reels hit 假装成 Instagram 全站 trending。
5. `联系方式 = email only`，`联系方式备注 = email 获取方法`。
