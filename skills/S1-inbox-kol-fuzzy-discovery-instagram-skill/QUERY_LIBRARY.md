# Query Keyword Matrix Library

用于沉淀 `S1-inbox-kol-fuzzy-discovery-instagram-skill` 的 query 方法论、历史 query 资产与去重经验。

---

## Part 1. 基本原则与方法

### 1.1 目标

Instagram 的 query library 主要服务于：

- 通过 topic / hashtag / caption 搜高信号内容
- 再从内容反推 profile
- 用于后续 L2 联系方式补全

### 1.2 Instagram 的 query 原则

Instagram 不适合假设有一个天然稳定的“全站热榜”，所以 query matrix 更强调：

- topic lock
- hashtag / caption relevance
- content style relevance

标准模板：

```text
"{TOPIC}" ({AI_LOCK}) ({HASHTAG_OR_INTENT}) -{NEG_1} -{NEG_2}
```

### 1.3 Query Group 建议

| Query Group | 用途 |
| --- | --- |
| `Core` | 锁定 topic 主讨论面 |
| `Workflow` | 找真实使用场景 |
| `Builder` | 找 builder / founder / engineer |
| `Content` | 找教程、测评、carousel/reels 型 creator |
| `Compare` | 找对比型内容 |
| `Hashtag` | 找高信号 hashtag/topic cluster |

### 1.4 去重规则

- 优先复用既有 `Query Name`
- 同一意图的 hashtag 变体尽量并入同一个 query family
- 不要因为平台字段不同就放弃记录 query 的去重经验

---

## Part 2. Query Keyword History Library

### 2.1 `Generic AI`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-10` | `Core` | `topic_core` | `"AI" ("AI tools" OR LLM OR "AI agents" OR automation) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Workflow` | `topic_workflow` | `"AI" (workflow OR automation OR "use case" OR productivity OR research) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Content` | `topic_content` | `"AI" (tutorial OR review OR demo OR walkthrough OR comparison) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |

### 2.2 `Claude Code`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-10` | `Core` | `cc_core` | `"Claude Code" ("AI coding" OR coding OR developer OR engineering OR terminal) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Content` | `cc_tutorial` | `"Claude Code" (tutorial OR walkthrough OR guide OR demo OR setup) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Hashtag` | `cc_stack` | `"Claude Code" (Cursor OR Codex OR Cline OR IDE OR terminal) -crypto -trader -airdrop` | `planned` | `pending_run` | used for hashtag / caption expansion |

## Part 3. 当前维护要求

- 先更新 `QUERY_LIBRARY.md`，再写 spec
- 对 Instagram 来说，`Result Count` 之外最好记录 `caption relevance` 和 `net-new creator yield`

### 2.3 `Accio`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-10` | `Core` | `brand_core` | `accio` | `scrapecreators.instagram.reels_search` | `10` | first validated keyword-content route |
| `2026-04-10` | `Content` | `brand_review` | `accio review` | `planned` | `pending_run` | round2 api search |
| `2026-04-10` | `AI Lock` | `brand_ai` | `accio ai` | `planned` | `pending_run` | round2 api search |
