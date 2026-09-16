#!/usr/bin/env python3
"""本机全自动收发彩排：一台电脑同时扮演「我们的服务器」和「KOL 外部世界」。

全程 127.0.0.1 + tempfile，不碰外网，跑完自动清理。完整复现上线后的剧本：
mail1 首触 → KOL-A/B 自动回信 → 收件入库 → master 回填（硬归因）→
mail2 回信（挂线程头、豁免首触守卫）→ A 二次回信 → mail2 回填。
用法: python3 tests/demo_local_loop.py
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from email import message_from_bytes
from email.utils import make_msgid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mailkit.fake_smtp import start_fake_smtp  # noqa: E402

PY = sys.executable
DOMAIN = "demo-company.example"
ME = f"partnerships@{DOMAIN}"


def run(args, cwd):
    import os
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    r = subprocess.run([PY, "-m", *args], cwd=cwd, capture_output=True, text=True,
                       env=env)
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        raise SystemExit(f"[fail] mailkit {' '.join(args)}\n{out}")
    print(out or "(no output)", flush=True)
    return out


def banner(t):
    print(f"\n{'=' * 64}\n▶ {t}\n{'=' * 64}", flush=True)


class World:
    """假外部世界：收到我方信件存档；剧本命中后经 postfix_pipe 自动回信。"""

    def __init__(self, base_url, api_key):
        self.scripts = {}   # 我方 message_id(去<>小写) -> (kol, subject, body)
        self.arrivals = []  # (to, subject, message_id)
        self.pipe = [PY, "-m", "mailkit.postfix_pipe", "--url", base_url,
                     "--api-key", api_key, "--rcpt-user", "partnerships",
                     "--rcpt-domain", DOMAIN]

    def schedule(self, trigger_mid, kol, subject, body):
        self.scripts[trigger_mid.strip("<>").lower()] = (kol, subject, body)

    def on_message(self, raw: bytes):
        msg = message_from_bytes(raw)
        mid = (msg.get("Message-ID") or "").strip()
        self.arrivals.append((msg.get("To", ""), msg.get("Subject", ""), mid))
        print(f"  📤 世界收到 → {msg['To']} :: {msg['Subject']} :: mid={mid}", flush=True)

    def flush(self):
        """把已到信里命中剧本的回信投进 receiver（模拟 KOL 点了发送）。"""
        for _to, _s, mid in self.arrivals:
            script = self.scripts.pop(mid.strip("<>").lower(), None)
            if script:
                self._deliver(*script, in_reply_to=mid)

    def _deliver(self, kol, subject, body, in_reply_to):
        mid = make_msgid(domain="kol.example")
        raw = (f"From: {kol}\r\nTo: {ME}\r\nSubject: {subject}\r\n"
               f"Message-ID: {mid}\r\nIn-Reply-To: {in_reply_to}\r\n"
               f"Date: {datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}\r\n"
               f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n").encode()
        r = subprocess.run(self.pipe, input=raw, capture_output=True,
                           env={**__import__("os").environ, "PYTHONPATH": str(REPO)})
        ok = r.returncode == 0
        print(f"  📥 {kol} 自动回信 :: {subject} :: "
              f"{'OK' if ok else 'FAIL ' + (r.stdout + r.stderr).decode(errors='replace')}",
              flush=True)


def inbox(base_url, api_key, addr):
    req = urllib.request.Request(
        f"{base_url}/api/emails?email={addr}", headers={"x-api-key": api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)["data"]["emails"]


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="mailkit-demo-")
    print(f"工作区: {tmp}")
    api_key = "demo-key"

    import mailkit.receiver as receiver_mod
    srv = receiver_mod.serve(str(Path(tmp) / "mailkit.db"), 0, api_key)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    recv_port = srv.server_address[1]
    base_url = f"http://127.0.0.1:{recv_port}"

    world = World(base_url, api_key)
    smtp = start_fake_smtp(world.on_message)
    threading.Thread(target=smtp.serve_forever, daemon=True).start()

    (Path(tmp) / "config.toml").write_text(f"""[smtp]
host = "127.0.0.1"
port = {smtp.server_address[1]}
username = "demo-user"
password = "demo-pass"
use_tls = false
from_addr = "{ME}"
from_name = "Demo Co"

[receiver]
base_url = "{base_url}"
api_key = "{api_key}"
domain = "{DOMAIN}"
watch_addrs = "{ME}"

[send]
max_per_window = 5
window_minutes = 60
daily_cap = 50
allow_links_first_touch = false

[paths]
workdir = "workbench"
""", encoding="utf-8")
    (Path(tmp) / "master.csv").write_text(
        "Reply_Contact_Email,Display_Name,Pipeline_Stage,Mail1_Status,Mail1_Reply_At,"
        "Mail2_Status,Mail2_Reply_At,Outbound_Message_IDs,Latest_Inbound_Message_ID,"
        "Latest_Inbound_InReplyTo,Latest_Inbound_Subject,Reply_Stage,"
        "Reply_Needs_Manual_Review,Reply_Received_At\r\n"
        "kol-a@kol.example,KOL Alpha,M1_M2_Waiting,,,,,,,\r\n"
        "kol-b@kol.example,KOL Beta,M1_M2_Waiting,,,,,,,\r\n"
        "kol-c@kol.example,KOL Gamma,M1_M2_Waiting,,,,,,,\r\n", encoding="utf-8-sig")
    (Path(tmp) / "batch.csv").write_text(
        "email,name,subject,body,wave\r\n"
        "kol-a@kol.example,KOL Alpha,Partnership intro - Alpha,"
        "Hi Alpha - we love your channel.,mail1\r\n"
        "kol-b@kol.example,KOL Beta,Partnership intro - Beta,"
        "Hi Beta - we love your streams.,mail1\r\n"
        "kol-c@kol.example,KOL Gamma,Partnership intro - Gamma,"
        "Hi Gamma - we love your videos.,mail1\r\n", encoding="utf-8")
    print(f"receiver :{recv_port}   假世界SMTP:{smtp.server_address[1]}")

    banner("1) mail1 首触 dry-run（守卫生效：首触无链接、节奏上限内 3 封）")
    run(["mailkit.send", "--config", "config.toml", "--csv", "batch.csv"], tmp)

    banner("2) mail1 真发 → 假世界收下 3 封；A/B 安排自动回信，C 装死")
    run(["mailkit.send", "--config", "config.toml", "--csv", "batch.csv",
         "--execute"], tmp)
    a_mail1_mid = world.arrivals[0][2]
    world.schedule(a_mail1_mid, "kol-a@kol.example", "Re: Partnership intro - Alpha",
                   "Interested. Our rate is $1500 per video.")
    world.schedule(world.arrivals[1][2], "kol-b@kol.example",
                   "Re: Partnership intro - Beta", "Send more details please.")
    world.flush()

    banner("3) 发件回执 → master（manifest 行内 wave=mail1 → A/B/C 全 sent）")
    run(["mailkit.master_sync", "sent", "--config", "config.toml",
         "--master", "master.csv", "--execute"], tmp)

    banner("4) 收件回填：In-Reply-To 硬归因 mail1（A/B 命中，C 不动）")
    run(["mailkit.master_sync", "replies", "--config", "config.toml",
         "--master", "master.csv", "--execute"], tmp)

    banner("5) mail2 回信 A：In-Reply-To 挂 A 的信（豁免首触守卫+限速），wave=mail2")
    a_reply = [e for e in inbox(base_url, api_key, ME)
               if (e.get("in_reply_to") or "").strip("<>").lower()
               == a_mail1_mid.strip("<>").lower()]
    assert a_reply, "没找到 A 的回信"
    a_reply_mid = a_reply[0]["external_id"]
    (Path(tmp) / "reply_batch.csv").write_text(
        "email,name,subject,body,in_reply_to,wave\r\n"
        f"kol-a@kol.example,KOL Alpha,Re: Partnership intro - Alpha,"
        f"Great - here is our media kit and rates.,<{a_reply_mid}>,mail2\r\n",
        encoding="utf-8")
    run(["mailkit.send", "--config", "config.toml", "--csv", "reply_batch.csv",
         "--execute"], tmp)

    banner("6) A 二次回信（报价 $2200）→ mail2 回执+回复双回填")
    our_mail2_mid = world.arrivals[-1][2]
    world.schedule(our_mail2_mid, "kol-a@kol.example", "Re: Partnership intro - Alpha",
                   "$2200 final. Deal?")
    world.flush()
    time.sleep(0.3)
    run(["mailkit.master_sync", "sent", "--config", "config.toml",
         "--master", "master.csv", "--execute"], tmp)
    run(["mailkit.master_sync", "replies", "--config", "config.toml",
         "--master", "master.csv", "--execute"], tmp)

    banner("终态 master.csv 关键列")
    with open(Path(tmp) / "master.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            print(f"  {row['Reply_Contact_Email']} :: stage={row['Pipeline_Stage']} "
                  f"mail1={row['Mail1_Status']}/{(row['Mail1_Reply_At'] or '-')[:16]} "
                  f"mail2={row['Mail2_Status']}/{(row['Mail2_Reply_At'] or '-')[:16]}")
            print(f"      out={row['Outbound_Message_IDs']}")
            print(f"      in={row['Reply_Last_Subject']} "
                  f"(in_reply_to={row['Latest_Inbound_InReplyTo']})")

    banner("终态收件箱")
    print(f"  {ME} 共 {len(inbox(base_url, api_key, ME))} 封")

    smtp.shutdown()
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n✅ 彩排完成，工作区已清理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
