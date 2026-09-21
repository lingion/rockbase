---
description: "[Workflow] YouTube S2 merged final -> Mail1 fill | 直接转调 Gmail canonical workflow，不重复定义邮件文案逻辑。"
---

# L4-WF_youtube_mail1_fill

## 目标

把 YouTube 的 `S2 merged final` 直接推进到 `Mail1` 字段已写回的状态。

这一步不在 YouTube skill 内部自定义另一套冷邮件模板。  
默认直接复用 Gmail skill 的 canonical workflow：

- 相对路径：`.agent/skills/S2-ag-gmail-bulk-drafts/WF_Cold Mail Run.md`

## Canonical Runner

YouTube 侧统一入口：

- `src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py`

这个 runner 负责：

1. 定位 YouTube `S2 merged final`
2. 先做物理备份
3. 直接转调 Gmail skill 的 `scripts/gmail/fill_mail1_with_codex.py`（历史文件名，实际通过 `--api-key` / `--base-url` / `--model` 调用 OpenAI-compatible LLM）
4. 可选接入 Gmail `prepare_jobs.py` 生成 manifest
5. 可选接入 Gmail `sample_send.py` / `bulk_send.py` 创建草稿
6. 把 audit / runlog 落到当天 `workbench/{YYYY-MM-DD}/YouTube/`

## 默认输入

- `.agent/skills/S1-inbox-kol-fuzzy-discovery-youtube-skill/deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_youtube_kol_S2_merged_final.csv`

## 默认命令

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD}
```

## 常用选项

小批量试跑：

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD} \
  --limit 5
```

从指定 sheet row 开始：

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD} \
  --start-row 36
```

只做 audit，不写回：

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD} \
  --dry-run \
  --limit 5
```

生成 Gmail manifest 并跑 1 封 sample draft：

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD} \
  --gmail-stage sample \
  --gmail-sample-limit 1
```

只生成 Gmail manifest，不创建草稿：

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD} \
  --gmail-stage prepare
```

生成 Gmail manifest 并跑 bulk draft writer：

```bash
python3 src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date {YYYY-MM-DD} \
  --gmail-stage bulk
```

## 输出位置

- 源表：原地写回 `Mail1_*`
- Gmail manifest：`workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_mail1_manifest_{YYYY-MM-DD}.csv`
- runlog：`workbench/{YYYY-MM-DD}/YouTube/youtube_kol_S2_mail1_fill_runlog_{YYYY-MM-DD}.json`
- Mail1 audit：由 Gmail canonical script 写到当天 `workbench/{YYYY-MM-DD}/YouTube/`

## 原则

- YouTube skill 只负责把行推进到 `S2 merged final`
- Mail1 的 `Greeting / Hook / Subject / Content` 规则全部以 Gmail canonical workflow 为准
- 不要在 YouTube skill 内再造第二套 Mail1 文案系统
