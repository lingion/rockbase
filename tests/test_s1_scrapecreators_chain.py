"""Cross-script S1 export -> apply verification against a local HTTP API."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_export.py"
APPLY = ROOT / "skills/S1-inbox-enrichment/scripts/api/youtube_scrapecreators_s1_apply.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def fake_scrapecreators(payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/youtube/channel"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def fixture_csv(path: Path) -> None:
    fields = [
        "平台", "账号链接", "账号ID", "频道/作者名称", "粉丝数",
        "账号简介__平台抓取", "账号类目标签__平台抓取", "外链__平台抓取",
        "多平台标记", "联系方式", "联系方式备注", "语言", "博主国家",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "平台": "YouTube",
            "账号链接": "https://youtube.com/@old",
            "账号ID": "UC_old",
            "频道/作者名称": "Old Name",
        })


def test_real_requests_export_then_apply_preview_and_apply(tmp_path, monkeypatch, capsys):
    export = load(EXPORT, "youtube_export_chain")
    apply = load(APPLY, "youtube_apply_chain")
    csv_path = tmp_path / "input.csv"
    fixture_csv(csv_path)
    payload = {
        "success": True,
        "handle": "newcreator",
        "name": "New Creator",
        "subscriberCount": 12500,
        "subscriberCountText": "12.5K subscribers",
        "description": "AI tools for teams. Contact creator@example.invalid",
        "tags": "AI, technology",
        "links": ["https://instagram.com/newcreator"],
        "email": "",
    }

    with fake_scrapecreators(payload) as base_url:
        monkeypatch.setattr(export, "BASE_URL", base_url)
        monkeypatch.setattr(export, "GLOBAL_ENV", tmp_path / "missing.env")
        monkeypatch.setattr(sys, "argv", [
            "export", "--csv", str(csv_path), "--api-key", "sk-local",
            "--date", "2026-09-21", "--delay-seconds", "0",
        ])
        export.main()
    export_output = json.loads(capsys.readouterr().out)
    raw_path = Path(export_output["raw_path"])
    assert export_output["count"] == 1
    assert json.loads(raw_path.read_text())["items"][0]["payload"]["handle"] == "newcreator"

    before = csv_path.read_bytes()
    monkeypatch.setattr(sys, "argv", ["apply", "--csv", str(csv_path), "--json", str(raw_path), "--mode", "preview"])
    apply.main()
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "preview"
    assert preview["stats"]["rows_matched"] == 1
    assert csv_path.read_bytes() == before

    monkeypatch.setattr(sys, "argv", ["apply", "--csv", str(csv_path), "--json", str(raw_path), "--mode", "apply"])
    apply.main()
    applied = json.loads(capsys.readouterr().out)
    assert applied["mode"] == "apply"
    assert applied["backup_path"]
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["账号ID"] == "@newcreator"
    assert row["频道/作者名称"] == "New Creator"
    assert row["粉丝数"] == "12.5K"
    assert row["联系方式"] == "creator@example.invalid"
    assert row["多平台标记"] == "Instagram"
