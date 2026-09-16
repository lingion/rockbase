---
description: "[Workflow] TikTok KOL Layer3 selection workflow."
---

# L3-WF_tiktok_kol_selection_csv

## 默认判断维度

- `topic_match_score`
- `profile_match_score`
- `activity_score`
- `contactability_score`
- `overall_score`
- `recommended_action`

## 保守规则

- content evidence 弱则最多 `review`
- session 不稳不影响评分，但影响可信度备注
- `followers_count < 3000` 默认不进正式 keep
- `bio` 太空、联系线索太弱时可降为 `review`
- `contact_value` 为空不一定 drop，但会拉低优先级
- 机构号、媒体号、品牌号默认不能直接 `keep`
- 命中 `official / team / company / media / agency / shop / wholesale / supplier` 等明显组织信号时，至少进 `review`
- `300k+ followers` 视为 `big account`，即使基础分数达标也要二次复核是否过分一线
- `1M+ followers` 且同时存在组织信号时，默认优先 `drop`
- 有明确个人品牌证据（如 `founder / creator / realtor / recruiter / educator`）时，可覆盖部分模糊组织信号

## 机构号删除规范

- `L3` 负责识别和打标，不是最终删除出口
- 命中 `org_keyword:*`、`llm_entity_type = org_or_media`、或 `llm_decision = drop` 且伴随组织信号时，应视为机构号候选
- 这类行即使保留在 `review`，也不得进入正式 `S2 deliverable`
- 正式删除发生在 `run_l3_to_s2_mapping.py`
- `run_merge_s2_deliverables.py` 必须再次执行机构号兜底过滤

## 当前 L3 额外输出字段

- `account_risk_flags`
- `needs_llm_review`
- `llm_review_status`
- `llm_entity_type`
- `llm_decision`
- `script_decision`
- `final_decision`
