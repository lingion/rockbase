---
description: "[Workflow] YouTube KOL Layer3 selection workflow."
---

# L3-WF_youtube_kol_selection_csv

## 核心目标

把 `L2` 的 creator table 变成 `keep / drop` shortlist，并把机构号筛选交给 LLM 自动完成。

## 默认判断维度

- `followers_count`
- `max_views`
- `topic_match_score`
- `profile_match_score`
- `activity_score`
- `overall_score`
- `recommended_action`

## 默认保守规则

- `followers_count < 1000` 默认不能直接进入 `keep`
- 没有主题证据，不进入 `keep`
- 联系方式缺失不直接 drop，但会降低优先级
- 机构号、媒体号、品牌号由 LLM 直接判为 `drop`

## Deliverable Gate

- `L3` 负责把结构化证据喂给 LLM，不再输出人工 `review` 流
- `LLM` 负责最终 `keep / drop`
- `ambiguous` 默认按 `drop` 处理，不回到人工 review
- `run_l3_to_s2_mapping.py` 必须执行正式拦截
- `run_merge_s2_deliverables.py` 必须再次执行同样规则兜底
- 默认只有 `final_decision = keep` 且 `llm_decision = keep` 的行可以进入 `S2`

## 证据来源

`L3` 不重新搜索内容，而是只使用 `L1 / L2` 已经落盘的证据：

- `L1` 的 `content_title / theme_text / sample_contents / tags`
- `L1` 的 `view_count / max_views`
- `L2` 的 `bio / followers_count / external_links / contact_signals`

这层的核心目标是把这些证据变成：

- `topic_match_score`
- `profile_match_score`
- `activity_score`
- `overall_score`
- `recommended_action`
- `decision_reason`
