---
description: "[Workflow] X KOL Layer2 补全层 CSV 工作流 | 目标：把 Layer1 candidates 升级成 enriched profile CSV。"
---

# L2-WF_x_kol_enrichment_csv

> 用途：把 `Layer1 candidates CSV` 升级成一张真正可判断的 `Layer2 enriched CSV`。

## 一、核心目标

`Layer2` 只负责一件事：补数。

这层不负责模糊找人。  
它要做的是：把 `Layer1` 的候选账号，补成标准化 profile object，并先给出一版保守的内部优先级字段。

当前执行版默认链路：

- `ScrapeCreators Twitter profile`

增强补全链路：

- `Scweet user-info`
- `twscrape user lookup`

失败 fallback：

- `Scweet`
- `twscrape`
- `OmniChrome`

## 二、输入与输出

### 输入 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L1_candidates_batch1_{YYYY-MM-DD}.csv`

### 主输出 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L2_enriched_batch1_{YYYY-MM-DD}.csv`

### 辅助文件

- `workbench/{YYYY-MM-DD}/x_kol_L2_raw_batch1_{YYYY-MM-DD}.json`
- `workbench/{YYYY-MM-DD}/x_kol_L2_contact_stub_batch1_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/x_kol_L2_runlog_batch1_{YYYY-MM-DD}.json`
- `workbench/{YYYY-MM-DD}/x_kol_L2_master_audit_batch1_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/x_kol_L2_master_audit_batch1_{YYYY-MM-DD}.json`

规则：

- 主进度看 `enriched CSV`
- 联系方式和外链线索单独落 `contact stub CSV`
- 原始 API payload 只做审计和 debug
- `master audit` 专门解释这批人为什么进入或被拦截
- 同一天如有第二批、第三批，文件名依次改成 `batch2 / batch3`

当前免费版默认准入门槛：

- 只有 `max_views >= 5000` 的账号，才进入 `Layer2` profile enrichment
- `max_views < 5000` 的账号保留在 `L1`，但默认不调用 `ScrapeCreators Twitter profile`
- 命中 `discovery master` 的账号一律视为老人，本批 `L2` 不再复用、不再刷新，只拦截
- 因此当前批次的 `Layer2 enriched CSV` 只代表“本批新进入 Layer2 的账号”

## 三、CSV 字段契约

`Layer2 enriched CSV` 应在保留 `Layer1` 主键与发现信号的基础上，新增这些字段：

| 字段 | 说明 |
| :--- | :--- |
| `username` | 主键，继承自 Layer1 |
| `display_name` | 显示名 |
| `bio` | 标准化简介 |
| `location_raw` | 原始 location 字段 |
| `followers_count` | 粉丝数 |
| `following_count` | 关注数 |
| `tweet_count` | 命中 tweet 数，继续保留 |
| `statuses_count` | 总发帖数 |
| `verified` | 是否官方认证 |
| `blue_verified` | 是否蓝标 |
| `matched_queries` | 保留 Layer1 发现依据 |
| `sample_posts` | 保留 Layer1 样例帖子 |
| `top_tweet_url` | 保留最强发现链接 |
| `profile_url` | 账号主页链接 |
| `source_tweet_ids` | 保留 Layer1 证据链 |
| `provider_source` | Layer1 来源 |
| `enrichment_provider` | 当前补全来源 |
| `layer2_eligible` | 是否通过 Layer2 views 准入门槛 |
| `layer2_skip_reason` | 若未进入 Layer2，这里写明跳过原因 |

可选增强字段：

- `recent_tweets`
- `external_links`
- `contact_signals`
- `profile_data_status`
- `needs_enhanced_enrichment`
- `enrichment_status`
- `enrichment_error`

## 四、升级规则

1. 必须保留 `Layer1` 的发现字段，不能因为补数把发现证据丢掉。
2. `Layer2` 的一行仍然代表一个账号。
3. 补全失败的账号不能直接丢弃，必须留下并标注状态。
4. 当前免费版默认先做 `views gate`，只有 `max_views >= 5000` 的账号才真正进入 profile lookup。
5. `views gate` 之后必须先查 `discovery master`；只要命中 master，就不进入本批 `L2`。
6. 当前实现里这层已经会先产出一版 `recommended_action`，但这只是内部保守草案，最终 shortlist 仍以 `Layer3` 为准。
7. 如果 `Scweet` 某个批次整批返回 `0`，必须自动拆成单账号重试，不能直接视为全量失败。
8. 当前主链路默认直接走 `ScrapeCreators Twitter profile`；只有在需要控制成本或做免费实验时，才切到 `Scweet` / `twscrape`。

## 五、排序规则

默认排序：

1. `followers_count` 降序
2. `overall_score` 降序
3. `tweet_count` 降序
4. `username` 升序

说明：

- `Layer2` 是账号层，所以默认不再按 `max_views` 作为主排序。
- `max_views` 继续保留用于审计和回看热帖来源，但主排序统一看 `followers_count`。

## 六、保留与去掉

必须保留：

- `Layer1` 的来源与发现痕迹
- 所有已补到的 profile 字段
- 补全来源标记
- 缺失状态标记
- `layer2_eligible`
- `layer2_skip_reason`

不能在这层做的事：

- 不能直接按主观感觉删账号
- 不能把“字段缺失”直接等同于“drop”
- 不能把最终业务判断提前到 Layer2
- 不能把命中 `discovery master` 的老人继续混进本批 `L2`

## 七、CSV 升级关系

`Layer2 enriched CSV` 是在 `Layer1 candidates CSV` 基础上的升级版，不是替换版。

升级方向：

- `x_kol_L1_candidates_batchN_{YYYY-MM-DD}.csv`
  ->
- `x_kol_L2_enriched_batchN_{YYYY-MM-DD}.csv`
  ->
- `x_kol_L3_shortlist_batchN_{YYYY-MM-DD}.csv`

## 八、脚本入口

当前对应脚本：

- `src/x_kol_discovery/pipelines/run_layer2_from_candidates.py`
- `src/x_kol_discovery/pipelines/run_batch_pipeline.py`

推荐调用方式：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_layer2_from_candidates.py \
  --input-csv workbench/2026-04-01/x_kol_L1_candidates_batch1_2026-04-01.csv \
  --run-date 2026-04-01
```

## 九、这层完成的判定标准

- 能从 `Layer1` CSV 稳定升级出 `Layer2` CSV
- 主键和发现证据没有丢
- 粉丝数、bio、认证、location 等基础判断字段已经落盘
- 未进入 `Layer2` 的账号被清晰标记为 `views gate` 跳过，而不是和抓取失败混在一起
- 命中 `discovery master` 的账号不会进入本批 `Layer2 enriched CSV`
- 后续 `Layer3` 可以直接基于这张表打分和筛选
- runlog 能区分 `views gate`、`blocked_by_master`、`batch empty`、`single retry recovered`、`still unresolved`
- `master audit` 能单独列出 `new_candidate / blocked_by_master`
