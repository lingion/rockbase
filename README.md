# Rockbase

**A creator/KOL marketing automation toolkit — the full S1→S5 outreach workflow plus a self-hosted email send/receive layer.**

English | [中文](#中文)

---

## What this is

Rockbase packages a real, end-to-end creator-marketing pipeline as an installable source toolkit:

- **Workflow toolkit** (repo root, 17 skills): discovery & enrichment, outreach drafting, reply operations, active-asset management, brief matching, delivery checks, OCR, sheet sync, dedupe checks, and invoice generation — organized as five stages, **S1 → S5**.
- **Mail layer** ([`mailkit/`](mailkit/README.md)): a self-hosted SMTP send/receive adapter that replaces manual Gmail work. It covers **S2 outreach sending** and **S3 reply intake**, runs a fully automated local rehearsal loop, and ships its own roadmap and hardening notes.

## Workflow map

```
S1 Discovery/Enrichment → S2 Drafting/Outreach → S3 Reply Ops → S4 Active Assets → S5 Matching, QC & Sync
     inbox enrichment          bulk drafts           reply recovery        active              brief matching,
     fuzzy discovery IG/       (mailkit send)        (mailkit intake)      enrichment          delivery check,
     TikTok/X/YouTube                                                                          OCR & sheet sync,
                                                                                               dedupe, invoices
```

## Repository layout

```
skills/     17 skills, one directory each (README.md + SKILL.md + scripts)
rockbase/   installable path-compatibility layer (rockbase.paths)
mailkit/    self-hosted email send/receive layer (S2/S3 automation)
docs/       setup, dependency matrix, migration status, Gmail authorization
templates/  outreach & ops templates
tests/      offline test cases (paths, S1, S3)
```

## Quick start

Requirements: Python 3.11+. Dependencies are optional and per-skill — install only what you need.

```bash
pip install -e .
python -m pytest -q          # offline cases: paths layer, S1, S3
```

Mail layer local rehearsal (fully automated send → receive → reconcile loop, no external traffic):

```bash
cd mailkit
python tests/test_smoke.py        # 34 checks
python tests/demo_local_loop.py   # end-to-end local rehearsal
```

## Design principles

- **Installable source package, not a turnkey image.** You wire up your own Gmail/Feishu/social/data authorizations; nothing here ships live credentials or business data.
- **Portable paths.** `rockbase.paths` resolves paths as: explicit argument → `ROCKBASE_PROJECT_ROOT` → config file → safe discovery. Unresolved environment variables fail loudly instead of creating garbage directories.
- **Safety rails built in.** Every external write stops for dry-run/preview first; the mail layer defaults to dry-run with rate limiting (3–5 messages per 2 hours) and resumable batches.

## Hard boundaries

- Unauthorized external writes must stop; run a dry-run or preview first.
- First-touch DMs carry no external links or phone numbers; respect the 3–5 messages / 2 hours pacing.
- If contact info can't be verified, record "not available" — never guess.
- Back up production master sheets before writing, and confirm schema/field mapping on the target system.

## Documentation

- [Setup](docs/SETUP.md) · [Dependency matrix](docs/DEPENDENCY_MATRIX.md) · [Migration status](docs/inventory/MIGRATION_STATUS.md)
- [Gmail self-authorization](docs/GOOGLE_GMAIL_SETUP.md) · [Security notes](SECURITY.md)
- Mail layer: [mailkit/README.md](mailkit/README.md) · [Roadmap](mailkit/docs/ROADMAP.md) · [ADR: stdlib-only](mailkit/docs/adr/0001-stdlib-only.md)

## Security statement

This repository contains **no cookies, tokens, secrets, real contact lists, historical emails, or business data**. All configuration uses `PLACEHOLDER` values (see `mailkit/config.example.toml`). Commit history was audited before publishing.

---

# 中文

**Rockbase —— 达人营销自动化工具包:完整的 S1→S5 外联工作流 + 自建邮件收发层。**

## 这是什么

Rockbase 把一条真实跑通的达人营销流水线整理成可安装的源码工具包:

- **工作流工具包**(仓库根目录,17 个 Skill):发现与补全、外联草稿、回复运营、活跃资产化、Brief 匹配、交付检查、OCR、表格同步、查重、发票生成,按 **S1→S5** 五个阶段组织。
- **邮件收发层**([`mailkit/`](mailkit/README.md)):自建 SMTP 收发适配器,替代 Gmail 手工操作,覆盖 **S2 外联发送**与 **S3 回复接收**,含本机全自动彩排闭环、加固记录与路线图。

## 工作流地图

```
S1 发现/补全 → S2 草稿/外联 → S3 回复运营 → S4 活跃资产 → S5 匹配、QC 与同步
  inbox 补全      批量草稿         回复恢复        活跃化          brief 匹配、交付检查、
  社媒模糊发现    (mailkit 发)    (mailkit 收)    enrichment      OCR/表格同步、查重、发票
  IG/TikTok/X/YT
```

## 目录结构

```
skills/     17 个 Skill,每个一个目录(README.md + SKILL.md + 脚本)
rockbase/   可安装的路径兼容层(rockbase.paths)
mailkit/    自建邮件收发层(S2/S3 自动化)
docs/       安装说明、依赖矩阵、迁移状态、Gmail 授权
templates/  外联与运营模板
tests/      离线测试用例(路径层、S1、S3)
```

## 快速开始

要求 Python 3.11+。依赖按 Skill 可选,只装需要的:

```bash
pip install -e .
python -m pytest -q          # 离线用例:路径层、S1、S3
```

邮件层本机彩排(全自动 发→收→对账 闭环,无外部流量):

```bash
cd mailkit
python tests/test_smoke.py        # 34 项检查
python tests/demo_local_loop.py   # 端到端本机彩排
```

## 设计原则

- **可安装的源码包,不是开箱即用镜像。** Gmail/飞书/社媒/数据服务授权由使用者自行完成;本包不携带任何实时凭据或业务数据。
- **可移植路径。** `rockbase.paths` 解析顺序:显式参数 → `ROCKBASE_PROJECT_ROOT` → 配置文件 → 安全发现。未解析的环境变量直接报错,不会生成字面量错误目录。
- **内置安全护栏。** 所有外部写入先 dry-run/预览;邮件层默认 dry-run + 限速(每 2 小时 3–5 条)+ 断点续传。

## 重要边界

- 未授权的外部写入操作必须停止;先运行 dry-run 或预览。
- 初次 DM 不带外链与手机号;遵循每 2 小时 3–5 条的发送节奏。
- 联系方式查不到时填写"拿不到",不得猜测或编造。
- 对生产主表写入前先备份,并在目标系统完成 schema/字段映射确认。

## 文档

- [安装说明](docs/SETUP.md) · [依赖矩阵](docs/DEPENDENCY_MATRIX.md) · [迁移状态](docs/inventory/MIGRATION_STATUS.md)
- [Gmail 自主授权](docs/GOOGLE_GMAIL_SETUP.md) · [安全说明](SECURITY.md)
- 邮件层:[mailkit/README.md](mailkit/README.md) · [路线图](mailkit/docs/ROADMAP.md) · [ADR:仅用标准库](mailkit/docs/adr/0001-stdlib-only.md)

## 安全声明

本仓库**不包含任何 Cookie、token、密钥、真实名单、历史邮件或业务数据**。所有配置均为 `PLACEHOLDER` 占位值(见 `mailkit/config.example.toml`)。公开前已审计全部提交历史。
