from __future__ import annotations

import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/S3-codex-plugin-reply/scripts/build_daily_incremental_queues.py"


def test_s3_daily_queue_runs_offline_from_external_directory(tmp_path: Path) -> None:
    input_path = tmp_path / "input with spaces.csv"
    output_dir = tmp_path / "output with spaces"
    columns = [
        "频道/作者名称",
        "Reply_Contact_Email",
        "Reply_Last_At",
        "Reply_Stream",
        "Reply_Ownership",
        "Need_Reply_State",
        "Latest_Thread_Speaker",
        "Next_Reply_Action",
        "Attachment_OCR_Status",
        "Reply_Needs_Manual_Review",
    ]
    with input_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(
            {
                "频道/作者名称": "Example Creator",
                "Reply_Contact_Email": "creator@one.example.invalid",
                "Reply_Last_At": datetime.now().isoformat(timespec="seconds"),
                "Reply_Stream": "Outreach",
                "Reply_Ownership": "auto_reply",
                "Need_Reply_State": "reply_needed_from_us",
                "Latest_Thread_Speaker": "them",
                "Next_Reply_Action": "request_rate",
                "Attachment_OCR_Status": "none",
                "Reply_Needs_Manual_Review": "no",
            }
        )

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--shadow-csv",
            str(input_path),
            "--out-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    with (output_dir / "queue_draft_ready.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["creator_name"] == "Example Creator"
    assert (output_dir / "summary_daily_incremental_queues.md").is_file()
