"""Receiver inbound → follow-up worker event dispatch contract (TDD red).

These tests lock the contract that:
  * HTTP response is acknowledged only after the SQLite commit succeeds.
  * The signed dispatch happens asynchronously and does not block the response.
  * Dispatch payload contains identifiers only; never raw bodies, html, text,
    credentials, or API keys.
  * The HMAC signature is verifiable on the worker side; receiver refuses to
    dispatch without a configured secret.
  * A failed/slow downstream does NOT roll back the stored message.
  * Duplicate external IDs produce stable event_ids (idempotency at the source).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mailkit"))
from mailkit import receiver  # noqa: E402  — inner package under mailkit/


# ---------- helpers ----------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post_inbound(port: int, body: dict, api_key: str = "secret") -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/inbound",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


class _Sink:
    """Local HTTP server that records inbound event deliveries."""

    def __init__(self, sleep_seconds: float = 0.0):
        self.sleep_seconds = sleep_seconds
        self.events: list[dict] = []
        self.signatures: list[str] = []
        self.bodies: list[bytes] = []
        self._lock = threading.Lock()

    def make_handler(self):
        sink = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                sig = self.headers.get("x-rockbase-event-signature", "")
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {}
                with sink._lock:
                    sink.bodies.append(raw)
                    sink.signatures.append(sig)
                    sink.events.append(payload)
                if sink.sleep_seconds > 0:
                    time.sleep(sink.sleep_seconds)
                self.send_response(202)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"OK")

        return H


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def wired_receiver(tmp_path):
    """Yields (port, secret, sink, stop_receiver)."""
    sink = _Sink()
    port = _free_port()
    sink_port = _free_port()
    sink_srv = ThreadingHTTPServer(("127.0.0.1", sink_port), sink.make_handler())
    threading.Thread(target=sink_srv.serve_forever, daemon=True).start()
    secret = "shared-secret-xyz"
    dispatch_url = f"http://127.0.0.1:{sink_port}/internal/events/inbound"
    srv = receiver.serve(
        db=str(tmp_path / "m.db"),
        port=port,
        api_key="secret",
        host="127.0.0.1",
        dispatch_url=dispatch_url,
        dispatch_secret=secret,
        dispatch_timeout=2.0,
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # readiness wait
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    yield {"port": port, "secret": secret, "sink": sink, "srv": srv, "sink_srv": sink_srv}
    sink_srv.shutdown()
    try:
        srv.shutdown()
    except Exception:
        pass


# ---------- tests ----------

def test_receiver_responds_before_dispatch(wired_receiver):
    port = wired_receiver["port"]
    t0 = time.monotonic()
    status, _ = _post_inbound(
        port,
        {"to": "alice@example.invalid", "from": "bob@example.invalid",
         "subject": "hi", "text": "hello"},
    )
    dur = time.monotonic() - t0
    assert status == 200, f"expected 200; got {status}"
    assert dur < 1.0, f"receiver must not wait for dispatch; took {dur:.2f}s"


def test_receiver_dispatch_payload_excludes_bodies_and_secrets(wired_receiver):
    port = wired_receiver["port"]
    sink = wired_receiver["sink"]
    _post_inbound(
        port,
        {"to": "carol@example.invalid", "from": "dave@example.invalid",
         "subject": "hi", "text": "SECRET BODY", "html": "<p>SECRET</p>",
         "raw": "full-mime-bytes-very-private",
         "external_id": "ext-1"},
    )
    assert _wait_until(lambda: len(sink.events) >= 1), "no event delivered"
    payload = sink.events[-1]
    for forbidden in ("text", "html", "raw", "api_key", "api-key", "authorization",
                      "password", "token"):
        assert forbidden not in payload, f"dispatch leaked {forbidden!r}: {payload}"
    assert payload["event"] == "inbound.accepted"
    assert payload["schema_version"] == 1
    assert payload["mailbox"] == "carol@example.invalid"
    assert payload["message_id"]
    assert payload["event_id"]


def test_receiver_dispatch_signs_with_hmac(wired_receiver):
    port = wired_receiver["port"]
    secret = wired_receiver["secret"]
    sink = wired_receiver["sink"]
    _post_inbound(port, {"to": "e@e.com", "subject": "s", "text": "t"})
    assert _wait_until(lambda: len(sink.events) >= 1), "no event delivered"
    body = sink.bodies[-1]
    sig = sink.signatures[-1]
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert sig == expected, "HMAC signature mismatch"


def test_receiver_keeps_message_when_dispatch_fails(tmp_path):
    """Failure of the dispatch endpoint must NOT roll back the persisted message."""
    sink_port = _free_port()

    class FailHandler(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()

    sink_srv = ThreadingHTTPServer(("127.0.0.1", sink_port), FailHandler)
    threading.Thread(target=sink_srv.serve_forever, daemon=True).start()
    port = _free_port()
    secret = "k"
    try:
        srv = receiver.serve(
            db=str(tmp_path / "m.db"),
            port=port,
            api_key="secret",
            host="127.0.0.1",
            dispatch_url=f"http://127.0.0.1:{sink_port}/internal/events/inbound",
            dispatch_secret=secret,
            dispatch_timeout=0.5,
        )
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        time.sleep(0.1)
        status, body = _post_inbound(
            port,
            {"to": "frank@example.invalid", "subject": "s", "text": "t"},
        )
        assert status == 200
        assert body["data"]["id"]
        store = receiver.Store(str(tmp_path / "m.db"))
        msgs = store.list_by_address("frank@example.invalid")
        assert len(msgs) == 1, "message must persist even if dispatch 500s"
    finally:
        sink_srv.shutdown()
        try:
            srv.shutdown()
        except Exception:
            pass


def test_receiver_stable_event_id_for_duplicate_external_id(wired_receiver):
    """Two posts with the same external_id must share event_id so workers dedupe."""
    port = wired_receiver["port"]
    sink = wired_receiver["sink"]
    body = {"to": "dup@example.invalid", "subject": "hi", "text": "x",
            "external_id": "ext-stable"}
    _post_inbound(port, body)
    _post_inbound(port, body)
    assert _wait_until(lambda: len(sink.events) >= 2), "expected two events"
    assert sink.events[0]["event_id"] == sink.events[1]["event_id"], \
        "event_id must be stable for dedupe"


def test_receiver_skips_dispatch_when_secret_unset(tmp_path):
    """If dispatch_secret is empty (no worker configured), receiver must commit but skip dispatch silently."""
    port = _free_port()
    sink_called = {"n": 0}

    class CountSink(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            return

        def do_POST(self):
            sink_called["n"] += 1
            self.send_response(200)
            self.end_headers()

    sink_port = _free_port()
    srv_sink = ThreadingHTTPServer(("127.0.0.1", sink_port), CountSink)
    threading.Thread(target=srv_sink.serve_forever, daemon=True).start()
    try:
        srv = receiver.serve(
            db=str(tmp_path / "m.db"),
            port=port,
            api_key="secret",
            host="127.0.0.1",
            dispatch_url=f"http://127.0.0.1:{sink_port}/",
            dispatch_secret="",
            dispatch_timeout=0.5,
        )
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        time.sleep(0.1)
        status, _ = _post_inbound(port, {"to": "silent@example.invalid",
                                          "subject": "s", "text": "t"})
        assert status == 200
        time.sleep(0.4)
        assert sink_called["n"] == 0, "must not call dispatch when secret unset"
        store = receiver.Store(str(tmp_path / "m.db"))
        assert store.list_by_address("silent@example.invalid")
    finally:
        srv_sink.shutdown()
        try:
            srv.shutdown()
        except Exception:
            pass