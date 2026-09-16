---
tags: [spec, build-log, tiktok, kol, skill, execution]
date: 2026-04-10
status: active
---

# TikTok KOL Discovery Build Spec

这份文档是 TikTok skill 的真实搭建记录，不是抽象方案。  
目标是把这次 `accio` 实验沉淀成后面 `Instagram` 可直接参考的执行 spec。

## 1. 总目标

TikTok 这条链路的真实目标是：

1. 给一个关键词或角度
2. 先搜大量相关热内容
3. 从内容反推 creator
4. 用 `L2 / L3 / S2` 把 creator 变成可继续外联的表

也就是：

`search-first, hot-content-led KOL mining`

不是：

- 平台总榜 discover
- 直接搜 creator 列表
- 一上来就写 coldmail

## 2. 从 X / YouTube 吸取的骨架

TikTok 复用的不是平台代码，而是成熟的业务骨架：

- `L1 -> L2 -> L3 -> S2`
- 项目级 `workbench/{YYYY-MM-DD}/TikTok/` 与 skill 内 `deliverables/` 分层
- `master` 在 `L2` 前去重
- `L3 -> S2 base mapping -> S2 merge`
- `Mail1` 列从 `S2 base` 开始预留，但先不填

当前 TikTok 仍然保持独立 runtime，不强行抽 shared core。

## 3. 按时间顺序的搭建过程

### Phase 0. 先验证认证层

先验证了两件事：

- `ms_token` 哪一组可用
- 静态代理应该怎么接

结论：

- `ms_token` 第 2 组可用
- 代理需要用 `http://user:pass@ip:port`
- 这些配置只放 skill-local `.env.local`
- 不写入全局大 env

### Phase 1. 先验证 TikTokApi 的边界

做过一轮 `TikTokApi + proxy + ms_token` 实测。

结果：

- `user search` 可以
- `item/content search` 不稳定，容易空响应或被风控

结论：

- `TikTokApi` 适合 `account-first / user lookup`
- 不适合作为 `content-first` 主 collector

### Phase 2. 转向 ScrapeCreators-first 的 L1

后续把 TikTok 的 `L1 content-first` 切到了 `ScrapeCreators`。

主路径：

- `/v1/tiktok/search/keyword`

补充路径：

- `/v1/tiktok/search/hashtag`

为什么这么做：

- 更符合你要的“先搜内容，再找背后 KOL”
- 已经真实验证可以返回：
  - `content_title/theme_text`
  - `creator_handle`
  - `content_url`
  - `view_count`
  - `like_count`
  - `comment_count`

也就是说，TikTok 的 `L1 views gate` 可以落地，不再是猜测。

### Phase 3. 用 accio 做第一轮实验

实验任务：

- topic: `accio`
- query:
  - `accio`
  - `accio review`
  - `accio ai`
- `L1 views gate = 2000`
- `L2 followers gate = 3000`

第一轮真实结果：

- `L1 eligible creators = 40`
- `L2 shortlist = 27`
- `shortlist email = 18`

### Phase 4. 在 L2 前先接 master 去重

和 YouTube 一样，TikTok 的去重也放在 `L2` 前。

顺序固定为：

1. `L1 candidates`
2. `views gate`
3. `check discovery master`
4. 仅对 net-new creator 调 `L2 provider`
5. 将进入 L2 的新账号写回 master

master 位置：

- `docs/tiktok_kol_discovery_master.csv`

这样做的原因：

- 节省 profile 深挖 credits
- 避免重复进入 `L3 / S2`
- 保证每批尽量是净新增

### Phase 5. L2 先做 profile enrich，再做 email augment

L2 的真实分层是：

第一层：

- `ScrapeCreators /v1/tiktok/profile`
- 拿回：
  - `followers_count`
  - `following_count`
  - `statuses_count`
  - `bio = user.signature`
  - `external_links = user.bioLink.link`

第二层：

- 从 `bio` 做邮箱正则提取
- 这是当前 TikTok 最有效的 email 来源

第三层：

- 对无 email 但有 `external_links` 的 shortlist 行
- 再跑 contact page augment

重要经验：

- TikTok 首轮最值钱的是 `bio regex email`
- 官网/聚合页补扫应该做成单独 augment
- 不要把它强绑在首轮 profile enrich 里，否则整批会过慢

### Phase 6. L3 和 S2

L3 的职责：

- 不重新搜索
- 对 `L2` 做复核
- 输出 `keep / review / drop`

S2 的职责：

- 输出 cold outreach 底稿
- 预留 `Mail1` 列
- 但 `Mail1` 文案填充后面统一做

TikTok 也沿用同一条硬规则：

- `联系方式 = email only`
- `联系方式备注 = email source / method`
- `外链__平台抓取 = website / link page / socials`

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
- 机构号、媒体号、品牌号不能因为分数高就直接进 `keep`
- 机构号、媒体号、品牌号的正式删除不应停留在 `L3`；必须在 `S2 export` 删除，并在 `merge` 再兜底一次
- `300k+ followers` 视为过分一线候选，需要额外 creator-fit 复核
- `1M+ followers` 且伴随组织信号时，默认不进入正式 shortlist

### S2

目标：

- 变成可继续外联的底稿
- 为 merge 和 Mail1 fill 做准备

注意事项：

- `Mail1` 字段从 `S2 base` 开始建列
- `S2 merge` 只保留字段，不新增字段

## 5. 这次遇到的主要问题和解决方式

### 问题 1. TikTokApi content search 不稳

解决：

- 放弃让 `TikTokApi` 做主 `L1 content-first`
- 改成 `ScrapeCreators-first`

### 问题 2. 不是所有 creator 都会直接暴露 email

解决：

- 先用 `bio regex`
- 再把外链扫邮箱做成单独 augment

### 问题 3. contact crawl 放进首轮 L2 会太慢

解决：

- `L2 profile enrich` 先独立完成
- `contact crawl` 后置为 shortlist augment

### 问题 4. TikTok 的 hashtags 返回不总是结构化

解决：

- 保留原始 `hashtags/textExtra`
- 再从 caption 文本中补做 `#hashtag` 正则提取

## 6. 当前已落地的关键文件

- `L1 ScrapeCreators runner`
- `L2 from candidates runner`
- `L3 from L2 runner`
- `S2 mapping runner`
- `S2 merge runner`
- `L2 contact crawl augment`
- `discovery master`

这套骨架已经足够给 Instagram 复用，只需要替换：

- `L1 collector`
- `profile enrich`
- 平台字段映射

## 7. 当前还没做的内容

TikTok 目前已经能跑到 `S2`，但还没做：

- `Mail1 / 3.2 fill`
- 更强版本的网页级邮箱扫描
- 更完整的批量 smoke / regression tests

## 8. 当前阶段结论

现在可以把 TikTok 视为：

- `L1 -> L2 -> L3 -> S2` 主链路已经打通
- `ScrapeCreators-first` 是目前最合理的默认方案
- `bio regex email` 是当前最有效的联系方式来源
- `contact page augment` 适合作为后置增强层
