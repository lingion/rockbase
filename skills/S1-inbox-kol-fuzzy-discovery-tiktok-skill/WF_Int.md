---
description: "[Runner] TikTok KOL fuzzy discovery 总工作流 | 负责 intake、spec、L1/L2/L3、S2 与 master 去重。"
---

# WF_Int

> 这是 `S1-inbox-kol-fuzzy-discovery-tiktok-skill` 的默认启动入口。  
> 当前已经冻结的现实判断是：
>
> - `L1 content-first` 默认优先 `ScrapeCreators`
> - `L1 account-first` 可由 `ScrapeCreators search users / profile videos` 与 `TikTok-Api user search` 共同承担
> - `TikTok-Api item/content search` 当前不作为默认主路径

## 一、当前默认闭环

默认链路：

```text
自然语言需求
-> Intake
-> QUERY_LIBRARY 更新
-> 当天 spec
-> plan
-> run L1 content-first
-> L1 unified / candidates
-> L1 views gate
-> check discovery master
-> run L2 on net-new creators only
-> L2 enriched
-> run L3
-> L3 shortlist
-> S2 outreach export
-> STOP：向用户汇报结果并等待下一步
```

当前目标实验：

- `topic_query`: `accio`
- `L1 views gate`: `2000`
- `L2 followers gate`: `3000`

## 二、子工作流位置

根目录核心索引：

- `SKILL.md`
- `WF_Int.md`
- `QUERY_LIBRARY.md`

子工作流统一在：

- `WF/L1-WF_tiktok_kol_discovery_csv.md`
- `WF/L2-WF_tiktok_kol_enrichment_csv.md`
- `WF/L3-WF_tiktok_kol_selection_csv.md`
- `WF/L3-WF_to-S2-cold-outreach-mapping.md`
- `WF/Lx-Field-Matrix_tiktok_kol_csv.md`

## 三、Intake 最小字段

| 字段 | 说明 | 当前实验值 |
| --- | --- | --- |
| `KOL平台` | 本次平台 | `TikTok` |
| `语言` | 目标语言 | `en` |
| `L1内容门槛` | 内容流量最低值 | `2000+ views` |
| `L2粉丝门槛` | 进入正式 shortlist 的最低粉丝量 | `3000+ followers` |
| `帖子覆盖时间` | 搜最近多久 | `过去 30 天` |
| `搜索关键词` | 领域 / 品牌 / 主题 | `accio` |
| `搜索模式` | 默认双通道 | `dual_channel` |
| `最终动作` | 先做到哪一层 | `先做到 L3 / S2 base` |

原则：

- 已明确的值不要重复追问
- 当前 TikTok 的不确定性主要集中在 `L1 content-first`
- 一旦 `L1` 有真实输出，后面的 `L2 -> L3 -> S2` 尽量复用 YouTube 的成熟节奏

## 四、Runner 标准步骤

### Step 1. 更新 QUERY_LIBRARY

规则：

- topic 已存在：复用并微调
- topic 不存在：补进 `QUERY_LIBRARY.md`
- spec 里的 `search_queries[].name` 必须能在 `QUERY_LIBRARY.md` 中找到对应项

### Step 2. 生成当天 spec

最低要求：

- 要明确 `search_queries`
- 要明确 `l1_mode`
- 要明确 `provider_plan`
- 要明确 `run_date`
- 要写死本轮 gate：
  - `min_content_views_for_l2 = 2000`
  - `min_followers_for_l3 = 3000`

### Step 3. 执行 L1

当前默认策略：

1. `content-first`:
   - 主入口：`ScrapeCreators /v1/tiktok/search/keyword`
   - 补入口：`ScrapeCreators /v1/tiktok/search/hashtag`
2. `account-first`:
   - `ScrapeCreators /v1/tiktok/search/users`
   - `ScrapeCreators /v3/tiktok/profile/videos`
   - `TikTok-Api user search` 只作辅助交叉验证

L1 完成后必须至少产出：

- `L1 unified`
- `L1 candidates`
- `L1 runlog`
- `content evidence rows`
- `creator_summary rows`

### Step 4. L1 gate + master 去重

默认顺序：

1. `L1 candidates`
2. `views gate >= 2000`
3. `check discovery master`
4. 仅对 net-new creator 进入本批 `L2`

长期主表位置：

- `docs/tiktok_kol_discovery_master.csv`

为什么 master 必须在 `L2` 前：

- 避免重复进入 `ScrapeCreators profile` 深挖
- 避免重复进入后续 contact/bio 补全
- 保持本批 `L2 / L3 / S2` 接近净新增

### Step 5. 执行 L2

当前默认策略：

1. 输入必须是：
   - `通过 L1 views gate`
   - `且未命中 master`
2. 用 `creator_handle / author_unique_id` 进入 profile 深挖
3. 目标是补：
   - `followers_count`
   - `bio`
   - `external_links`
   - `contact_signals`
   - `contact_value`
   - `contact_note`
4. 再根据 `followers_count >= 3000` 做 `L2 gate`

### Step 6. 执行 L3

L3 的职责：

- 不重新搜索
- 只做判断和排序
- 形成最终 shortlist
- 在进 S2 前拦住明显机构号和过分一线账号

建议判断轴：

- `topic_match_score`
- `profile_match_score`
- `activity_score`
- `contactability_score`
- `overall_score`
- `recommended_action`

默认额外闸门：

- `obvious org/media/account` 不能直接 `keep`
- `300k+ followers` 进入 `big account` 复核
- `1M+ followers` 且伴随组织信号时优先 `drop`
- 有明确个人品牌证据时，可保留为 `keep` 或 `review`

规范说明：

- `L3` 负责识别机构号、媒体号、品牌号与过大账号，并写出风险字段
- `L3` 不是最终 deliverable 删除环节；它负责判断与打标
- 正式删除发生在 `L3 -> S2 export`
- `merge` 必须再次执行同样规则兜底，避免旧批次或手工回流把机构号带回最终表

### Step 7. 输出 S2

规则与 YouTube 保持一致：

- `Mail1` 列不进入 `L1 / L2 / L3`
- 从 `L3 -> S2 base mapping` 开始预留：
  - `Mail1发出状态`
  - `Mail1_Hook`
  - `Mail1_Greeting_Name`
  - `Mail1_Subject`
  - `Mail1_Content V1`
  - `Mail1_Content V2`

TikTok deliverable 规则：

- `S2` 是正式 deliverable 出口
- 机构号、媒体号、品牌号不得进入 `S2`
- 识别依据优先读取 `llm_entity_type / llm_decision / account_risk_flags / final_decision`
- 若命中机构号信号，即使为 `review` 也不得写入 `S2`

## 五、deliverables / workbench 规则

`/400 🔴 Project/🔴 420 Social Agency/workbench/{YYYY-MM-DD}/TikTok/` 放：

- raw
- runlog
- audit
- smoke/test
- L1/L2/L3/S2 过程文件

`deliverables/{YYYY-MM-DD}/` 只放：

- 唯一正式 `merged_final`
- 不放 batch 级 `S2`
- 不放 raw / runlog / audit / shortlist / review / test

`S2 merge` 之后进入唯一主表阶段：

- `【S2_cold】{YYYY-MM-DD}_tiktok_kol_S2_merged_final.csv` 视为唯一 final 主表
- 后续补 email、补历史 overlay、写 `Mail1`、排序、subject 清洗，都直接改这张表
- 不允许在 merge 之后再平行维护第二张“另一个 final”
- 不允许把 batch 级 `S2` 再镜像进 `deliverables/`
- `workbench` 可以保留过程审计，但正式最新状态必须回到这张 `merged_final`

merge runner 保护规则：

- merge 默认从 `workbench/{YYYY-MM-DD}/TikTok/` 读取 batch 级 `S2`
- 若已有 `merged_final` 的已填邮箱数更高，runner 默认拒绝覆盖
- 只有明确知道要回退时，才允许使用 downgrade override

## 六、完成判定

本轮 TikTok 任务至少要达到：

- `L1 content-first` 有真实内容证据
- `L1 candidates` 可用
- `views gate` 已按 `2000` 执行
- `master` 已参与去重
- `L2` 能按 handle 深挖
- `followers gate` 已按 `3000` 执行
- `L3 shortlist` 和 `S2 base` 字段契约清楚

## 七、修改原则

以后改流程时：

- 总流程顺序改 `WF_Int.md`
- L1 细节改 `WF/L1-WF_tiktok_kol_discovery_csv.md`
- L2 细节改 `WF/L2-WF_tiktok_kol_enrichment_csv.md`
- L3 细节改 `WF/L3-WF_tiktok_kol_selection_csv.md`
- 字段契约改 `WF/Lx-Field-Matrix_tiktok_kol_csv.md`
- master 位置和规则也统一以本文件与 `L2-WF` 为准
