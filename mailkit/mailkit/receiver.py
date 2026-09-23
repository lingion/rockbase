#!/usr/bin/env python3
"""路线B：公司服务器自建收信端。mailgofer 兼容 API + SQLite，纯 stdlib。

契约与 mailgofer 对齐：
  POST /api/inbound    {to, from, subject, text, html, raw, received_at}
  GET  /api/emails?email=xxx    → {success, data:{emails:[...], count}}
  POST /api/mailboxes  {address}
  DELETE /api/emails/clear?email=xxx
  GET  /api/health

鉴权: 请求头 x-api-key（或 ?api_key=）。--api-key 为空 = dev 模式（放行并警告）。
用法: python -m mailkit.receiver --db mailkit.db --port 8788 --api-key <key>
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from email import message_from_bytes
from email.policy import default as default_policy
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib import request as urllib_request

from .events import emit

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10MB： Enough for mail with attachments, prevents DoS from large payloads
MAX_ADDR_LEN = 254  # RFC 5321 maximum length for email addresses

SCHEMA = """
CREATE TABLE IF NOT EXISTS mailboxes (
  id TEXT PRIMARY KEY,
  address TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  mailbox_id TEXT NOT NULL,
  external_id TEXT,
  from_addr TEXT,
  to_addr TEXT,
  subject TEXT,
  text_body TEXT,
  html_body TEXT,
  in_reply_to TEXT DEFAULT '',
  refs TEXT DEFAULT '',
  raw_json TEXT,
  received_at TEXT NOT NULL,
  FOREIGN KEY(mailbox_id) REFERENCES mailboxes(id)
);
CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_addr);
CREATE INDEX IF NOT EXISTS idx_messages_recv ON messages(received_at);
"""

_lock = threading.Lock()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def ensure_mailbox(self, address: str) -> str:
        address = address.lower().strip()
        with _lock:
            row = self.conn.execute(
                "SELECT id FROM mailboxes WHERE address=?", (address,)).fetchone()
            if row:
                return row["id"]
            mid = uuid.uuid4().hex
            self.conn.execute(
                "INSERT INTO mailboxes(id,address,created_at) VALUES(?,?,?)",
                (mid, address, utcnow()))
            self.conn.commit()
            return mid

    def put_message(self, mbx_id: str, msg: dict) -> str:
        mid = uuid.uuid4().hex
        with _lock:
            self.conn.execute(
                "INSERT INTO messages(id,mailbox_id,external_id,from_addr,to_addr,"
                "subject,text_body,html_body,in_reply_to,refs,raw_json,received_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid, mbx_id, msg.get("external_id") or uuid.uuid4().hex,
                 (msg.get("from") or "").lower(), (msg.get("to") or "").lower(),
                 msg.get("subject") or "", msg.get("text") or "", msg.get("html") or "",
                 msg.get("in_reply_to") or "", msg.get("references") or "",
                 json.dumps(msg.get("raw") or {}, ensure_ascii=False),
                 msg.get("received_at") or utcnow()))
            self.conn.commit()
        return mid

    def list_by_address(self, address: str, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id,external_id,to_addr,from_addr,subject,text_body,html_body,"
            "in_reply_to,refs,received_at FROM messages "
            "WHERE to_addr=? ORDER BY received_at DESC LIMIT ?",
            (address.lower().strip(), limit)).fetchall()
        return [{"id": r["id"], "external_id": r["external_id"],
                 "email_address": r["to_addr"], "from_address": r["from_addr"],
                 "subject": r["subject"], "content": r["text_body"],
                 "html_content": r["html_body"], "in_reply_to": r["in_reply_to"],
                 "references": r["refs"], "created_at": r["received_at"]}
                for r in rows]

    def clear(self, address: str) -> int:
        with _lock:
            cur = self.conn.execute("DELETE FROM messages WHERE to_addr=?",
                                    (address.lower().strip(),))
            self.conn.commit()
            return cur.rowcount


def parse_mime(raw: bytes) -> dict:
    """raw MIME → {from,to,subject,text,html}，stdlib email 解析。"""
    msg = message_from_bytes(raw, policy=default_policy)
    text = html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not text:
                text = part.get_content()
            elif ct == "text/html" and not html:
                html = part.get_content()
    else:
        content = msg.get_content()
        if msg.get_content_type() == "text/html":
            html = content
        else:
            text = content
    to_hdr = msg.get("To")
    if isinstance(to_hdr, list):
        to_hdr = to_hdr[0]
    return {"from": parseaddr(str(msg.get("From", "")))[1].lower(),
            "to": parseaddr(str(to_hdr or ""))[1].lower(),
            "subject": str(msg.get("Subject", "")), "text": text, "html": html,
            "external_id": str(msg.get("Message-ID", "")).strip("<>"),
            "in_reply_to": str(msg.get("In-Reply-To", "")).strip(),
            "references": " ".join(str(msg.get("References", "")).split())}


def make_handler(store: Store, api_key: str, dispatch_url: str = "",
                 dispatch_secret: str = "", dispatch_timeout: float = 2.0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # 安静：访问日志走结构化事件
            pass

        def _begin(self):
            self._rid = uuid.uuid4().hex[:12]
            self._t0 = time.monotonic()
            self._status = None
            self._route = ""

        def _end(self, method: str):
            emit("http_request", request_id=self._rid, method=method,
                 route=self._route, status=self._status,
                 dur_ms=round((time.monotonic() - self._t0) * 1000, 1))

        def _json(self, obj: dict, status: int = 200):
            self._status = status
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            # security-and-hardening：禁 MIME 嗅探、禁缓存（邮件内容敏感）
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Request-Id", self._rid)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self, qs: dict) -> bool:
            if not api_key:
                return True
            given = self.headers.get("x-api-key") or (qs.get("api_key") or [""])[0]
            ok = hmac.compare_digest(given.encode(), api_key.encode())  # 防时序侧信道
            if not ok:
                emit("auth_failed", request_id=self._rid, peer=self.client_address[0])
            return ok

        class BodyTooLarge(Exception):
            pass

        MAX_DRAIN_BYTES = 32 * 1024 * 1024  # 超限请求体最多排空这么多，多了直接断连

        def _drain(self, n: int) -> None:
            while n > 0:
                chunk = self.rfile.read(min(65536, n))
                if not chunk:
                    break
                n -= len(chunk)

        def _body(self) -> dict:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self.close_connection = True
                return {}
            if n > MAX_BODY_BYTES:
                self._drain(min(n, self.MAX_DRAIN_BYTES))
                if n > self.MAX_DRAIN_BYTES:
                    self.close_connection = True
                raise self.BodyTooLarge()
            raw = self.rfile.read(n) if n else b"{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}

        def do_GET(self):
            self._begin()
            try:
                u = urlparse(self.path)
                self._route = u.path
                qs = parse_qs(u.query)
                if u.path == "/api/health":
                    return self._json({"ok": True, "time": utcnow()})
                if not self._authed(qs):
                    return self._json({"success": False, "error": "unauthorized"}, 401)
                if u.path == "/api/emails":
                    email = (qs.get("email") or [""])[0].strip().lower()
                    if not email:
                        return self._json({"success": False,
                                           "error": "missing_email_parameter"}, 400)
                    if len(email) > MAX_ADDR_LEN:
                        return self._json({"success": False,
                                           "error": "invalid_address"}, 400)
                    emails = store.list_by_address(email)
                    return self._json({"success": True,
                                       "data": {"emails": emails, "count": len(emails)}})
                return self._json({"success": False, "error": "not_found"}, 404)
            except Exception as e:  # noqa: BLE001 —— 内部细节只进事件日志，不回给调用方
                emit("handler_error", request_id=self._rid, route=u.path,
                     error=str(e)[:300])
                return self._json({"success": False, "error": "internal_error"}, 500)
            finally:
                self._end("GET")

        def do_POST(self):
            self._begin()
            try:
                u = urlparse(self.path)
                self._route = u.path
                qs = parse_qs(u.query)
                if not self._authed(qs):
                    return self._json({"success": False, "error": "unauthorized"}, 401)
                try:
                    body = self._body()
                except self.BodyTooLarge:
                    return self._json({"success": False,
                                       "error": "payload_too_large"}, 413)
                if u.path == "/api/mailboxes":
                    addr = (body.get("address") or body.get("email") or "").strip().lower()
                    if not addr or "@" not in addr or len(addr) > MAX_ADDR_LEN:
                        return self._json({"success": False,
                                           "error": "invalid_address"}, 400)
                    mbx_id = store.ensure_mailbox(addr)
                    return self._json({"success": True,
                                       "data": {"id": mbx_id, "address": addr}})
                if u.path == "/api/inbound":
                    to = (body.get("to") or body.get("address") or "").strip().lower()
                    if not to or len(to) > MAX_ADDR_LEN:
                        return self._json({"success": False, "error": "missing_to"
                                           if not to else "invalid_address"}, 400)
                    if body.get("raw") and not body.get("text") and not body.get("html"):
                        raw = body["raw"]
                        try:
                            parsed = parse_mime(raw.encode("utf-8", "surrogateescape")
                                                if isinstance(raw, str) else raw)
                            body = {**parsed, **{k: v for k, v in body.items()
                                                 if k != "raw" and v}}
                            to = (body.get("to") or to).lower()
                        except Exception as e:  # noqa: BLE001
                            emit("mime_parse_failed", request_id=self._rid,
                                 error=str(e)[:300])
                            return self._json({"success": False,
                                               "error": "mime_parse_failed"}, 400)
                    mbx_id = store.ensure_mailbox(to)
                    mid = store.put_message(mbx_id, body)
                    emit("inbound_accepted", request_id=self._rid, to=to,
                         external_id=(body.get("external_id") or "")[:120])
                    if dispatch_url:
                        _dispatch_inbound_event(
                            event={
                                "schema_version": 1,
                                "event": "inbound.accepted",
                                "event_id": mid,
                                "message_id": mid,
                                "external_id": (body.get("external_id") or "")[:120],
                                "mailbox": to,
                                "received_at": body.get("received_at") or utcnow(),
                                "attempt": 1,
                            },
                            url=dispatch_url,
                            secret=dispatch_secret,
                            timeout=dispatch_timeout,
                        )
                    return self._json({"success": True, "data": {"id": mid}})
                return self._json({"success": False, "error": "not_found"}, 404)
            except Exception as e:  # noqa: BLE001
                emit("handler_error", request_id=self._rid, route=self._route,
                     error=str(e)[:300])
                return self._json({"success": False, "error": "internal_error"}, 500)
            finally:
                self._end("POST")

        def do_DELETE(self):
            self._begin()
            try:
                u = urlparse(self.path)
                self._route = u.path
                qs = parse_qs(u.query)
                if not self._authed(qs):
                    return self._json({"success": False, "error": "unauthorized"}, 401)
                if u.path == "/api/emails/clear":
                    email = (qs.get("email") or [""])[0].strip().lower()
                    if not email:
                        return self._json({"success": False,
                                           "error": "missing_email_parameter"}, 400)
                    return self._json({"success": True, "data":
                                       {"count": store.clear(email)}})
                return self._json({"success": False, "error": "not_found"}, 404)
            except Exception as e:  # noqa: BLE001
                emit("handler_error", request_id=self._rid, route=self._route,
                     error=str(e)[:300])
                return self._json({"success": False, "error": "internal_error"}, 500)
            finally:
                self._end("DELETE")

    return Handler


def _dispatch_inbound_event(event: dict, url: str, secret: str,
                            timeout: float = 2.0) -> None:
    """Best-effort asynchronous notification of a committed inbound message.

    Fire-and-forget by design: the message is already durably committed, and a
    slow or unavailable worker must never delay or fail the SMTP-side
    acknowledgement. The payload carries identifiers only.
    """

    def _send() -> None:
        body = json.dumps(event, ensure_ascii=False,
                          sort_keys=True).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        req = urllib_request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "x-rockbase-event-signature": sig})
        try:
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                resp.read()
            emit("dispatch_ok", event_id=event.get("event_id", ""))
        except Exception as e:  # noqa: BLE001 — never break inbound ack
            emit("dispatch_failed", event_id=event.get("event_id", ""),
                 error=str(e)[:300])

    threading.Thread(target=_send, daemon=True).start()


def serve(db: str, port: int, api_key: str, host: str = "127.0.0.1",
          dispatch_url: str = "", dispatch_secret: str = "",
          dispatch_timeout: float = 2.0) -> ThreadingHTTPServer:
    store = Store(db)
    if not api_key:
        print("[warn] api-key 为空 = dev 模式，任何本地进程都能读写邮件", flush=True)
    srv = ThreadingHTTPServer((host, port), make_handler(store, api_key,
                                                           dispatch_url,
                                                           dispatch_secret,
                                                           dispatch_timeout))
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="mailkit.db")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--dispatch-url", default="",
                    help="POST a signed inbound.accepted event to this URL after commit")
    ap.add_argument("--dispatch-secret", default="",
                    help="HMAC-SHA256 secret shared with the event consumer")
    ap.add_argument("--dispatch-timeout", type=float, default=2.0)
    args = ap.parse_args(argv)
    srv = serve(args.db, args.port, args.api_key, args.host,
                dispatch_url=args.dispatch_url,
                dispatch_secret=args.dispatch_secret,
                dispatch_timeout=args.dispatch_timeout)
    print(f"[receiver] http://{args.host}:{args.port}  db={args.db}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
