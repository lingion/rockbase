---
description: "[Workflow] X KOL Layer1 发现层 CSV 工作流 | 目标：把自然语言 brief 变成候选账号 CSV。"
---

# L1-WF_x_kol_discovery_csv

> 用途：把 `topic / country / language / role` 这类模糊 brief，转成一张可审阅、可继续升级的 `Layer1 candidates CSV`。

## 一、核心目标

`Layer1` 只负责一件事：找人。

这一层不做最终判断，不输出 `keep / review / drop`，也不要求一次就把资料补全。  
它的交付标准是：先产出一张“足够多、可继续补数”的候选人 CSV。

## 二、输入与输出

### 输入

- 自然语言 brief
- 结构化 query spec
- provider 执行计划

### 主输出 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L1_candidates_batch1_{YYYY-MM-DD}.csv`

### 辅助证据文件

- `workbench/{YYYY-MM-DD}/x_kol_L1_raw_batch1_{YYYY-MM-DD}.json`
- `workbench/{YYYY-MM-DD}/x_kol_L1_raw_batch1_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/x_kol_L1_runlog_batch1_{YYYY-MM-DD}.json`

规则：

- 主进度看 `candidates CSV`
- raw 文件只做审计和回溯，不作为主操作面
- 同一天如有第二批、第三批，文件名依次改成 `batch2 / batch3`

## 三、CSV 字段契约

`Layer1 candidates CSV` 至少保留这些字段：

| 字段 | 说明 |
| :--- | :--- |
| `username` | 候选账号唯一主键，必须小写 |
| `display_name` | 账号显示名 |
| `matched_queries` | 命中的 query 名称或组合 |
| `tweet_count` | 当前命中的帖子数量 |
| `max_views` | 命中帖子中的最高浏览量 |
| `max_likes` | 命中帖子中的最高点赞数 |
| `max_retweets` | 命中帖子中的最高转推数 |
| `max_comments` | 命中帖子中的最高评论数 |
| `sample_posts` | 最多保留 3 条样例文本，便于人工快速感知 |
| `top_tweet_url` | 当前最强信号帖子链接 |
| `source_tweet_ids` | 支撑该候选人的 tweet id 列表 |
| `provider_source` | 来源 provider，例如 `scweet` |

## 四、生成规则

1. 先按 query 抓 raw rows。
2. 再按 `username` 做 merge / dedupe。
3. 一行代表一个账号，不允许在 `Layer1 candidates CSV` 保留 tweet-level 重复行。
4. 同一个账号的多条命中帖子，只允许体现在聚合字段里，不允许展开成多行。

## 五、排序规则

默认排序：

1. `max_views` 降序
2. `max_likes` 降序
3. `max_retweets` 降序
4. `max_comments` 降序
5. `tweet_count` 降序

说明：

- `L1` 是内容发现层，所以默认按 `max_views` 排序，不按粉丝数排序。
6. `username` 升序

目的：

- 让最有“浏览量热度”的账号先浮上来
- 让人工 review 时先看到真正发出热帖的对象

## 六、保留与去掉

必须保留：

- 所有 dedupe 后的候选账号
- query 命中痕迹
- 帖子热度信号，尤其是浏览量
- 样例帖子

必须去掉：

- tweet-level 重复行
- 没有 `username` 的脏记录
- 完全空白或无法追溯来源的记录

## 七、升级关系

这一层的 CSV 不应该直接被人工大改。  
它的职责是作为 `Layer2` 的输入基底。

升级方向：

- `x_kol_L1_candidates_batchN_{YYYY-MM-DD}.csv`
  ->
- `x_kol_L2_enriched_batchN_{YYYY-MM-DD}.csv`

意思是：`Layer2` 不是重做一张全新表，而是在保留 `Layer1` 候选主键和发现信号的基础上补字段。

## 八、脚本入口

当前对应脚本：

- `src/x_kol_discovery/pipelines/run_layer1_mvp.py`
- `src/x_kol_discovery/pipelines/run_batch_pipeline.py`

推荐调用方式：

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_layer1_mvp.py \
  --run-date 2026-04-01
```

## 九、这层完成的判定标准

- 能稳定输出一张候选账号 CSV
- 候选账号已按 `username` 去重
- 人可以通过这一张 CSV 感知当前找到了哪些人、为什么找到他们
- 下一层可以直接拿它继续补数
