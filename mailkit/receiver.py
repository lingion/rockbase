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
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from email import message_from_bytes
from email.policy import default as default_policy
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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


def make_handler(store: Store, api_key: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # 安静
            pass

        def _json(self, obj: dict, status: int = 200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self, qs: dict) -> bool:
            if not api_key:
                return True
            given = self.headers.get("x-api-key") or (qs.get("api_key") or [""])[0]
            return given == api_key

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}

        def do_GET(self):
            u = urlparse(self.path)
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
                emails = store.list_by_address(email)
                return self._json({"success": True,
                                   "data": {"emails": emails, "count": len(emails)}})
            return self._json({"success": False, "error": "not_found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if not self._authed(qs):
                return self._json({"success": False, "error": "unauthorized"}, 401)
            body = self._body()
            if u.path == "/api/mailboxes":
                addr = (body.get("address") or body.get("email") or "").strip().lower()
                if not addr or "@" not in addr:
                    return self._json({"success": False, "error": "invalid_address"}, 400)
                mbx_id = store.ensure_mailbox(addr)
                return self._json({"success": True,
                                   "data": {"id": mbx_id, "address": addr}})
            if u.path == "/api/inbound":
                to = (body.get("to") or body.get("address") or "").strip().lower()
                if not to:
                    return self._json({"success": False, "error": "missing_to"}, 400)
                if body.get("raw") and not body.get("text") and not body.get("html"):
                    raw = body["raw"]
                    try:
                        parsed = parse_mime(raw.encode("utf-8", "surrogateescape")
                                            if isinstance(raw, str) else raw)
                        body = {**parsed, **{k: v for k, v in body.items()
                                             if k != "raw" and v}}
                        to = (body.get("to") or to).lower()
                    except Exception as e:  # noqa: BLE001
                        return self._json({"success": False,
                                           "error": f"mime_parse_failed: {e}"}, 400)
                mbx_id = store.ensure_mailbox(to)
                mid = store.put_message(mbx_id, body)
                return self._json({"success": True, "data": {"id": mid}})
            return self._json({"success": False, "error": "not_found"}, 404)

        def do_DELETE(self):
            u = urlparse(self.path)
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

    return Handler


def serve(db: str, port: int, api_key: str, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    store = Store(db)
    if not api_key:
        print("[warn] api-key 为空 = dev 模式，任何本地进程都能读写邮件", flush=True)
    srv = ThreadingHTTPServer((host, port), make_handler(store, api_key))
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="mailkit.db")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--api-key", default="")
    args = ap.parse_args(argv)
    srv = serve(args.db, args.port, args.api_key, args.host)
    print(f"[receiver] http://{args.host}:{args.port}  db={args.db}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
