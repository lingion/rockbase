import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "build_daily_incremental_queues.py"
SPEC = importlib.util.spec_from_file_location("build_daily_incremental_queues", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ClassifyQueueTests(unittest.TestCase):
    def test_excludes_threads_owned_by_steve(self) -> None:
        row = {
            "Reply_Stream": "Outreach",
            "Reply_Ownership": "steve_handle",
            "Need_Reply_State": "reply_needed_from_us",
            "Latest_Thread_Speaker": "them",
            "Next_Reply_Action": "request_rate",
            "Attachment_OCR_Status": "none",
            "Reply_Needs_Manual_Review": "no",
        }

        self.assertEqual(
            MODULE.classify_queue(row),
            ("excluded", "ownership_steve_handle", "not_applicable"),
        )

    def test_excludes_threads_where_latest_outbound_is_ours(self) -> None:
        row = {
            "Reply_Stream": "Outreach",
            "Reply_Ownership": "auto_reply",
            "Need_Reply_State": "no_reply_needed_latest_outbound_ours",
            "Latest_Thread_Speaker": "us",
            "Next_Reply_Action": "hold_warm",
            "Attachment_OCR_Status": "none",
            "Reply_Needs_Manual_Review": "no",
        }

        self.assertEqual(
            MODULE.classify_queue(row),
            ("excluded", "no_reply_needed_latest_outbound_ours", "not_applicable"),
        )

    def test_routes_stale_unresolved_threads_into_missed_reply_queue(self) -> None:
        row = {
            "Reply_Stream": "Outreach",
            "Reply_Ownership": "auto_reply",
            "Need_Reply_State": "reply_needed_from_us",
            "Latest_Thread_Speaker": "them",
            "Next_Reply_Action": "stale_thread_refresh_required",
            "Attachment_OCR_Status": "none",
            "Reply_Needs_Manual_Review": "no",
        }

        self.assertEqual(
            MODULE.classify_queue(row),
            ("missed_reply_queue", "stale_thread_refresh_required", "needs_thread_refresh"),
        )

    def test_routes_contact_updates_without_draft_need(self) -> None:
        row = {
            "Reply_Stream": "Outreach",
            "Reply_Ownership": "auto_reply",
            "Need_Reply_State": "contact_update_only",
            "Latest_Thread_Speaker": "them",
            "Next_Reply_Action": "update_contact_only",
            "Attachment_OCR_Status": "none",
            "Reply_Needs_Manual_Review": "no",
        }

        self.assertEqual(
            MODULE.classify_queue(row),
            ("contact_update_queue", "update_contact_only", "contact_update_only"),
        )


if __name__ == "__main__":
    unittest.main()
