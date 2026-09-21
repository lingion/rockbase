# Rockbase

Creator outreach automation for a server.

Rockbase collects creator data, prepares outreach, sends and receives email, extracts reply data, and writes reviewed results back to a master CSV. It is a Python source repository, not a hosted service and not a wrapper around Codex.

[中文](#中文)

## What is working now

The current `main` branch contains three server-oriented paths:

- **S1 discovery and enrichment**: Instagram, TikTok, and YouTube exports can call the ScrapeCreators API directly. The apply scripts support preview first, then backup and write-back.
- **S2 Mail1 generation**: Mail1 greeting, hook, variant, and reason fields are generated through an OpenAI-compatible API using the Python OpenAI SDK. The endpoint and model come from deployment configuration.
- **S5 screenshot extraction**: the explicit `--ocr-engine llm` path sends an image to a vision-capable OpenAI-compatible endpoint and maps the response into the existing review, matching, dry-run, backup, and CSV write-back flow.
- **S2/S3 mail transport**: [`mailkit/`](mailkit/README.md) sends through company SMTP, receives through its HTTP receiver, fetches replies, and syncs sent/replied fields back to the master CSV.

The repository has not yet grown a single scheduler or daemon that runs every stage in sequence. That is the next phase. Until then, each path is a command-line job that can be called from cron or systemd.

## Pipeline

```text
S1 discover/enrich
        |
        v
S2 generate Mail1 fields --> mailkit.send --> company SMTP
        |                                      |
        |                                      v
        +------------------------------ S3 receiver
                                               |
                                               v
                                      fetch replies / parse / sync
                                               |
                                               v
S4 active assets --> S5 matching, delivery checks, OCR, dedupe, invoices
                                               |
                                               v
                                      reviewed master CSV
```

The write path is deliberately staged. Export first. Review the report. Apply with a backup. Sending has the same shape: dry-run first, `--execute` only when the batch is approved.

## Quick start

Requirements: Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,llm]'
python -m pytest -q
```

The full offline suite currently covers the SDK request contracts, the S1 export-to-apply chain, the multimodal OCR request, and the existing path/mail tests. It does not call a real OpenAI, Anthropic, ScrapeCreators, SMTP, or production receiver account.

## Deployment configuration

Keep secrets in the server secret manager or environment. Do not put them in CSV files, workflow JSON, or committed config.

```bash
export OPENAI_API_KEY='...'
export SCRAPECREATORS_API_KEY='...'
export ROCKBASE_PROJECT_ROOT='/srv/rockbase'
```

The code uses an OpenAI-compatible API surface. Point `--base-url` or `--llm-base-url` at the endpoint configured by the deployment team. The business scripts do not select OpenAI versus Anthropic themselves.

## Run the server paths

### S1: export creator data

The three export scripts have the same credential behavior: an explicit `--api-key` wins, then the environment variable is used. The old iCloud dotenv path is optional and is not required on a server.

```bash
python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_export.py \
  --csv /srv/rockbase/data/master.csv \
  --api-key "$SCRAPECREATORS_API_KEY" \
  --rows 2,8,11 \
  --date 2026-09-21
```

Use the matching export script for `instagram` or `tiktok`. The command writes raw and summary JSON into the workbench. Nothing is written to the master CSV by export.

### S1: preview and apply

```bash
python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_apply.py \
  --csv /srv/rockbase/data/master.csv \
  --json /srv/rockbase/workbench/2026-09-21/youtube_scrapecreators_*_raw.json \
  --mode preview

python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_apply.py \
  --csv /srv/rockbase/data/master.csv \
  --json /srv/rockbase/workbench/2026-09-21/youtube_scrapecreators_*_raw.json \
  --mode apply
```

`preview` does not modify the CSV. `apply` makes a dated backup before writing.

### S2: generate Mail1 fields

```bash
python skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py \
  --input /srv/rockbase/data/master.csv \
  --api-key "$OPENAI_API_KEY" \
  --base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --model "${LLM_MODEL:-gpt-4o-mini}" \
  --dry-run
```

Despite its historical filename, this script no longer starts Codex. It calls `chat.completions.create`, validates every returned row, and writes an audit CSV. Remove `--dry-run` only after reviewing that audit. `OPENAI_API_KEY` is accepted when `--api-key` is omitted.

The YouTube runner passes the same settings through:

```bash
python skills/S1-inbox-kol-fuzzy-discovery-youtube-skill/src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date 2026-09-21 \
  --api-key "$OPENAI_API_KEY" \
  --base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --model "${LLM_MODEL:-gpt-4o-mini}" \
  --dry-run
```

### S2/S3: send, receive, sync

```bash
cd mailkit
cp config.example.toml config.toml
python3 tests/test_smoke.py

# Inspect the send plan first.
python3 -m mailkit.send --config config.toml --csv /srv/rockbase/data/mail1.csv

# Send only an approved batch.
python3 -m mailkit.send --config config.toml --csv /srv/rockbase/data/mail1.csv --execute

# Run the receiver on the server, in its service manager.
python3 -m mailkit.receiver --db mailkit.db --port 8788 --api-key "$MAILKIT_RECEIVER_API_KEY"

# Fetch and review replies, then sync them.
python3 -m mailkit.fetch_replies --config config.toml
python3 -m mailkit.master_sync replies --config config.toml --master /srv/rockbase/data/master.csv
python3 -m mailkit.master_sync replies --config config.toml --master /srv/rockbase/data/master.csv --execute
```

Read [`mailkit/README.md`](mailkit/README.md) for SMTP, receiver, Postfix, rate limits, and the local send-to-receive rehearsal.

### Phase 2: resumable mail loop

The first server orchestrator slice starts from an already generated Mail1 CSV and chains the existing mailkit commands. It persists stage state atomically, skips completed stages only when their declared artifacts still exist, and records failures without running later stages.

```bash
python -m scripts.run_mail_loop \
  --batch-csv /srv/rockbase/data/mail1.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --master /srv/rockbase/data/master.csv \
  --state /srv/rockbase/workbench/mail-loop.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21
```

This defaults to mailkit send dry-run and master sync dry-run. Add `--execute-send` only for an approved SMTP batch; add `--execute-sync` only after reviewing the send/reply previews. The two flags are independent. Credentials are read by mailkit configuration/environment and are redacted from the orchestrator state file.

### S5: direct multimodal OCR

```bash
python skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py \
  --image-dir /srv/rockbase/workbench/2026-09-21/screenshots \
  --csv-path /srv/rockbase/data/master.csv \
  --ocr-engine llm \
  --llm-base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --llm-model "${LLM_VISION_MODEL:-gpt-4o-mini}" \
  --dry-run
```

The model must support image input. The result still goes through the existing review threshold, row matching, duplicate handling, backup, and write-back rules. `OPENAI_API_KEY` is used unless `--llm-api-key` is supplied.

## Repository map

```text
skills/
  S1-inbox-enrichment/                 ScrapeCreators and browser-era enrichment tools
  S1-inbox-kol-fuzzy-discovery-*/      platform discovery and S2 handoff runners
  S2-ag-gmail-bulk-drafts/             Mail1 generation, manifests, draft/send helpers
  S3-ag-reply-recovery-sync-v3/        reply extraction and recovery tools
  S4-ag-active-asset-enrichment/       active creator/asset operations
  S5-ag-ocr-sync/                      screenshot OCR and master sync
mailkit/                               SMTP send, HTTP receive, reply/sent sync
rockbase/                              shared path resolution
scripts/                               supporting command-line jobs
docs/                                  setup, dependency notes, migration notes, ADRs
tests/                                 offline and local-loopback contract tests
templates/                             example operational templates
```

Every skill directory has its own `SKILL.md`. The repository README is the deployment map; the skill files contain field names, source-specific rules, and destructive-action boundaries.

## Safety rules

- Run export, OCR, and mail operations in dry-run or preview mode first.
- `mailkit.send` is dry-run by default. `--execute` is an explicit send operation.
- Mailkit limits first-touch traffic to the configured window and daily cap, and blocks first-touch links by default.
- Back up the production master before any write-back. The S1 apply and mailkit sync paths provide backup/dry-run boundaries; verify the target path before using them.
- If a contact cannot be verified, leave it unavailable. Do not invent an address, audience number, collaboration, or creator fact.
- Do not run old macOS/Chrome paths on the server. Use the API export scripts, SDK LLM paths, and `mailkit` commands described here.
- Keep credentials out of logs, audit CSVs, screenshots, commits, and issue comments.

## Verification and boundaries

```bash
python -m pytest -q
cd mailkit && python3 tests/test_smoke.py
```

The tests use fake data and local loopback HTTP servers. They prove request shapes, parsing, preview/write boundaries, and cross-script wiring. They do not prove that a deployment account has permission, quota, deliverability, or access to a specific third-party API.

The current orchestrator covers the server-side S2 → mailkit → S3 mail loop, with optional S1 enrichment and S5 OCR stages. The following work remains outside the current merged code:

- service-level alerts and a host-specific secret-manager integration;
- real-account acceptance with the company's API keys, SMTP, receiver, and master data;
- migration of every historical script that still assumes a local macOS path.

## Documentation

- [Setup and self-check](docs/SETUP.md)
- [Dependency matrix](docs/DEPENDENCY_MATRIX.md)
- [Migration status](docs/inventory/MIGRATION_STATUS.md)
- [Security notes](SECURITY.md)
- [mailkit guide](mailkit/README.md)
- [LLM endpoint ADR](docs/adr/0002-llm-openai-compatible-sdk.md)
- [Multimodal OCR ADR](docs/adr/0003-direct-multimodal-ocr.md)

## License and data

This repository contains no production credentials, cookies, browser profiles, historical mail, real creator lists, or business data. Example configurations use placeholders. Put operational data outside the repository and keep the deployment copy private.

---

# 中文

Rockbase 是一套跑在服务器上的达人外联自动化工具。

它负责收集达人资料、准备外联邮件、发信、收信、整理回复，再把审核过的结果写回主表。它是 Python 源码仓库，不是托管服务，也不再依赖 Codex 才能运行。

## 现在已经能跑什么

当前 `main` 已经合入三条服务器路径：

- **S1 发现和补全**：Instagram、TikTok、YouTube 都能直接调用 ScrapeCreators API。导出先落 raw/summary JSON，应用脚本先 preview，再备份并写回。
- **S2 Mail1 生成**：Greeting、Hook、Variant、Reason 走 OpenAI-compatible API 和 Python OpenAI SDK。endpoint、模型由部署配置决定。
- **S5 截图提取**：显式使用 `--ocr-engine llm` 时，图片直接发给支持视觉输入的兼容 endpoint，结果继续走原来的审核、匹配、dry-run、备份和主表写回。
- **S2/S3 邮件层**：[`mailkit/`](mailkit/README.md) 通过公司 SMTP 发信，通过 HTTP receiver 收信，回收回复并同步 sent/replied 字段。

统一调度器还没有合入。现在每条链都是一个命令行任务，可以交给 cron 或 systemd；S1→S2→收发信→S3→S4/S5 的统一编排属于下一阶段。

## 流程图

```text
S1 发现/补全
        |
        v
S2 生成 Mail1 ------> mailkit.send ------> 公司 SMTP
        |                                      |
        |                                      v
        +------------------------------ S3 receiver
                                               |
                                               v
                                      回收回复 / 解析 / 同步
                                               |
                                               v
                         S4 活跃达人 ------> S5 匹配、交付检查、OCR、查重、发票
                                               |
                                               v
                                           审核后的主表
```

所有写入都分两步。先导出、看报告，再 apply；先 preview、备份，再写。发信也是一样，先看 dry-run，确认批次后才加 `--execute`。

## 快速安装

要求 Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,llm]'
python -m pytest -q
```

完整离线测试覆盖 SDK 请求契约、S1 导出到应用链、多模态 OCR 请求，以及原有路径和邮件测试。测试不会调用真实 OpenAI、Anthropic、ScrapeCreators、SMTP 或生产 receiver。

## 服务器配置

密钥放服务器的 secret manager 或环境变量里，不要放 CSV、workflow JSON 或提交文件。

```bash
export OPENAI_API_KEY='...'
export SCRAPECREATORS_API_KEY='...'
export ROCKBASE_PROJECT_ROOT='/srv/rockbase'
```

代码使用 OpenAI-compatible 接口。部署团队可以通过 `--base-url` 或 `--llm-base-url` 指向实际 endpoint，业务脚本不自行判断使用 OpenAI 还是 Anthropic。

## 常用命令

### S1 导出

```bash
python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_export.py \
  --csv /srv/rockbase/data/master.csv \
  --api-key "$SCRAPECREATORS_API_KEY" \
  --rows 2,8,11 \
  --date 2026-09-21
```

Instagram 和 TikTok 换用对应的 export 脚本。导出只写 workbench 下的 raw/summary JSON，不修改主表。

### S1 预览和写回

```bash
python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_apply.py \
  --csv /srv/rockbase/data/master.csv \
  --json /srv/rockbase/workbench/2026-09-21/youtube_scrapecreators_*_raw.json \
  --mode preview

python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_apply.py \
  --csv /srv/rockbase/data/master.csv \
  --json /srv/rockbase/workbench/2026-09-21/youtube_scrapecreators_*_raw.json \
  --mode apply
```

`preview` 不改 CSV；`apply` 写入前会生成带日期的备份。

### S2 生成 Mail1

```bash
python skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py \
  --input /srv/rockbase/data/master.csv \
  --api-key "$OPENAI_API_KEY" \
  --base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --model "${LLM_MODEL:-gpt-4o-mini}" \
  --dry-run
```

文件名是历史遗留，脚本已经不启动 Codex。它调用 `chat.completions.create`，逐批校验返回结果，并先生成 audit CSV。看完 audit 再去掉 `--dry-run`。不传 `--api-key` 时会读取 `OPENAI_API_KEY`。

YouTube runner 会透传同一组配置：

```bash
python skills/S1-inbox-kol-fuzzy-discovery-youtube-skill/src/youtube_kol_discovery/pipelines/run_s2_mail1_fill.py \
  --run-date 2026-09-21 \
  --api-key "$OPENAI_API_KEY" \
  --base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --model "${LLM_MODEL:-gpt-4o-mini}" \
  --dry-run
```

### S2/S3 收发和同步

```bash
cd mailkit
cp config.example.toml config.toml
python3 tests/test_smoke.py

python3 -m mailkit.send --config config.toml --csv /srv/rockbase/data/mail1.csv
python3 -m mailkit.send --config config.toml --csv /srv/rockbase/data/mail1.csv --execute

python3 -m mailkit.receiver --db mailkit.db --port 8788 --api-key "$MAILKIT_RECEIVER_API_KEY"
python3 -m mailkit.fetch_replies --config config.toml
python3 -m mailkit.master_sync replies --config config.toml --master /srv/rockbase/data/master.csv
python3 -m mailkit.master_sync replies --config config.toml --master /srv/rockbase/data/master.csv --execute
```

SMTP、receiver、Postfix、限速和本机彩排看 [`mailkit/README.md`](mailkit/README.md)。

### Phase 2: 可恢复邮件编排

第一版服务器编排从已经生成的 Mail1 CSV 开始，串起现有 mailkit 命令。它原子持久化阶段状态；只有声明的产物仍存在时才跳过已完成阶段；阶段失败会记录并停止后续阶段。

```bash
python -m scripts.run_mail_loop \
  --batch-csv /srv/rockbase/data/mail1.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --master /srv/rockbase/data/master.csv \
  --state /srv/rockbase/workbench/mail-loop.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21
```

默认是 mailkit 发信 dry-run 和主表同步 dry-run。只对已批准批次加 `--execute-send`；检查发件/回件预览后，才加 `--execute-sync`。两个开关相互独立。凭据由 mailkit 配置/环境读取，不会写入编排器状态文件。

### S5 直接多模态 OCR

```bash
python skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py \
  --image-dir /srv/rockbase/workbench/2026-09-21/screenshots \
  --csv-path /srv/rockbase/data/master.csv \
  --ocr-engine llm \
  --llm-base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --llm-model "${LLM_VISION_MODEL:-gpt-4o-mini}" \
  --dry-run
```

模型必须支持图片输入。结果仍会经过审核阈值、行匹配、图片去重、备份和写回规则。没有传 `--llm-api-key` 时读取 `OPENAI_API_KEY`。

## 目录

```text
skills/                                  各阶段脚本和 SKILL.md
  S1-inbox-enrichment/                  ScrapeCreators 与旧浏览器补全工具
  S1-inbox-kol-fuzzy-discovery-*/       平台发现与 S2 handoff
  S2-ag-gmail-bulk-drafts/              Mail1、manifest、草稿/发送工具
  S3-ag-reply-recovery-sync-v3/         回复恢复和同步
  S4-ag-active-asset-enrichment/        活跃达人和资产处理
  S5-ag-ocr-sync/                       截图 OCR 与主表同步
mailkit/                                SMTP 发信、HTTP 收信、回复/回执同步
rockbase/                               共享路径解析
scripts/                                辅助命令行任务
docs/                                   安装、依赖、迁移状态、ADR
tests/                                  离线和本地 loopback 契约测试
templates/                              示例模板
```

每个 skill 目录都有自己的 `SKILL.md`。README 负责告诉你服务器怎么跑；字段名、平台差异和危险写入边界留在各 skill 文档里。

## 安全边界

- S1 导出、OCR、邮件发送先跑 dry-run 或 preview。
- `mailkit.send` 默认 dry-run，只有 `--execute` 才真的发信。
- mailkit 按时间窗口和日上限限速，首触默认拦截外链。
- 写生产主表前先备份。S1 apply 和 mailkit sync 自带一部分备份/预览保护，运行前仍要确认目标路径。
- 联系方式拿不到就留空或记为不可用，不猜地址，不编达人数据。
- 服务器不要跑旧的 macOS/Chrome 路径，改用这里写的 API export、SDK LLM 和 mailkit 命令。
- 密钥不能进入日志、audit CSV、截图、commit 或 issue 评论。

## 验证和未完成部分

```bash
python -m pytest -q
cd mailkit && python3 tests/test_smoke.py
```

测试使用假数据和本地 loopback HTTP，验证请求形状、解析、preview/write 边界和跨脚本接线。它不能证明真实账号的权限、额度、邮件送达率或第三方 API 对某个目标账号可用。

当前 main 还没有：

- 从 S1 发现/补全开始、覆盖 S2 生成和 S4/S5 的全链路编排；当前 runner 从已生成的 Mail1 CSV 开始；
- 编排器的服务级告警和部署级重试策略；阶段失败状态与超时记录已经落地；
- 使用公司真实 API key、SMTP、receiver 和主表数据做的验收；
- 所有历史脚本的 macOS 路径清理。

## 文档

- [安装和自检](docs/SETUP.md)
- [依赖矩阵](docs/DEPENDENCY_MATRIX.md)
- [迁移状态](docs/inventory/MIGRATION_STATUS.md)
- [安全说明](SECURITY.md)
- [mailkit 使用说明](mailkit/README.md)
- [LLM endpoint ADR](docs/adr/0002-llm-openai-compatible-sdk.md)
- [多模态 OCR ADR](docs/adr/0003-direct-multimodal-ocr.md)

## 数据和凭据

仓库不包含生产凭据、Cookie、浏览器 Profile、历史邮件、真实达人名单或业务数据。示例配置都是占位值。运营数据放在仓库外，服务器上的部署副本单独保管。
