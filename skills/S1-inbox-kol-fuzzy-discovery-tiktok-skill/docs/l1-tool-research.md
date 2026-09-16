---
tags: [tiktok, l1, research, search, proxy]
date: 2026-04-10
status: active
---

# TikTok L1 Tool Research

## 结论先行

TikTok 这一版的首要问题不是 `L2 / L3 / S2`，而是先把 `L1 search-first` 跑通。

当前建议路径已经更新为：

1. 第一候选：`ScrapeCreators TikTok search`
2. 第二层：`TikTok-Api` 只承担 `account-first / user lookup`
3. 默认启用 skill-local 静态 IP
4. `ms_token` 继续保留，作为 `TikTok-Api` 路径的已验证认证层
5. 如果 `ScrapeCreators` 结果质量不足，再升级到 browser/session-heavy fallback

## 为什么不是先做完整 skill

因为 TikTok 真正的不确定项集中在：

- keyword search 是否稳定
- 单条内容能否拿到 `title/theme + handle + traffic`
- `ms_token` 是否足够
- static proxy 是否需要默认启用

这些不确定项在 `L1` 没验证前，后面的 `L2 -> L3 -> S2` 都只是空骨架。

## 明星项目的作用边界

### `mvanhorn/last30days-skill`

适合借鉴：

- query orchestration
- 多源搜索工作流
- 按 engagement 排序

不直接解决：

- creator 聚合
- KOL shortlist 导出
- 你的 `L1 -> L2` 字段 contract

### `Panniantong/Agent-Reach`

适合借鉴：

- provider boundary
- 选择上游 collector 的方式

不直接解决：

- 从 content 聚合 creator
- KOL 表格输出

### `davidteather/TikTok-Api`

已验证更适合承担：

- `account-first`
- user/profile lookup
- 作为 `ScrapeCreators` 的辅助交叉验证

已知限制：

- `item/content search` 当前不稳定
- anti-bot 敏感
- 即使有 proxy 和 `ms_token`，也不应再默认当作 `content-first` 主 collector

### `ScrapeCreators`

当前最适合直接承担 TikTok `L1 content-first`。

适合承担：

- keyword search
- hashtag search
- search users
- profile videos

已知限制：

- 有 credits 成本
- 结果质量仍取决于 query 设计
- 不同平台的“模糊搜索”能力并不完全对等

## ScrapeCreators 平台能力矩阵

### 适合直接做 `L1 content-first`

- `TikTok`
  - `GET /v1/tiktok/search/keyword`
  - `GET /v1/tiktok/search/hashtag`
  - 优势：原生短视频内容搜索能力最完整
  - 局限：需要 query 设计，结果仍可能混入低相关内容
- `YouTube`
  - `GET /v1/youtube/search`
  - `GET /v1/youtube/search/hashtag`
  - 优势：搜索稳定、字段完整、最接近 YouTube 已落地 workflow
  - 局限：更偏公开视频搜索，不等于“全站 hot feed”
- `Instagram`
  - `GET /v2/instagram/reels/search`
  - 优势：支持关键词找 Reels
  - 局限：本质是 SEO/public discovery，不是 IG 内部原生登录态搜索
- `Threads`
  - `GET /v1/threads/search`
  - `GET /v1/threads/search/users`
  - 优势：可做关键词发现
  - 局限：平台成熟度和结果密度要视具体主题而定
- `Reddit`
  - `GET /v1/reddit/search`
  - 优势：内容搜索明确
  - 局限：社区帖子不天然等于 KOL，需要更强 aggregation
- `Pinterest`
  - `GET /v1/pinterest/search`
  - 优势：可以做视觉/内容 discovery
  - 局限：creator 商业联系方式链路较弱

### 更适合做已知账号深挖，不适合当前统一 `content-first`

- `X / Twitter`
  - 当前看到的是：
    - `GET /v1/twitter/profile`
    - `GET /v1/twitter/user-tweets`
    - `GET /v1/twitter/tweet`
  - 优势：已知账号深挖稳定
  - 局限：当前没有看到等价的通用 keyword content search 入口

## 推荐命令

以下命令是当前最值得保留在 TikTok skill 文档里的“可执行入口”。

### TikTok keyword search

```bash
curl --request GET \
  --url 'https://api.scrapecreators.com/v1/tiktok/search/keyword?query=ai%20agents&date_posted=30&sort_by=most_likes&region=US' \
  --header 'x-api-key: $SCRAPECREATORS_API_KEY'
```

用途：

- `L1 content-first` 主入口
- 先拿内容，再聚合 creator

### TikTok hashtag search

```bash
curl --request GET \
  --url 'https://api.scrapecreators.com/v1/tiktok/search/hashtag?query=aiagents&sort_by=most_likes&region=US' \
  --header 'x-api-key: $SCRAPECREATORS_API_KEY'
```

用途：

- 对 hashtag 明显的 query 做补充 probe

### TikTok search users

```bash
curl --request GET \
  --url 'https://api.scrapecreators.com/v1/tiktok/search/users?query=ai%20agents' \
  --header 'x-api-key: $SCRAPECREATORS_API_KEY'
```

用途：

- `account-first`
- 先拿候选 creator，再补视频

### TikTok profile videos

```bash
curl --request GET \
  --url 'https://api.scrapecreators.com/v3/tiktok/profile/videos?handle=aiagentsmastery&sort_by=newest&region=US' \
  --header 'x-api-key: $SCRAPECREATORS_API_KEY'
```

用途：

- 已知 creator 后补热视频证据
- 适合作为 `account-first -> evidence stitch`

## 当前最推荐的平台判断

如果只看 `ScrapeCreators-first L1`：

- 当前最适合的是 `TikTok`

原因：

- 它同时具备：
  - `keyword search`
  - `hashtag search`
  - `search users`
  - `profile videos`
- 这比 `Instagram` 和 `X` 更完整
- 对你要的 workflow：
  - `先搜内容 -> 再聚合 creator`
  非常贴合

所以当前建议已经冻结为：

- `TikTok` 应该把 `ScrapeCreators API` 作为 `L1` 的默认入口
- `TikTok-Api` 降级为辅助入口，不再是默认主入口

## 当前 L1 字段策略

不要先过度裁剪字段。

第一原则：

- 先把工具能稳定拿到的字段尽量全量保留

第二原则：

- 再根据真实返回结果，更新 `WF/Lx-Field-Matrix_tiktok_kol_csv.md`

也就是说，TikTok `L1` 当前采用：

- `必备字段 + 灵活字段`
- 先看真实 collector 能拿回什么
- 再冻结哪些字段进入长期 contract

## 第一版最想看到的 raw 字段

如果 `ScrapeCreators TikTok search` 跑通，优先争取拿到这些：

- `content_id`
- `content_title`
- `theme_text`
- `content_url`
- `author_unique_id`
- `author_id`
- `nickname`
- `sec_uid`
- `create_time`
- `view_count`
- `like_count`
- `comment_count`
- `share_count`
- `collect_count`
- `music_title`
- `region`
- `duration`
- `cover_url`
- `content_tags_or_hashtags`

## 验收标准

TikTok `L1` 算“跑通”，至少要满足：

1. 给一个 query 能返回一批内容，不只是空 blocker
2. 单条内容里有：
   - `theme_text`
   - `creator_handle`
   - `content_url`
   - `view_count`
3. 能把多条内容聚合回 creator
4. 能输出 unified CSV
5. 默认测试时启用 skill-local static proxy

## 当前默认运行策略

- 默认启用静态 IP：
  - `149.119.188.182:443`
- 默认从 skill-local `.env.local` 读取
- 不把这组代理写进 shared global env

## 下一步

1. 保留当前已验证的 `ms_token + static proxy` 作为辅助认证层
2. 先接 `ScrapeCreators TikTok keyword search`
3. 再接 `ScrapeCreators search users / profile videos`
4. 用真实返回字段回填 field matrix
