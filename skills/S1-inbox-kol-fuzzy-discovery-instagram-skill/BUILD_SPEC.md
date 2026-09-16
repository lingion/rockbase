---
tags: [spec, build-log, instagram, kol, skill, execution]
date: 2026-04-10
status: active
---

# Instagram KOL Discovery Build Spec

这份文档记录的是 Instagram skill 的真实搭建过程，同时也承担当前唯一的长期设计说明。  
它的作用是把这次 `accio` 实战沉淀成后面继续开发、以及迁移到其他平台时可直接参考的执行 spec。

说明：

- Instagram skill 现在只保留一个根目录 spec 文件：`BUILD_SPEC.md`
- 之前单独拆过的 `DESIGN_SPEC.md`，其长期设计内容现已并回本文件
- 后续统一只维护这个名字

## 1. 总目标

Instagram 这条链路的真实目标是：

1. 给一个关键词或角度
2. 先搜大量相关高信号内容
3. 从内容反推 creator
4. 用 `L2 / L3 / S2` 把 creator 变成可继续外联的表

也就是：

`search-first, content-led KOL mining`

不是：

- 平台总榜 discover
- 直接搜 creator 列表
- 一上来就写 coldmail

## 2. 从 X / YouTube / TikTok 吸取的骨架

Instagram 复用的不是平台代码，而是成熟的业务骨架：

- `L1 -> L2 -> L3 -> S2`
- 项目级 `workbench/{YYYY-MM-DD}/Instagram/` 与 skill 内 `deliverables/` 分层
- `master` 在 `L2` 前去重
- `L3 -> S2 base mapping -> S2 merge`
- `Mail1` 列从 `S2 base` 开始预留，但先不填

Instagram 仍然保持独立 runtime，不强行抽 shared core。

## 3. 按时间顺序的搭建过程

### Phase 0. 先验证 Instagram 的两条 L1 路线

一开始同时验证了两条 L1：

- `ScrapeCreators /v2/instagram/reels/search`
- `Instaloader + cookies/session`

结论：

- `ScrapeCreators reels search` 现在最稳定，适合作为 `content-first` 默认主入口
- `Instaloader` 可以借浏览器 cookies 转成 session，不需要重新登录
- 但 `Instaloader hashtag` 仍然不够稳，会遇到 `checkpoint_required` / `more_available` 等问题

所以当前默认口径是：

- `content-first default = ScrapeCreators reels search`
- `account-first supplement = ScrapeCreators profile + Instaloader session-backed profile`

### Phase 1. 用 accio 做第一轮内容搜索

先做了一轮 `accio` 的 Instagram Reels 搜索。

真实结果表明：

- 可以拿到内容级结果
- 可以拿到 `video_view_count`
- 可以拿到 owner `username`
- 再回查 profile 后还能拿到 `followers_count / biography / external_url`

这一步证明了 Instagram 的 `L1 views gate` 可以落地。

### Phase 2. 再补 2 次 API 搜索

为了验证 query 扩展，对 `accio` 又补了两次：

- `accio review`
- `accio ai`

这两次总共额外消耗 `2` credits。

之后把旧的 `accio` core 结果和这两次新结果合并，形成正式的 `L1 merged`。

真实合并结果：

- `deduped content rows = 21`
- `creator candidates = 18`
- `l2 eligible = 15`

### Phase 3. 在 L2 前接 master 去重

Instagram 和 YouTube / TikTok 一样，把去重放在 `L2` 前。

顺序固定为：

1. `L1 candidates`
2. `views gate`
3. `check discovery master`
4. 仅对 net-new creator 调 `L2 provider`
5. 将进入 L2 的新账号写回 master

master 位置：

- `docs/instagram_kol_discovery_master.csv`

这样做的原因：

- 节省 profile 深挖 credits
- 避免重复进入 `L3 / S2`
- 保证每批尽量是净新增

### Phase 4. L2 先做 profile enrich，再做 contact augment

L2 的真实分层是：

第一层：

- `ScrapeCreators /v1/instagram/profile`
- 拿回：
  - `followers_count`
  - `following_count`
  - `statuses_count`
  - `bio`
  - `external_links`
  - 部分账号的 `business_email`

第二层：

- 如果 API 已直接返回 `business_email`，优先写入 `contact_value`
- 若无，则从 `bio` 做邮箱正则提取

第三层：

- 对无 email 但有 `external_links` 的 shortlist 行
- 再跑 contact page crawl augment

当前 Instagram 最重要的经验是：

- 它和 TikTok 不一样
- Instagram L2 里，API 本身就有机会直接返回 `business_email`
- 所以 email 来源优先级应该明确写死：
  1. `business_email`
  2. `bio regex`
  3. `contact page crawl`

### Phase 5. L3 和 S2

L3 的职责：

- 不重新搜索
- 对 `L2` 做复核
- 输出 `keep / review / drop`

S2 的职责：

- 输出 cold outreach 底稿
- 预留 `Mail1` 列
- 但 `Mail1` 文案填充后面统一做

Instagram 也沿用同一条硬规则：

- `联系方式 = email only`
- `联系方式备注 = email source / method`
- `外链__平台抓取 = website / link-in-bio / socials`

## 4. 各层目标和注意事项

### L1

目标：

- 搜内容
- 保留匹配证据
- 聚合 creator
- 先做流量筛选

注意事项：

- 一定保留 `theme_text`
- 一定保留 `creator_handle`
- 一定保留 `view_count`
- 一定保留 `content_url`
- 一定保留 `content_tags_or_hashtags`
- `hot` 在 Instagram 上定义为高信号 Reels/topic content，不是平台全站 trending

### L2

目标：

- 补账号体量
- 补 bio
- 补 email / contact clue
- 形成真正可判断的 creator 表

注意事项：

- `followers_count` 是 L2 门槛，不是 L1 门槛
- `contact_value` 只能放 email
- `contact_note` 只能放 email 获取方法
- `external_links` 不能塞进联系方式
- 进入 provider 前必须先查 master

### L3

目标：

- 只做判断和收口
- 输出 `keep / review / drop`
- 形成 shortlist

注意事项：

- 没 email 不一定 drop
- 但会影响优先级
- 不在 L3 里开始写 Mail1

### S2

目标：

- 变成可继续外联的底稿
- 为 merge 和 Mail1 fill 做准备

注意事项：

- `Mail1` 字段从 `S2 base` 开始建列
- `S2 merge` 只保留字段，不新增字段

## 5. 这次遇到的主要问题和解决方式

### 问题 1. Instaloader 重新登录风险太高

解决：

- 不走重新登录
- 直接从浏览器 cookies 转成 skill-local session

### 问题 2. Instaloader hashtag 路线不稳

解决：

- 不再把 `Instaloader` 当默认 `content-first` 主入口
- 改成 `ScrapeCreators reels search` 作为主路径
- `Instaloader` 保留成 session-backed 补充线

### 问题 3. workbench 放错到了 skill 内部

解决：

- 全部改成项目级：
  - `Social Agency/workbench/{YYYY-MM-DD}/Instagram/`
- 只把最终交付留在 skill 内 `deliverables/`

### 问题 4. contact crawl 的 run_date 推断在新 workbench 规则下出错

解决：

- 修改脚本，使其优先从父目录和祖父目录识别 `YYYY-MM-DD`
- 修掉曾经误写到 `workbench/Instagram/Instagram/` 的问题

## 6. 当前真实结果

基于 `accio + accio review + accio ai`：

- `L1 creator candidates = 18`
- `L2 shortlist = 15`
- `L3 shortlist = 15`
- `S2 merged final = 15`
- `email = 9`

这是 Instagram 目前已经真实跑通的结果，不是估算。

## 7. deliverables 与 workbench 规则

### workbench

过程文件统一放：

- `.../Social Agency/workbench/{YYYY-MM-DD}/Instagram/`

包括：

- L1 raw / unified / candidates / runlog
- L1 merge summary
- L2 enriched / shortlist / master audit / runlog
- contact crawl augment 输出
- L3 reviewed / shortlist / runlog
- S2 base mapping runlog

### deliverables

只保留最终交付：

- `【S2_cold】{date}_instagram_kol_S2_batch*.csv`
- `【S2_cold】{date}_instagram_kol_S2_merged_final.csv`
- `merge audit json`

## 8. 还没做的内容

当前 Instagram 主干已经成型，但还有几块没有收尾：

- `Mail1 / 3.2 fill` 还没做
- `Instaloader hashtag` 兼容问题还没彻底解决
- 更强的网页级 email augment 还可以再升级成 subagent / Firecrawl 版

## 9. 当前推荐的默认执行顺序

1. 先跑 `ScrapeCreators reels search`
2. 合并多组 query 的 L1
3. 做 `views gate`
4. 进 `master dedupe`
5. 用 `ScrapeCreators profile` 做 L2 enrich
6. 做 `followers gate`
7. 对 shortlist 跑 contact crawl augment
8. 进入 `L3`
9. 进入 `S2 base`
10. `S2 merge`
11. 后面再统一做 `Mail1`
