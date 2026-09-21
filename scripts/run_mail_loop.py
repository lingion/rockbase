"""Run the existing S2/mailkit reply loop with resumable state."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .rockbase_orchestrator import Stage, run_pipeline


def _module_command(module: str, *args: object) -> tuple[str, ...]:
    return (sys.executable, "-m", module, *(str(arg) for arg in args))


def build_mail_loop_stages(
    *,
    batch_csv: Path,
    config: Path,
    master: Path,
    state_path: Path,
    fetch_out: Path,
    execute_send: bool = False,
    execute_sync: bool = False,
) -> list[Stage]:
    """Build the four existing CLI stages for one Mail1 batch."""
    workdir = config.parent / "workbench"
    manifest = workdir / "send_manifest.jsonl"
    replies_csv = fetch_out.with_suffix(".csv")

    send_args = ["--config", config, "--csv", batch_csv,
                 "--to-field", "联系方式", "--name-field", "频道/作者名称",
                 "--subject-field", "Mail1_Subject", "--body-field", "Mail1_Content V1"]
    if execute_send:
        send_args.append("--execute")

    sent_sync_args = ["sent", "--config", config, "--master", master,
                      "--wave", "mail1", "--manifest", manifest]
    replies_sync_args = ["replies", "--config", config, "--master", master,
                         "--from-csv", replies_csv]
    if execute_sync:
        sent_sync_args.append("--execute")
        replies_sync_args.append("--execute")

    return [
        Stage("mailkit_send", _module_command("mailkit.mailkit.send", *send_args),
              artifacts=(manifest,) if execute_send else ()),

        Stage("fetch_replies", _module_command("mailkit.mailkit.fetch_replies", "--config", config,
                                                "--out", fetch_out), artifacts=(fetch_out.with_suffix(".json"),)),
        Stage("master_sync_sent", _module_command("mailkit.mailkit.master_sync", *sent_sync_args)),
        Stage("master_sync_replies", _module_command("mailkit.mailkit.master_sync", *replies_sync_args)),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-csv", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--fetch-out", type=Path, required=True)
    parser.add_argument("--execute-send", action="store_true",
                        help="allow SMTP send; default is mailkit dry-run")
    parser.add_argument("--execute-sync", action="store_true",
                        help="allow master CSV write-back; default is dry-run")
    parser.add_argument("--retries", type=int, default=0,
                        help="extra attempts per stage on failure (default 0)")
    parser.add_argument("--plan", action="store_true",
                        help="print stage commands without executing them")
    args = parser.parse_args(argv)
    stages = build_mail_loop_stages(
        batch_csv=args.batch_csv,
        config=args.config,
        master=args.master,
        state_path=args.state,
        fetch_out=args.fetch_out,
        execute_send=args.execute_send,
        execute_sync=args.execute_sync,
    )
    return run_pipeline(stages, state_path=args.state, plan_only=args.plan, retries=args.retries)


if __name__ == "__main__":
    raise SystemExit(main())
