# Platform Extraction Notes

这份文档用于沉淀各平台在提取 `账号ID(handle)`、`频道/作者名称(author_name)`、`粉丝数(followers)` 等核心字段时的经验规则。

目的不是替代脚本，而是给脚本设计、执行判断和后续维护提供稳定依据，避免每次都从零回忆。

## 总原则

- 不要只依赖 URL 提取 `账号ID`
- `handle` 和 `author_name` 是两个不同字段，不能混写
- 平台差异很大，必须分别总结和分别实现
- 优先相信主页可见内容，其次才是 URL、meta、fallback
- 当 URL 可用于兜底时，也只能作为兜底，不应覆盖主页已经明确显示的字段

## YouTube 经验

### 1. `账号ID(handle)` 的提取

YouTube 的 `handle` 不能只依赖 URL。

原因：

- 有些 URL 是 `/channel/UC...`
- 有些 URL 是 `/@handle`
- 有些旧链接、视频链接、`/videos` 链接会掩盖真实主页结构
- 用户要求补的是 `账号ID`，而不是“从 URL 猜出来的可能值”

正确做法：

- 优先从频道主页首页可见黑字内容中抓取 `@handle`
- 主页中如能看到 `@...`，优先使用页面内容
- 只有页面拿不到时，才允许从 URL 兜底

### 2. `频道/作者名称(author_name)` 的提取

YouTube 的 `author_name` 应优先从频道主页首页的大黑体标题提取。

经验要点：

- 首页上方的大号黑体字，通常就是频道名
- `@handle` 一般在频道名附近，但两者不是同一个字段
- 不要把 `@handle` 误写进 `author_name`

提取优先级：

1. 首页顶部大号黑体频道名
2. `handle` 附近的频道标题文字
3. 页面标题或 meta 作为兜底

### 3. YouTube 的实现提醒

- 抓 `handle` 时要先看主页内容，再看 URL
- 抓 `author_name` 时要优先看首页顶部视觉最明确的频道名
- `author_name` 和 `handle` 应分别抓取、分别回写

## TikTok 与 Instagram 经验

TikTok 和 Instagram 在这件事上有一个共同点：

- `账号ID(handle)` 相对容易从 URL 获得
- `作者名称(author_name)` 很难从 URL 获得
- `author_name` 必须优先从主页 UI 可见内容提取

这两个平台天然没有 YouTube 那种“频道名称”的概念，更接近“账号 ID + 显示名”结构。

### 1. `账号ID(handle)` 的提取

对于 TikTok / Instagram：

- URL 通常能提供 `handle`
- 但仍建议先校验主页显示内容是否一致
- URL 可作为 `handle` 的重要来源，但不能替代对页面的基本核验

### 2. `作者名称(author_name)` 的提取

对于 TikTok / Instagram：

- `author_name` 不是 URL 里的东西
- 一般出现在主页上 `handle` 的右边、下方或相邻位置的小字
- 应从主页 UI 可见位置提取，而不是从 URL 推测

正确做法：

- 先识别主页上的 `handle`
- 再在它相邻区域寻找显示名/作者名
- 优先取主页明确展示的小字作者名

错误做法：

- 把 URL 中的 `handle` 直接当 `author_name`
- 把 `handle` 原样复制到 `author_name`

## 平台差异结论

### YouTube

- `handle`：主页内容优先，URL 只兜底
- `author_name`：首页顶部大黑体频道名优先

### TikTok

- `handle`：URL 可辅助，但要结合主页显示核验
- `author_name`：主页中 `handle` 邻近的小字显示名优先

### Instagram

- `handle`：URL 可辅助，但要结合主页显示核验
- `author_name`：主页中 `handle` 邻近的小字显示名优先

## 对脚本设计的要求

这些经验应体现在 extractor 设计里：

- `youtube.py`
  必须区分 `handle` 抓取逻辑和 `author_name` 抓取逻辑
- `tiktok.py`
  必须显式区分 URL-derived handle 和 UI-derived author name
- `instagram.py`
  必须显式区分 URL-derived handle 和 UI-derived author name

主脚本不应该把这些经验揉成统一逻辑，而应让各平台 extractor 分别实现。

## 对执行时的提醒

当用户要求补以下字段时：

- `账号ID`
- `频道/作者名称`

系统应始终优先检查：

- 是否把 `handle` 和 `author_name` 混淆了
- 是否过度依赖 URL
- 是否错误地把同一个值写进了两个字段

这份文档的作用，就是避免上述错误反复发生。
