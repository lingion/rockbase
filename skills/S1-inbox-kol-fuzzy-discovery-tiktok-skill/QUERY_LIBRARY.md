# Query Keyword Matrix Library

用于沉淀 `S1-inbox-kol-fuzzy-discovery-tiktok-skill` 的 query 方法论、历史 query 资产与去重经验。

---

## Part 1. 基本原则与方法

### 1.1 目标

这个 library 用来固定 TikTok 的 `search-first hot-content-led KOL mining` 方法，而不是记录一次性 runlog。

### 1.2 TikTok 的 query 原则

TikTok 的搜索逻辑依然是：

- 先找热视频或高信号 topic 内容
- 再聚合背后的 creator
- 再做 L2 profile enrichment

标准模板：

```text
"{TOPIC}" ({AI_LOCK}) ({INTENT_OR_SIGNAL}) -{NEG_1} -{NEG_2}
```

### 1.3 Query Group 建议

| Query Group | 用途 |
| --- | --- |
| `Core` | 锁定 topic 主讨论面 |
| `Workflow` | 找真实使用场景 |
| `Builder` | 找 builder / founder / engineer |
| `Content` | 找教程、测评、demo 型 creator |
| `Compare` | 找对比型、评测型 creator |
| `Trend` | 找高传播、跟热点的人 |

### 1.4 去重规则

- 轻微 wording 变化优先复用旧 `Query Name`
- 只有搜索意图真正改变时才新增 `Query Name`
- 记录每条 query 的净新增 creator 表现，而不仅是 result count

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
| `2026-04-10` | `Workflow` | `cc_workflow` | `"Claude Code" (workflow OR automation OR "use case" OR productivity OR systems) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Trend` | `cc_agentic` | `"Claude Code" (agents OR agentic OR multi-agent OR orchestration OR worktree) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |

## Part 3. 当前维护要求

- 先更新 `QUERY_LIBRARY.md`，再写 spec
- session / proxy 导致的阻塞也应回填到 `Notes`
- 对 TikTok 来说，`Result Count` 之外还要记录 `net-new creator yield`
