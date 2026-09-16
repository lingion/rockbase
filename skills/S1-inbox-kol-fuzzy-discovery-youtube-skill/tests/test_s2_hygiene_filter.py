from __future__ import annotations

import unittest

from youtube_kol_discovery.pipelines.run_s2_hygiene_filter import evaluate_row


class TestS2HygieneFilter(unittest.TestCase):
    def test_missing_email_is_kept_for_follow_up(self) -> None:
        row = {
            "creator_handle": "UC123",
            "display_name": "Jane Creator",
            "bio": "Independent creator sharing AI workflows for content research.",
            "contact_value": "",
        }

        reviewed = evaluate_row(
            row,
            explicit_org_channel_ids=set(),
            explicit_org_handles=set(),
            explicit_org_names=set(),
            remove_suspected_orgs=False,
        )

        self.assertEqual(reviewed["manual_clean_decision"], "keep")
        self.assertEqual(reviewed["clean_email"], "")
        self.assertEqual(reviewed["email_qc_flag"], "missing")
        self.assertIn("missing email", reviewed["manual_clean_reason"])

    def test_blocked_email_still_drops(self) -> None:
        row = {
            "creator_handle": "UC456",
            "display_name": "Bad Contact Creator",
            "bio": "Solo creator",
            "contact_value": "<YOUR_ACCOUNT_EMAIL>",
        }

        reviewed = evaluate_row(
            row,
            explicit_org_channel_ids=set(),
            explicit_org_handles=set(),
            explicit_org_names=set(),
            remove_suspected_orgs=False,
        )

        self.assertEqual(reviewed["manual_clean_decision"], "drop")
        self.assertEqual(reviewed["email_qc_flag"], "invalid")
        self.assertIn("blocked_domain:skool.com", reviewed["manual_clean_reason"])


if __name__ == "__main__":
    unittest.main()
