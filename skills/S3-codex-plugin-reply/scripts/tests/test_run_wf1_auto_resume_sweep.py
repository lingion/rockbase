import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_wf1_auto_resume_sweep.py"
SPEC = importlib.util.spec_from_file_location("run_wf1_auto_resume_sweep", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ResumeSweepSummaryTests(unittest.TestCase):
    def test_classify_rollup_distinguishes_new_refresh_and_reply_followup(self) -> None:
        rows = [
            {
                "queue_name": "new_price_and_new_draft",
                "price_source": "body_quote",
                "in_master": "no",
                "is_refresh_vs_master": "no",
                "thread_has_draft": "no",
                "is_system_thread": "no",
                "latest_message_speaker": "them",
            },
            {
                "queue_name": "pass_existing_draft_writeback_only",
                "price_source": "ocr_quote",
                "in_master": "yes",
                "is_refresh_vs_master": "yes",
                "thread_has_draft": "yes",
                "is_system_thread": "no",
                "latest_message_speaker": "them",
            },
            {
                "queue_name": "draft_needed_no_price",
                "price_source": "",
                "in_master": "yes",
                "is_refresh_vs_master": "no",
                "thread_has_draft": "no",
                "is_system_thread": "no",
                "latest_message_speaker": "them",
            },
            {
                "queue_name": "non_wf1_system",
                "price_source": "",
                "in_master": "no",
                "is_refresh_vs_master": "no",
                "thread_has_draft": "no",
                "is_system_thread": "yes",
                "latest_message_speaker": "them",
            },
        ]

        rollup = MODULE.build_rollup_counts(rows)

        self.assertEqual(rollup["new_price_threads"], 1)
        self.assertEqual(rollup["refreshed_price_threads"], 1)
        self.assertEqual(rollup["price_signal_threads"], 2)
        self.assertEqual(rollup["needs_reply_threads"], 1)
        self.assertEqual(rollup["existing_draft_threads"], 1)
        self.assertEqual(rollup["non_wf1_threads"], 1)

    def test_summary_includes_boundary_proof_and_message_totals(self) -> None:
        rows = [
            {
                "queue_name": "new_price_and_new_draft",
                "price_source": "body_quote",
                "in_master": "no",
                "is_refresh_vs_master": "no",
                "thread_has_draft": "no",
                "is_system_thread": "no",
                "latest_message_speaker": "them",
                "message_count": "3",
            },
            {
                "queue_name": "draft_needed_no_price",
                "price_source": "",
                "in_master": "yes",
                "is_refresh_vs_master": "no",
                "thread_has_draft": "no",
                "is_system_thread": "no",
                "latest_message_speaker": "them",
                "message_count": "2",
            },
        ]

        summary = MODULE.build_summary(
            scan_rows=rows,
            checkpoint={"last_window_end_at": "2026-06-11T00:00:00", "resume_boundary_lower_date": "2026-05-28T00:00:00"},
            lower_bound=MODULE.parse_iso("2026-06-11T00:00:00"),
            scanned_pages=2,
            stopped_on_lower_bound=True,
            newest_seen_at="Mon, 23 Jun 2026 10:00:00 +0800",
            oldest_seen_at="Thu, 11 Jun 2026 09:00:00 +0800",
            attachment_count=0,
            manifest_rows=[{"Reply_Thread_ID": "t1"}],
            artifact_paths={"scan_csv": "/tmp/scan.csv"},
            boundary_thread={
                "thread_id": "boundary-1",
                "subject": "Older boundary thread",
                "latest_message_at": "Wed, 10 Jun 2026 09:00:00 +0800",
            },
            mode="dry-run",
        )

        self.assertEqual(summary["execution_mode"], "dry-run")
        self.assertTrue(summary["connected_to_previous_stop"])
        self.assertEqual(summary["message_total_seen"], 5)
        self.assertEqual(summary["new_price_thread_count"], 1)
        self.assertEqual(summary["reply_needed_thread_count"], 1)
        self.assertEqual(summary["boundary_hit_thread"]["thread_id"], "boundary-1")


if __name__ == "__main__":
    unittest.main()
