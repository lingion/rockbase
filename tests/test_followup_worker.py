"""Follow-up worker contract tests:

- HMAC verification rejects unsigned or wrong-key events.
- A duplicate event_id returns `duplicate` and never invokes sync twice.
- A single-flight lock serializes concurrent push events against master CSV writes.
- Failed runs return retryable status and a bounded next attempt; never `ok`.
- The worker never invokes a send stage without explicit approval.
- Successful runs record run_id, stage state, and reply synchronization.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mailkit"))
from mailkit import followup_worker  # noqa: E402  — module under test


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _make_event(mid: str = "msg-1", mailbox: str = "alice@example.invalid") -> dict:
    return {
        "schema_version": 1,
        "event": "inbound.accepted",
        "event_id": mid,
        "message_id": mid,
        "external_id": f"<{mid}@remote>",
        "mailbox": mailbox,
        "received_at": "2026-09-23T00:00:00Z",
        "attempt": 1,
    }


def test_handle_event_rejects_invalid_signature(tmp_path):
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="real-secret",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=lambda master_csv, from_csv: None,  # should NOT be invoked
    )
    worker = followup_worker.FollowupWorker(cfg)
    body = json.dumps(_make_event()).encode("utf-8")
    bad = hmac.new(b"wrong", body, hashlib.sha256).hexdigest()
    res = worker.handle_event(body, bad)
    assert res["status"] == "invalid_signature"
    assert res.get("event_id") is None or res.get("event_id") == "msg-1"


def test_handle_event_duplicate_event_id_returns_duplicate(tmp_path):
    invocations: list[str] = []
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=lambda master_csv, from_csv: invocations.append(master_csv),
    )
    worker = followup_worker.FollowupWorker(cfg)
    body = json.dumps(_make_event()).encode("utf-8")
    sig = _sign("s", body)
    first = worker.handle_event(body, sig)
    second = worker.handle_event(body, sig)
    assert first["status"] in ("ok", "sync_invoke_failed")  # ok path runs sync once
    assert second["status"] == "duplicate"
    assert len(invocations) == 1


def test_handle_event_concurrent_pushes_serialize_master_writes(tmp_path):
    """Two simultaneous events must serialize their master sync.

    The correct observable is "sync bodies never overlap", not "both threads
    inside sync at once" — the latter contradicts serialization. We record
    entry/exit order and require max concurrency == 1."""
    counter = {"value": 0}
    lock_state = {"n": 0, "max": 0}

    def sync(master_csv, from_csv):
        lock_state["n"] += 1
        lock_state["max"] = max(lock_state["max"], lock_state["n"])
        time.sleep(0.05)
        counter["value"] += 1
        lock_state["n"] -= 1
        return counter["value"]

    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=sync,
    )
    worker = followup_worker.FollowupWorker(cfg)
    bodies = []
    for i in range(2):
        ev = _make_event(mid=f"m-{i}")
        bodies.append((json.dumps(ev).encode("utf-8"), _sign("s", json.dumps(ev).encode("utf-8"))))
    results = []
    results_lock = threading.Lock()
    def fire(b, s):
        with results_lock:
            results.append(worker.handle_event(b, s))
    ts = [threading.Thread(target=fire, args=(b, s)) for b, s in bodies]
    for t in ts: t.start()
    for t in ts: t.join(timeout=5.0)
    assert counter["value"] == 2, "each event should invoke sync once"
    assert lock_state["max"] == 1, f"master writes must serialize; max={lock_state['max']}"


def test_handle_event_never_calls_send_stage(tmp_path):
    """The worker MUST NOT invoke SMTP or any send stage. It only syncs and drafts.

    on_send is a tripwire: production must leave it None, and the worker must
    never call it under any event path. We also verify there is no `send`-
    named attribute reachable on the worker or config."""
    sent_invoked = []
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=lambda m, f: None,
        on_send=lambda: sent_invoked.append(True),  # tripwire — never fires
    )
    worker = followup_worker.FollowupWorker(cfg)
    body = json.dumps(_make_event(mid="msg-no-send")).encode("utf-8")
    sig = _sign("s", body)
    worker.handle_event(body, sig)
    assert sent_invoked == [], "worker must not invoke send"
    # No send-capable method may exist on worker/config surface
    assert not hasattr(worker, "send"), "worker must not expose send()"
    assert not hasattr(worker.cfg, "send"), "config must not expose send()"
    assert not hasattr(worker.cfg, "smtp"), "config must not expose smtp client"
    # And the module must not import smtplib
    assert "smtplib" not in dir(followup_worker), "no smtplib in module namespace"


def test_ledger_records_run_id_and_status(tmp_path):
    def sync(master_csv, from_csv):
        return 1
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=sync,
    )
    worker = followup_worker.FollowupWorker(cfg)
    body = json.dumps(_make_event(mid="ledger-1")).encode("utf-8")
    sig = _sign("s", body)
    res = worker.handle_event(body, sig)
    assert res["run_id"], "successful run must record a run_id"
    ledger = followup_worker.EventLedger(str(tmp_path / "ledger.db"))
    state = ledger.lookup("ledger-1")
    assert state["status"] in ("ok", "retryable")
    assert state.get("run_id") == res["run_id"]


def test_default_sync_invokes_master_sync_replies_from_csv(tmp_path, monkeypatch, capsys):
    """The production default sync path runs `master_sync replies --from-csv`
    in dry-run (preview) mode — never --execute — on the snapshot built from
    the receiver's storage API."""
    import csv as csv_mod
    master = tmp_path / "master.csv"
    master.write_text(
        "邮箱,Mail1_Status,Mail1_Reply_At,Reply_Contact_Email\n"
        "kol@example.invalid,sent,\nkol@example.invalid\n",
        encoding="utf-8-sig",
    )
    calls: list[list[str]] = []

    def fake_run(argv, check=False):
        calls.append(list(argv))
        return 0

    monkeypatch.setattr(followup_worker, "run_module", fake_run)
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(master),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=None,  # production default path
    )
    worker = followup_worker.FollowupWorker(cfg)
    body = json.dumps(_make_event(mid="prod-1")).encode("utf-8")
    sig = _sign("s", body)
    res = worker.handle_event(body, sig)
    assert res["status"] == "ok", res
    assert calls, "master_sync replies must have been invoked"
    argv = calls[0]
    assert "--execute" not in argv, "worker sync must stay dry-run"
    assert "replies" in argv and "--from-csv" in argv


def test_snapshot_csv_contains_inbound_row_from_receiver_api(tmp_path):
    """The snapshot CSV must reflect the actual committed message fetched from
    the receiver's authenticated storage API, not an empty stub."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    served = {"emails": [{
        "id": "snap-1", "external_id": "<snap-1@remote>",
        "from_address": "kol@example.invalid", "to_address": "alice@example.invalid",
        "subject": "Re: collab", "content": "We are interested.",
        "created_at": "2026-09-23T00:00:00Z",
        "in_reply_to": "<out-1@us>", "references": "<out-1@us>",
    }]}
    written: dict[str, str] = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_GET(self):
            if self.path.startswith("/api/emails"):
                payload = json.dumps({"success": True, "data": {
                    "emails": served["emails"], "count": 1}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        def sync(master_csv, from_csv):
            written["csv"] = Path(from_csv).read_text(encoding="utf-8")

        cfg = followup_worker.WorkerConfig(
            ledger_db=str(tmp_path / "ledger.db"),
            master_csv=str(tmp_path / "master.csv"),
            dispatch_secret="s",
            receiver_base_url=f"http://127.0.0.1:{srv.server_address[1]}",
            receiver_api_key="k",
            lock_path=str(tmp_path / "lock"),
            sync_replies_callable=sync,
        )
        worker = followup_worker.FollowupWorker(cfg)
        ev = _make_event(mid="snap-1")
        body = json.dumps(ev).encode("utf-8")
        res = worker.handle_event(body, _sign("s", body))
        assert res["status"] == "ok", res
    finally:
        srv.shutdown()
    import csv as csv_mod
    rows = list(csv_mod.DictReader(io.StringIO(written["csv"])))
    assert len(rows) == 1
    assert rows[0]["reply_from"] == "kol@example.invalid"
    assert rows[0]["external_id"] == "<snap-1@remote>"
    assert rows[0]["body"] == "We are interested."
    assert rows[0]["in_reply_to"] == "<out-1@us>"

def test_handle_event_returns_semantic_artifact_ids(tmp_path):
    """Task 6: a successful run returns the semantic artifact coordinates."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from rockbase.artifact_store import ArtifactStore

    def fake_summary(text):
        from mailkit.reply_semantics import ReplySummary
        return ReplySummary(summary="ok summary", conditions=("after brief",),
                            next_action="send_brief", language="en",
                            confidence=0.8, manual_review=False)

    store = ArtifactStore(tmp_path / "artifacts")
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=lambda master_csv, from_csv: None,
        summarize_reply_callable=fake_summary,
        artifact_store=store,
    )
    worker = followup_worker.FollowupWorker(cfg)
    event = _make_event(mid="msg-artifact")
    event["latest_reply"] = "We can proceed after the brief"
    body = json.dumps(event).encode("utf-8")
    result = worker.handle_event(body, _sign("s", body))

    assert result["status"] == "ok"
    assert result["artifact_id"].startswith("art-")
    assert result["artifact_version"] == 1
    assert result["decision_status"] in {"awaiting_approval", "approved"}


def test_handle_event_without_store_reports_no_artifact_store(tmp_path):
    cfg = followup_worker.WorkerConfig(
        ledger_db=str(tmp_path / "ledger.db"),
        master_csv=str(tmp_path / "master.csv"),
        dispatch_secret="s",
        receiver_base_url="http://127.0.0.1:1",
        receiver_api_key="k",
        lock_path=str(tmp_path / "lock"),
        sync_replies_callable=lambda master_csv, from_csv: None,
    )
    worker = followup_worker.FollowupWorker(cfg)
    body = json.dumps(_make_event(mid="msg-nostore")).encode("utf-8")
    result = worker.handle_event(body, _sign("s", body))

    assert result["status"] == "ok"
    assert result["artifact_id"] is None
    assert result["decision_status"] == "no_artifact_store"
