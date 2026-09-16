---
description: "[Workflow] Map Instagram L3 shortlist to S2 outreach export."
---

# L3-WF_to-S2-cold-outreach-mapping

保留：

- `creator_handle`
- `display_name`
- `platform`
- `profile_url`
- `contact_value`
- `contact_note`
- `external_links`
- `decision_reason`

联系方式字段规则必须写死：

- `联系方式 = email only`
- `联系方式备注 = email source / method`
- `外链__平台抓取 = website / link-in-bio / socials`
- `contact_signals` 不能直接映射到 `联系方式`

## 当前输出位置

- `S2 base` 先写入：
  - `.../Social Agency/workbench/{YYYY-MM-DD}/Instagram/`
- 再镜像到 skill 内：
  - `deliverables/{YYYY-MM-DD}/`

## Mail1 字段进入时点

参考 X 的成熟 workflow，Instagram 也沿用同一规则：

- `Mail1` 列不在 `L2` 或 `L3` 出现
- 从 `L3 -> S2 base mapping` 开始，CSV 必须预留：
  - `Mail1发出状态`
  - `Mail1_Hook`
  - `Mail1_Greeting_Name`
  - `Mail1_Subject`
  - `Mail1_Content V1`
  - `Mail1_Content V2`
- `S2 merge` 只保留这些列，不负责首次建列
- merge 后的 `DM fill / 3.2` 才真正填文案
