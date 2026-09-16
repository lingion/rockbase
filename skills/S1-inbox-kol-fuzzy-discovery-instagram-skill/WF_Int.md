---
description: "[Workflow] Instagram KOL discovery intake workflow."
---

# WF_Int

## Intake 必问字段

- `platform`: 固定为 `instagram`
- `topic_query`
- `l1_mode`
- `search_queries`
- `seed_profiles`
- `operator_requirements`
- `provider_plan`

## 默认答案

- `l1_mode`: `dual_channel`
- `content_first.primary`: `instagram.scrapecreators_reels_search`
- `account_first.primary`: `instagram.scrapecreators_profile_lookup`
- `fallback`: `instagram.instaloader_session_backed_profile_or_hashtag`

## 当前成熟执行顺序

1. Intake task spec
2. 锁定 query 组
3. 跑 `ScrapeCreators reels search`
4. 合并多轮 L1，形成 `L1 unified / candidates`
5. `views gate`
6. 在 `L2` 前先查 `docs/instagram_kol_discovery_master.csv`
7. 仅对 net-new creator 跑 `ScrapeCreators profile`
8. `followers gate`
9. 对 shortlist 跑 contact page augment
10. 进入 `L3 shortlist`
11. `L3 -> S2 base mapping`
12. `S2 merge`
13. 机构号规则：`L3` 负责识别风险；`S2 export` 正式删除明显机构号；`merge` 再兜底一次

## 路径规则

- 过程文件统一放到：
  - `.../Social Agency/workbench/{YYYY-MM-DD}/Instagram/`
- skill 内 `deliverables/` 只放唯一正式 `merged_final.csv`
- batch 级 `S2` 一律只放 `workbench/`
- 不把 raw / runlog / audit / shortlist / review / test 放进 `deliverables/`
- `master` 固定放在：
  - `docs/instagram_kol_discovery_master.csv`

## Deliverable Gate

- `Instagram` 的正式 deliverable 默认不得包含明显机构号 / 媒体号 / 品牌号
- `run_l3_to_s2_mapping.py` 必须先执行一次 deliverable gate
- `run_merge_s2_deliverables.py` 必须再次执行同样规则兜底
- `review` 不等于可进入 deliverable；命中机构号规则的行即使是 `review` 也不得进入 `S2 final`
