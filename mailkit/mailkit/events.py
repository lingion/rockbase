"""结构化事件日志（融合自 observability-and-instrumentation skill）。

一行一 JSON、稳定事件名、机器可读字段；事件走 stderr，人读摘要走 stdout，
互不污染（重定向/管道友好）。🚫 事件里放密码 / token / 完整邮件正文。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def emit(event: str, **fields) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    rec.update(fields)
    print(json.dumps(rec, ensure_ascii=False), file=sys.stderr, flush=True)
