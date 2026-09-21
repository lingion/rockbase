# Phase 3 Operations and Long-Tail Migration

## Operational questions

The host operator needs three answers:

1. Did the latest pipeline finish successfully?
2. If it did not, which stage and attempt failed?
3. When did the latest successful stage finish?

`python -m scripts.rockbase_health --state <state.json>` emits one JSON report for those questions. It exits `0` for `ok`, `1` for degraded/incomplete, and `2` for missing, invalid, or failed state. The systemd health service intentionally has no notification vendor dependency: systemd, cron, or the host's existing supervisor can alert on the exit code and retain the JSON line.

## Health checks

Install and enable:

```bash
sudo install -m 0644 deploy/rockbase-phase2-health.service /etc/systemd/system/
sudo install -m 0644 deploy/rockbase-phase2-health.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rockbase-phase2-health.timer
systemctl status rockbase-phase2-health.timer
systemctl start rockbase-phase2-health.service
journalctl -u rockbase-phase2-health.service -n 20
```

The health output contains only stage names, statuses, attempts, timestamps, and bounded failure summaries. It must not contain credentials or full email bodies.

## Long-tail path audit

The historical skills are not all one compatible application. Do not mechanically rewrite every `${ROCKBASE_HOME}` or `sys.path` occurrence. Run the audit before migrating a selected entrypoint:

```bash
python -m scripts.audit_server_paths . --output workbench/server-path-audit.json
```

The audit reports these categories:

- hard blockers: literal macOS/Windows user paths; exit code `2`;
- `${ROCKBASE_HOME}` references;
- CWD assumptions;
- `PYTHONPATH`/`sys.path` injection.

The categories are migration inventory, not automatic proof of a bug. A selected skill still needs a dry-run and an external-directory smoke test after conversion.

## Phase 3 acceptance matrix

| Area | Offline proof | Not proven |
|---|---|---|
| Phase 2 runner | unit tests for state, retry, resume, redaction | supervisor restart behavior on a target host |
| Mailkit | fake SMTP + loopback receiver + master sync | real SMTP deliverability |
| Health | success/failure/missing-state JSON and exit codes | vendor notification delivery |
| Path audit | fixture classification and repository report | correctness of every historical skill |
| S1/S2/S5 | CLI contracts and dry-run boundaries | real API quota and account permissions |

Run the repository verification matrix:

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/test_smoke.py
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/demo_local_loop.py
.venv/bin/python -m scripts.audit_server_paths . --output /tmp/rockbase-path-audit.json
```

Real-account acceptance remains an operator-owned step. Use test accounts and test master data first; never put tokens, cookies, mail, or production CSVs in the repository or test fixtures.
