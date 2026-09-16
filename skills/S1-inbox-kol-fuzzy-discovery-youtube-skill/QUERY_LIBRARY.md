# Query Keyword Matrix Library

用于沉淀 `S1-inbox-kol-fuzzy-discovery-youtube-skill` 的 query 方法论、历史 query 资产与去重经验。

---

## Part 1. 基本原则与方法

### 1.1 目标

这个 library 不是单次 runlog 归档，而是一个可持续更新的 `query 关键词矩阵`：

- 上半部分沉淀方法论
- 下半部分按 topic 持续累计历史 query 记录
- 新 campaign 先更新本文件，再生成 spec，再执行 run

### 1.2 Query 设计原则

YouTube 默认采用：

```text
"核心 topic" + AI Lock + Creator Intent + Expansion Signal + Negative Keywords
```

标准模板：

```text
"{TOPIC}" ({AI_LOCK}) ({INTENT_OR_SIGNAL}) -{NEG_1} -{NEG_2} -{NEG_3}
```

说明：

- `AI Lock` 用来防止 query 跑偏
- `Creator Intent` 用来锁定你要找的 KOL 类型
- `Expansion Signal` 用来扩大覆盖、提高发现热内容的概率
- `Negative Keywords` 单独管理，不和核心词池混在一起

### 1.3 YouTube 的搜索逻辑

YouTube skill 的 `L1` 不是平台 discover 榜优先，而是：

- 先搜大量热视频
- 再把这些热视频聚合回 channel / creator
- 再用 `view_count` 做准入门槛

### 1.4 推荐的 Query Matrix 结构

| Query Group | 用途 | 典型词 |
| --- | --- | --- |
| `Core` | 起盘，锁定 topic 主讨论面 | `AI`, `LLM`, `AI tools`, `generative AI`, `AI agents` |
| `Workflow` | 找真实使用场景 | `workflow`, `automation`, `use case`, `productivity`, `research` |
| `Builder` | 找 builder / founder / engineer | `builder`, `founder`, `engineer`, `researcher`, `creator` |
| `Content` | 找能产出内容的 creator | `tutorial`, `review`, `demo`, `walkthrough`, `comparison` |
| `Compare` | 找有决策影响力的人 | `compare`, `comparison`, `vs`, `alternative`, `tested` |
| `Stack` | 找会公开比较工具栈的人 | `Cursor`, `Codex`, `Cline`, `IDE`, `terminal` |

### 1.5 去重规则

- 同一主题下，优先复用已有 `Query Name`
- 新增 `Query Name` 之前，先检查是否只是旧 query 的轻微变体
- 轻微变体优先记为同一 `Query Name` 的新 `Date / Query Text / Notes`
- 只有当搜索意图真正不同，才新增新的 `Query Name`

### 1.6 执行顺序

固定顺序：

1. 更新 `QUERY_LIBRARY.md`
2. 生成或修改 `spec`
3. 执行 `L1`
4. 回填实际结果和去重观察

---

## Part 2. Query Keyword History Library

### 2.1 `Generic AI`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-10` | `Core` | `topic_core` | `"AI" ("AI tools" OR LLM OR "generative AI" OR "AI agents") -crypto -trader -airdrop` | `yt-dlp` | `pending_backfill` | default pack |
| `2026-04-10` | `Workflow` | `topic_workflow` | `"AI" (workflow OR automation OR "use case" OR productivity OR research) -crypto -trader -airdrop` | `yt-dlp` | `pending_backfill` | default pack |
| `2026-04-10` | `Builder` | `topic_roles` | `"AI" (builder OR founder OR engineer OR researcher OR creator) -crypto -trader -airdrop` | `yt-dlp` | `pending_backfill` | default pack |
| `2026-04-10` | `Content` | `topic_content` | `"AI" (tutorial OR review OR demo OR walkthrough OR comparison) -crypto -trader -airdrop` | `yt-dlp` | `pending_backfill` | default pack |

### 2.2 `Claude Code`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-10` | `Core` | `cc_core` | `"Claude Code" ("AI coding" OR coding OR developer OR engineering OR terminal) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Workflow` | `cc_workflow` | `"Claude Code" (workflow OR automation OR "use case" OR productivity OR systems) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Content` | `cc_tutorial` | `"Claude Code" (tutorial OR walkthrough OR guide OR demo OR setup) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |
| `2026-04-10` | `Stack` | `cc_stack` | `"Claude Code" (Cursor OR Codex OR Cline OR Warp OR IDE OR terminal) -crypto -trader -airdrop` | `planned` | `pending_run` | inherited from X methodology |

### 2.3 `Accio (AI Sourcing / Ecom)`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-10` | `Core` | `accio_core` | `"Accio" ("AI sourcing" OR sourcing OR "product sourcing" OR "supplier") -harry -potter -magic -spell` | `planned` | `pending_run` | accio core lock |
| `2026-04-10` | `Workflow` | `accio_ecom_workflow` | `"Accio" ("ecommerce" OR "product research" OR "product selection" OR "supplier match") -harry -potter -magic -spell` | `planned` | `pending_run` | ecom workflow |
| `2026-04-10` | `Content` | `accio_review_demo` | `"Accio" (review OR demo OR tutorial OR walkthrough OR comparison) -harry -potter -magic -spell` | `planned` | `pending_run` | creator intent |
| `2026-04-10` | `Compare` | `accio_compare_alt` | `"Accio" (alternative OR vs OR comparison OR "Alibaba" OR "B2B sourcing") -harry -potter -magic -spell` | `planned` | `pending_run` | competitor framing |
| `2026-04-10` | `Workflow` | `accio_supplier_ops` | `"Accio" ("supplier" OR "wholesale" OR "procurement" OR "RFQ") -harry -potter -magic -spell` | `planned` | `pending_run` | sourcing ops |

## Part 2.4 `Airtap / Batch 01 / Costco Amazon Money Return`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Core` | `airtap_b1_refund_core` | `("Amazon refund" OR "Costco return") (tips OR hack OR policy OR trick) -news -commercial -ads` | `yt-dlp` | `pending_run` | refund / return core discovery |
| `2026-05-11` | `Workflow` | `airtap_b1_shopping_hacks` | `("shopping hacks" OR "save money shopping") (Amazon OR Costco OR grocery OR household) -news -commercial -ads` | `yt-dlp` | `pending_run` | practical shopping systems |
| `2026-05-11` | `Content` | `airtap_b1_cashback_budget` | `("cashback tips" OR "budget shopping" OR couponing) (Amazon OR Costco OR household) -news -commercial -ads` | `yt-dlp` | `pending_run` | money-saving creator language |
| `2026-05-11` | `Creator` | `airtap_b1_frugal_living` | `("frugal living" OR "money saving tips") (shopping OR household OR groceries) -news -commercial -ads` | `yt-dlp` | `pending_run` | adjacent creator niche |
| `2026-05-11` | `Expansion` | `airtap_b1_consumer_hacks` | `("consumer hacks" OR "smart shopping") (refund OR return OR savings) -news -commercial -ads` | `yt-dlp` | `pending_run` | expansion for creator-language overlap |
| `2026-05-11` | `Expansion` | `airtap_b1_coupon_deals` | `("couponing" OR deals OR "shopping deals") (Amazon OR Costco) -news -commercial -ads` | `yt-dlp` | `pending_run` | deal-seeking audience overlap |

## Part 2.5 `Airtap / Batch 02 / Prescription Refill For Parents`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Core` | `airtap_b2_caregiver_core` | `("caregiver tips" OR "elder care" OR caregiving) (parents OR family OR medication) -news -commercial -ads` | `yt-dlp` | `pending_run` | caregiver and parent support entrypoint |
| `2026-05-11` | `Workflow` | `airtap_b2_prescription_workflow` | `("prescription refill" OR "medication management" OR pharmacy) (parents OR seniors OR family) -news -commercial -ads` | `yt-dlp` | `pending_run` | refill and medication workflow creators |
| `2026-05-11` | `Workflow` | `airtap_b2_family_admin` | `("family admin" OR "adulting systems" OR "caregiver routines") (health OR parents OR family) -news -commercial -ads` | `yt-dlp` | `pending_run` | family organizer systems language |
| `2026-05-11` | `Expansion` | `airtap_b2_healthcare_navigation` | `("healthcare workflow" OR "healthcare navigation" OR "caregiving support") (family OR seniors OR parents) -news -commercial -ads` | `yt-dlp` | `pending_run` | healthcare admin simplification |
| `2026-05-11` | `Expansion` | `airtap_b2_elder_care_systems` | `("elder care systems" OR "caregiver help" OR "family management") (routine OR workflow OR tips) -news -commercial -ads` | `yt-dlp` | `pending_run` | adjacent elder-care workflow overlap |

## Part 2.6 `Airtap / Batch 03 / Find Restaurant And Reserve`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Core` | `airtap_b3_restaurant_core` | `("restaurant reservation" OR "where to eat" OR "restaurant finder") (city OR date OR guide) -news -commercial -ads` | `yt-dlp` | `pending_run` | convenience-led restaurant decision content |
| `2026-05-11` | `Creator` | `airtap_b3_city_food_guide` | `("city food guide" OR "food spots" OR "local guide") (restaurant OR city OR neighborhood) -news -commercial -ads` | `yt-dlp` | `pending_run` | local guide creators with practical selection signal |
| `2026-05-11` | `Creator` | `airtap_b3_date_night` | `("date night ideas" OR "date night planning") (restaurant OR city OR dinner) -news -commercial -ads` | `yt-dlp` | `pending_run` | fast social-planning creators |
| `2026-05-11` | `Expansion` | `airtap_b3_weekend_plans` | `("things to do in" OR "weekend plans") (food OR restaurant OR city) -news -commercial -ads` | `yt-dlp` | `pending_run` | broader convenience and urban-planner overlap |
| `2026-05-11` | `Expansion` | `airtap_b3_city_hacks` | `("city hacks" OR convenience OR shortcuts) (restaurant OR food OR reservation) -news -commercial -ads` | `yt-dlp` | `pending_run` | shortcut-oriented urban workflow language |

## Part 2.7 `Airtap / Batch 04 / Weekly Grocery Shopping`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Core` | `airtap_b4_grocery_core` | `("weekly grocery shopping" OR "grocery planning") (routine OR budget OR family) -news -commercial -ads` | `yt-dlp` | `pending_run` | direct grocery workflow discovery |
| `2026-05-11` | `Workflow` | `airtap_b4_meal_prep` | `("meal prep workflow" OR "meal prep") (grocery OR weekly OR routine) -news -commercial -ads` | `yt-dlp` | `pending_run` | meal-prep-first household systems creators |
| `2026-05-11` | `Creator` | `airtap_b4_home_systems` | `("home systems" OR "weekly reset" OR "home organization") (grocery OR meal OR routine) -news -commercial -ads` | `yt-dlp` | `pending_run` | household optimization and reset routines |
| `2026-05-11` | `Expansion` | `airtap_b4_budget_groceries` | `("budget groceries" OR "save money grocery shopping") (family OR weekly OR shopping) -news -commercial -ads` | `yt-dlp` | `pending_run` | low-mental-load and savings angle |
| `2026-05-11` | `Expansion` | `airtap_b4_working_adult_routine` | `("working adult routine" OR "busy adult life hacks") (grocery OR meal prep OR home) -news -commercial -ads` | `yt-dlp` | `pending_run` | busy professional routine overlap |

## Part 2.8 `Airtap / Batch 05 / Save Duolingo Streak`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Core` | `airtap_b5_duolingo_core` | `("Duolingo streak" OR Duolingo) (tips OR habit OR routine) -news -commercial -ads` | `yt-dlp` | `pending_run` | direct Duolingo streak discovery |
| `2026-05-11` | `Workflow` | `airtap_b5_language_habit` | `("language learning habit" OR "language learning tips") (daily OR routine OR streak) -news -commercial -ads` | `yt-dlp` | `pending_run` | language learning systems angle |
| `2026-05-11` | `Creator` | `airtap_b5_habit_building` | `("habit building" OR "daily habits" OR "micro habits") (app OR learning OR routine) -news -commercial -ads` | `yt-dlp` | `pending_run` | app habit and consistency creators |
| `2026-05-11` | `Expansion` | `airtap_b5_streak_motivation` | `("streak motivation" OR streak OR consistency) (learning OR app OR study) -news -commercial -ads` | `yt-dlp` | `pending_run` | streak culture and consistency overlap |
| `2026-05-11` | `Expansion` | `airtap_b5_study_routine` | `("study routine" OR "self improvement apps") (language OR daily OR habit) -news -commercial -ads` | `yt-dlp` | `pending_run` | adjacent self-improvement routine creators |

## Part 2.9 `Airtap / Batch 06 / Find A Job LinkedIn Tracking`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Core` | `airtap_b6_linkedin_core` | `("LinkedIn job search" OR LinkedIn) (job OR application OR tips) -news -commercial -ads` | `yt-dlp` | `pending_run` | direct LinkedIn discovery |
| `2026-05-11` | `Workflow` | `airtap_b6_job_workflow` | `("job application workflow" OR "job tracker" OR "find a job fast") -news -commercial -ads` | `yt-dlp` | `pending_run` | application tracking and job ops creators |
| `2026-05-11` | `Creator` | `airtap_b6_career_tips` | `("career tips" OR "job search tips" OR "career advice") (resume OR interview OR application) -news -commercial -ads` | `yt-dlp` | `pending_run` | career-ops creator language |
| `2026-05-11` | `Expansion` | `airtap_b6_resume_help` | `("resume help" OR "interview prep" OR "career switch") (job OR LinkedIn OR application) -news -commercial -ads` | `yt-dlp` | `pending_run` | adjacent application support angle |
| `2026-05-11` | `Expansion` | `airtap_b6_layoff_transition` | `("laid off" OR "what next" OR transition) (job search OR career) -news -commercial -ads` | `yt-dlp` | `pending_run` | layoff-to-reemployment workflow overlap |

## Part 3. 当前维护要求

- 每次新的 `Query Name` 必须先写进本文件，再进入 spec
- 每次 run 后应把真实 provider、result count、去重观察回填
- 若某条 query 长期高重合、低净新增，应在 `Notes` 标记为弱 query

## Part 4. 2026-04-24 `Brazil / Mexico AI Coding Agents`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-04-24` | `Core` | `br_codex_core` | `"Codex" (tutorial OR review OR demo OR workflow) (Brasil OR Brazil OR português) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Brazil coding creator discovery |
| `2026-04-24` | `Core` | `br_claude_code_core` | `"Claude Code" (tutorial OR review OR demo OR workflow) (Brasil OR Brazil OR português) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Brazil coding creator discovery |
| `2026-04-24` | `Core` | `br_openclaw_core` | `"OpenClaw" (tutorial OR review OR demo OR workflow) (Brasil OR Brazil OR português) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Brazil coding creator discovery |
| `2026-04-24` | `Core` | `br_hermes_agent_core` | `"Hermes Agent" (tutorial OR review OR demo OR workflow) (Brasil OR Brazil OR português) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Brazil coding creator discovery |
| `2026-04-24` | `Workflow` | `br_ai_agents_builder` | `("AI agents" OR "AI coding") (builder OR developer OR automation OR tutorial) (Brasil OR Brazil OR português) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Brazil expansion for sparse brand coverage |
| `2026-04-24` | `Compare` | `br_ai_coding_compare` | `("Codex" OR "Claude Code") (vs OR comparison OR alternative) (Brasil OR Brazil OR português) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Brazil compare intent |
| `2026-04-24` | `Core` | `mx_codex_core` | `"Codex" (tutorial OR review OR demo OR workflow) (Mexico OR México OR español) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Mexico coding creator discovery |
| `2026-04-24` | `Core` | `mx_claude_code_core` | `"Claude Code" (tutorial OR review OR demo OR workflow) (Mexico OR México OR español) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Mexico coding creator discovery |
| `2026-04-24` | `Core` | `mx_openclaw_core` | `"OpenClaw" (tutorial OR review OR demo OR workflow) (Mexico OR México OR español) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Mexico coding creator discovery |
| `2026-04-24` | `Core` | `mx_hermes_agent_core` | `"Hermes Agent" (tutorial OR review OR demo OR workflow) (Mexico OR México OR español) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Mexico coding creator discovery |
| `2026-04-24` | `Workflow` | `mx_ai_agents_builder` | `("AI agents" OR "AI coding") (builder OR developer OR automation OR tutorial) (Mexico OR México OR español) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Mexico expansion for sparse brand coverage |
| `2026-04-24` | `Compare` | `mx_ai_coding_compare` | `("Codex" OR "Claude Code") (vs OR comparison OR alternative) (Mexico OR México OR español) -crypto -trader -airdrop` | `yt-dlp` | `pending_run` | Mexico compare intent |
| `2026-04-24` | `Local` | `br_claude_code_pt_local` | `"Claude Code" (tutorial OR curso OR guia OR programação OR programador) (Brasil OR brasileiro OR português)` | `yt-dlp` | `pending_run` | Brazil local-language compression |
| `2026-04-24` | `Local` | `br_codex_pt_local` | `"Codex" (tutorial OR curso OR guia OR programação OR programador) (Brasil OR brasileiro OR português)` | `yt-dlp` | `pending_run` | Brazil local-language compression |
| `2026-04-24` | `Local` | `br_ai_agents_pt_local` | `("agentes de IA" OR "IA para programadores" OR "IA para dev") (tutorial OR automação OR produtividade) (Brasil OR português)` | `yt-dlp` | `pending_run` | Brazil local-language expansion |
| `2026-04-24` | `Local` | `br_devtools_pt_compare` | `("Claude Code" OR "Codex") (comparação OR versus OR vale a pena) (Brasil OR português)` | `yt-dlp` | `pending_run` | Brazil local compare |
| `2026-04-24` | `Local` | `mx_claude_code_es_local` | `"Claude Code" (tutorial OR curso OR guía OR programacion OR programador) (México OR mexicano OR español)` | `yt-dlp` | `pending_run` | Mexico local-language compression |
| `2026-04-24` | `Local` | `mx_codex_es_local` | `"Codex" (tutorial OR curso OR guía OR programacion OR programador) (México OR mexicano OR español)` | `yt-dlp` | `pending_run` | Mexico local-language compression |
| `2026-04-24` | `Local` | `mx_ai_agents_es_local` | `("agentes de IA" OR "IA para programadores" OR "IA para devs") (tutorial OR automatización OR productividad) (México OR español)` | `yt-dlp` | `pending_run` | Mexico local-language expansion |
| `2026-04-24` | `Local` | `mx_devtools_es_compare` | `("Claude Code" OR "Codex") (comparativa OR versus OR vale la pena) (México OR español)` | `yt-dlp` | `pending_run` | Mexico local compare |
| `2026-04-24` | `Geo` | `mx_claude_code_geo` | `"Claude Code" ("México" OR CDMX OR mexicano OR "programadores mexicanos") (tutorial OR curso OR guía)` | `yt-dlp` | `pending_run` | Mexico geo-tight query |
| `2026-04-24` | `Geo` | `mx_codex_geo` | `"Codex" ("México" OR CDMX OR mexicano OR "programadores mexicanos") (tutorial OR curso OR guía)` | `yt-dlp` | `pending_run` | Mexico geo-tight query |
| `2026-04-24` | `Geo` | `mx_ai_agents_geo` | `("agentes de IA" OR "IA para programadores") ("México" OR CDMX OR mexicano) (tutorial OR productividad OR automatización)` | `yt-dlp` | `pending_run` | Mexico geo-tight AI agents |
| `2026-04-24` | `Geo` | `mx_devtools_geo_compare` | `("Claude Code" OR "Codex") ("México" OR CDMX OR mexicano) (comparativa OR versus OR "vale la pena")` | `yt-dlp` | `pending_run` | Mexico geo-tight compare |
| `2026-04-24` | `Geo` | `mx_founder_builder_geo` | `("IA" OR "inteligencia artificial") (emprendedor OR fundador OR desarrollador) ("México" OR Monterrey OR Guadalajara OR CDMX)` | `yt-dlp` | `pending_run` | Mexico local founder/builder expansion |
| `2026-04-24` | `Geo` | `mx_ai_business_geo` | `("automatizaciones con IA" OR "negocio con IA") ("México" OR mexicano OR CDMX) (tutorial OR caso de uso)` | `yt-dlp` | `pending_run` | Mexico business/agency local expansion |

## Part 5. 2026-05-11 `Aully Hub`

| Date | Query Group | Query Name | Query Text | Provider | Result Count | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-05-11` | `Creator` | `aully_creator_research` | `("content creator" OR YouTuber OR podcaster OR newsletter) (research OR analysis OR workflow OR productivity) ("AI" OR tools) -crypto -trader -airdrop` | `planned` | `pending_run` | Aully creator research angle |
| `2026-05-11` | `Creator` | `aully_creator_productivity` | `("creator workflow" OR "content workflow" OR "creator productivity") ("AI tools" OR research OR planning) -crypto -trader -airdrop` | `planned` | `pending_run` | creator systems angle |
| `2026-05-11` | `Creator` | `aully_creator_ai_workflow` | `("AI for creators" OR "content research" OR "content planning") (tutorial OR demo OR workflow) -crypto -trader -airdrop` | `planned` | `pending_run` | creator AI assist angle |
| `2026-05-11` | `Creator` | `aully_creator_business_ops` | `("creator business" OR "audience growth" OR newsletter OR podcast) (systems OR workflow OR productivity) -crypto -trader -airdrop` | `planned` | `pending_run` | creator ops angle |
| `2026-05-11` | `RealEstate` | `aully_real_estate_analysis` | `("real estate" OR realtor OR broker) ("market analysis" OR comps OR research) ("AI" OR tools OR workflow) -crypto -trader -airdrop` | `planned` | `pending_run` | real estate research angle |
| `2026-05-11` | `RealEstate` | `aully_real_estate_workflow` | `("real estate workflow" OR "realtor productivity" OR "agent systems") (tutorial OR tools OR automation) -crypto -trader -airdrop` | `planned` | `pending_run` | realtor systems angle |
| `2026-05-11` | `RealEstate` | `aully_property_research` | `("property research" OR "listing analysis" OR "deal analysis") (realtor OR investor OR agent) -crypto -trader -airdrop` | `planned` | `pending_run` | property diligence angle |
| `2026-05-11` | `RealEstate` | `aully_lead_gen_real_estate` | `("real estate lead generation" OR "real estate CRM" OR "agent productivity") (workflow OR tools OR systems) -crypto -trader -airdrop` | `planned` | `pending_run` | pipeline and CRM angle |
| `2026-05-11` | `HR` | `aully_recruiting_workflow` | `("recruiting workflow" OR "talent sourcing" OR recruiter) ("AI" OR tools OR productivity) -crypto -trader -airdrop` | `planned` | `pending_run` | recruiting workflow angle |
| `2026-05-11` | `HR` | `aully_hr_productivity` | `("HR productivity" OR "people ops" OR "talent acquisition") (workflow OR systems OR automation) -crypto -trader -airdrop` | `planned` | `pending_run` | HR ops angle |
| `2026-05-11` | `HR` | `aully_candidate_research` | `("candidate research" OR "resume screening" OR "hiring workflow") (recruiter OR HR OR sourcer) -crypto -trader -airdrop` | `planned` | `pending_run` | screening and research angle |
| `2026-05-11` | `HR` | `aully_recruiter_tools` | `("recruiter tools" OR "sourcing tools" OR "hiring tools") (demo OR tutorial OR comparison) -crypto -trader -airdrop` | `planned` | `pending_run` | tooling angle |
| `2026-05-11` | `Investment` | `aully_investment_research` | `("investment research" OR "equity research" OR analyst) (workflow OR analysis OR productivity) -crypto -airdrop` | `planned` | `pending_run` | analyst research angle |
| `2026-05-11` | `Investment` | `aully_market_mapping` | `("market analysis" OR "industry analysis" OR "market mapping") (investor OR analyst OR VC) -crypto -airdrop` | `planned` | `pending_run` | market mapping angle |
| `2026-05-27` | `Investment` | `aully_due_diligence` | `("due diligence" OR "investment memo" OR "company research") (investor OR analyst OR VC) -crypto -airdrop` | `planned` | `pending_run` | diligence and memo workflow angle |
| `2026-05-27` | `Investment` | `aully_investor_workflow` | `("investment workflow" OR "analyst productivity" OR "thesis building") (tutorial OR workflow OR tools) -crypto -airdrop` | `planned` | `pending_run` | investor workflow systems angle |
| `2026-05-11` | `Investment` | `aully_due_diligence` | `("due diligence" OR "investment memo" OR "company research") (investor OR analyst OR VC) -crypto -airdrop` | `planned` | `pending_run` | diligence angle |
| `2026-05-11` | `Investment` | `aully_vc_workflow` | `("VC workflow" OR "venture capital research" OR "startup analysis") (tools OR workflow OR productivity) -crypto -airdrop` | `planned` | `pending_run` | VC workflow angle |
| `2026-05-13` | `Creator` | `aully_creator_newsletter_systems` | `("newsletter workflow" OR "newsletter growth" OR "newsletter system") (research OR productivity OR "AI tools" OR planning) -crypto -trader -airdrop` | `planned` | `pending_run` | creator newsletter systems expansion |
| `2026-05-13` | `Creator` | `aully_creator_podcast_workflow` | `("podcast workflow" OR "podcast research" OR "podcast production") ("AI tools" OR productivity OR planning OR systems) -crypto -trader -airdrop` | `planned` | `pending_run` | creator podcast ops expansion |
| `2026-05-13` | `Creator` | `aully_creator_personal_brand_systems` | `("personal brand" OR solopreneur OR "creator economy") ("AI tools" OR workflow OR research OR systems) -crypto -trader -airdrop` | `planned` | `pending_run` | personal-brand operator expansion |
| `2026-05-13` | `Creator` | `aully_creator_content_strategy` | `("content strategy" OR "audience strategy" OR "content systems") (creator OR newsletter OR youtube OR podcast) -crypto -trader -airdrop` | `planned` | `pending_run` | creator strategy expansion |
| `2026-05-13` | `RealEstate` | `aully_real_estate_wholesaling_ops` | `("real estate wholesaling" OR wholesaler OR "investor workflow") (CRM OR systems OR automation OR outreach) -crypto -trader -airdrop` | `planned` | `pending_run` | wholesaling operator expansion |
| `2026-05-13` | `RealEstate` | `aully_real_estate_underwriting` | `("real estate underwriting" OR "deal underwriting" OR "rental analysis") (investor OR multifamily OR property) -crypto -trader -airdrop` | `planned` | `pending_run` | underwriting analysis expansion |
| `2026-05-13` | `RealEstate` | `aully_real_estate_proptech_tools` | `("proptech" OR "real estate tools" OR "broker tools") (workflow OR demo OR review OR automation) -crypto -trader -airdrop` | `planned` | `pending_run` | proptech workflow expansion |
| `2026-05-13` | `RealEstate` | `aully_real_estate_investor_research` | `("real estate investing" OR "property investing") ("market research" OR analysis OR due diligence OR workflow) -crypto -trader -airdrop` | `planned` | `pending_run` | investor-research expansion |
| `2026-05-13` | `HR` | `aully_recruiter_boolean_sourcing` | `("boolean search" OR "candidate sourcing" OR "sourcing strategy") (recruiter OR "talent acquisition" OR sourcer) -crypto -trader -airdrop` | `planned` | `pending_run` | sourcing workflow expansion |
| `2026-05-13` | `HR` | `aully_recruitment_automation_ops` | `("recruitment automation" OR "ATS workflow" OR "screening automation") ("AI" OR tools OR workflow) -crypto -trader -airdrop` | `planned` | `pending_run` | recruitment automation expansion |
| `2026-05-13` | `HR` | `aully_interview_ops_systems` | `("interview workflow" OR "interview process" OR "interview coordination") (recruiter OR hiring OR talent) -crypto -trader -airdrop` | `planned` | `pending_run` | interview ops expansion |
| `2026-05-13` | `HR` | `aully_talent_acquisition_systems` | `("talent acquisition" OR "people operations" OR "hiring operations") (systems OR workflow OR automation) -crypto -trader -airdrop` | `planned` | `pending_run` | talent-acquisition systems expansion |
| `2026-05-13` | `Investment` | `aully_equity_research_process` | `("equity research" OR "stock analysis" OR "fundamental analysis") ("research process" OR workflow OR checklist) -crypto -airdrop` | `planned` | `pending_run` | equity-research process expansion |
| `2026-05-13` | `Investment` | `aully_investment_thesis_workflow` | `("investment thesis" OR "company analysis" OR "industry thesis") (investor OR analyst OR VC) -crypto -airdrop` | `planned` | `pending_run` | thesis-building expansion |
| `2026-05-13` | `Investment` | `aully_startup_vc_diligence` | `("startup due diligence" OR "venture diligence" OR "startup research") (VC OR investor OR angel) -crypto -airdrop` | `planned` | `pending_run` | startup diligence expansion |
| `2026-05-13` | `Investment` | `aully_angel_investing_workflow` | `("angel investing" OR "startup investing") (workflow OR memo OR analysis OR research) -crypto -airdrop` | `planned` | `pending_run` | angel-investing workflow expansion |
