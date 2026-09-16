---
name: s1-inbox-kol-fuzzy-discovery-youtube-skill
description: 面向 Social Agency 的 YouTube KOL 模糊发现技能。默认采用 shared contract, separate runtime 架构，主流程为 L1 发现、L2 补全、L3 shortlist、S2 outreach export。
---

# S1 Inbox YouTube KOL Fuzzy Discovery Skill

本技能用于把一句模糊的 YouTube KOL 寻找需求，收口成一条可审计、可续跑、可交付的 `L1 -> L2 -> L3 -> S2` 工作流。

这条链路的默认逻辑不是“先找平台全站 discover 榜”，而是：

`给一个领域角度 -> 搜大量热内容 -> 聚合背后的 creator -> 进入 L2/L3/S2`

## 当前定位

- 这是 `3` 个新平台 skill 中最优先、最稳的首发版本
- 本技能独立开发、独立调试
- 但从 day 1 起共享跨平台字段契约、spec 结构、output contract
- 当前最主要的新设计工作集中在 `L1`

## 当前默认 L1 策略

- `dual_channel`
- `content-first`
  - 主路径是多 query 的 `yt-dlp` 热内容搜索
  - `discover` 只作为可选补充信号，不是默认主轴
- `account-first`
  - 从 `channel` / `video author` / `channel metadata` 反推创作者
- fallback
  - 扩 query、扩 seed channels，而不是先依赖平台总榜

## 不负责

- 自动联系达人
- 编造联系方式
- 平台全量抓取
- 在未说明 operator requirement 时假装 cookies / API key 已经齐备

## 先读什么

1. `BUILD_SPEC.md`
2. 本文件
3. `WF_Int.md`
4. `QUERY_LIBRARY.md`
5. `docs/spec.md`
6. `WF/L1-WF_youtube_kol_discovery_csv.md`
7. `WF/Lx-Field-Matrix_youtube_kol_csv.md`
8. `specs/_template.youtube_kol_task.json`
9. `docs/operator-requirements.md`
10. `docs/plan.md`
11. `tests/README.md`

## 目录结构

```text
S1-inbox-kol-fuzzy-discovery-youtube-skill/
├── SKILL.md
├── WF_Int.md
├── QUERY_LIBRARY.md
├── WF/
│   ├── L1-WF_youtube_kol_discovery_csv.md
│   ├── L2-WF_youtube_kol_enrichment_csv.md
│   ├── L3-WF_youtube_kol_selection_csv.md
│   ├── L3-WF_to-S2-cold-outreach-mapping.md
│   ├── L4-WF_youtube_mail1_fill.md
│   └── Lx-Field-Matrix_youtube_kol_csv.md
├── docs/
│   ├── spec.md
│   ├── plan.md
│   └── operator-requirements.md
├── specs/
│   └── _template.youtube_kol_task.json
├── src/
│   └── youtube_kol_discovery/
└── tests/
```

## 执行原则

1. 先保留 raw evidence，再产出 shortlist。
2. `L1` 默认双通道并行，但主引擎是 `search-first hot-content mining`。
3. `L2 -> L3 -> S2` 尽量沿用 X skill 的业务逻辑，不额外发明新层。
4. `creator_handle` 是跨平台主键名；平台原生字段保留为 alias。
5. `youtube/api-samples` 已归档，只可当 API 调用参考，不可当活跃实现基座。
6. `S2` 前必须补一轮 `LLM entity screen + dirty-contact hygiene`：
   - LLM 负责判定 `person-led creator` / `org_or_media`
   - `keep` 才能进入正式 `S2`
   - `drop` / `ambiguous` 直接拦截，不走人工 review
   - dirty email 仍然由脚本清洗并直接剔除
7. `Mail1 fill` 不在 YouTube skill 内自造模板：
   - YouTube 负责把表推进到 `S2 merged final`
   - `Mail1` 语义填充与正文拼装，默认转交 `.agent/skills/S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`
   - YouTube 侧 canonical runner 是 `src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`
