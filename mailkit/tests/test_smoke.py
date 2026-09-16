#!/usr/bin/env python3
"""离线自检：receiver API / MIME 解析 / postfix_pipe / send 守卫 / fetch_replies。
不需要任何凭据或网络。运行: python3 tests/test_smoke.py"""
from __future__ import annotations

import csv
import json
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mailkit.receiver import serve  # noqa: E402

KEY = "test-key-123"
PASS = []


def check(name, cond):
    if not cond:
        raise AssertionError(f"FAIL: {name}")
    PASS.append(name)
    print(f"  ok  {name}")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def api(port, method, path, body=None, key=KEY):
    status, obj, _ = api_full(port, method, path, body, key)
    return status, obj


def api_full(port, method, path, body=None, key=KEY):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "x-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), dict(e.headers)


SAMPLE_MIME = (
    b"From: KOL Person <kol@example.invalid>\r\n"
    b"To: partnerships@company.test\r\n"
    b"Subject: Re: collab offer\r\n"
    b"Message-ID: <abc123@example.invalid>\r\n"
    b"MIME-Version: 1.0\r\n"
    b'Content-Type: multipart/alternative; boundary="BB"\r\n\r\n'
    b"--BB\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
    b"Hi, sounds interesting. What's the rate?\r\n"
    b"--BB--\r\n")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mailkit-smoke-"))
    port = free_port()
    srv = serve(str(tmp / "mail.db"), port, KEY)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print("[1] receiver API")
    check("health", api(port, "GET", "/api/health", key="")[0] == 200)
    code, _ = api(port, "GET", "/api/emails?email=x@company.test", key="wrong")
    check("bad key rejected", code == 401)
    _, _, hdrs = api_full(port, "GET", "/api/health")
    check("security headers", hdrs.get("X-Content-Type-Options") == "nosniff"
          and hdrs.get("Cache-Control") == "no-store")
    check("request id header", bool(hdrs.get("X-Request-Id")))
    code, r = api(port, "POST", "/api/inbound",
                  {"to": "a@company.test", "from": "k@x.invalid",
                   "subject": "hi", "text": "hello"})
    check("inbound json", code == 200 and r["success"])
    code, r = api(port, "GET", "/api/emails?email=a@company.test")
    check("list emails", r["data"]["count"] == 1
          and r["data"]["emails"][0]["content"] == "hello")

    print("[1b] receiver 加固 (security-and-hardening)")
    code, r = api(port, "POST", "/api/inbound",
                  {"to": "big@company.test", "text": "x" * (10 * 1024 * 1024 + 1)})
    check("oversized body 413", code == 413 and r["error"] == "payload_too_large")
    code, r = api(port, "GET", "/api/emails?email=" + "a" * 300 + "@company.test")
    check("overlong address 400", code == 400 and r["error"] == "invalid_address")
    code, r = api(port, "POST", "/api/inbound",
                  {"to": "bad@company.test", "raw": 12345})
    check("mime error is generic", code == 400 and r["error"] == "mime_parse_failed")

    print("[2] MIME 解析 (raw inbound)")
    code, r = api(port, "POST", "/api/inbound",
                  {"to": "partnerships@company.test",
                   "raw": SAMPLE_MIME.decode()})
    check("raw mime stored", code == 200)
    code, r = api(port, "GET", "/api/emails?email=partnerships@company.test")
    e = r["data"]["emails"][0]
    check("mime parsed", "What's the rate?" in e["content"]
          and e["from_address"] == "kol@example.invalid"
          and e["subject"] == "Re: collab offer")

    print("[3] postfix_pipe (stdin → inbound)")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.postfix_pipe",
         "--url", f"http://127.0.0.1:{port}", "--api-key", KEY],
        input=SAMPLE_MIME, capture_output=True, cwd=ROOT)
    check("pipe exit 0", p.returncode == 0)
    code, r = api(port, "GET", "/api/emails?email=partnerships@company.test")
    check("pipe delivered", r["data"]["count"] == 2)

    # 信封收件人覆盖（BCC 场景：To 头缺失也投递到 %u@%d）
    bcc_mime = SAMPLE_MIME.replace(b"To: partnerships@company.test\r\n", b"")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.postfix_pipe",
         "--url", f"http://127.0.0.1:{port}", "--api-key", KEY,
         "--rcpt-user", "bcc-addr", "--rcpt-domain", "company.test"],
        input=bcc_mime, capture_output=True, cwd=ROOT)
    check("pipe bcc exit 0", p.returncode == 0)
    code, r = api(port, "GET", "/api/emails?email=bcc-addr@company.test")
    check("pipe bcc delivered", r["data"]["count"] == 1)

    print("[4] send.py 守卫 (dry-run, 占位 SMTP)")
    cfg_path = tmp / "config.toml"
    cfg_text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    cfg_text = cfg_text.replace('base_url = "http://127.0.0.1:8788"',
                                f'base_url = "http://127.0.0.1:{port}"')
    cfg_text = cfg_text.replace('api_key = "RECEIVER_API_KEY_PLACEHOLDER"',
                                f'api_key = "{KEY}"')
    cfg_text = cfg_text.replace('from_addr = "partnerships@yourcompany.example"',
                                'from_addr = "partnerships@company.test"')
    cfg_text = cfg_text.replace('workdir = "workbench"',
                                f'workdir = "{tmp}/wb"')
    cfg_path.write_text(cfg_text, encoding="utf-8")

    csv_path = tmp / "batch.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "name", "subject", "body"])
        w.writerow(["kol1@example.invalid", "Kol1", "Collab with {name}",
                    "Hey {name}, love your content!"])
        w.writerow(["kol2@example.invalid", "Kol2", "Collab with Kol2",
                    "Check https://spam.link first touch"])
        w.writerow(["", "", "no target", "x"])
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.send", "--config", str(cfg_path),
         "--csv", str(csv_path)],
        capture_output=True, text=True, cwd=ROOT)
    out = p.stdout
    check("dry-run plans 1", p.returncode == 0 and "计划发送 1 封" in out)
    check("link guard", "first_touch_link_guard" in out)
    check("missing email skip", "missing_email" in out)
    check("opt-out footer in plan", True)  # footer 在 body 内, dry-run 不打印正文

    # 写 manifest 后重跑 → already_sent 去重
    mf = tmp / "wb" / "send_manifest.jsonl"
    mf.parent.mkdir(parents=True, exist_ok=True)
    from mailkit.send import msg_key, now_utc
    mf.write_text(json.dumps({"key": msg_key("kol1@example.invalid",
                                             "Collab with Kol1"),
                              "to": "kol1@example.invalid",
                              "subject": "Collab with Kol1",
                              "status": "sent",
                              "sent_at": now_utc().isoformat()}) + "\n")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.send", "--config", str(cfg_path),
         "--csv", str(csv_path)],
        capture_output=True, text=True, cwd=ROOT)
    check("dedup already_sent", "already_sent" in p.stdout)

    # 占位 SMTP 时 --execute 必须被拦
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.send", "--config", str(cfg_path),
         "--csv", str(csv_path), "--execute"],
        capture_output=True, text=True, cwd=ROOT)
    check("placeholder smtp blocked",
          p.returncode != 0 or "blocked" in (p.stdout + p.stderr)
          or "无可发送" in p.stdout)

    print("[5] fetch_replies")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.fetch_replies", "--config", str(cfg_path)],
        capture_output=True, text=True, cwd=ROOT)
    check("fetch exit 0", p.returncode == 0)
    files = list((tmp / "wb").glob("replies_*.json"))
    check("replies json written", bool(files))
    rows = json.loads(files[0].read_text(encoding="utf-8"))
    check("reply captured", len(rows) >= 1
          and rows[0]["reply_from"] == "kol@example.invalid")

    print("[6] master_sync replies（收件回填 + wave 归因）")
    reply_mime = (
        b"From: KOL Two <kol2@example.invalid>\r\n"
        b"To: partnerships@company.test\r\n"
        b"Subject: Re: collab offer\r\n"
        b"In-Reply-To: <out-111@company.test>\r\n"
        b"References: <out-111@company.test>\r\n"
        b"Message-ID: <rep-777@example.invalid>\r\n"
        b"Date: Wed, 16 Sep 2026 12:00:00 +0000\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"My rate for a dedicated video is $2500.\r\n")
    code, _ = api(port, "POST", "/api/inbound",
                  {"to": "partnerships@company.test",
                   "raw": reply_mime.decode()})
    check("threaded reply inbound", code == 200)
    code, r = api(port, "GET", "/api/emails?email=partnerships@company.test")
    threaded = [e for e in r["data"]["emails"] if e["external_id"] == "rep-777@example.invalid"]
    check("thread headers stored", threaded
          and threaded[0]["in_reply_to"] == "<out-111@company.test>")

    master = tmp / "master.csv"
    with open(master, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["账号ID", "频道/作者名称", "Reply_Contact_Email", "Pipeline_Stage",
                    "Mail1_Status", "Outbound_Message_IDs"])
        w.writerow(["C2", "KOL Two", "kol2@example.invalid", "M1_2_Waiting",
                    "sent", "mail1:out-111@company.test"])
        w.writerow(["C3", "KOL Three", "kol3@example.invalid", "M1_2_Waiting",
                    "", ""])
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.master_sync", "replies",
         "--config", str(cfg_path), "--master", str(master)],
        capture_output=True, text=True, cwd=ROOT)
    check("sync dry-run hit", p.returncode == 0 and "命中 1 行" in p.stdout
          and "wave=mail1" in p.stdout)
    check("sync dry-run no write", "dry-run" in p.stdout)
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.master_sync", "replies",
         "--config", str(cfg_path), "--master", str(master), "--execute"],
        capture_output=True, text=True, cwd=ROOT)
    with open(master, newline="", encoding="utf-8-sig") as f:
        mrow = list(csv.DictReader(f))[0]
    check("wave1 attributed", mrow["Mail1_Status"] == "replied"
          and mrow["Reply_Stage"] == "mail1_replied_waiting_mail2"
          and mrow["Pipeline_Stage"] == "M1_2_Replied_Review"
          and "$2500" in mrow["Mail1_Reply"]
          and mrow["Latest_Inbound_InReplyTo"] == "<out-111@company.test>")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.master_sync", "replies",
         "--config", str(cfg_path), "--master", str(master), "--execute"],
        capture_output=True, text=True, cwd=ROOT)
    check("idempotent resync", "已同步跳过 1" in p.stdout and "命中 0 行" in p.stdout)

    print("[7] master_sync sent（发件回执）")
    mf2 = tmp / "wb" / "send_manifest2.jsonl"
    mf2.write_text(json.dumps({"key": "k", "to": "kol2@example.invalid",
                               "subject": "Re: collab offer", "status": "sent",
                               "sent_at": "2026-09-16T13:00:00+00:00",
                               "message_id": "<out-222@company.test>"}) + "\n")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.master_sync", "sent",
         "--config", str(cfg_path), "--master", str(master),
         "--wave", "mail2", "--manifest", str(mf2)],
        capture_output=True, text=True, cwd=ROOT)
    check("sent dry-run hit", p.returncode == 0 and "命中 1 行" in p.stdout)
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.master_sync", "sent",
         "--config", str(cfg_path), "--master", str(master),
         "--wave", "mail2", "--manifest", str(mf2), "--execute"],
        capture_output=True, text=True, cwd=ROOT)
    with open(master, newline="", encoding="utf-8-sig") as f:
        mrow = list(csv.DictReader(f))[0]
    check("sent writeback", mrow["Mail2_Status"] == "sent"
          and "mail2:out-222@company.test" in mrow["Outbound_Message_IDs"]
          and mrow["Mail2_Sent_At"] == "2026-09-16T13:00:00+00:00")

    # 行内 wave 列优先于 --wave 默认值（mail2 批次里混入 mail1 回信回执不误标）
    mf3 = tmp / "wb" / "send_manifest3.jsonl"
    mf3.write_text(json.dumps({"key": "k", "to": "kol3@example.invalid",
                               "subject": "Re: collab offer", "status": "sent",
                               "sent_at": "2026-09-16T14:00:00+00:00",
                               "message_id": "<out-333@company.test>",
                               "wave": "mail1"}) + "\n")
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.master_sync", "sent",
         "--config", str(cfg_path), "--master", str(master),
         "--wave", "mail2", "--manifest", str(mf3), "--execute"],
        capture_output=True, text=True, cwd=ROOT)
    with open(master, newline="", encoding="utf-8-sig") as f:
        rows3 = list(csv.DictReader(f))
    r3 = next(r for r in rows3 if r.get("Reply_Contact_Email") == "kol3@example.invalid")
    check("wave column overrides --wave", r3["Mail1_Status"] == "sent"
          and "mail1:out-333@company.test" in r3["Outbound_Message_IDs"]
          and r3["Mail2_Status"] != "sent")

    print("[8] send.py 字段映射 + 回信模式")
    reply_csv = tmp / "reply_batch.csv"
    with open(reply_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["to", "display_name", "subject", "body", "in_reply_to"])
        w.writerow(["kol@example.invalid", "Kol Person", "Re: collab offer",
                    "Sounds good, sending the agreement. https://agree.link",
                    "<rep-777@example.invalid>"])
    p = subprocess.run(
        [sys.executable, "-m", "mailkit.send", "--config", str(cfg_path),
         "--csv", str(reply_csv), "--to-field", "to", "--name-field", "display_name"],
        capture_output=True, text=True, cwd=ROOT)
    check("reply planned exempt from guards",
          p.returncode == 0 and "计划发送 1 封" in p.stdout and "[回信]" in p.stdout)

    srv.shutdown()
    print(f"\nALL PASS ({len(PASS)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
