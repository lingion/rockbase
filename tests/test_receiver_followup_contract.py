"""Receiver inbound → follow-up worker event dispatch contract.

Red-phase tests. These lock the contract that:

- The HTTP response is acknowledged only after the SQLite commit succeeds.
- The signed dispatch happens asynchronously and does not block the response.
- The dispatch payload contains identifiers only; never raw bodies, html, text,
  credentials, or API keys.
- The HMAC signature is verifiable on the receiver side.
- A failed/slow downstream does not roll back the stored message.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

# The mailkit package is a nested source distribution in this repository.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mailkit"))
from mailkit import receiver


class _SlowSentinel:
    """Local sink that records the dispatch and can sleep to simulate a stuck worker."""

    def __init__(self, sleep_seconds: float = 0.0):
        self.sleep_seconds = sleep_seconds
        self.events: list[dict[str, Any]] = []
        self.signatures: list[str] = []
        self.bodies: list[bytes] = []
        self._lock = threading.Lock()

    def handler(self):
        sentinel = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                sig = self.headers.get("x-rockbase-event-signature", "")
                with sentinel._lock:
                    sentinel.bodies.append(raw)
                    sentinel.signatures.append(sig)
                if sentinel.sleep_seconds > 0:
                    time.sleep(sentinel.sleep_seconds)
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {}
                with sentinel._lock:
                    sentinel.events.append(payload)
                self.send_response(202)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"OK")

        return H


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post_inbound(port: int, body: dict) -> tuple[int, dict]:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/inbound",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": "secret"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _wait_for_events(sink: _SlowSentinel, expected: int, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with sink._lock:
            if len(sink.events) >= expected:
                return True
        time.sleep(0.02)
    return False


@pytest.fixture
def running_receiver(tmp_path):
    """Start a receiver wired to a local sentinel sink; return (port, secret, sink)."""
    sink = _SlowSentinel()
    sink_port = _free_port()
    port = _free_port()
    secret = "shared-secret-xyz"
    sink_srv = ThreadingHTTPServer(("127.0.0.1", sink_port), sink.handler())
    threading.Thread(target=sink_srv.serve_forever, daemon=True).start()
    srv = receiver.serve(
        db=str(tmp_path / "m.db"),
        port=port,
        api_key="secret",
        host="127.0.0.1",
        dispatch_url=f"http://127.0.0.1:{sink_port}/internal/events/inbound",
        dispatch_secret=secret,
        dispatch_timeout=2.0,
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # readiness wait
    deadline = time.monotonic() + 2.0
    import urllib.request
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    yield {"port": port, "secret": secret, "sink": sink, "srv": srv, "sink_srv": sink_srv}
    try:
        srv.shutdown()
    except Exception:
        pass
    try:
        sink_srv.shutdown()
    except Exception:
        pass


def test_receiver_returns_200_before_dispatch_succeeds(running_receiver):
    port = running_receiver["port"]
    t0 = time.monotonic()
    status, _ = _post_inbound(
        port,
        {"to": "alice@example.invalid", "from": "bob@example.invalid",
         "subject": "hi", "text": "hello body"},
    )
    dur = time.monotonic() - t0
    assert status == 200
    assert dur < 1.0, f"receiver should respond without waiting for dispatch; took {dur:.2f}s"


def test_receiver_dispatch_payload_omits_body_and_secrets(running_receiver):
    port = running_receiver["port"]
    sink = running_receiver["sink"]
    _post_inbound(
        port,
        {"to": "carol@example.invalid", "from": "dave@example.invalid",
         "subject": "hi", "text": "SECRET BODY", "html": "<p>SECRET</p>",
         "raw": "full-mime-bytes-very-private"},
    )
    assert _wait_for_events(sink, expected=1, timeout=2.0)
    payload = sink.events[-1]
    for forbidden in ("text", "html", "raw", "api_key", "api-key", "authorization", "secret"):
        assert forbidden not in payload, f"dispatch leaked {forbidden!r}: {payload}"
    assert payload["event"] == "inbound.accepted"
    assert payload["schema_version"] == 1
    assert payload["mailbox"] == "carol@example.invalid"
    assert payload["message_id"]
    assert payload["event_id"]


def test_receiver_dispatch_signs_hmac(running_receiver):
    port = running_receiver["port"]
    sink = running_receiver["sink"]
    secret = running_receiver["secret"]
    _post_inbound(port, {"to": "e@e.com", "subject": "s", "text": "t"})
    assert _wait_for_events(sink, expected=1, timeout=2.0)
    body = sink.bodies[-1]
    sig_header = sink.signatures[-1]
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert sig_header == expected


def test_receiver_keeps_message_when_dispatch_fails(tmp_path):
    class FailHandler(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            return
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(500)
            self.end_headers()

    bad_port = _free_port()
    port = _free_port()
    fs = ThreadingHTTPServer(("127.0.0.1", bad_port), FailHandler)
    threading.Thread(target=fs.serve_forever, daemon=True).start()
    try:
        srv = receiver.serve(
            db=str(tmp_path / "m.db"),
            port=port,
            api_key="secret",
            host="127.0.0.1",
            dispatch_url=f"http://127.0.0.1:{bad_port}/internal/events/inbound",
            dispatch_secret="k",
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
        assert len(msgs) == 1
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            fs.shutdown()
        except Exception:
            pass