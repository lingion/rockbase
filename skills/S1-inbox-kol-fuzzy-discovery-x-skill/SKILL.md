---
name: s1-inbox-kol-fuzzy-discovery-x-skill
description: 面向 Rockbase 的 X KOL 模糊发现技能。`S1` 仅为历史目录名；当前默认执行链路已收口为 Layer1 发现、Layer2 补全、Layer3 shortlist、L3 到 S2 冷启动映射与 Mail1 DM 预填充的一条保守闭环，当前默认 provider 为 ScrapeCreators。
---

# S1 Inbox X KOL Fuzzy Discovery Skill

说明：

- `S1-inbox` 现在只是历史目录名，不代表当前默认业务终点
- 当前默认主流程已经是 `L1 -> L2 -> L3 -> S2 Cold(workbench) -> merged final deliverable`
- `S1 inbox` 仅保留为 legacy compatibility，不是默认执行步骤

本技能用于把一段模糊的 X KOL 寻找需求，收口成可审计、可续跑、可映射到 `S2 Cold` 的业务产物。

当前已经跑通的最小闭环是：

- `WF_Int`: 自然语言任务 -> intake 提问与澄清
- `QUERY_LIBRARY`: query 方法论 / query matrix / topic query pack
- `Spec`: library 确认后生成可执行 spec
- `Layer1`: `Scweet search`
- `Layer2`: `ScrapeCreators Twitter profile`
- `Layer2 gate`: `max_views >= 5000`
- `Layer3 gate`: `followers_count >= 1000`
- `Layer3`: 规则评分与 `keep / review / drop`
- `Mapping`: `L3 shortlist -> S2 Cold CSV`
- `DM Fill`: `S2 Cold CSV -> Mail1_Greeting_Name / Mail1_Hook / Mail1_Content V1`

当前 `Layer1` 的运行策略：

- 默认通过 `WF_Int -> QUERY_LIBRARY -> spec -> task_spec.py` 生成 query pack
- 对显式 `search_queries`，`Query Name` 必须先在 `QUERY_LIBRARY.md` Part 2 中注册；未注册的 name 不应直接进入 batch run
- 默认优先使用主账号 `steveding150` 对应 cookies
- 若主账号 cookies 导致 Scweet 命令失败，可按 env 配置自动切到后备账号 cookies
- 同一天命中过相同 `query_variant + query_name + query_text + run_date` 的 query 默认不再执行
- 隔天默认允许重跑同主题 query
- 如需换搜索角度，优先切换 `query_variant`，而不是手工改脚本

当前 `Layer2` 的运行策略：

- 默认按 `views gate` 只补 `max_views >= 5000` 的账号
- `views gate` 后命中 `discovery master` 的账号一律视为老人，不进入本批 `L2`
- 默认 provider 为 `ScrapeCreators Twitter profile`
- 默认把 `ScrapeCreators` 输入切成 `30` 个账号一组，逐组补全并写 runlog
- `Scweet user-info` 仍保留为可选备用 provider

当前 `Layer3` 的运行策略：

- 只允许 `followers_count >= 1000` 的账号进入 `Layer3`
- 低于该阈值的账号直接停留在 `Layer2`，不进入 shortlist / review / S2

本技能当前不负责：

- 直接对外联络达人
- 猜测联系方式
- 编造国家、语言、报价等字段
- 绕过 `4-Step Action Budget` 去做深层网页套娃

## 适用任务

- 用户给一句自然语言 brief，需要在 `X` 上找一批 AI / devtools / workflow 相关 KOL
- 用户要把昨天的候选池继续补数、打分、做 shortlist
- 用户要把 `x_kol_L3_shortlist_*.csv` 直接映射成 `S2 Cold` 可继续使用的 CSV
- 用户要在 `S2 Cold CSV` 上继续补好 `Mail1` 相关列，进入 DM / drafts 前状态
- 用户要复盘某批候选是怎么被找到、为什么被保留或跳过

## 执行原则

1. 先保留 raw 证据，再产出业务表。
2. 所有正式业务产物都进入 `workbench/{YYYY-MM-DD}/`。
3. 同一天如需多轮实验，用 `batch1 / batch2 / batch3` 明确区分，不覆盖旧产物。
4. 同一天重复 query 默认由 `query registry` 自动拦截，不再重复搜索。
5. `Layer2` 默认先过 `views gate`，不对全部候选做 profile lookup。
6. `Layer3` 默认先过 `followers gate`，不对低于 `1000` 粉的账号做 shortlist。
7. batch 级 `S2` 默认只写 `workbench/{YYYY-MM-DD}/`。
8. `deliverables/{YYYY-MM-DD}/` 默认只保留唯一 `merged_final.csv`，全量底稿留在 `workbench/`。
9. `联系方式` 找不到就留空或写“拿不到”，绝不编造邮箱。
10. `Layer3` 的 `keep / review / drop` 只是内部优先级，不等于对外承诺。
11. `Mail1_Greeting_Name` 与 `Mail1_Hook` 默认由 LLM 判断；`Mail1_Content V1` 默认使用冻结正文拼接，不自由重写。
12. `L3 shortlist` 默认只输出 `keep / review`，不再把 `drop` 混入正式 shortlist。
13. `明显机构号去除` 不能只依赖脚本关键词；merge 后必须补一次 `LLM / 人工 obvious-org review`，再封板 final merged。

## 先读什么

1. 先读 `BUILD_SPEC.md`，确认当前总骨架、门槛、workbench / deliverables 规则与 Mail1 进入时点。
2. 再读本文件，确认范围和边界。
3. 再读 `WF_Int.md`，确认启动提问、library 更新、spec / plan / todo 的正式顺序。
4. 再读 `QUERY_LIBRARY.md`，确认 query 方法论、关键词矩阵与历史 topic query pack。
5. 再看 `WF/README.md`，了解子工作流目录。
6. 再看 `specs/_template.x_kol_task.json` 和 `specs/openclaw_recent_hot_kol_en.json`，分别确认模板与案例。
7. 再读 `WF/Lx-Field-Matrix_x_kol_csv.md`，确认各层字段契约。
8. 需要看逐层逻辑时：
   - `WF/L1-WF_x_kol_discovery_csv.md`
   - `WF/L2-WF_x_kol_enrichment_csv.md`
   - `WF/L3-WF_x_kol_selection_csv.md`
   - `WF/L3-WF_to-S2-cold-outreach-mapping.md`
   - `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
   - `WF/L3-WF_to-S2-DM-fill.md`
9. 需要看当前架构判断与待办时：
   - `docs/Spec-X模糊搜索KOL-Skill架构设计.md`
   - `docs/plan.md`
   - `docs/TODO-skill开发清单.md`

## 目录结构

```text
S1-inbox-kol-fuzzy-discovery-x-skill/
├── SKILL.md
├── README.md
├── WF_Int.md
├── QUERY_LIBRARY.md
├── WF/
│   ├── README.md
│   ├── WF_Spec.md
│   ├── L1-WF_x_kol_discovery_csv.md
│   ├── L2-WF_x_kol_enrichment_csv.md
│   ├── L3-WF_x_kol_selection_csv.md
│   ├── L3-WF_to-S2-cold-outreach-mapping.md
│   ├── S2-WF_merge-deliverables-and-dm-3.2.md
│   ├── L3-WF_to-S2-DM-fill.md
│   ├── Lx-Field-Matrix_x_kol_csv.md
│   └── legacy/
├── specs/
├── legacy/
├── docs/
├── examples/
├── src/x_kol_discovery/
└── tests/
```

## 推荐执行顺序

### A. 跑最小闭环

1. 先通过 `WF_Int` 补齐平台 / 语言 / 热度 / 粉丝量 / 覆盖时间 / 搜索关键词 / cookies 节奏
2. 更新 `QUERY_LIBRARY.md`
   - 若本轮引入新的 `Query Name`，必须先把它写入 Part 2，再继续生成 spec
3. 再确认或生成一份 `specs/*.json`
4. 先生成当天 `Implementation Plan`
5. 再生成当天 `Batch Allocation Table / Todo List`
6. `run_batch_pipeline.py --spec specs/...`
7. 检查 `workbench/{YYYY-MM-DD}/x_kol_{batch}_pipeline/`
8. 核对 `workbench/{YYYY-MM-DD}/x_kol_S2_cold_{batch}_{YYYY-MM-DD}.csv`
9. 如有多 batch，总表合并使用 `run_merge_s2_deliverables.py`
10. 核对 `deliverables/{YYYY-MM-DD}/【S2_cold】..._merged_final.csv`
11. 合并、去重、机构过滤、排序完成后必须先向用户确认
12. 只有用户明确确认继续填 DM，才链接到 `S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md` 的 `3.2`

### B. 分层续跑

1. 先跑 `run_layer1_mvp.py` 或已有 L1 结果继续
2. 再跑 `run_layer2_from_candidates.py`
3. 再跑 `run_layer3_from_enriched.py`
4. 最后跑 `run_l3_to_s2_mapping.py`
5. 如需继续进入触达预填充，跑 `run_s2_dm_fill.py`

### C. 文档优先复盘

1. 先看 `x_kol_*_runlog_*.json`
2. 再看 `x_kol_L3_audit_summary_*.md`
3. 最后才去翻 raw JSON / CSV

## 脚本入口

- 一键批次闭环：
  - `PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_batch_pipeline.py --run-date 2026-04-01 --batch batch1 --spec specs/openclaw_recent_hot_kol_en.json`
  - 默认直接产出 `S2 cold(workbench only)`
  - 只有显式加 `--emit-legacy-s1` 时才额外输出 `S1 inbox`
- 只跑 Layer1：
  - `PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_layer1_mvp.py --run-date 2026-04-01 --spec specs/openclaw_recent_hot_kol_en.json`
- 从已有 L1 候选继续跑 Layer2：
  - `PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_layer2_from_candidates.py --input-csv workbench/2026-04-01/x_kol_L1_candidates_batch1_2026-04-01.csv --run-date 2026-04-01 --spec specs/openclaw_recent_hot_kol_en.json`
- 从已有 L2 表继续跑 Layer3：
  - `PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_layer3_from_enriched.py --input-csv workbench/2026-04-01/x_kol_L2_enriched_batch1_2026-04-01.csv --run-date 2026-04-01 --batch batch1 --spec specs/openclaw_recent_hot_kol_en.json`
- `L3 -> S2` 主 workflow：
  - `WF/L3-WF_to-S2-cold-outreach-mapping.md`
- 多 batch 合并 / 3.2 DM handoff workflow：
  - `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
- `S2 -> Mail1` legacy in-skill DM fill workflow：
  - `WF/L3-WF_to-S2-DM-fill.md`
- 多 batch 合并：
  - `PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_merge_s2_deliverables.py --run-date 2026-04-07`
- 只做 DM fill manifest：
  - `PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_s2_dm_fill.py --input-csv workbench/2026-04-01/x_kol_S2_merged_filtered_2026-04-01.csv --run-date 2026-04-01 --mode conversation_llm`
- `L3 -> S1` legacy workflow：
  - `legacy/L3-WF_to-S1-inbox-mapping.md`
  - `WF/legacy/L3-WF_to-S1-inbox-mapping-full.md`
  - 仅在需要兼容旧表或旧自动化时使用

## 依赖与限制

- `Layer1` 与 `Layer2` 统一优先读取 skill 根目录 `.env`
- 可在 skill `.env` 中用 `X_COOKIE_PROFILE_PRIMARY` 和 `X_COOKIE_PROFILE_FALLBACKS` 控制 Scweet cookies 的主备顺序
- `Layer2` 默认依赖 `SCRAPECREATORS_API_KEY`
- 当前默认 query pack 仍是 `OpenClaw` 场景，不是任意 brief 的通用 planner
- `ScrapeCreators` 已接进正式默认 pipeline
- spec 中若显式提供 `search_queries`，默认优先采用这些 query；只有显式设置 `search_query_mode=prefer_generated` 才走自动 pack
- 国家、语言判断是规则推断，不是平台真值
- `Scweet user-info` 可能出现“前几批成功，后续整批返回 0” 的情况，所以它适合作为 primary，不适合作为唯一 provider

## Layer2 Provider Strategy

推荐顺序：

1. `ScrapeCreators Twitter profile`
   - 当前默认主链路
   - 直接返回更完整的 profile 字段
   - 更适合承接 `L3 -> S2` 所需的 `external_links / contact` 结构
2. `Scweet user-info`
   - 低成本可选备用
   - 已加上整批为空时的单账号重试
3. `twscrape user lookup`
   - 免费 fallback
   - 用于承接默认 provider 仍未补到的 handle 列表
   - 需要单独治理 cookies、账号池与 cooldown

当前不建议把 `bird` 直接作为 `Layer2` 主 fallback。
原因是：

- 现有验证主要集中在 `Layer1 search`
- 本项目里还没有稳定的 `bird handle -> profile enrichment` 批量补全证据
- 直接替换会把一个已知不稳定点换成另一个未验证点

## 交付判断

一个任务若要算“完成”，至少应产出：

- `L1 candidates`
- `L2 enriched`
- `L3 shortlist`
- `S2 cold mapping`
- `deliverables/{YYYY-MM-DD}/` 下可供最终阅读的 `S2` 副本
- 一份当天的 `Implementation Plan`
- 一份当天的 `Batch Allocation Table`
- 一份简短 `audit / summary`
- 如果用户要求多 batch 总表：一份合并后的 `x_kol_S2_merged_filtered_*.csv`
- 如果用户确认进入 cold DM：`Mail1_Greeting_Name / Mail1_Hook / Mail1_Content V1` 必须填满，且应说明使用的模板版本

如果只做了调研、probe 或 provider 对比，还不算这个技能真正完成执行。

## Batch Allocation Table

对于存在多 `cookies`、多 `batches`、或需要保留补跑窗口的任务，`Batch Allocation Table` 现在视为本 skill 的正式执行组件。

它的作用是：

- 把“计划跑哪些 batch”写清楚
- 把“每个 batch 属于哪个 cookie”写清楚
- 把“每个 batch 跑哪些 query”写清楚
- 把“哪些 batch 是核心 batch，哪些只是 rescue / fallback batch”写清楚

推荐最小字段：

- `Cookie`
- `Batch`
- `Query Names`
- `Primary Goal`
- `Fallback Rule`
- `Stop / Continue Rule`

边界约定：

- `batch1 / batch2 / batch3` 表示 discovery round
- `chunk01 / chunk02 / chunk03` 表示 `Layer2` provider 内部分块
- 二者不得混写，否则会混淆“搜索轮次”和“补全分块”

## Legacy

- 历史 `L3 -> S1` workflow 已降级到：
  - `legacy/L3-WF_to-S1-inbox-mapping.md`
  - `WF/legacy/L3-WF_to-S1-inbox-mapping-full.md`
- 当前默认业务输出应优先参考：
  - `WF/L3-WF_to-S2-cold-outreach-mapping.md`
  - `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
