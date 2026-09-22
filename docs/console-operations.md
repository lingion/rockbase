# Rockbase Console Operations Guide

This guide covers local-only operation of the Rockbase operations console. The
console binds to `127.0.0.1:8790` by default and exposes the loopback HTTP API
plus the static workbench. The recommended runtime is the Docker image; the
image contains the service and static assets, while only console state is
persisted outside the container.

## Language

The workbench opens in English. Use the `EN` / `中文` control on the login page
or top bar to switch languages. The choice is stored in the browser only and
is not sent to the server.

## Docker startup

Install Docker Compose v2, then run from the repository root:

```bash
docker compose up --build -d
curl --fail http://127.0.0.1:8790/api/health
docker compose logs -f console
```

The Compose file publishes only `127.0.0.1:8790`, runs as the unprivileged
`rockbase` user, drops Linux capabilities, and persists state in the
`rockbase-console-state` volume. Stop it with `docker compose down`; use
`docker compose down -v` only when intentionally deleting console sessions,
approvals, and audit history. No demo account or external credential is baked
into the image: provision `users.toml` in the mounted state volume before
expecting login to work.

## Account provisioning

Accounts live in `users.toml`. Generate salt and hash locally with the same
stdlib routine the runner uses:

```bash
python3 - <<'PY'
import hashlib, secrets
salt = secrets.token_hex(16)
password = "REPLACE-ME"
iterations = 200_000
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
print(f"salt_hex='{salt}'\npassword_hash_hex='{digest.hex()}'\niterations={iterations}")
PY
```

Paste the printed values into a `[[users]]` entry with `username`, `role`
(`viewer` or `operator`) and the generated hex. Set `umask 0077` before writing
the file so the secret stays operator-only.

## Local startup

1. Set the runtime base directory (default `/etc/rockbase/console`):

   ```bash
   export ROCKBASE_CONSOLE_BASE_DIR=/etc/rockbase/console
   ```

2. Launch via systemd after deploying `deploy/rockbase-console.service`:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now rockbase-console
   ```

3. Confirm the loopback port is reachable locally:

   ```bash
   curl --silent http://127.0.0.1:8790/api/health
   ```

## Remote access

Two supported paths; never expose the loopback bind without one of them.

- **SSH tunnel**: `ssh -L 8790:127.0.0.1:8790 operator@server`.
- **TLS reverse proxy**: deploy `deploy/rockbase-console-nginx.conf` after
  provisioning a certificate. Configure nginx to forward to `127.0.0.1:8790`
  and set `ROCKBASE_CONSOLE_HOST=127.0.0.1` plus
  `ROCKBASE_CONSOLE_COOKIE_SECURE=true`.

## Approvals

The console requires a 24-hour approval record before any `send` or `sync`
write stage can start. Each approval records:

- run id
- gate (`send` or `sync`)
- operator username
- batch label (`[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`)
- issued and expiry timestamps

Reruns that newly enable a write gate require fresh approval. The audit log
records every parameter diff and approval event with the originating request
id.

## Recovery

- **Interrupting a runaway run**: open the workbench, select the run, click
  *Terminate* and confirm. The state transitions to `interrupted`, still-running
  stages are rewritten to `failed` with `error="interrupted by console kill"`,
  and the next resume re-validates mailkit manifest + master `.bak` backups.
- **Approval expiry**: re-issue via *Approve gate*; the new record overwrites
  the previous one.
- **Health drift**: `python3 -m scripts.rockbase_health --state <path>` reports
  `critical` for interrupted or failed stages and `degraded` for `running` /
  `pending`.

## Backups

The console persists only metadata (sessions, audit, approvals). Back up the
mailkit manifest and master `.bak` artifacts separately and independently.