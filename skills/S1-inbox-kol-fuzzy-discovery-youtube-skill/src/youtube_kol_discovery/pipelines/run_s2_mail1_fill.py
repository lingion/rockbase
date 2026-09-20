from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from youtube_kol_discovery.io_utils import ensure_project_root, skill_dir, workbench_dir, write_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Mail1 fill for YouTube S2 merged final and optionally bridge into Gmail draft writing."
    )
    parser.add_argument("--run-date", required=True, help="Run date, e.g. 2026-05-12")
    parser.add_argument("--input-csv", default="", help="Optional S2 merged final CSV override.")
    parser.add_argument("--config", default="", help="Optional cold mail workflow config override.")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model for semantic Mail1 fill.")
    parser.add_argument("--api-key", default="", help="LLM API key. Falls back to OPENAI_API_KEY env in the fill script.")
    parser.add_argument("--base-url", default="", help="OpenAI-compatible base URL for the fill script.")
    parser.add_argument("--batch-size", type=int, default=12, help="Rows per LLM batch.")
    parser.add_argument("--max-workers", type=int, default=3, help="Concurrent LLM workers.")
    parser.add_argument("--start-row", type=int, default=2, help="Start from this sheet row number.")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows to process.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing Mail1 fields.")
    parser.add_argument("--dry-run", action="store_true", help="Run audit only, without writing back CSV.")
    parser.add_argument("--timeout-seconds", type=int, default=180, help="LLM client timeout seconds.")
    parser.add_argument(
        "--gmail-stage",
        choices=["none", "prepare", "sample", "bulk"],
        default="none",
        help="Optional Gmail handoff stage after Mail1 fill. Use prepare to build a manifest or sample to create one draft.",
    )
    parser.add_argument(
        "--gmail-manifest-out",
        default="",
        help="Optional Gmail manifest path. Defaults to workbench/{date}/YouTube/youtube_kol_S2_mail1_manifest_{date}.csv",
    )
    parser.add_argument(
        "--gmail-sample-limit",
        type=int,
        default=1,
        help="Number of drafts to create in Gmail sample stage.",
    )
    parser.add_argument(
        "--gmail-bulk-batch-size",
        type=int,
        default=20,
        help="Number of jobs per Gmail bulk batch.",
    )
    parser.add_argument(
        "--gmail-resume",
        action="store_true",
        help="Resume pending/failed jobs in bulk stage.",
    )
    parser.add_argument(
        "--gmail-include-sampled",
        action="store_true",
        help="Also process sampled jobs in bulk stage.",
    )
    parser.add_argument(
        "--gmail-user-id",
        default="me",
        help="Gmail user id for draft creation.",
    )
    parser.add_argument(
        "--gmail-access-token",
        default="",
        help="Optional Gmail access token override for draft creation.",
    )
    parser.add_argument(
        "--gmail-token-file",
        default="${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-google-workspace/auth/<YOUR_ACCOUNT_EMAIL>",
        help="Path to the Gmail OAuth token JSON file.",
    )
    return parser.parse_args()


def _gmail_skill_root() -> Path:
    return ensure_project_root() / "⚪ skills" / "S2-ag-gmail-bulk-drafts"


def _default_input_csv(run_date: str) -> Path:
    return skill_dir() / "deliverables" / run_date / f"【S2_cold】{run_date}_youtube_kol_S2_merged_final.csv"


def _backup_input_csv(input_csv: Path, run_date: str) -> Path:
    project_root = ensure_project_root()
    backup_dir = project_root / "Agency" / "list-bak" / run_date
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    backup_path = backup_dir / f"{input_csv.name}_bak_{stamp}.csv"
    shutil.copy2(input_csv, backup_path)
    return backup_path


def _run_subprocess(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))


def _gmail_manifest_path(args: argparse.Namespace, wb_dir: Path) -> Path:
    if args.gmail_manifest_out:
        return Path(args.gmail_manifest_out).expanduser().resolve()
    return wb_dir / f"youtube_kol_S2_mail1_manifest_{args.run_date}.csv"


def _run_gmail_prepare(
    gmail_skill_root: Path,
    source_csv: Path,
    manifest_path: Path,
) -> subprocess.CompletedProcess[str]:
    prepare_script = gmail_skill_root / "scripts" / "gmail" / "prepare_jobs.py"
    if not prepare_script.exists():
        raise SystemExit(f"Missing Gmail prepare script: {prepare_script}")
    cmd = [
        "python3",
        str(prepare_script),
        "--input",
        str(source_csv),
        "--output",
        str(manifest_path),
        "--to-field",
        "联系方式",
        "--subject-field",
        "Mail1_Subject",
        "--body-field",
        "Mail1_Content V1",
        "--skip-mail1-coherence-check",
    ]
    return _run_subprocess(cmd, gmail_skill_root)


def _run_gmail_sample(
    gmail_skill_root: Path,
    source_csv: Path,
    manifest_path: Path,
    gmail_user_id: str,
    gmail_access_token: str,
    gmail_token_file: str,
    sample_limit: int,
) -> subprocess.CompletedProcess[str]:
    sample_script = gmail_skill_root / "scripts" / "gmail" / "sample_send.py"
    if not sample_script.exists():
        raise SystemExit(f"Missing Gmail sample script: {sample_script}")
    cmd = [
        "python3",
        str(sample_script),
        "--manifest",
        str(manifest_path),
        "--source-csv",
        str(source_csv),
        "--source-status-field",
        "Mail1发出状态",
        "--source-drafted-value",
        "drafted",
        "--limit",
        str(sample_limit),
        "--user-id",
        gmail_user_id,
        "--token-file",
        gmail_token_file,
    ]
    if gmail_access_token:
        cmd.extend(["--access-token", gmail_access_token])
    return _run_subprocess(cmd, gmail_skill_root)


def _run_gmail_bulk(
    gmail_skill_root: Path,
    source_csv: Path,
    manifest_path: Path,
    gmail_user_id: str,
    gmail_access_token: str,
    gmail_token_file: str,
    gmail_bulk_batch_size: int,
    gmail_resume: bool,
    gmail_include_sampled: bool,
) -> subprocess.CompletedProcess[str]:
    bulk_script = gmail_skill_root / "scripts" / "gmail" / "bulk_send.py"
    if not bulk_script.exists():
        raise SystemExit(f"Missing Gmail bulk script: {bulk_script}")
    cmd = [
        "python3",
        str(bulk_script),
        "--manifest",
        str(manifest_path),
        "--source-csv",
        str(source_csv),
        "--source-status-field",
        "Mail1发出状态",
        "--source-drafted-value",
        "drafted",
        "--user-id",
        gmail_user_id,
        "--token-file",
        gmail_token_file,
        "--batch-size",
        str(gmail_bulk_batch_size),
    ]
    if gmail_resume:
        cmd.append("--resume")
    if gmail_include_sampled:
        cmd.append("--include-sampled")
    if gmail_access_token:
        cmd.extend(["--access-token", gmail_access_token])
    return _run_subprocess(cmd, gmail_skill_root)


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve() if args.input_csv else _default_input_csv(args.run_date)
    if not input_csv.exists():
        raise SystemExit(f"Missing input CSV: {input_csv}")

    gmail_skill_root = _gmail_skill_root()
    fill_script = gmail_skill_root / "scripts" / "gmail" / "fill_mail1_with_codex.py"
    if not fill_script.exists():
        raise SystemExit(f"Missing Gmail Mail1 fill script: {fill_script}")

    wb_dir = workbench_dir(args.run_date)
    audit_dir = wb_dir
    runlog_json = wb_dir / f"youtube_kol_S2_mail1_fill_runlog_{args.run_date}.json"
    gmail_manifest = _gmail_manifest_path(args, wb_dir)

    backup_path = None if args.dry_run else _backup_input_csv(input_csv, args.run_date)
    print(f"📍 Routing to: {wb_dir}")

    cmd = [
        "python3",
        str(fill_script),
        "--input",
        str(input_csv),
        "--model",
        args.model,
        "--batch-size",
        str(args.batch_size),
        "--max-workers",
        str(args.max_workers),
        "--start-row",
        str(args.start_row),
        "--audit-dir",
        str(audit_dir),
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.api_key:
        cmd.extend(["--api-key", args.api_key])
    if args.base_url:
        cmd.extend(["--base-url", args.base_url])
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.overwrite:
        cmd.append("--overwrite")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.config:
        cmd.extend(["--config", str(Path(args.config).expanduser().resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(gmail_skill_root))
    gmail_prepare = None
    gmail_sample = None
    gmail_bulk = None
    if proc.returncode == 0 and args.gmail_stage != "none":
        gmail_prepare = _run_gmail_prepare(
            gmail_skill_root=gmail_skill_root,
            source_csv=input_csv,
            manifest_path=gmail_manifest,
        )
        if gmail_prepare.returncode != 0:
            raise SystemExit(
                f"Gmail prepare failed. See stdout/stderr in runlog.\nSTDERR:\n{gmail_prepare.stderr[-4000:]}"
            )
        if args.gmail_stage == "sample":
            gmail_sample = _run_gmail_sample(
                gmail_skill_root=gmail_skill_root,
                source_csv=input_csv,
                manifest_path=gmail_manifest,
                gmail_user_id=args.gmail_user_id,
                gmail_access_token=args.gmail_access_token,
                gmail_token_file=args.gmail_token_file,
                sample_limit=args.gmail_sample_limit,
            )
            if gmail_sample.returncode != 0:
                raise SystemExit(
                    f"Gmail sample failed. See stdout/stderr in runlog.\nSTDERR:\n{gmail_sample.stderr[-4000:]}"
                )
        elif args.gmail_stage == "bulk":
            gmail_bulk = _run_gmail_bulk(
                gmail_skill_root=gmail_skill_root,
                source_csv=input_csv,
                manifest_path=gmail_manifest,
                gmail_user_id=args.gmail_user_id,
                gmail_access_token=args.gmail_access_token,
                gmail_token_file=args.gmail_token_file,
                gmail_bulk_batch_size=args.gmail_bulk_batch_size,
                gmail_resume=args.gmail_resume,
                gmail_include_sampled=args.gmail_include_sampled,
            )
            if gmail_bulk.returncode != 0:
                raise SystemExit(
                    f"Gmail bulk failed. See stdout/stderr in runlog.\nSTDERR:\n{gmail_bulk.stderr[-4000:]}"
                )
    runlog = {
        "run_date": args.run_date,
        "input_csv": str(input_csv),
        "backup_csv": str(backup_path) if backup_path else "",
        "gmail_skill_root": str(gmail_skill_root),
        "fill_script": str(fill_script),
        "audit_dir": str(audit_dir),
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "dry_run": args.dry_run,
        "gmail_stage": args.gmail_stage,
        "gmail_manifest": str(gmail_manifest) if args.gmail_stage != "none" else "",
        "gmail_prepare_returncode": None if gmail_prepare is None else gmail_prepare.returncode,
        "gmail_prepare_stdout": "" if gmail_prepare is None else gmail_prepare.stdout,
        "gmail_prepare_stderr": "" if gmail_prepare is None else gmail_prepare.stderr,
        "gmail_sample_returncode": None if gmail_sample is None else gmail_sample.returncode,
        "gmail_sample_stdout": "" if gmail_sample is None else gmail_sample.stdout,
        "gmail_sample_stderr": "" if gmail_sample is None else gmail_sample.stderr,
        "gmail_bulk_returncode": None if gmail_bulk is None else gmail_bulk.returncode,
        "gmail_bulk_stdout": "" if gmail_bulk is None else gmail_bulk.stdout,
        "gmail_bulk_stderr": "" if gmail_bulk is None else gmail_bulk.stderr,
        "notes": [
            "This runner delegates Mail1 fill to the canonical Gmail bulk drafts skill.",
            "YouTube skill owns S2 merged final; Gmail skill owns Mail1 semantic fill and copy assembly.",
            "When gmail_stage is prepare or sample, the bridge also generates a Gmail manifest and optionally creates a sample draft.",
            "When gmail_stage is bulk, the bridge generates a Gmail manifest and runs the bulk draft writer.",
        ],
    }
    write_json(runlog_json, runlog)

    if proc.returncode != 0:
        raise SystemExit(
            f"Mail1 fill failed. See runlog: {runlog_json}\nSTDERR:\n{proc.stderr[-4000:]}"
        )

    print(
        json.dumps(
            {
                "input_csv": str(input_csv),
                "backup_csv": str(backup_path) if backup_path else "",
                "runlog_json": str(runlog_json),
                "audit_dir": str(audit_dir),
                "dry_run": args.dry_run,
                "gmail_stage": args.gmail_stage,
                "gmail_manifest": str(gmail_manifest) if args.gmail_stage != "none" else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
