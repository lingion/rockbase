# Rockbase

Rockbase 是一套运行在服务器上的达人外联自动化工具。它负责达人发现与补全、Mail1 外联准备、发信、收信、回复整理、活跃素材处理，以及把审核后的结果写回主表。

它是 Python 源码仓库，带有可选的 Docker 运维控制台；不是托管 SaaS，也不再依赖 Codex 才能运行主要业务链路。

[English README](README.md)

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

## 完整项目的 Docker 运行

Docker 镜像包含整个 Rockbase 项目：`skills/`、`rockbase/`、`scripts/`、`mailkit/`、`console/`、templates 和运维文档。Console 只是控制平面。`docker-compose.yml` 把同一份全源码镜像同时用作四个明确的角色：

| 服务 | 角色 |
| --- | --- |
| `console` | `127.0.0.1:8790` 上带认证的运维工作台 |
| `receiver` | `127.0.0.1:8788` 上的 mailkit 入站接收端 |
| `pipeline` | 一次性执行 S1/S2/mailkit/S3/S5 业务链路 |
| `health` | 一次性对状态文件做健康探测 |

构建并启动常驻服务：

```bash
docker build -t rockbase:local .
docker compose up --build -d console receiver
curl --fail http://127.0.0.1:8790/api/health
curl --fail http://127.0.0.1:8788/api/health
```

在挂载好数据卷后用一次性服务运行完整业务链路：

```bash
docker compose --profile pipeline run --rm pipeline
```

对持久化的链路状态做一次健康探测：

```bash
docker compose --profile health run --rm health
```

所有角色都以非特权用户运行，使用只读根文件系统、`/tmp` tmpfs、丢弃 Linux capability、`no-new-privileges`，并通过命名卷分别持久化 console 状态、运行状态、mailkit 数据、主表数据和 workbench 产物。镜像内不含凭据或生产数据。运行 pipeline 前必须把 `ROCKBASE_MASTER_CSV` 和 `ROCKBASE_MAILKIT_CONFIG` 指向已挂载数据卷里的具体路径。

## 编排与健康检查

### 可恢复邮件编排

`scripts/run_mail_loop.py` 可以从已有 Mail1 CSV 开始，串起 mailkit 发信、收信、拉取和同步阶段。它原子持久化状态，校验产物后才跳过已完成阶段，并支持中断后恢复。

```bash
python -m scripts.run_mail_loop \
  --batch-csv /srv/rockbase/data/mail1.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --master /srv/rockbase/data/master.csv \
  --state /srv/rockbase/workbench/mail-loop.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21
```

默认是 dry-run。只对已批准批次使用 `--execute-send`；查看预览后才使用 `--execute-sync`。两个开关相互独立，凭据会从编排器状态和输出中脱敏。

### 完整阶段运行器

`scripts/run_full_pipeline.py` 构建更完整的阶段列表，可选择接入 S1 补全、S2 Mail1 生成、S5 OCR、发信和回复同步。`scripts/rockbase_orchestrator.py` 提供：

- 原子 JSON 状态写入；
- 阶段顺序和产物检查；
- 有界重试和超时处理；
- 暂停标记和中断恢复；
- 发信和同步审批文件；
- 输出和凭据脱敏；
- 可选的 Console 运行登记。

先执行计划：

```bash
python -m scripts.run_full_pipeline \
  --csv /srv/rockbase/data/master.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --state /srv/rockbase/workbench/full-pipeline.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21 \
  --date 2026-09-21 \
  --with-s1 --with-s5 --plan
```

完整运行器不是所有历史 skill 和平台的通用适配器。目前 S2 生成路径只支持 YouTube；剩余统一工作见[迁移状态](docs/inventory/MIGRATION_STATUS.md)。

### 健康检查

```bash
python -m scripts.rockbase_health \
  --state /srv/rockbase/workbench/full-pipeline.json
```

命令输出 JSON，并返回：

- `0`：健康或已完成；
- `1`：降级或未完成；
- `2`：状态缺失、无效或失败。

仓库提供 systemd service/timer 示例。服务重启策略、secret manager、告警路由和主机级策略仍由部署方配置。

## 业务路径

### S1：发现和补全

Instagram、TikTok、YouTube 的 API 导出路径使用 ScrapeCreators。导出只把 raw 和 summary JSON 写入 workbench，不修改主表。

```bash
python skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_export.py \
  --csv /srv/rockbase/data/master.csv \
  --api-key "$SCRAPECREATORS_API_KEY" \
  --rows 2,8,11 \
  --date 2026-09-21
```

预览和写回分开执行：

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

`apply` 写入前会生成带日期的备份。

### S2：生成 Mail1

```bash
python skills/S2-ag-gmail-bulk-drafts/scripts/gmail/fill_mail1_with_codex.py \
  --input /srv/rockbase/data/master.csv \
  --api-key "$OPENAI_API_KEY" \
  --base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --model "${LLM_MODEL:-gpt-4o-mini}" \
  --dry-run
```

文件名是历史兼容名；脚本调用 OpenAI-compatible `chat.completions` endpoint，不会启动 Codex。查看 audit 输出后再移除 `--dry-run`。

### S2/S3：收发和同步

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

SMTP、receiver、Postfix、限速和本机收发彩排见 [`mailkit/README.md`](mailkit/README.md)。

### S5：多模态 OCR

```bash
python skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py \
  --image-dir /srv/rockbase/workbench/2026-09-21/screenshots \
  --csv-path /srv/rockbase/data/master.csv \
  --ocr-engine llm \
  --llm-base-url "${LLM_BASE_URL:-https://api.openai.com/v1}" \
  --llm-model "${LLM_VISION_MODEL:-gpt-4o-mini}" \
  --dry-run
```

结果会继续经过审核阈值、行匹配、查重、备份和写回规则。endpoint 必须支持图片输入。

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
- 服务器上不要继续运行旧的 macOS/Chrome 路径；优先使用 API、SDK 和 mailkit 服务器路径。

## 验证命令

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/test_smoke.py
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/demo_local_loop.py
.venv/bin/python -m scripts.audit_server_paths . \
  --output workbench/server-path-audit.json
```

这些命令验证本地契约和流程接线，不验证真实账号权限、API 额度、邮件投递、第三方可用性或生产数据正确性。

## 仓库结构

```text
skills/                          历史业务技能和来源规则
mailkit/                         SMTP 发信、HTTP 收信、回复/发送同步
rockbase/                        共享路径和配置助手
scripts/run_full_pipeline.py    完整阶段列表构建器
scripts/rockbase_orchestrator.py 可恢复阶段执行器
scripts/rockbase_health.py      JSON 健康检查和退出状态
scripts/audit_server_paths.py   可移植性审计
console/                         带认证的运维控制台
Dockerfile / docker-compose.yml  容器运行配置
docs/                            安装、运维、迁移说明和 ADR
tests/                           离线及本地 loopback 契约测试
templates/                       示例运维模板
```

每个 skill 目录都有自己的 `SKILL.md`。README 是部署总览；字段定义、来源规则和破坏性操作边界以各 skill 文档为准。

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
