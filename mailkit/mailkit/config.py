"""配置加载：TOML 子集 + 环境变量覆盖。零依赖，兼容 Python 3.9+。"""
from __future__ import annotations

import os
import re
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"PLACEHOLDER")


def parse_toml_subset(text: str) -> dict:
    """只支持本项目用到的子集：[section]、key = 值、; 与 # 注释。"""
    data: dict = {}
    section = data
    for raw in text.splitlines():
        line = re.split(r"(?<!\\);", raw, maxsplit=1)[0]
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^\[([A-Za-z0-9_.-]+)\]$", line)
        if m:
            section = data.setdefault(m.group(1), {})
            continue
        m = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*(.+)$', line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith(('"', "'")) and val.endswith(val[0]):
            section[key] = val[1:-1].replace('\\"', '"')
        elif val in ("true", "false"):
            section[key] = val == "true"
        else:
            try:
                section[key] = int(val)
            except ValueError:
                try:
                    section[key] = float(val)
                except ValueError:
                    section[key] = val
    return data


def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {p}\n先执行: cp config.example.toml config.toml 并填写占位符"
        )
    cfg = parse_toml_subset(p.read_text(encoding="utf-8"))
    # 环境变量覆盖: MAILKIT_SMTP_HOST / MAILKIT_RECEIVER_API_KEY ...
    for sec in ("smtp", "receiver", "send", "paths"):
        for key in list(cfg.get(sec, {})):
            env = os.environ.get(f"MAILKIT_{sec.upper()}_{key.upper()}")
            if env is not None:
                cur = cfg[sec][key]
                cfg[sec][key] = env if isinstance(cur, str) else type(cur)(env)
    return cfg


def is_placeholder(value) -> bool:
    return isinstance(value, str) and bool(_PLACEHOLDER_RE.search(value))


def require_real(cfg: dict, dotted: str) -> str:
    """取配置值；仍是占位符/空则抛错（发送等真实动作前的闸门）。"""
    node = cfg
    for part in dotted.split("."):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    val = node
    if not val or is_placeholder(val):
        raise SystemExit(f"[blocked] 配置项 {dotted} 未填写（当前: {val!r}）")
    return val
