#!/usr/bin/env python3
"""Postfix pipe 传输：stdin 收 RFC822 → 解析 → POST /api/inbound。

Postfix master.cf 挂法见 deploy/postfix-notes.md。
用法: python -m mailkit.postfix_pipe --config config.toml
      python -m mailkit.postfix_pipe --url http://127.0.0.1:8788 --api-key <key>
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from .config import is_placeholder, load_config
from .receiver import parse_mime


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--url", default="", help="receiver base_url，覆盖 config")
    ap.add_argument("--api-key", default="", help="覆盖 config")
    ap.add_argument("--rcpt-user", default="", help="Postfix 宏 %%u（信封收件人本地部）")
    ap.add_argument("--rcpt-domain", default="", help="Postfix 宏 %%d（信封收件人域）")
    args = ap.parse_args(argv)

    url, key = args.url.rstrip("/"), args.api_key
    if not url:
        cfg = load_config(args.config)
        url = cfg.get("receiver", {}).get("base_url", "").rstrip("/")
        key = key or cfg.get("receiver", {}).get("api_key", "")
    if not url or is_placeholder(url):
        print("[blocked] receiver.base_url 未配置", file=sys.stderr)
        return 2

    raw = sys.stdin.buffer.read()
    try:
        parsed = parse_mime(raw)
    except Exception as e:  # noqa: BLE001
        # 解析失败也投递 raw 存根，保证不丢信
        parsed = {"to": "", "from": "", "subject": "", "text": "",
                  "raw_error": str(e)}
    # 信封收件人(Postfix %u/%d)优先：BCC 等无 To 头场景不丢信
    if args.rcpt_user and args.rcpt_domain:
        to = f"{args.rcpt_user}@{args.rcpt_domain}"
    else:
        to = parsed.get("to", "")
        if "," in to:
            to = to.split(",")[0]
    payload = {**parsed, "to": to.strip().lower(), "raw": {"size": len(raw)}}

    req = urllib.request.Request(
        f"{url}/api/inbound",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = json.loads(resp.read()).get("success")
            return 0 if ok else 1
    except Exception as e:  # noqa: BLE001
        print(f"[error] inbound POST 失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
