---
description: "[Runner] YouTube KOL fuzzy discovery 总工作流 | 负责 intake、query library、spec、L1/L2/L3、S2 与后续扩展。"
---

# WF_Int

> 这是 `S1-inbox-kol-fuzzy-discovery-youtube-skill` 的默认启动入口。  
> 本文件只负责总 runner，子流程细节统一放到 `WF/` 目录。

## 一、当前默认闭环

默认链路：

```text
自然语言需求
-> Intake
-> QUERY_LIBRARY 更新
-> 当天 spec
-> plan
-> run L1
-> L1 unified / candidates
-> run L2
-> L2 enriched
-> run L3
-> L3 shortlist
-> contact / email enrichment for missing rows
-> LLM entity screen (no manual review)
-> S2 outreach export
-> S2 merge
-> Mail1 fill via Gmail canonical workflow
-> STOP：向用户汇报结果并等待下一步
```

当前已经接上的部分：

- `QUERY_LIBRARY.md`
- `L1 search-first hot-content mining`
- `L1 unified / candidates`
- 一版可运行的 `L2 fallback enrichment`
- `Mail1 fill` 默认衔接到 `../S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`
- YouTube 侧直接转调入口：`src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`

当前仍需继续补强的部分：

- 更正式的 `workbench/{YYYY-MM-DD}/` runner 文件组织
- 更成熟的 `L3 -> S2` 输出
- `scrapecreator fallback` 的 L2 正式链路

## 二、子工作流位置

根目录核心索引：

- `SKILL.md`
- `WF_Int.md`
- `QUERY_LIBRARY.md`

子工作流统一在：

- `WF/L1-WF_youtube_kol_discovery_csv.md`
- `WF/L2-WF_youtube_kol_enrichment_csv.md`
- `WF/L3-WF_youtube_kol_selection_csv.md`
- `WF/L3-WF_to-S2-cold-outreach-mapping.md`
- `WF/L4-WF_youtube_mail1_fill.md`
- `WF/Lx-Field-Matrix_youtube_kol_csv.md`

## 三、Intake 最小字段

Friday 启动后，应优先确认这些字段。若用户已经给出明确值，不要重复追问。

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `KOL平台` | 本次找哪一个平台 | `YouTube` |
| `语言` | 目标语言区 | `en` |
| `热度 / 播放量` | L1 内容门槛 | `1000+ views` |
| `粉丝量` | 进入 shortlist 的最低粉丝量 | `1000+ followers` |
| `帖子覆盖时间` | 搜最近多久的内容 | `过去 7 天` |
| `搜索关键词` | 核心 topic / brand / tool | `Claude Code` |
| `搜索模式` | 默认 search-first | `dual_channel` |
| `执行节奏` | 今天打算跑几次 | `先跑 1 轮，再扩 query` |
| `最终动作` | 先做到哪一层 | `先做到 L2` |

原则：

- 缺少关键字段时才问
- 用户目标明确时直接执行，不让用户替我们写 spec
- 当天主要是 search-first，就不优先追问 discover

## 四、Runner 标准步骤

### Step 1. 更新 QUERY_LIBRARY

先看：

- `QUERY_LIBRARY.md`

规则：

- topic 已存在：复用并微调
- topic 不存在：在 Part 2 新建 topic query matrix
- 有新方法论：回写 Part 1
- spec 里的所有 `search_queries[].name` 必须先在 `QUERY_LIBRARY.md` 中存在
- 严禁先在 spec 里临时发明 `Query Name`，再事后回填 library

### Step 2. 生成当天执行设计

建议在 `/400 🔴 Project/🔴 420 Social Agency/workbench/{YYYY-MM-DD}/YouTube/` 生成：

- spec JSON
- implementation plan
- todo

最低要求：

- spec 要明确 `search_queries`
- 要明确 `l1_mode`
- 要明确 `provider_plan`
- 要明确 `run_date`

### Step 3. 执行 L1

默认入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_layer1_mvp.py \
  --spec specs/_template.youtube_kol_task.json \
  --run-date 2026-04-10
```

完成后必须核对：

- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L1_unified_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L1_candidates_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L1_runlog_{YYYY-MM-DD}.json`

### Step 4. 执行 L2

默认批次规范：

- `L2` 默认按 **20 creators / batch** 执行
- 若 `L1 candidates > 20`，先物理拆分 candidate CSV，再逐批运行 `L2`
- 不默认对大于 `20` 的候选表直接一次性全量跑 `L2`
- `20` 是默认吞吐单位，不只是 smoke/debug 参数
- batch 命名建议使用：`{task_batch}_part1`、`{task_batch}_part2` ...

默认入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_layer2_from_candidates.py \
  --input-csv workbench/2026-04-10/YouTube/youtube_kol_L1_candidates_2026-04-10.csv
```

当前默认补全策略：

1. 先查 `docs/youtube_kol_discovery_master.csv`
2. 命中 master 的 creator 不进入本批 L2 provider
3. 新 creator 优先走 `YouTube Data API`
4. 若 API 不可用，使用当前 fallback enrichment
5. 后续补接 `scrapecreator` 风格的 profile/contact fallback

完成后必须核对：

- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_shortlist_{batch}_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_runlog_{batch}_{YYYY-MM-DD}.json`

整理规则：

- 项目级 `workbench/{YYYY-MM-DD}/YouTube/` 保存 L1/L2 过程文件、raw、runlog、audit、smoke/test 批次
- `deliverables/` 只保存最终可交付 CSV，例如 `【L2_enriched】...`、`【L2_shortlist】...`、`【L2_merged】...`
- 等接上 `S2` 后，`deliverables/` 只保留 `【S2_cold】..._merged_final.csv`，batch 级 `S2` 一律留在 `workbench/`

`S2 merge` 之后进入唯一主表阶段：

- 后续补 email、补历史 overlay、写 `Mail1`、排序、最终 QC，都直接更新 `deliverables/{YYYY-MM-DD}/【S2_cold】..._merged_final.csv`
- 不再平行维护第二份 final
- `workbench` 只保留过程态与审计态副本

### Step 5. 执行 L3

当前目标：

- 先保留 `L3 shortlist` 的结构和字段契约
- 让 `L3` 输出的结构化证据直接进入 LLM entity screen
- 机构号、媒体号、品牌号由 LLM 自动判定，不再走人工 review

规范说明：

- `L3` 负责整理证据，不再输出人工 `review` 处理流
- `LLM` 负责最终 `llm_entity_type / llm_decision / final_decision`
- `L3` 的输出应至少包含：`account_risk_flags / llm_entity_type / llm_confidence / llm_decision / final_decision`
- 正式删除发生在 `L3 -> S2 export`
- `S2 merge` 必须再次执行同样规则兜底，避免旧批次或手工回流把机构号带回最终表

### Step 6. 补 contact / email

默认规则：

- `L3 shortlist` 之后、`S2 base mapping` 之前，必须先检查 missing email
- 补 email 的目标是提升后续触达率，不是把没 email 的人删掉
- 没拿到 email 的行允许继续保留在 `S2`，但 `联系方式` 留空
- 优先使用现有 `L2 enriched` 的 `contact_value / contact_note / external_links / contact_signals`
- 若仍缺 email，优先追加：
  1. `scrapecreators` 已有结果复用
  2. `contact page crawl`
  3. `augment_layer2_contact_crawl.py` 增量补抓

建议入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/augment_layer2_contact_crawl.py \
  --input-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_{YYYY-MM-DD}.csv \
  --output-csv workbench/{YYYY-MM-DD}/YouTube/youtube_kol_L2_enriched_{batch}_contact_crawl_{YYYY-MM-DD}.csv \
  --timeout-seconds 3 \
  --max-urls-per-creator 4
```

### Step 7. 输出 S2

当前目标：

- 先保证 `L1 / L2 / L3` 的结构和字段完整
- 等 YouTube 的 L2 正式跑稳，再把 `L3 -> S2` 固化成默认产物

YouTube deliverable 规则：

- `S2` 是正式 deliverable 出口，不是 review 池
- 机构号、媒体号、品牌号必须在 LLM screen 阶段被拦下
- 命中 `llm_decision = drop`、`final_decision != keep` 的行必须在 `S2 export` 被拦下
- 默认只允许 `deliverable_gate = allowed_keep` 的行进入 `S2`
- `review` 不再是标准处理流的一部分

Mail1 列的进入时点先冻结：

- 不在 `L2` 加 `Mail1` 列
- 不在 `L3 shortlist` 加 `Mail1` 列
- 从 `L3 -> S2 base mapping` 开始，S2 CSV 必须预留：
  - `Mail1发出状态`
  - `Mail1_Hook`
  - `Mail1_Greeting_Name`
  - `Mail1_Subject`
  - `Mail1_Content V1`
  - `Mail1_Content V2`
- 这些列在 `S2 base` 默认留空
- `S2 merge` 只继承这些列
- merge 后再进入 `Mail1 / 3.2 DM fill`

当前最小 runner 已可用：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_l3_to_s2_mapping.py \
  --input-csv workbench/2026-04-10/YouTube/youtube_kol_L2_shortlist_scrapecreator_test_2026-04-10.csv \
  --run-date 2026-04-10 \
  --batch batch1
```

当前阶段允许先把 `L2 shortlist` 视作 `L3 shortlist` 输入，先把 `S2 base` 和 `Mail1` 预留列跑通。

### Step 8. 合并 S2

默认入口：

```bash
PYTHONPATH=src python3 src/youtube_kol_discovery/pipelines/run_merge_s2_deliverables.py \
  --run-date 2026-04-10
```

完成后必须核对：

- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_merged_filtered_{YYYY-MM-DD}.csv`
- `workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_merged_filter_audit_{YYYY-MM-DD}.json`
- `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_youtube_kol_S2_merged_final.csv`

规则：

- `S2 merge` 只做合并、去重、排序、轻量机构号过滤
- 不在 merge 时新增 `Mail1` 字段
- 不在 merge 时填写 `Mail1` 文案
- `Mail1 / 3.2 fill` 是 merge 之后的下一步

### Step 9. Mail1 / Cold Mail Fill

默认 handoff：

- 相对路径：`.agent/skills/S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`
- YouTube 侧 runner：`src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`

执行规则：

- YouTube 的 `S2 merged final` 进入 `Mail1 fill` 后，默认直接复用这个 cold mail workflow
- 不再为 YouTube 单独发明另一套 `Greeting / Hook / Subject / Content` 规则
- YouTube skill 只认 `WF_Cold Mail Run.md` 作为 Mail1 canonical workflow，不再公开引用旧模板名
- YouTube 侧 runner 现在还能继续接 Gmail `prepare_jobs.py -> sample_send.py -> bulk_send.py`
- `Mail1_Content V1` 采用 `Greeting + Hook + 冻结正文` 结构
- `Mail1_Content V2` 采用同一 CTA 骨架下的 creator-specific 版本
- `Subject`、`Greeting`、`Hook` 的生成与正文冻结规则，统一遵循该 workflow

进入条件：

- `联系方式` 非空
- `manual_clean_decision != drop`（若该列存在）
- `email_qc_flag` 不是 `dirty / invalid / suspect`（若该列存在）
- 已完成 `S2 merge`

## 五、YouTube API 与 L2 依赖

当前依赖分两层：

- `L1` 主搜索：
  - `yt-dlp`
  - 不依赖 YouTube API key
- `L2` 资料补全：
  - 优先 `YOUTUBE_API_KEY`
  - 后续 fallback 采用 `scrapecreator` 风格工具

后续设计要求：

- 需要一条 env 软连接，指向：
  - `${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env`
- 用于后续提取 `scrapecreator` 所需 API key
- 但当前优先级仍是先开通 `YOUTUBE_API_KEY`

## 六、完成判定

一个当天任务至少算完成，需要检查：

- `QUERY_LIBRARY` 已更新
- spec 已确定
- `L1 unified` 存在
- `L1 candidates` 存在
- `L2 enriched` 存在
- runlog 存在
- 用户已收到结果汇报，并确认下一步

## 七、修改原则

以后改流程时：

- 总流程顺序改 `WF_Int.md`
- query 方法改 `QUERY_LIBRARY.md`
- L1 细节改 `WF/L1-WF_youtube_kol_discovery_csv.md`
- L2 细节改 `WF/L2-WF_youtube_kol_enrichment_csv.md`
- L3 细节改 `WF/L3-WF_youtube_kol_selection_csv.md`
- 字段契约改 `WF/Lx-Field-Matrix_youtube_kol_csv.md`
