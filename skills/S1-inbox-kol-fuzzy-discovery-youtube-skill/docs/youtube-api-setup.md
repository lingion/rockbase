# YouTube API Setup

用于给 `S1-inbox-kol-fuzzy-discovery-youtube-skill` 开通 `YOUTUBE_API_KEY`。

## 目标

当前 YouTube skill 的 `L1` 主搜索不依赖 API key。
开通 `YOUTUBE_API_KEY` 的主要目的，是提升 `L2` 的频道资料补全质量。

优先补全的字段：

- `followers_count`
- `statuses_count`
- `bio`
- `profile_url`
- `verified`

## 开通步骤

1. 登录你的 Google 账号，进入 [Google Cloud Console](https://console.cloud.google.com/).
2. 创建一个新的项目，或者选一个专门给 YouTube KOL skill 用的项目。
3. 在项目里打开 [YouTube Data API v3](https://developers.google.com/youtube/v3/getting-started)。
4. 进入 `APIs & Services -> Credentials`。
5. 点击 `Create credentials -> API key`。
6. 创建后，立刻给这把 key 加 restriction。

## 推荐 restriction

建议至少做这两层限制：

- `API restrictions`
  - 只允许 `YouTube Data API v3`
- `Application restrictions`
  - 如果只是本机本 skill 使用，先用 unrestricted 也可以
  - 但长期建议改成你能控制的来源限制

不要把 unrestricted key 长期暴露在公共环境里。

## 本地接入方式

当前 skill 读取的环境变量名是：

```bash
YOUTUBE_API_KEY
```

你可以先临时这样验证：

```bash
export YOUTUBE_API_KEY='你的_key'
```

如果后面确认长期使用，再把它写进统一 secrets env。

## 当前与后续关系

- 现在优先解决 `YOUTUBE_API_KEY`
- 之后再把 `scrapecreator` 的 fallback env 软连接接进来
- `scrapecreator` 的 secrets 源将设计为软连接到：
  - `${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env`

## 官方参考

- [YouTube Data API Overview](https://developers.google.com/youtube/v3/getting-started)
- [Manage API keys](https://cloud.google.com/docs/authentication/api-keys)
