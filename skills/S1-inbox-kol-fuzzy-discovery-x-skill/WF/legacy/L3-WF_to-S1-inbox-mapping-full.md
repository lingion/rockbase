---
description: "[Workflow] L3 到 S1 Inbox 映射工作流 | 目标：把 L3 shortlist CSV 映射成业务可流转的 S1 Inbox CSV。"
---

# L3-WF_to-S1-inbox-mapping

> 用途：这份 workflow 不负责找人，也不负责补数。  
> 它只负责把 `L3 shortlist CSV` 转成符合业务使用习惯的 `S1 Inbox CSV`。
>
> 状态：legacy compatibility only。当前默认主流程已经直接进入 `S2 Cold`，只有在兼容旧表、旧自动化或历史批次时才使用本页。

## 一、核心目标

`L1 / L2 / L3` 是 skill 内部过程层。  
`S1 Inbox CSV` 是业务流转层。

所以这一层的职责是：

- 保留 `L3` 的判断结果
- 转换成 `S1 Inbox` 习惯的字段名
- 按 `S1 Inbox` 需要的字段顺序输出
- 让后续人工 review、入池、流转更顺

一句话：

**把技术 shortlist 变成业务 shortlist。**

## 二、输入与输出

### 输入 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L3_shortlist_batch1_{YYYY-MM-DD}.csv`

### 输出 CSV

- `workbench/{YYYY-MM-DD}/x_kol_S1_inbox_batch1_{YYYY-MM-DD}.csv`

### 辅助文件

- `workbench/{YYYY-MM-DD}/x_kol_S1_inbox_mapping_audit_batch1_{YYYY-MM-DD}.md`
- `workbench/{YYYY-MM-DD}/x_kol_S1_inbox_mapping_runlog_batch1_{YYYY-MM-DD}.json`

## 三、S1 Inbox 建议字段顺序

当前建议先输出这一版字段顺序：

1. `备注`
2. `账号ID`
3. `频道/作者名称`
4. `平台`
5. `多平台标记`
6. `账号链接`
7. `语言`
8. `博主国家`
9. `粉丝数`
10. `账号类目标签`
11. `账号类目标签__平台抓取`
12. `置顶最高播放`
13. `近期10条均播`
14. `近10条平均ER（按曝光）`
15. `近10条平均ER（按粉丝）`
16. `rate（USD$)报价`
17. `原价`
18. `账号简介`
19. `账号简介__平台抓取`
20. `Sample Content`
21. `Latest Activity Proof`
22. `粉丝受众`
23. `粉丝性别`
24. `粉丝年龄`
25. `联系方式`
26. `联系方式备注`
27. `外链__平台抓取`
28. `Recommendation`

## 四、字段映射表

| S1 Inbox 字段 | 来源层 | 来源字段 | 当前是否可稳定产出 | 映射规则 |
| :--- | :--- | :--- | :---: | :--- |
| `备注` | - | - | 是 | 当前默认留空 |
| `账号ID` | L1/L2/L3 | `username` | 是 | 必须映射成带 `@` 的格式 |
| `频道/作者名称` | L1/L2/L3 | `display_name` | 是 | 直接映射 |
| `平台` | 固定值 | `X` | 是 | 固定写 `X` |
| `多平台标记` | 暂无 | - | 否 | 先留空 |
| `账号链接` | L2/L3 | `profile_url` | 是 | 直接映射 |
| `语言` | L3 | `primary_language` / tweets language analysis | 部分 | 必须基于贴文内容语言分析填写，当前无稳定分析则留空 |
| `博主国家` | L3 | `country_inferred` | 部分 | 若无则留空 |
| `粉丝数` | L2/L3 | `followers_count` | 是 | 直接映射 |
| `账号类目标签` | - | - | 是 | 当前默认留空 |
| `账号类目标签__平台抓取` | L2 | `bio` / 平台原始标签 | 是 | 当前按你的执行口径默认留空，后续如要增强再补规则标签 |
| `置顶最高播放` | - | - | 是 | 当前默认留空 |
| `近期10条均播` | 暂无 | - | 否 | 当前留空 |
| `近10条平均ER（按曝光）` | 暂无 | - | 否 | 当前留空 |
| `近10条平均ER（按粉丝）` | 暂无 | - | 否 | 当前留空 |
| `rate（USD$)报价` | 暂无 | - | 否 | 当前留空 |
| `原价` | 暂无 | - | 否 | 当前留空 |
| `账号简介` | - | - | 是 | 当前默认留空 |
| `账号简介__平台抓取` | L2/L3 | `bio` | 是 | 直接映射平台原始 bio |
| `Sample Content` | L1/L2/L3 | `top_tweet_url` + `top_tweet_text` / `sample_posts` | 是 | 格式为 `URL - 帖子原文`；语义为本批主题下最相关的一条命中帖 |
| `Latest Activity Proof` | 后续活跃补全 | `recent post` from timeline enrichment | 否 | 当前阶段留空；后续由 `S3/S4` 活跃补全填写 |
| `粉丝受众` | 暂无 | - | 否 | 当前留空 |
| `粉丝性别` | 暂无 | - | 否 | 当前留空 |
| `粉丝年龄` | 暂无 | - | 否 | 当前留空 |
| `联系方式` | L2 | `contact_value` | 部分 | 当前有值则映射，无值留空 |
| `联系方式备注` | L2 | `contact_note` / contact stub | 部分 | 当前有值则映射，无值留空 |
| `外链__平台抓取` | L2 | `external_links` | 部分 | 当前有值则映射，无值留空 |
| `Recommendation` | - | - | 是 | 当前默认留空 |

## 五、字段格式契约

以下格式规则应视为本 workflow 的硬规则：

- `账号ID`
  最终统一成带 `@` 的格式。

- `平台`
  统一标准值，只允许 `X`。

- `博主国家`
  统一成中文标准国别，不允许中英混写。

- `语言`
  统一成中文标准表达，例如 `英语`，不允许混用 `en`、`English` 等写法。

- `联系方式备注`
  一旦填写，必须写成“来源 + 结果”的格式，不写空泛备注。

- `外链__平台抓取`
  多个值统一用 ` | ` 拼接；只写原始链接或主域名，不写解释句，不写邮箱。

- `账号简介__平台抓取`
  直接写平台原始 `bio`；不做人工脱水，不做改写。

- `Sample Content`
  必须统一写成 `URL - 帖子原文`；它表示本批主题下最相关的一条命中帖，不承担“近期活跃证明”的语义。

- `Latest Activity Proof`
  当前阶段必须留空；后续由 `S3/S4` 环节通过 timeline / active enrichment 抓取“最近最新一条帖子”后再填写。

## 六、直接映射规则

这些字段属于“直接映射”，不需要复杂加工：

- `账号ID <- @username`
- `频道/作者名称 <- display_name`
- `平台 <- X`
- `账号链接 <- profile_url`
- `粉丝数 <- followers_count`
- `账号简介__平台抓取 <- bio`
- `Sample Content <- top_tweet_url + top_tweet_text`
- `Latest Activity Proof <- 当前阶段留空`

## 七、半直接映射规则

这些字段当前可以先映射，但语义上是“业务近似映射”，后续可优化：

- `语言 <- 基于贴文内部的语言分析`
- `博主国家 <- country_inferred`
- `Latest Activity Proof <- 后续活跃补全（ScrapeCreators / timeline provider）`

备注：

- `语言` 不能简单直接拿技术层暂存字段硬写，应该优先以贴文语言分析为准，且最终需转成中文标准表达
- `博主国家` 当前优先基于 `location_raw`、`bio` 与国旗 emoji 等弱结构线索推断；即使后续有值，也应先统一成中文标准国别再写入
- `置顶最高播放` 在未做 pinned post 级别抓取前，当前先留空，不做近似映射
- `Latest Activity Proof` 不允许拿主题命中帖冒充“近期活跃证明”
- `账号简介` 当前按你的执行口径保留为空，不同步写入 `bio`
- `Recommendation` 当前按你的执行口径保留为空，不映射 `keep / review / drop`

## 八、当前必须留空的字段

这些字段现阶段不能假填：

- `备注`
- `多平台标记`
- `账号类目标签`
- `置顶最高播放`
- `近期10条均播`
- `近10条平均ER（按曝光）`
- `近10条平均ER（按粉丝）`
- `rate（USD$)报价`
- `原价`
- `账号简介`
- `Latest Activity Proof`
- `粉丝受众`
- `粉丝性别`
- `粉丝年龄`
- `Recommendation`

原则：

- 可以保留列
- 但不能编造值
- 当前拿不到就留空

批次规则：

- 同一天允许存在多批
- `S1 Inbox` 输出必须跟随上游批次编号
- 例如 `batch2` 的 `L3 shortlist` 只能映射成 `batch2` 的 `S1 inbox`

## 九、当前增强后可补的字段

这些字段现在不稳定，但属于明确可继续增强的区块：

- `账号类目标签__平台抓取`
- `联系方式`
- `联系方式备注`
- `外链__平台抓取`

增强来源主要是：

- `ScrapeCreators enhanced enrichment`
- `OmniChrome fallback`

补充要求：

- `联系方式备注` 一旦后续开始填写，必须遵守“来源 + 结果”的格式纪律
- `外链__平台抓取` 一旦后续开始填写，必须遵守 ` | ` 拼接与“只写原始链接/域名”的格式纪律

## 十、排序规则

`S1 Inbox CSV` 默认排序建议：

1. `Recommendation` 顺序：`keep` -> `review` -> `drop`
2. `置顶最高播放` 降序
3. `粉丝数` 降序
4. `账号ID` 升序

目的：

- 让最值得入池的对象先浮到前面
- 同时保留“热帖强度”这个你已经确认很重要的判断因子

## 十一、保留与去掉

进入 `S1 Inbox CSV` 时，原则上应去掉这些纯技术字段：

- `matched_queries`
- `sample_posts`
- `source_tweet_ids`
- `provider_source`
- `enrichment_provider`
- `country_confidence`
- `language_mix`
- `topic_match_score`
- `profile_match_score`
- `activity_score`
- `overall_score`
- `matched_signals`

这些字段不应该消失，而是应留在：

- `L3 shortlist CSV`
- 或 mapping audit / runlog

也就是说：

- `L3 CSV` 保留技术判断细节
- `S1 Inbox CSV` 保留业务操作字段

## 十二、脚本方向

后续应补一个独立脚本：

- `src/x_kol_discovery/pipelines/run_l3_to_s1_mapping.py`

职责：

- 读取 `L3 shortlist CSV`
- 按本 workflow 的字段顺序与映射规则输出 `S1 Inbox CSV`
- 同时落一份 mapping audit

## 十三、这层完成的判定标准

- `L3 shortlist CSV` 能稳定映射成一张可读的 `S1 Inbox CSV`
- 输出字段顺序固定
- 能明确区分“直接映射字段”和“当前留空字段”
- 不因业务表格式化而丢失原始技术判断结果
