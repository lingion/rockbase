---
tags: [spec, build-log, youtube, kol, skill, execution]
date: 2026-04-10
status: active
---

# YouTube KOL Discovery Build Spec

这份文档不是抽象设计稿，而是按照本次真实搭建顺序整理出来的执行 spec。  
目标是让后面的 `TikTok / Instagram` 可以直接参考这套经验，先独立落地，再考虑 shared core。

## 1. 总目标

YouTube 这条链路的真实目标不是“做一个平台 discover 榜单抓取器”，而是：

1. 给一个领域角度或关键词
2. 先搜大量热内容
3. 聚合这些热内容背后的 creator
4. 用 `L2 / L3 / S2` 把 creator 变成可继续外联的表

也就是说，它本质上是：

`search-first, hot-content-led KOL mining`

而不是：

- 平台总榜收集
- 平台全量 discover
- 直接写 DM

## 2. 从 X Skill 吸取的核心经验

真正要复用的不是平台代码，而是 X 的业务骨架：

- `L1 -> L2 -> L3 -> S2`
- 项目级 `workbench/{YYYY-MM-DD}/YouTube/` 与 skill 内 `deliverables/` 分层
- `discovery master` 去重位置
- `L3 -> S2 base mapping -> S2 merge -> Mail1 fill`
- `Mail1` 字段从 `S2 base` 开始进入 CSV，但默认先留空

不直接照抄 X runtime 的原因：

- X 用的是 `username / tweet / top_tweet_url`
- YouTube 用的是 `channel_id / video / top_content_url`
- 联系方式来源、profile 结构、证据字段都不一样

所以当前策略是：

- 先复用 X 的 contract
- 再为 YouTube 写自己的 adapter/runtime
- 等 3 个平台都跑稳后，再决定抽 shared core

## 3. 按时间顺序的搭建过程

### Phase 0. 先定边界

一开始先统一几个关键原则：

- 先做 `3` 个独立 skill，不强行共用脚本
- 先把 shared logic 冻结在文档/字段契约层
- YouTube 先落地，但 spec 要能给 TikTok / Instagram 复用
- 当前最难的是 `L1`
- `L2 -> L3 -> S2` 尽量沿用 X 的成熟逻辑

### Phase 1. 先做 L1

YouTube 的 L1 最终采用的是：

- 主路径：`yt-dlp` 搜索热内容
- 可选补充：YouTube discover / API supplement
- 默认主轴：`search-first`

为什么这么定：

- 不依赖 API key 就能开始
- 更符合“给一个领域，搜很多热内容，再聚合 creator”的真实业务逻辑
- 比“先做 discover 榜单”更贴近 X 的热帖反推 KOL 思路

L1 最低要求必须保留：

- `content_title / theme_text`
- `creator_handle`
- `view_count`
- `content_url`
- `content_tags_or_hashtags`

原因：

- `theme_text / content_title` 是关键词匹配入口
- `creator_handle` 决定能不能反推 KOL
- `view_count` 决定能不能做 L1 流量门槛

### Phase 2. 把 L1 做成 unified table

L1 最后没有拆成两套表，而是统一成一张表：

- `row_type = content`
- `row_type = creator_summary`

这样做的原因：

- 保留 content-first 搜索证据
- 又能把 creator 聚合结果放进同一份 CSV
- 后面调试时不需要来回切两个规范

但真正给 `L2` 喂数据时，仍然主要使用 creator 粒度的 candidates。

### Phase 3. 接 L2

L2 的职责被明确为：

- 补齐 creator profile
- 补齐粉丝数
- 补齐联系方式线索
- 不重新发明 discovery

L2 的主要来源：

1. `YouTube Data API`
2. `ScrapeCreators` fallback
3. `contact page / website crawl`

字段分工：

- `followers_count`：YouTube API `subscriberCount`
- `statuses_count`：YouTube API `videoCount`
- `bio`：YouTube API `description`
- `contact_value`：email only
- `contact_note`：email source / method
- `external_links`：官网 / link page / newsletter / socials
- `contact_signals`：联系线索集合，供进一步分析，但不能直接当 email

### Phase 4. 把 email 补全做成三层

email 命中率提升的关键经验是：不要只盯平台内。

最终补全顺序：

1. `YouTube API`
2. `ScrapeCreators`
3. `contact page / website crawl`

第三层为什么重要：

- YouTube 本身很多频道不会直接暴露 email
- ScrapeCreators 也不一定每次直接给 email
- 但 creator 放出来的官网、newsletter、link page 往往更容易扫到公开 email

这层的执行规则：

- 只在 `contact_value` 仍为空时触发
- 只扫 `external_links / contact_signals` 指向的公开页面
- 优先官网、newsletter、link page
- 再尝试 `/contact`、`/about` 等路径
- 不做猜测式邮箱生成

### Phase 5. 先做 master 去重

去重不能等到 merge 才做。  
真正省 API / 省成本的去重点是在 `L2` 前。

最终规则：

1. `L1 candidates`
2. `views gate`
3. `check discovery master`
4. 仅对 net-new creator 调 `L2 provider`
5. 本批进入 L2 的新账号写回 master

master 的位置最终定为：

- `docs/youtube_kol_discovery_master.csv`

为什么不放深层 `Agency/list-master`：

- YouTube skill 当前阶段不需要那么重的运营目录
- skill 内单文件更直观
- 逻辑重要，目录不必复杂

## 4. 各层的目标和注意事项

### L1

目标：

- 搜热内容
- 留证据
- 聚合 creator
- 做第一道流量筛选

注意事项：

- 一定要保留 `theme_text`
- 一定要保留 `creator_handle`
- 一定要保留 `view_count`
- 默认 `view_count >= 1000` 才进 L2
- `L1` 是 content-first，不是直接搜 creator 列表

### L2

目标：

- 补资料
- 补粉丝数
- 补 email / 联系线索
- 形成可筛选 creator table

注意事项：

- `followers_count` 是 L2 门槛，不是 L1 门槛
- `contact_value` 必须是 email only
- `contact_note` 必须是 email 获取方式
- `external_links` 和 `contact_signals` 不能混进 email 列
- `L2` 进入 provider 前必须先查 master

### L3

目标：

- 只做判断，不重新搜索
- 把机构号、媒体号、品牌号的最终判定交给 LLM
- 让 `L3 -> S2` 直接执行 LLM 门禁，而不是人工 review

YouTube 的正式 deliverable 规范：

- `L3` 负责整理证据并调用 LLM，不再输出人工 review 流
- `S2 export` 必须删除 `llm_decision = drop` 的行
- `merge` 必须再次执行相同规则兜底
- 输出 `keep / drop`
- 形成 shortlist

注意事项：

- 联系方式缺失不一定 drop
- 但会影响优先级
- `L3` 不应该开始写 Mail1

### S2

目标：

- 把 shortlist 变成可继续外联的底稿
- 为 merge 和 Mail1 fill 做结构准备

注意事项：

- `Mail1` 字段从 `S2 base` 开始建列
- `S2 merge` 不新增字段
- `Mail1` 文案不应早于 `S2`

## 5. 当前最终冻结的关键规则

### 5.1 联系方式字段

这条规则必须写死：

- `联系方式 = email only`
- `联系方式备注 = email source / method`
- `外链__平台抓取 = website / link page / newsletter / socials`
- `contact_signals` 不能直接映射到 `联系方式`

这条规则已经写进脚本和文档。

### 5.2 Mail1 字段

Mail1 字段进入 CSV 的时点：

- 不在 `L1 / L2 / L3`

Mail1 文案 workflow 的默认挂载点：

- YouTube skill 在 `S2 merge` 之后，默认切换到
  `.agent/skills/S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`
- 这一步不再由 YouTube skill 自己定义另一套 cold mail 正文
- 也就是说，YouTube 负责把行推进到可写 Mail1 的 `S2 final` 状态，邮件模板则复用 Gmail drafts skill 的 canonical workflow
- YouTube 侧直接转调 runner：
  `src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`
- 从 `L3 -> S2 base mapping` 开始建列

当前预留列：

- `Mail1发出状态`
- `Mail1_Hook`
- `Mail1_Greeting_Name`
- `Mail1_Subject`
- `Mail1_Content V1`
- `Mail1_Content V2`

当前规则：

- `S2 base` 建列，但默认留空
- `S2 merge` 只保留这些列
- merge 后才进入 `Mail1 / 3.2 fill`

### 5.3 Master 去重

位置：

- `L2 provider` 之前

文件：

- `docs/youtube_kol_discovery_master.csv`

目的：

- 避免重复进入 API / fallback
- 避免重复进入 L3 / S2
- 保持当前批次接近 net-new 口径

## 6. 目前落地的文件和目录约定

### `docs/`

放：

- 长期规则
- setup 文档
- spec
- master CSV

当前关键文件：

- `docs/spec.md`
- `docs/youtube-api-setup.md`
- `docs/youtube_kol_discovery_master.csv`

### `/400 🔴 Project/🔴 420 Social Agency/workbench/{YYYY-MM-DD}/YouTube/`

放：

- 过程文件
- raw
- runlog
- audit
- smoke/test 批次
- L1/L2/S2 中间稿

例如：

- `youtube_kol_L1_*`
- `youtube_kol_L2_*`
- `youtube_kol_S2_cold_*`
- `youtube_kol_S2_mapping_runlog_*`
- `youtube_kol_S2_merged_filtered_*`
- `youtube_kol_S2_merged_filter_audit_*`

### `deliverables/{YYYY-MM-DD}/`

只放：

- 最终可交付 CSV
- 最终 merged

当前约定：

- `【S2_cold】..._merged_final.csv`

不放：

- raw
- runlog
- audit
- smoke/test
- batch 级 `S2`
- `netnew`

## 7. 当前已落地的 runner

### L1

- `src/youtube_kol_discovery/pipelines/run_layer1_mvp.py`

### L2

- `src/youtube_kol_discovery/pipelines/run_layer2_from_candidates.py`
- `src/youtube_kol_discovery/pipelines/augment_layer2_contact_crawl.py`

### S2

- `src/youtube_kol_discovery/pipelines/run_l3_to_s2_mapping.py`
- `src/youtube_kol_discovery/pipelines/run_merge_s2_deliverables.py`

说明：

- 当前还没有独立的 `L3 runner`
- 目前允许先把 `L2 shortlist` 视作 `L3 shortlist` 输入
- 这是为了先把 `S2 base / merge / Mail1 预留列` 跑通

## 8. 本次遇到的关键问题与解决方式

### 问题 1：master 目录太重

一开始沿用了 X 的深层 `Agency/list-master` 结构。  
后面改成：

- `docs/youtube_kol_discovery_master.csv`

经验：

- 逻辑保留
- 目录简化

### 问题 2：deliverables 被过程文件污染

一开始 `deliverables` 混进了：

- raw
- runlog
- audit
- smoke test

后面改成：

- 过程文件移到 `workbench`
- `deliverables` 只保留最终 CSV
- merge runner 会在写出 final 后自动清理误放进去的 `batch*.csv` / `*_netnew.csv`

### 问题 3：email 命中率太低

一开始只靠：

- YouTube API
- ScrapeCreators

后来加入：

- contact page / website crawl

结果：

- `contact_value` 从 `2` 提升到 `19`

### 问题 4：S2 的 `联系方式` 填错

一开始在 `S2 mapping` 里用了错误兜底：

- `contact_value or contact_signals`

导致外链被塞进 `联系方式`。

修复方式：

- 源头改脚本
- `联系方式` 只认 `contact_value`
- `联系方式备注` 只认 `contact_note`
- 用带 contact crawl 的最新版 shortlist 重跑 `S2 batch` 和 `S2 merged`

经验：

- 这种问题必须从 mapping 源头修
- 不能只在最终 CSV 上做表面替换

### 问题 5：机构号靠关键词规则误杀 / 漏杀

一开始在 `L3` / `S2 merge` 里使用了关键词与显式 handle 规则做机构号过滤。

修复方式：

- 把机构号判定前移到 LLM entity screen
- `L3` 只产出证据，不做人工 review 分叉
- `S2` 只接收 `llm_decision = keep` 的行
- `ambiguous` 默认按 `drop` 处理

经验：

- 机构号识别是语义任务，不应再主要依赖规则删行
- 规则最多只能做卫生检查，不应成为最终 gate

## 9. Subagent 的使用经验

适合开 subagent 的场景：

- contact page crawl
- 长时间外部 I/O
- 完整批次跑数
- 统计汇总

不一定要开 subagent 的场景：

- 短脚本修改
- 字段契约修正
- 小范围本地验证

推荐边界：

- 主线程负责改代码、改规则、定口径
- subagent 负责长时间运行和结果汇总
- 尤其是“只爬现有外链、不额外消耗 paid API credits”的流程，很适合交给 subagent

## 10. 对 TikTok / Instagram 的直接参考建议

后续开发时，直接复用这些结论：

1. 先把 `L1` 做成 content-first
2. `L2` 必须拆清：
   - `contact_value`
   - `contact_note`
   - `external_links`
   - `contact_signals`
3. `master` 去重放在 `L2 provider` 前
4. 一开始就分开：项目级 `workbench/{YYYY-MM-DD}/YouTube/` 与 skill 内 `deliverables/`
5. `Mail1` 列不要提前进 `L2 / L3`
6. 从 `S2 base` 开始统一预留 `Mail1` 列
7. email 不够时，不要只盯平台内；优先考虑官网/contact page crawl
8. 长跑任务优先考虑 subagent

## 11. 当前建议的下一步

YouTube 这条链路下一步最自然的是：

1. 补独立 `L3 runner`
2. `Mail1 / 3.2 fill` runner 已收口到 `src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`
3. 然后把同样节奏迁移到 TikTok / Instagram

在那之前，这份文档可以作为新平台开发的第一参考。
