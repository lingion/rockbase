#!/usr/bin/env python3
"""S2 发信：CSV → 公司 SMTP。默认 dry-run；带节奏限制、断点续传、首封链接守卫。

CSV 列: email,name,subject,body   （subject/body 里可用 {name} 占位）
用法:
  python -m mailkit.send --config config.toml --csv batch.csv            # dry-run
  python -m mailkit.send --config config.toml --csv batch.csv --execute  # 真发
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from .config import is_placeholder, load_config, require_real

LINK_RE = re.compile(r"https?://", re.I)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def msg_key(to: str, subject: str) -> str:
    return hashlib.sha256(f"{to.lower().strip()}|{subject.strip()}".encode()).hexdigest()[:16]


def load_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def plan(cfg: dict, rows: list[dict], manifest: list[dict]) -> tuple[list[dict], list[dict]]:
    sent = [m for m in manifest if m.get("status") == "sent"]
    sent_keys = {m["key"] for m in sent}
    contacted = {m["to"].lower() for m in sent}
    send_cfg = cfg.get("send", {})
    max_w = int(send_cfg.get("max_per_window", 4))
    win = int(send_cfg.get("window_minutes", 120))
    cap = int(send_cfg.get("daily_cap", 30))
    footer = send_cfg.get("opt_out_line", "")
    allow_links = bool(send_cfg.get("allow_links_first_touch", False))

    cutoff_w = now_utc() - timedelta(minutes=win)
    cutoff_d = now_utc() - timedelta(hours=24)
    in_window = sum(1 for m in sent if datetime.fromisoformat(m["sent_at"]) >= cutoff_w)
    in_day = sum(1 for m in sent if datetime.fromisoformat(m["sent_at"]) >= cutoff_d)

    planned, skipped = [], []
    for row in rows:
        to = (row.get("email") or "").strip()
        name = (row.get("name") or "").strip()
        subject = (row.get("subject") or "").format(name=name)
        body = (row.get("body") or "").format(name=name)
        key = msg_key(to, subject)
        if not to:
            skipped.append({"row": row, "reason": "missing_email"})
            continue
        if key in sent_keys:
            skipped.append({"row": {"email": to, "subject": subject}, "reason": "already_sent"})
            continue
        first_touch = to.lower() not in contacted
        if first_touch and not allow_links and LINK_RE.search(body):
            skipped.append({"row": {"email": to, "subject": subject},
                            "reason": "first_touch_link_guard(SOP: 首封不带外链)"})
            continue
        if footer and footer not in body:
            body = f"{body}\n\n--\n{footer}"
        if in_window >= max_w:
            skipped.append({"row": {"email": to, "subject": subject},
                            "reason": f"rate_window({max_w}/{win}min 已满)"})
            continue
        if in_day >= cap:
            skipped.append({"row": {"email": to, "subject": subject},
                            "reason": f"daily_cap({cap}) 已满"})
            continue
        in_window += 1
        in_day += 1
        planned.append({"key": key, "to": to, "name": name,
                        "subject": subject, "body": body, "first_touch": first_touch})
    return planned, skipped


def send_one(cfg: dict, item: dict) -> str:
    smtp_cfg = cfg["smtp"]
    host = require_real(cfg, "smtp.host")
    user = require_real(cfg, "smtp.username")
    pwd = require_real(cfg, "smtp.password")
    from_addr = require_real(cfg, "smtp.from_addr")

    message = EmailMessage()
    message["From"] = f'{smtp_cfg.get("from_name", "")} <{from_addr}>'
    message["To"] = item["to"]
    message["Subject"] = item["subject"]
    message.set_content(item["body"])

    port = int(smtp_cfg.get("port", 587))
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        if smtp_cfg.get("use_tls", True):
            server.starttls(context=ssl.create_default_context())
    try:
        server.login(user, pwd)
        server.send_message(message)
        return message.get("Message-ID", "n/a")
    finally:
        server.quit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--execute", action="store_true", help="真正发送；缺省为 dry-run")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    workdir = Path(cfg.get("paths", {}).get("workdir", "workbench"))
    workdir.mkdir(parents=True, exist_ok=True)
    manifest_path = workdir / "send_manifest.jsonl"

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    planned, skipped = plan(cfg, rows, load_manifest(manifest_path))

    for s in skipped:
        print(f"[skip] {s['row'].get('email')} :: {s['reason']}")
    if not planned:
        print("无可发送条目。")
        return 0

    if not args.execute:
        print(f"[dry-run] 计划发送 {len(planned)} 封（加 --execute 真发）:")
        for p in planned:
            tag = "首触" if p["first_touch"] else "跟进"
            print(f"  - [{tag}] {p['to']} :: {p['subject']}")
        return 0

    with open(manifest_path, "a", encoding="utf-8") as mf:
        for p in planned:
            try:
                mid = send_one(cfg, p)
                rec = {"key": p["key"], "to": p["to"], "subject": p["subject"],
                       "status": "sent", "sent_at": now_utc().isoformat(), "message_id": mid}
                print(f"[sent] {p['to']} :: {p['subject']}")
            except Exception as e:  # noqa: BLE001
                rec = {"key": p["key"], "to": p["to"], "subject": p["subject"],
                       "status": "error", "sent_at": now_utc().isoformat(), "error": str(e)}
                print(f"[error] {p['to']} :: {e}", file=sys.stderr)
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mf.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
