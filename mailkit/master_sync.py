#!/usr/bin/env python3
"""master CSV 回填：S3 字段字典协议（见 rockbase-skills S3 replied_master_field_dictionary）。

  # 收件回填：receiver/mailgofer 的回复 → master（默认 dry-run）
  python -m mailkit.master_sync replies --config config.toml --master master.csv [--execute]
      [--from-csv workbench/replies_2026-09-16.csv]

  # 发件回执：send_manifest.jsonl → master
  python -m mailkit.master_sync sent --config config.toml --master master.csv \
      --wave mail1 [--manifest workbench/send_manifest.jsonl] [--execute]

写字段全部属于字典 recovery/draft-ops 归属；价格提取与流分类不做（置人工复核）。
匹配键：Reply_Contact_Email > 联系方式 > 联系邮箱。wave 归因：
  1) In-Reply-To/References 命中行内 Outbound_Message_IDs → 该 wave
  2) 否则最早一个 MailN_Status∈{sent,waiting} 且 MailN_Reply_At 为空的 wave
  3) 都不行 → 只写共享字段 + Reply_Needs_Manual_Review=yes
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .fetch_replies import fetch_emails

KEY_COLS = ["Reply_Contact_Email", "联系方式", "联系邮箱"]
STATUS_SENT_LIKE = {"sent", "waiting"}
WAITING_STAGE_RE = re.compile(r"(waiting|drafted|^$)", re.I)


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_master(path: Path) -> tuple[list[dict], list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys()) if rows else []
    return rows, fieldnames


def ensure_fields(fieldnames: list[str], needed: list[str]) -> list[str]:
    out = list(fieldnames)
    for f in needed:
        if f not in out:
            out.append(f)
    return out


def key_of(row: dict) -> str:
    for c in KEY_COLS:
        v = (row.get(c) or "").strip().lower()
        if v:
            return v
    return ""


def parse_outbound_ids(raw: str) -> dict[str, str]:
    """'mail1:<id>|mail2:<id>' → {<id去尖括号小写>: 'mail1', ...}"""
    out: dict[str, str] = {}
    for part in (raw or "").split("|"):
        if ":" in part:
            wave, mid = part.split(":", 1)
            out[mid.strip().strip("<>").lower()] = wave.strip().lower()
    return out


def norm_id(x: str) -> str:
    return (x or "").strip().strip("<>").lower()


def attr_wave(row: dict, in_reply_to: str, references: str) -> str:
    outbound = parse_outbound_ids(row.get("Outbound_Message_IDs", ""))
    if outbound:
        for hdr in (in_reply_to, references):
            for mid, wave in outbound.items():
                if mid and mid in norm_id(hdr):
                    return wave
    for n in (1, 2, 3):
        if (row.get(f"Mail{n}_Status", "") or "").strip().lower() in STATUS_SENT_LIKE \
                and not (row.get(f"Mail{n}_Reply_At", "") or "").strip():
            return f"mail{n}"
    return ""


def load_replies(cfg: dict, from_csv: str, workdir: Path) -> list[dict]:
    if from_csv:
        with open(from_csv, newline="", encoding="utf-8-sig") as f:
            return [r for r in csv.DictReader(f) if (r.get("reply_from") or "")]
    rcv = cfg.get("receiver", {})
    base_url = (rcv.get("base_url") or "").rstrip("/")
    api_key = rcv.get("api_key", "")
    if not base_url:
        raise SystemExit("[blocked] receiver.base_url 未配置（或改用 --from-csv）")
    watch = [a.strip().lower() for a in
             (rcv.get("watch_addrs") or "").replace(";", ",").split(",") if a.strip()]
    if not watch:
        watch = [(cfg.get("smtp", {}).get("from_addr") or "").lower()]
    seen, rows = set(), []
    for addr in [a for a in watch if a]:
        for e in fetch_emails(base_url, api_key, addr):
            frm = (e.get("from_address") or "").lower()
            ext = e.get("external_id") or e.get("id") or ""
            if not ext or ext in seen or frm == addr:
                continue
            seen.add(ext)
            rows.append({
                "reply_from": frm, "reply_to": addr,
                "subject": e.get("subject") or "",
                "body": e.get("content") or "",
                "received_at": e.get("created_at") or "",
                "external_id": ext,
                "in_reply_to": e.get("in_reply_to") or "",
                "references": e.get("references") or "",
            })
    rows.sort(key=lambda r: r["received_at"])
    return rows


def summary_of(body: str, limit: int = 160) -> str:
    line = " ".join((body or "").split())
    return line[:limit]


def sync_replies(args) -> int:
    cfg = load_config(args.config)
    master_path = Path(args.master)
    rows, fieldnames = read_master(master_path)
    if not rows:
        raise SystemExit(f"[blocked] master 无数据行: {master_path}")
    workdir = Path(cfg.get("paths", {}).get("workdir", "workbench"))
    workdir.mkdir(parents=True, exist_ok=True)
    by_key: dict[str, dict] = {}
    for r in rows:
        k = key_of(r)
        if k:
            by_key.setdefault(k, r)

    replies = load_replies(cfg, args.from_csv, workdir)
    changed, audits = [], []
    for rep in replies:
        k = (rep["reply_from"] or "").strip().lower()
        row = by_key.get(k)
        if not row:
            audits.append({"issue": "unmatched", "email": k,
                           "external_id": rep["external_id"]})
            continue
        if (row.get("Latest_Inbound_Message_ID", "") or "").strip() == rep["external_id"]:
            audits.append({"issue": "already_synced", "email": k,
                           "external_id": rep["external_id"]})
            continue
        old_at = (row.get("Reply_Last_At", "") or "").strip()
        if old_at and rep["received_at"] <= old_at:
            audits.append({"issue": "stale_reply", "email": k,
                           "external_id": rep["external_id"]})
            continue

        wave = attr_wave(row, rep["in_reply_to"], rep["references"])
        upd: dict[str, str] = {
            "Reply_Last_Message_ID": rep["external_id"],
            "Reply_Last_Subject": rep["subject"],
            "Reply_Last_At": rep["received_at"],
            "Latest_Inbound_Message_ID": rep["external_id"],
            "Latest_Inbound_InReplyTo": rep["in_reply_to"],
            "Reply_Needs_Manual_Review": "yes",  # v0：价格/分类未自动提取
        }
        if not (row.get("Reply_Contact_Email", "") or "").strip():
            upd["Reply_Contact_Email"] = k

        if wave:
            n = int(wave[-1])
            upd.update({
                f"Mail{n}_Reply_At": rep["received_at"],
                f"Mail{n}_Reply": rep["body"],
                f"Mail{n}_Reply_Summary": summary_of(rep["body"]),
                f"Mail{n}_Status": "replied",
                "Reply_Status": "replied",
                "Reply_Stage": f"mail{n}_replied_waiting_mail{n + 1}" if n < 3
                else "mail3_replied",
            })
            stage = (row.get("Pipeline_Stage", "") or "").strip()
            if WAITING_STAGE_RE.search(stage):
                upd["Pipeline_Stage"] = (f"M{n}_{n + 1}_Replied_Review" if n < 3
                                         else "Z_Manual_Review")
        else:
            upd["Reply_Stage"] = "manual_review"
            audits.append({"issue": "wave_ambiguous", "email": k,
                           "external_id": rep["external_id"]})

        before = dict(row)
        row.update(upd)
        diff = {f: (before.get(f, ""), row.get(f, "")) for f in upd
                if before.get(f, "") != row.get(f, "")}
        changed.append({"email": k, "wave": wave or "?", "diff": diff})

    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    preview = workdir / f"master_sync_preview_{run}.json"
    preview.write_text(json.dumps({"changed": changed, "audit": audits},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[replies] 命中 {len(changed)} 行 / 未匹配 {sum(1 for a in audits if a['issue']=='unmatched')} / "
          f"已同步跳过 {sum(1 for a in audits if a['issue']=='already_synced')}")
    for c in changed:
        print(f"  - {c['email']} wave={c['wave']} 改 {len(c['diff'])} 字段")
    for a in audits:
        print(f"  [audit] {a['issue']} {a['email']}")
    print(f"[preview] {preview}")

    if changed and args.execute:
        backup = master_path.with_suffix(master_path.suffix + f".bak-{run}")
        backup.write_bytes(master_path.read_bytes())
        all_fields = ensure_fields(fieldnames, sorted({f for c in changed for f in c["diff"]}))
        with open(master_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=all_fields)
            w.writeheader()
            w.writerows(rows)
        print(f"[execute] 已写回 {master_path}（备份 {backup.name}）")
    elif not args.execute:
        print("[dry-run] 加 --execute 写回 master")
    return 0


def sync_sent(args) -> int:
    cfg = load_config(args.config)
    manifest_path = Path(args.manifest) if args.manifest else \
        Path(cfg.get("paths", {}).get("workdir", "workbench")) / "send_manifest.jsonl"
    default_wave = args.wave.strip().lower() if args.wave else ""
    if default_wave and default_wave not in {"mail1", "mail2", "mail3"}:
        raise SystemExit("[blocked] --wave 必须是 mail1|mail2|mail3")
    master_path = Path(args.master)
    rows, fieldnames = read_master(master_path)
    by_key: dict[str, dict] = {}
    for r in rows:
        k = key_of(r)
        if k:
            by_key.setdefault(k, r)

    sent = [json.loads(l) for l in manifest_path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    changed = []
    per_wave: dict[str, int] = {}
    for rec in sent:
        if rec.get("status") != "sent":
            continue
        wave = (rec.get("wave") or default_wave).strip().lower()
        if wave not in {"mail1", "mail2", "mail3"}:
            print(f"[skip] {rec.get('to')} 无有效 wave（rec={rec.get('wave')!r} / "
                  f"default={default_wave!r}）", file=sys.stderr)
            continue
        n = int(wave[-1])
        k = (rec.get("to") or "").strip().lower()
        row = by_key.get(k)
        if not row:
            continue
        mid = norm_id(rec.get("message_id", ""))
        # 幂等：该 wave 已完整记过账的旧 manifest 行直接跳过
        if (mid and (row.get(f"Mail{n}_Status", "") or "").strip().lower() == "sent"
                and (row.get(f"Mail{n}_Sent_At", "") or "").strip()
                and mid in (row.get("Outbound_Message_IDs", "") or "").lower()):
            continue
        updates = {}
        if mid:
            outbound = row.get("Outbound_Message_IDs", "") or ""
            token = f"{wave}:{mid}"
            if token not in outbound:
                updates["Outbound_Message_IDs"] = f"{outbound}{('|' if outbound else '')}{token}"
        cur_status = (row.get(f"Mail{n}_Status", "") or "").strip().lower()
        if cur_status in {"", "drafted", "waiting", "sent"}:
            updates[f"Mail{n}_Status"] = "sent"
        if rec.get("sent_at") and not (row.get(f"Mail{n}_Sent_At", "") or "").strip():
            updates[f"Mail{n}_Sent_At"] = rec["sent_at"]
        if updates:
            row.update(updates)
            per_wave[wave] = per_wave.get(wave, 0) + 1
            changed.append({"email": k, "wave": wave, **updates})

    run = now_ts()
    if changed and args.execute:
        backup = master_path.with_suffix(master_path.suffix + f".bak-{run.replace(':', '')}")
        backup.write_bytes(master_path.read_bytes())
        all_fields = ensure_fields(fieldnames, sorted({f for c in changed for f in c
                                                       if f not in ("email", "wave")}))
        with open(master_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=all_fields)
            w.writeheader()
            w.writerows(rows)
        print(f"[execute] 已写回 {master_path}（备份 {backup.name}）")
    wave_desc = " / ".join(f"{w}×{c}" for w, c in sorted(per_wave.items())) or "0"
    print(f"[sent] 回执命中 {len(changed)} 行（{wave_desc}）"
          + ("" if args.execute else "（dry-run，加 --execute 写回）"))
    for c in changed:
        print(f"  - [{c['wave']}] {c['email']} :: "
              f"{', '.join(k for k in c if k not in ('email', 'wave'))}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("replies", help="回复 → master（收件回填）")
    p1.add_argument("--config", default="config.toml")
    p1.add_argument("--master", required=True)
    p1.add_argument("--from-csv", default="", help="离线模式：用 fetch_replies 导出的 CSV")
    p1.add_argument("--execute", action="store_true")
    p1.set_defaults(func=sync_replies)

    p2 = sub.add_parser("sent", help="send manifest → master（发件回执）")
    p2.add_argument("--config", default="config.toml")
    p2.add_argument("--master", required=True)
    p2.add_argument("--wave", default="",
                    help="manifest 行无 wave 列时的缺省 wave（mail1|mail2|mail3）")
    p2.add_argument("--manifest", default="")
    p2.add_argument("--execute", action="store_true")
    p2.set_defaults(func=sync_sent)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
