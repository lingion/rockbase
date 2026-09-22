# Rockbase

Rockbase is a server-oriented creator outreach automation toolkit. It discovers and enriches creator records, prepares Mail1 outreach, sends and receives email, extracts reply data, processes active assets, and writes reviewed results back to a master CSV.

It is a Python source repository with an optional Dockerized operations console. It is not a hosted SaaS service, and it does not require Codex to run the business paths.

[简体中文](README.zh-CN.md)

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

## Full-project Docker runtime

The Docker image contains the whole Rockbase project: `skills/`, `rockbase/`, `scripts/`, `mailkit/`, `console/`, templates, and operational docs. The Console is only the control plane. `docker-compose.yml` runs the same full-source image as four explicit roles:

| Service | Role |
| --- | --- |
| `console` | Authenticated operations workbench on `127.0.0.1:8790` |
| `receiver` | Mailkit inbound receiver on `127.0.0.1:8788` |
| `pipeline` | One-shot S1/S2/mailkit/S3/S5 business pipeline |
| `health` | One-shot state-file health probe |

Build and start the long-running services:

```bash
docker build -t rockbase:local .
docker compose up --build -d console receiver
curl --fail http://127.0.0.1:8790/api/health
curl --fail http://127.0.0.1:8788/api/health
```

Run the complete pipeline as a one-shot service after mounting/provisioning the data volume:

```bash
docker compose --profile pipeline run --rm pipeline
```

Probe the persisted pipeline state:

```bash
docker compose --profile health run --rm health
```

All roles use an unprivileged user, a read-only root filesystem, `/tmp` tmpfs, dropped Linux capabilities, `no-new-privileges`, and named volumes for console state, run state, mailkit data, master data, and workbench artifacts. The image never contains credentials or production data. Set `ROCKBASE_MASTER_CSV` and `ROCKBASE_MAILKIT_CONFIG` to paths under the mounted data volume before running the pipeline.

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
skills/                         historical business skills and source-specific rules
mailkit/                        SMTP send, HTTP receive, reply/sent synchronization
rockbase/                       shared path and configuration helpers
scripts/run_full_pipeline.py   full stage-list builder
scripts/rockbase_orchestrator.py resumable stage executor
scripts/rockbase_health.py     JSON health check and exit status
scripts/audit_server_paths.py  portability audit
console/                        authenticated operations workbench
Dockerfile / docker-compose.yml container runtime
docs/                           setup, operations, migration notes, ADRs
tests/                          offline and local-loopback contract tests
templates/                      example operational templates
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
