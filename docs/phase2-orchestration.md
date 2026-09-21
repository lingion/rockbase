# Phase 2 Server Orchestration

## Scope

The production entrypoint is `python -m scripts.run_full_pipeline`. It composes existing scripts; it does not replace their API, SMTP, receiver, rate-limit, or master-sync logic.

The default path is conservative:

- S2 Mail1 generation runs audit-only unless `--s2-write` is supplied.
- mailkit send is dry-run unless `--execute-send` is supplied.
- master write-back is dry-run unless `--execute-sync` is supplied.
- S1 and S5 are omitted unless `--with-s1` or `--with-s5` is supplied.
- S1 apply and S5 CSV write-back remain preview/dry-run unless their separate write flags are supplied.

Credentials are loaded by the existing scripts from environment/configuration. The runner redacts credential-bearing CLI values in its JSON state file.

## Example

```bash
cd /srv/rockbase
python -m scripts.run_full_pipeline \
  --csv /srv/rockbase/data/master.csv \
  --config /srv/rockbase/mailkit/config.toml \
  --state /srv/rockbase/workbench/phase2-2026-09-21.json \
  --fetch-out /srv/rockbase/workbench/replies_2026-09-21 \
  --date 2026-09-21 \
  --retries 1
```

Review the state JSON and generated previews before adding `--execute-send` or `--execute-sync`.

## Cron

Use a locked-down service account, an absolute working directory, and an environment file supplied by the host's secret manager. Do not put keys in the crontab line.

```cron
17 6 * * * cd /srv/rockbase && /srv/rockbase/.venv/bin/python -m scripts.run_full_pipeline --csv /srv/rockbase/data/master.csv --config /srv/rockbase/mailkit/config.toml --state /srv/rockbase/workbench/phase2-$(date +\%F).json --fetch-out /srv/rockbase/workbench/replies_$(date +\%F) --date $(date +\%F) --retries 1 >> /var/log/rockbase/phase2.log 2>&1
```

The cron job intentionally omits all write gates. A separate reviewed invocation can add `--execute-send` and `--execute-sync` for an approved run.

## systemd

`deploy/rockbase-phase2.service` is a template. Put credentials in `/etc/rockbase/phase2.env` with mode `0600`; keep operational CSVs and state outside the repository.

```ini
[Unit]
Description=Rockbase Phase 2 pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/srv/rockbase
EnvironmentFile=/etc/rockbase/phase2.env
ExecStart=/bin/sh -c '/srv/rockbase/.venv/bin/python -m scripts.run_full_pipeline --csv /srv/rockbase/data/master.csv --config /srv/rockbase/mailkit/config.toml --state /srv/rockbase/workbench/phase2-current.json --fetch-out /srv/rockbase/workbench/replies-current --date "$ROCKBASE_RUN_DATE" --retries 1'
```

A timer should provide the schedule. The service exits non-zero when any stage fails or a declared artifact is missing.

## Recovery

1. Inspect the state JSON and the last stage's `status`, `attempts`, `returncode`, `stderr`, and `artifacts`.
2. Do not delete the state file. Fix the input/configuration or external service and rerun with the same state path.
3. Completed stages are skipped only while every declared artifact exists. A missing artifact causes that stage to run again.
4. A failed stage stops later stages. The runner never silently proceeds to send or write back.
5. Keep `--execute-send` and `--execute-sync` off while recovering. mailkit's own manifest remains the authority for sent-message idempotency.
6. Before master write-back, review the generated preview and confirm the target path. mailkit creates its own backup on execute.

## Verification

Offline verification requires no production credentials:

```bash
cd /srv/rockbase
.venv/bin/python -m pytest -q
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/test_smoke.py
PYTHONPATH=mailkit .venv/bin/python mailkit/tests/demo_local_loop.py
```

These checks prove local contracts and loopback behavior, not real account permission, deliverability, quotas, or third-party API access.
