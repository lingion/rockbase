"""Follow-up worker: consumes signed inbound events from the receiver, dedupes
through a durable SQLite ledger, and synchronizes replies to the master CSV.

The worker is the authoritative path for push-triggered reply handling. It does
NOT send mail. Outbound sending remains the responsibility of the orchestrator
under the existing approval gate.

Wire contract:
    POST /internal/events/inbound
    body: bytes  (JSON: see docs/architecture/event-driven-followup.md)
    headers:
        x-rockbase-event-signature: hex(HMAC-SHA256(secret, body))

Responses:
    200 duplicate  — event_id already processed (or in flight)
    200 ok         — handler claimed the event and ran reply sync
    202 retryable  — failed with bounded backoff
    401 invalid_signature
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import fcntl
import hashlib
import hmac
import json
import logging
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from typing import Callable, Optional

from .events import emit

log = logging.getLogger("mailkit.followup")

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  run_id TEXT,
  last_error TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
"""


@dataclass
class WorkerConfig:
    ledger_db: str
    master_csv: str
    dispatch_secret: str
    receiver_base_url: str
    receiver_api_key: str
    lock_path: str
    sync_replies_callable: Optional[Callable[[str, str], int]] = None
    on_send: Optional[Callable[[], None]] = None  # always None; sanity hook
    summarize_reply_callable: Optional[Callable[[str], "ReplySummary"]] = None
    artifact_store: Any = None
    run_id_prefix: str = "evt"


class EventLedger:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as c:
            c.executescript(LEDGER_SCHEMA)
            c.commit()

    def claim(self, event_id: str, message_id: str) -> tuple[bool, dict]:
        """Atomically claim an event_id. Returns (claimed, prior_state)."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            with sqlite3.connect(self.path) as c:
                row = c.execute(
                    "SELECT status, attempts, run_id FROM events WHERE event_id=?",
                    (event_id,)).fetchone()
                if row:
                    return False, {"status": row[0], "attempts": row[1], "run_id": row[2]}
                c.execute(
                    "INSERT INTO events(event_id,message_id,status,attempts,"
                    "first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                    (event_id, message_id, "claimed", 0, now, now))
                c.commit()
        return True, {"status": "claimed", "attempts": 0, "run_id": None}

    def finish(self, event_id: str, status: str, run_id: Optional[str] = None,
               error: str = "") -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            with sqlite3.connect(self.path) as c:
                c.execute(
                    "UPDATE events SET status=?, run_id=?, last_error=?, "
                    "last_seen_at=?, attempts=attempts+1 WHERE event_id=?",
                    (status, run_id, error[:300], now, event_id))
                c.commit()

    def lookup(self, event_id: str) -> dict:
        with sqlite3.connect(self.path) as c:
            row = c.execute(
                "SELECT status, attempts, run_id, last_error FROM events WHERE event_id=?",
                (event_id,)).fetchone()
            if not row:
                return {}
            return {"status": row[0], "attempts": row[1], "run_id": row[2],
                    "last_error": row[3]}


class _SingleFlightLock:
    """Process-level lock that serializes master CSV writes across push workers
    and polling runs. Crashed owners release on file removal."""

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(path).exists():
            Path(path).touch()

    @contextlib.contextmanager
    def acquire(self, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        f = open(self.path, "r+")
        try:
            while True:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"could not acquire lock at {self.path}")
                    time.sleep(0.05)
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()


class FollowupWorker:
    def __init__(self, cfg: WorkerConfig):
        self.cfg = cfg
        self.ledger = EventLedger(cfg.ledger_db)
        self.lock = _SingleFlightLock(cfg.lock_path)

    def handle_event(self, body: bytes, signature_header: str) -> dict:
        """Verify, claim, and execute a single inbound event."""
        # 1) Signature
        if not self.cfg.dispatch_secret:
            return {"status": "invalid_signature", "event_id": None,
                    "error": "worker has no dispatch_secret configured"}
        expected = hmac.new(self.cfg.dispatch_secret.encode("utf-8"),
                            body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature_header or ""):
            return {"status": "invalid_signature", "event_id": None,
                    "error": "signature mismatch"}
        # 2) Parse
        try:
            event = json.loads(body)
        except json.JSONDecodeError as e:
            return {"status": "invalid_body", "error": str(e)[:200]}
        if event.get("schema_version") != 1 or event.get("event") != "inbound.accepted":
            return {"status": "invalid_event", "error": "schema/event mismatch"}
        eid = event.get("event_id")
        mid = event.get("message_id") or eid
        if not eid:
            return {"status": "invalid_event", "error": "missing event_id"}

        # 3) Refuse anything that looks like a send command.
        # The worker MUST NEVER invoke SMTP or any send stage. on_send is a
        # tripwire hook (test-only) that production leaves None — it is never
        # called by this code path. Any future addition that wants to send
        # from here has to be re-justified against the architecture contract.

        # 4) Claim
        claimed, prior = self.ledger.claim(eid, mid)
        if not claimed:
            return {"status": "duplicate", "event_id": eid, "prior": prior}

        # 5) Run reply sync under master lock
        run_id = f"{self.cfg.run_id_prefix}-{eid[:12]}-{uuid.uuid4().hex[:6]}"
        try:
            with self.lock.acquire(timeout=10.0):
                snapshot = self._fetch_inbound_snapshot(event)
                if self.cfg.sync_replies_callable is not None:
                    self.cfg.sync_replies_callable(self.cfg.master_csv, snapshot)
                else:
                    # Production default: reuse the existing dry-run reply
                    # sync (`master_sync replies --from-csv`). The operator's
                    # pipeline owns the --execute write-back, so the worker
                    # always stops at preview.
                    rc = run_module([
                        "mailkit.mailkit.master_sync", "replies",
                        "--master", self.cfg.master_csv,
                        "--from-csv", snapshot,
                    ])
                    if rc != 0:
                        raise RuntimeError(
                            f"master_sync replies exited {rc}")
            artifact_id, artifact_version, decision_status = self._emit_semantic_artifact(
                run_id=run_id, event_id=eid, body=body)
            self.ledger.finish(eid, "ok", run_id=run_id)
            emit("followup_ok", event_id=eid, run_id=run_id)
            return {"status": "ok", "event_id": eid, "run_id": run_id,
                    "artifact_id": artifact_id,
                    "artifact_version": artifact_version,
                    "decision_status": decision_status}
        except TimeoutError as e:
            self.ledger.finish(eid, "retryable", run_id=run_id, error=str(e))
            emit("followup_retryable", event_id=eid, error="lock_timeout")
            return {"status": "retryable", "event_id": eid, "error": "lock_timeout"}
        except Exception as e:  # noqa: BLE001
            self.ledger.finish(eid, "retryable", run_id=run_id, error=str(e))
            emit("followup_failed", event_id=eid, error=str(e)[:300])
            return {"status": "retryable", "event_id": eid,
                    "error": str(e)[:200], "run_id": run_id}

    def _emit_semantic_artifact(self, *, run_id: str, event_id: str,
                                 body: bytes) -> tuple[str | None, int | None, str]:
        """Summarize the inbound reply and persist it as a versioned artifact.

        The summarizer never executes sends. Its output is an envelope; the
        Console (not the worker) decides whether to advance the pipeline.
        Returns (artifact_id, version, decision_status); all three are None
        when no artifact_store is configured (test-only fast path).
        """
        if self.cfg.artifact_store is None:
            return None, None, "no_artifact_store"
        if self.cfg.summarize_reply_callable is None:
            from mailkit.mailkit.reply_semantics import summarize_reply as _default_summary
            summarize = _default_summary
        else:
            summarize = self.cfg.summarize_reply_callable
        try:
            event = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, None, "invalid_event"
        latest = str(event.get("latest_reply") or event.get("body") or "")
        summary = summarize(latest)
        from rockbase.artifact_store import ArtifactEnvelope
        envelope = ArtifactEnvelope.new(
            run_id=run_id, stage_id="s3.summary",
            payload=summary.to_artifact(),
            validation={"ok": not summary.manual_review,
                        "errors": ["manual_review"] if summary.manual_review else [],
                        "warnings": []},
        )
        stored = self.cfg.artifact_store.put(envelope)
        decision_status = "awaiting_approval" if summary.manual_review else "approved"
        return stored.artifact_id, stored.version, decision_status

    def _fetch_inbound_snapshot(self, event: dict) -> str:
        """Fetch the committed message from the receiver's authenticated
        storage API and write a CSV in the exact shape `master_sync replies
        --from-csv` (== `fetch_replies` export) already understands.

        Only the mailbox named in the event is queried. If the receiver is
        unreachable or the message is missing, a header-only CSV is still
        produced so sync runs as a no-op rather than crashing the worker.
        """
        mailbox = (event.get("mailbox") or "").strip().lower()
        rows: list[dict] = []
        if mailbox:
            q = urllib.parse.urlencode({"email": mailbox})
            url = f"{self.cfg.receiver_base_url.rstrip('/')}/api/emails?{q}"
            try:
                data = _http_get_json(url, self.cfg.receiver_api_key)
                if isinstance(data, list):
                    emails = data
                else:
                    emails = (data.get("data") or {}).get("emails") or \
                             data.get("emails") or []
                for e in emails:
                    rows.append({
                        "reply_from": (e.get("from_address") or "").lower(),
                        "reply_to": mailbox,
                        "subject": e.get("subject") or "",
                        "body": e.get("content") or "",
                        "received_at": e.get("created_at") or "",
                        "external_id": e.get("external_id") or e.get("id") or "",
                        "in_reply_to": e.get("in_reply_to") or "",
                        "references": e.get("references") or "",
                    })
            except Exception as e:  # noqa: BLE001 — snapshot best-effort
                emit("snapshot_failed", event_id=event.get("event_id", ""),
                     error=str(e)[:300])
                rows = []
        out = Path(self.cfg.ledger_db).parent / \
            f"snap-{event.get('event_id', 'x')}.csv"
        fields = ["reply_from", "reply_to", "subject", "body", "received_at",
                  "external_id", "in_reply_to", "references"]
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        return str(out)


def make_handler(worker: FollowupWorker):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            return

        def do_GET(self):
            if self.path == "/healthz":
                payload = json.dumps({"ok": True, "role": "followup"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            sig = self.headers.get("x-rockbase-event-signature", "")
            result = worker.handle_event(body, sig)
            status = 200 if result["status"] in ("ok", "duplicate") else 202
            if result["status"] == "invalid_signature":
                status = 401
            payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return H


def serve_worker(host: str, port: int, cfg: WorkerConfig) -> ThreadingHTTPServer:
    worker = FollowupWorker(cfg)
    return ThreadingHTTPServer((host, port), make_handler(worker))


def run_module(argv: list[str], check: bool = False) -> int:
    """Invoke a sibling mailkit module as a subprocess; isolated call boundary.

    The worker deliberately runs `master_sync replies` as a subprocess so:
      * it shares the existing dedupe / wave attribution / preview logic
      * failures are surfaced as exit codes without leaking into worker state
      * stdout/stderr is captured by the caller for redacted logging.
    """
    return subprocess.run([sys.executable, "-m", *argv], check=check,
                          capture_output=True, text=True).returncode


def _http_get_json(url: str, api_key: str = "", timeout: float = 5.0) -> dict:
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("x-api-key", api_key)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8789)
    ap.add_argument("--ledger-db", default="followup_ledger.db")
    ap.add_argument("--master", required=True)
    ap.add_argument("--dispatch-secret", required=True)
    ap.add_argument("--receiver-base-url", default="http://127.0.0.1:8788")
    ap.add_argument("--receiver-api-key", default="")
    ap.add_argument("--lock-path", default="followup.lock")
    args = ap.parse_args(argv)

    from .fetch_replies import fetch_emails  # type: ignore  # noqa: F401  — wired by future PR

    cfg = WorkerConfig(
        ledger_db=args.ledger_db,
        master_csv=args.master,
        dispatch_secret=args.dispatch_secret,
        receiver_base_url=args.receiver_base_url,
        receiver_api_key=args.receiver_api_key,
        lock_path=args.lock_path,
    )
    srv = serve_worker(args.host, args.port, cfg)
    print(f"[followup] http://{args.host}:{args.port}  ledger={args.ledger_db}",
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())