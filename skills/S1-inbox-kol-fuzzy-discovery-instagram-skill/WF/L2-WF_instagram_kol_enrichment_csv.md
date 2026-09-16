---
description: "[Workflow] Instagram KOL Layer2 enrichment workflow."
---

# L2-WF_instagram_kol_enrichment_csv

## L2 新增字段

- `bio`
- `followers_count`
- `following_count`
- `profile_url`
- `external_links`
- `contact_signals`
- `recent_contents`
- `enrichment_provider`
- `contact_value`
- `contact_note`

## 当前重点

- 先和 `docs/instagram_kol_discovery_master.csv` 去重
- 再调 `ScrapeCreators /v1/instagram/profile`
- `followers_count >= 2000` 才进入正式 shortlist
- 联系方式来源优先级固定为：
  - `business_email`
  - `bio regex`
  - `external_links -> contact page crawl`

## workbench 路径

- `L2 enriched / shortlist / master audit / runlog`
- 统一放在：
  - `.../Social Agency/workbench/{YYYY-MM-DD}/Instagram/`
