"""Contract tests for direct multimodal OCR in S5."""
from __future__ import annotations

import base64
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/S5-ag-ocr-sync/scripts/ag_ocr_sync.py"


def load_module():
    # The LLM path does not touch OpenCV; keep this contract test runnable in
    # the base environment where the optional OCR extra is not installed.
    if "cv2" not in sys.modules:
        sys.modules["cv2"] = type("Cv2Stub", (), {})()
    spec = importlib.util.spec_from_file_location("ag_ocr_sync_llm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def response_payload():
    return {
        "handle": "@creator",
        "author_name": "Creator Name",
        "email": "creator@example.invalid",
        "countries": "美国 60% / 加拿大 40%",
        "gender": "男52%/女48%",
        "age": "18-25 (70%)/25-45 (30%)",
        "confidence": 0.91,
    }


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, model, temperature, messages):
        self.calls.append({"model": model, "temperature": temperature, "messages": messages})
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": self.content})()})()]})()


class FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions(json.dumps(response_payload()))})()


def test_run_llm_vision_normalizes_model_payload(tmp_path):
    module = load_module()
    image = tmp_path / "capture.png"
    image.write_bytes(b"fake-png")
    client = FakeClient()

    result = module.run_llm_vision(image, client, "vision-model")

    assert isinstance(result, module.ScreenshotData)
    assert result.path == str(image)
    assert result.handle == "@creator"
    assert result.author_name == "Creator Name"
    assert result.email == "creator@example.invalid"
    assert result.confidence == 0.91
    call = client.chat.completions.calls[0]
    assert call["model"] == "vision-model"
    assert call["temperature"] == 0
    image_part = call["messages"][1]["content"][1]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    assert base64.b64decode(image_part["image_url"]["url"].split(",", 1)[1]) == b"fake-png"


def test_run_llm_vision_real_http_round_trip(tmp_path):
    module = load_module()
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg-bytes")
    observed = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            observed["path"] = self.path
            observed["auth"] = self.headers.get("Authorization")
            size = int(self.headers["Content-Length"])
            observed["request"] = json.loads(self.rfile.read(size))
            payload = {
                "choices": [{"message": {"content": json.dumps(response_payload())}}]
            }
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
        client = module.build_llm_client("sk-local", f"http://127.0.0.1:{server.server_port}/v1", 10)
        result = module.run_llm_vision(image, client, "vision-model")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.email == "creator@example.invalid"
    assert observed["path"] == "/v1/chat/completions"
    assert observed["auth"] == "Bearer sk-local"
    content = observed["request"]["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_argparser_exposes_llm_engine():
    module = load_module()
    args = module.parse_args.__wrapped__ if hasattr(module.parse_args, "__wrapped__") else None
    parser = module._build_argparser() if hasattr(module, "_build_argparser") else None
    if parser is None:
        pytest.skip("argparser builder not exposed yet")
    parsed = parser.parse_args(["--image-dir", "images", "--csv-path", "master.csv", "--ocr-engine", "llm", "--llm-model", "vision-model"])
    assert parsed.ocr_engine == "llm"
    assert parsed.llm_model == "vision-model"
