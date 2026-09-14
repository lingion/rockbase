#!/usr/bin/env python3
"""S3 回复回收：轮询 receiver/mailgofer → 导出 replies CSV/JSON 给 S3 流水线。

用法: python -m mailkit.fetch_replies --config config.toml
"""
from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import is_placeholder, load_config


def fetch_emails(base_url: str, api_key: str, addr: str) -> list[dict]:
    q = urllib.parse.urlencode({"email": addr})
    req = urllib.request.Request(
        f"{base_url}/api/emails?{q}",
        headers={"x-api-key": api_key})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    # 兼容 mailgofer {success,data:{emails}} 与裸列表
    if isinstance(data, list):
        return data
    return (data.get("data") or {}).get("emails") or data.get("emails") or []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--out", default="", help="输出前缀，默认 workdir/replies_YYYY-MM-DD")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    rcv = cfg.get("receiver", {})
    base_url = rcv.get("base_url", "").rstrip("/")
    api_key = rcv.get("api_key", "")
    if not base_url or is_placeholder(base_url):
        raise SystemExit("[blocked] receiver.base_url 未配置")

    watch = [a.strip().lower() for a in
             (rcv.get("watch_addrs") or "").replace(";", ",").split(",") if a.strip()]
    if not watch:
        watch = [cfg.get("smtp", {}).get("from_addr", "").lower()]
    watch = [a for a in watch if a and not is_placeholder(a)]
    if not watch:
        raise SystemExit("[blocked] 没有可轮询的地址（watch_addrs / smtp.from_addr）")

    seen, rows = set(), []
    for addr in watch:
        for e in fetch_emails(base_url, api_key, addr):
            frm = (e.get("from_address") or e.get("from") or "").lower()
            ext = e.get("external_id") or e.get("id") or ""
            if ext in seen or frm == addr:  # 去重 + 排除自己发的
                continue
            seen.add(ext)
            rows.append({
                "reply_from": frm,
                "reply_to": addr,
                "subject": e.get("subject") or "",
                "body": e.get("content") or "",
                "received_at": e.get("created_at") or "",
                "external_id": ext,
            })
    rows.sort(key=lambda r: r["received_at"])

    workdir = Path(cfg.get("paths", {}).get("workdir", "workbench"))
    workdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prefix = Path(args.out) if args.out else workdir / f"replies_{stamp}"
    csv_path, json_path = prefix.with_suffix(".csv"), prefix.with_suffix(".json")
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"[fetch] {len(rows)} 条新回复 → {csv_path} / {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
