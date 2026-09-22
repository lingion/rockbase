# Rockbase

Rockbase is a server-oriented creator outreach automation toolkit. It discovers and enriches creator records, prepares Mail1 outreach, sends and receives email, extracts reply data, processes active assets, and writes reviewed results back to a master CSV.

It is a Python source repository with an optional Dockerized operations console. It is not a hosted SaaS service, and it does not require Codex to run the business paths.

[中文](#中文)

## Current status

The repository currently has two layers:

- **Business skills** under `skills/`: discovery, Mail1 generation, reply recovery, active-asset enrichment, and screenshot/OCR workflows.
- **Server operations** under `scripts/`, `console/`, and `mailkit/`: resumable orchestration, health checks, authenticated run control, SMTP/HTTP mail transport, and local verification.

The server layer is functional offline and against local loopback fixtures. Real-account acceptance is intentionally not part of the repository test suite.

## Pipeline

```text
S1 discover/enrich
        |
        v
S2 generate Mail1 ---> mailkit.send ---> company SMTP
        |                                   |
        |                                   v
        +---------------------------- S3 receiver
                                            |
                                            v
                                   fetch / parse / sync
                                            |
                                            v
                         S4 active assets ---> S5 OCR/matching
                                            |
                                            v
                                      reviewed master CSV
```

The write path is staged: export or generate first, inspect the report, then apply with a backup. Sending and synchronization are dry-run by default and require explicit execution flags. The orchestrator and Console add a second approval layer for send and sync actions.

## Quick start

Requirements: Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,llm]'
python -m pytest -q
```

The default suite uses fake data and local loopback services. It checks request contracts, parsing, stage wiring, preview/write boundaries, state persistence, and security controls. It does not prove access, quota, deliverability, or permissions for a real third-party account.

## Docker console

The Rockbase Console is an authenticated operations workbench for discovering runs, inspecting stage output, pausing/resuming runs, approving gated actions, and terminating a run. It uses session cookies, CSRF protection, viewer/operator roles, an append-only JSONL audit stream, and a strict same-origin content policy.

The image runs as an unprivileged user. The compose definition binds the console to loopback, uses a read-only root filesystem, a `/tmp` tmpfs, dropped Linux capabilities, `no-new-privileges`, and a persistent console data volume.

```bash
docker build -t rockbase-console:local .
docker run --rm \
  --name rockbase-console \
  -p 127.0.0.1:8790:8790 \
  -v rockbase-console-data:/var/lib/rockbase/console \
  rockbase-console:local
```

If Docker Compose is available, use:

```bash
docker compose up --build
```

The browser entry point is `http://127.0.0.1:8790`. Set the console configuration through environment variables; do not commit credentials or production state.

Important console variables:

- `ROCKBASE_CONSOLE_HOST`, `ROCKBASE_CONSOLE_PORT`
- `ROCKBASE_CONSOLE_ALLOW_REMOTE`
- `ROCKBASE_CONSOLE_BASE_DIR`, `ROCKBASE_CONSOLE_REPO_ROOT`
- `ROCKBASE_CONSOLE_RUNS_DIR`
- `ROCKBASE_CONSOLE_SESSION_TTL_SECONDS`
- `ROCKBASE_CONSOLE_COOKIE_SECURE`

See [console operations](docs/console-operations.md) for account seeding, deployment layout, and the API contract.

## Orchestration

### Resumable mail loop

This runner starts from an existing Mail1 CSV and chains the mailkit send, receive, fetch, and sync stages. It persists state atomically, validates declared artifacts before skipping a completed stage, records failures, and can resume after interruption.

```bash
python -m scripts.run_mail_loop \
  --batch-csv /srv/rockbase/data/mail1.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --master /srv/rockbase/data/master.csv \
  --state /srv/rockbase/workbench/mail-loop.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21
```

Dry-run is the default. Use `--execute-send` only for an approved SMTP batch and `--execute-sync` only after reviewing the previews. The flags are independent, and credentials are redacted from orchestrator state and output.

### Full stage runner

`scripts/run_full_pipeline.py` builds a stage list for the broader server flow. It can include S1 enrichment, S2 Mail1 generation, S5 OCR, mail send, and reply synchronization. `scripts/rockbase_orchestrator.py` executes that list with:

- atomic JSON state writes;
- ordered stages and artifact checks;
- bounded retries and timeout handling;
- pause markers and resumable completion;
- approval files for send and sync;
- output and credential redaction;
- optional Console run registration.

Plan before execution:

```bash
python -m scripts.run_full_pipeline \
  --csv /srv/rockbase/data/master.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --state /srv/rockbase/workbench/full-pipeline.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21 \
  --date 2026-09-21 \
  --with-s1 --with-s5 --plan
```

The full runner is not a universal adapter for every historical skill or platform. Its S2 generation path currently supports YouTube only; see [migration status](docs/inventory/MIGRATION_STATUS.md) for the remaining consolidation work.

### Health and host supervision

```bash
python -m scripts.rockbase_health \
  --state /srv/rockbase/workbench/full-pipeline.json
```

The command emits JSON and returns:

- `0`: healthy or complete;
- `1`: degraded or incomplete;
- `2`: missing, invalid, or failed state.

Systemd service/timer examples are included for health checks. Restart policy, secret-manager wiring, alert routing, and host-specific service policy remain deployment-owned.

## Business paths

### S1: discover and enrich

The API export paths for Instagram, TikTok, and YouTube use ScrapeCreators. Export writes raw and summary JSON to the workbench; it does not modify the master CSV.

```bash
python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_export.py \
  --csv /srv/rockbase/data/master.csv \
  --api-key "$SCRAPECREATORS_API_KEY" \
  --rows 2,8,11 \
  --date 2026-09-21
```

Preview and apply separately:

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

`apply` creates a dated backup before writing.

### S2: generate Mail1

```bash
python skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py \
  --input /srv/rockbase/data/master.csv \
  --api-key "$OPENAI_API_KEY" \
  --base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --model "${LLM_MODEL:-gpt-4o-mini}" \
  --dry-run
```

The historical filename is retained for compatibility; the script calls an OpenAI-compatible `chat.completions` endpoint and does not start Codex. Remove `--dry-run` only after reviewing the audit output.

### S2/S3: send, receive, and sync

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

Read [`mailkit/README.md`](mailkit/README.md) for SMTP, receiver, Postfix, rate limits, and local send-to-receive rehearsal.

### S5: multimodal OCR

```bash
python skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py \
  --image-dir /srv/rockbase/workbench/2026-09-21/screenshots \
  --csv-path /srv/rockbase/data/master.csv \
  --ocr-engine llm \
  --llm-base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --llm-model "${LLM_VISION_MODEL:-gpt-4o-mini}" \
  --dry-run
```

The result continues through review thresholds, row matching, duplicate handling, backup, and write-back rules. The endpoint must support image input.

## Automation coverage and remaining gaps

The code automates the following today: stage construction and execution, state persistence, retries, timeouts, pause/resume, artifact validation, send/sync approval gates, output redaction, run inspection, health JSON, local Docker startup, S1 export/apply, S2 generation, mailkit transport, S3 reply synchronization, and S5 OCR processing.

The remaining work is not one single missing feature. It falls into these evidence-based categories:

| Area | Current boundary |
| --- | --- |
| Historical skill consolidation | 17 historical skills are not yet rewritten behind one unified CLI and capability model. Legacy entrypoints remain. |
| Universal pipeline coverage | The full runner wires optional S1/S5/mail stages, but its S2 generation path currently supports YouTube only. Not every platform and historical workflow is a single end-to-end graph. |
| Path portability | `${ROCKBASE_HOME}`, CWD, `PYTHONPATH`, and `sys.path` assumptions remain in historical files. `audit_server_paths` inventories them; it does not migrate them. |
| Capability registry | There is no complete machine-readable registry for every skill's inputs, outputs, side effects, required credentials, and policy. |
| Cross-workflow approval | Console approval covers local send and sync gates. There is no generalized write-confirmation protocol shared by every historical write path. |
| External notifications | Health JSON and exit codes are available to systemd/cron/supervisors. Built-in Slack, Feishu, email, or webhook alert delivery is not implemented. |
| Deployment supervision | Runner retries exist, but restart policy, alert routing, secret-manager integration, and host-specific operational policy must be configured by the deployment. |
| Optional dependency CI | Gmail, browser, OCR, social, and LLM dependency groups are not all exercised continuously in a complete CI matrix. |
| Real-account acceptance | Real Gmail/SMTP/receiver, Feishu, social APIs, production master data, quotas, permissions, and deliverability have not been accepted automatically. Credentials and production data are intentionally absent. |
| Production data migration | Production master CSV migration, backup retention, reconciliation, and business sign-off remain operator-owned. |
| Cross-system CI | There is no repository-wide CI matrix covering every historical skill, optional dependency group, Docker runtime, systemd behavior, and every supported platform. |
| Vendor-specific integrations | No external notification vendor or generalized business-system connector is included in the current merged server layer. |

This means the project is automated for repeatable offline/server execution, but it is not yet a universal, self-governing production platform. The largest code items are consolidation, coverage, portability, governance, and CI. Real-account acceptance and deployment policy are intentionally external responsibilities.

## Safety boundaries

- Run export, OCR, and mail operations in dry-run or preview mode first.
- `mailkit.send` is dry-run by default; `--execute` is an explicit send operation.
- `--s1-apply`, `--s2-write`, `--s5-write`, `--execute-send`, and `--execute-sync` are explicit write/side-effect controls.
- Back up the master CSV before write-back and verify the target path.
- Do not invent an address, audience number, collaboration, or creator fact when it cannot be verified.
- Keep credentials, cookies, browser profiles, real email, real creator data, production CSVs, screenshots, and business data out of the repository and logs.
- Use the local Console preview account and isolated volume for demonstrations; do not point it at production state without deployment review.
- Do not run old macOS/Chrome paths on the server when an API, SDK, or mailkit server path exists.

## Verification

Run the main suite from the repository root:

```bash
.venv/bin/python -m pytest -q
```

Run mailkit's local checks:

```bash
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/test_smoke.py
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/demo_local_loop.py
```

Audit historical path assumptions:

```bash
.venv/bin/python -m scripts.audit_server_paths . \
  --output workbench/server-path-audit.json
```

These checks prove local contracts and wiring. They do not prove real-account permissions, API quota, email deliverability, third-party availability, or production data correctness.

## Repository map

```text
skills/                                historical business skills and source-specific rules
mailkit/                               SMTP send, HTTP receive, reply/sent synchronization
rockbase/                              shared path and configuration helpers
scripts/run_full_pipeline.py           full stage-list builder
scripts/rockbase_orchestrator.py       resumable stage executor
scripts/rockbase_health.py              JSON health check and exit status
scripts/audit_server_paths.py          portability audit
console/                               authenticated operations workbench
Dockerfile / docker-compose.yml        container runtime
 docs/                                 setup, operations, migration notes, ADRs
tests/                                 offline and local-loopback contract tests
templates/                             example operational templates
```

Every skill directory has its own `SKILL.md`. The repository README is the deployment map; skill files contain source-specific fields and destructive-action boundaries.

## Documentation

- [Setup and self-check](docs/SETUP.md)
- [Dependency matrix](docs/DEPENDENCY_MATRIX.md)
- [Migration status](docs/inventory/MIGRATION_STATUS.md)
- [Phase 2 orchestration](docs/phase2-orchestration.md)
- [Phase 3 operations](docs/phase3-operations.md)
- [Console operations](docs/console-operations.md)
- [Security notes](SECURITY.md)
- [mailkit guide](mailkit/README.md)
- [LLM endpoint ADR](docs/adr/0002-llm-openai-compatible-sdk.md)
- [Multimodal OCR ADR](docs/adr/0003-direct-multimodal-ocr.md)

## License and data

This repository contains no production credentials, cookies, browser profiles, historical mail, real creator lists, or business data. Example configurations use placeholders. Keep operational data outside the repository and keep deployment copies private.

---

# 中文

Rockbase 是一套运行在服务器上的达人外联自动化工具。它负责达人发现与补全、Mail1 外联准备、发信、收信、回复整理、活跃素材处理，以及把审核后的结果写回主表。

它是 Python 源码仓库，带有可选的 Docker 运维控制台；不是托管 SaaS，也不再依赖 Codex 才能运行主要业务链路。

## 当前状态

当前仓库由两层组成：

- `skills/` 下的业务技能：发现、Mail1 生成、回复恢复、活跃素材补全、截图/OCR。
- `scripts/`、`console/`、`mailkit/` 下的服务器运行层：可恢复编排、健康检查、带认证的运行控制、SMTP/HTTP 邮件传输和本地验证。

服务器运行层已经能够在离线夹具和本地 loopback 服务上运行。真实账号验收不属于仓库测试套件，生产密钥和生产数据也不会进入仓库。

## 流程

```text
S1 发现/补全
        |
        v
S2 生成 Mail1 ---> mailkit.send ---> 公司 SMTP
        |                                   |
        |                                   v
        +---------------------------- S3 receiver
                                            |
                                            v
                                   回收 / 解析 / 同步回复
                                            |
                                            v
                         S4 活跃素材 ---> S5 OCR/匹配
                                            |
                                            v
                                      审核后的主表
```

写入采用分阶段方式：先导出或生成，再查看报告，最后备份后 apply。发信和同步默认是 dry-run，必须显式传执行参数。编排器和 Console 对发信、同步还提供额外审批闸门。

## 安装与测试

要求 Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,llm]'
python -m pytest -q
```

默认测试使用假数据和本地 loopback 服务，验证请求契约、解析、阶段接线、preview/write 边界、状态持久化和安全控制。它不会证明真实第三方账号的权限、额度、投递能力或可用性。

## Docker 控制台

Rockbase Console 是带认证的运维工作台，可查看运行、查看阶段输出、暂停/恢复运行、批准有副作用的动作，以及终止运行。它使用 session cookie、CSRF 防护、viewer/operator 角色、JSONL 审计流和严格的同源内容策略。

镜像以非特权用户运行。Compose 配置绑定 loopback，使用只读根文件系统、`/tmp` tmpfs、丢弃 Linux capability、`no-new-privileges` 和持久化 Console 数据卷。

```bash
docker build -t rockbase-console:local .
docker run --rm \
  --name rockbase-console \
  -p 127.0.0.1:8790:8790 \
  -v rockbase-console-data:/var/lib/rockbase/console \
  rockbase-console:local
```

如果本机提供 Docker Compose：

```bash
docker compose up --build
```

浏览器访问 `http://127.0.0.1:8790`。配置通过环境变量注入，不要提交凭据或生产状态。详细的账号初始化、部署目录和 API 契约见 [Console 运维文档](docs/console-operations.md)。

## 编排与健康检查

`scripts/run_mail_loop.py` 可以从已有 Mail1 CSV 开始，串起 mailkit 发信、收信、拉取和同步阶段。它原子持久化状态，校验产物后才跳过已完成阶段，并支持中断后恢复。默认 dry-run，只有批准后的批次才使用 `--execute-send` 和 `--execute-sync`。

`scripts/run_full_pipeline.py` 构建更完整的阶段列表，可选择接入 S1、S2、S5、发信和回复同步。`scripts/rockbase_orchestrator.py` 提供原子状态、阶段顺序、产物检查、重试、超时、暂停标记、审批文件、输出脱敏和 Console 运行登记。

```bash
python -m scripts.run_full_pipeline \
  --csv /srv/rockbase/data/master.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --state /srv/rockbase/workbench/full-pipeline.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21 \
  --date 2026-09-21 \
  --with-s1 --with-s5 --plan
```

健康检查：

```bash
python -m scripts.rockbase_health \
  --state /srv/rockbase/workbench/full-pipeline.json
```

返回码为：`0` 健康或完成，`1` 降级或未完成，`2` 状态缺失、无效或失败。systemd service/timer 示例已经提供，但重启策略、告警路由、secret manager 和主机级策略仍由部署方配置。

## 还没有自动化的地方

当前已经自动化的内容包括：阶段构建与执行、状态持久化、重试、超时、暂停/恢复、产物校验、发信/同步审批闸门、输出脱敏、运行查看、健康 JSON、本地 Docker 启动、S1 导出与应用、S2 生成、mailkit 收发、S3 回复同步和 S5 OCR 处理。

剩余边界如下：

| 领域 | 当前边界 |
| --- | --- |
| 历史技能统一 | 17 个历史 skill 尚未统一到一个 CLI 和 capability 模型，旧入口仍然存在。 |
| 全流程覆盖 | full runner 能接入 S1/S5/mail 阶段，但 S2 生成目前只支持 YouTube；并非所有平台和历史流程都已成为一条统一端到端图。 |
| 路径可移植性 | 历史文件仍有 `${ROCKBASE_HOME}`、CWD、`PYTHONPATH`、`sys.path` 假设；路径审计只负责盘点，不负责迁移。 |
| 能力注册表 | 没有完整机器可读注册表统一描述每个 skill 的输入、输出、副作用、凭据和策略。 |
| 通用写入审批 | Console 覆盖本地发信和同步闸门；所有历史写入路径尚未共用一个通用确认协议。 |
| 外部通知 | 有健康 JSON 和退出码可供 supervisor 使用，但没有内置 Slack、飞书、邮件或 webhook 告警发送层。 |
| 部署监管 | 编排器有重试，但服务重启、告警路由、secret manager 和主机策略需要部署方配置。 |
| 可选依赖 CI | Gmail、browser、OCR、social、LLM 依赖组尚未在完整 CI 矩阵中持续全部执行。 |
| 真实账号验收 | 真实 Gmail/SMTP/receiver、飞书、社交 API、生产主表、额度、权限和投递能力尚未自动验收。凭据和生产数据按设计不进仓库。 |
| 生产数据迁移 | 生产主表迁移、备份保留、对账和业务签字仍由操作人员负责。 |
| 跨系统 CI | 尚无覆盖所有历史 skill、可选依赖、Docker、systemd 和所有支持平台的完整仓库级 CI 矩阵。 |
| 厂商集成 | 当前合入的服务器层没有外部通知厂商或通用业务系统连接器。 |

因此，项目已经能自动执行可重复的离线/服务器流程，但还不是一个覆盖所有历史技能、平台和生产账号的全自动自治平台。代码侧最大的工作是统一入口、扩大覆盖、清理路径依赖、建立能力治理和补齐 CI；真实账号验收及部署策略则属于外部责任。

## 安全边界

- 导出、OCR、邮件操作先使用 dry-run 或 preview。
- `mailkit.send` 默认 dry-run；`--execute` 才是实际发信。
- `--s1-apply`、`--s2-write`、`--s5-write`、`--execute-send`、`--execute-sync` 都是明确的写入或副作用开关。
- 主表写回前必须备份并核对目标路径。
- 无法验证的邮箱、粉丝数、合作关系或达人事实不得编造。
- 凭据、cookie、浏览器 profile、真实邮件、真实达人数据、生产 CSV、截图和业务数据不得进入仓库或日志。
- Console 演示使用隔离 volume 和预览账号；未经部署审查不要指向生产状态。

## 验证命令

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/test_smoke.py
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/demo_local_loop.py
.venv/bin/python -m scripts.audit_server_paths . \
  --output workbench/server-path-audit.json
```

这些命令验证本地契约和流程接线，不验证真实账号权限、API 额度、邮件投递、第三方可用性或生产数据正确性。

## 文档

- [安装与自检](docs/SETUP.md)
- [依赖矩阵](docs/DEPENDENCY_MATRIX.md)
- [迁移状态](docs/inventory/MIGRATION_STATUS.md)
- [Phase 2 编排](docs/phase2-orchestration.md)
- [Phase 3 运维](docs/phase3-operations.md)
- [Console 运维](docs/console-operations.md)
- [安全说明](SECURITY.md)
- [mailkit 指南](mailkit/README.md)

## 许可证与数据

仓库不包含生产凭据、cookie、浏览器 profile、历史邮件、真实达人名单或业务数据。示例配置只使用占位符。运行数据放在仓库之外，部署副本保持私有。
