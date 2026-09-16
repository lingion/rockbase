from __future__ import annotations

import unittest

from tiktok_kol_discovery.pipelines.run_layer3_from_l2 import evaluate_l3_row


class TestTikTokLayer3Review(unittest.TestCase):
    def test_big_org_account_is_not_kept(self) -> None:
        row = {
            "creator_handle": "growthmedialab",
            "display_name": "Growth Media Lab",
            "bio": "Official media company sharing business AI tips.",
            "followers_count": "450000",
            "overall_score": "84",
            "topic_match_score": "78",
            "contact_value": "",
        }

        reviewed = evaluate_l3_row(row, min_followers=2000)

        self.assertEqual(reviewed["script_decision"], "review")
        self.assertEqual(reviewed["recommended_action"], "drop")
        self.assertEqual(reviewed["needs_llm_review"], "yes")
        self.assertEqual(reviewed["llm_review_status"], "auto_resolved")
        self.assertEqual(reviewed["llm_decision"], "drop")

    def test_big_person_led_creator_can_still_keep(self) -> None:
        row = {
            "creator_handle": "alexfounder",
            "display_name": "Alex Founder",
            "bio": "Founder and creator teaching AI workflow systems for operators.",
            "followers_count": "360000",
            "overall_score": "82",
            "topic_match_score": "75",
            "contact_value": "",
        }

        reviewed = evaluate_l3_row(row, min_followers=2000)

        self.assertEqual(reviewed["script_decision"], "review")
        self.assertEqual(reviewed["recommended_action"], "keep")
        self.assertEqual(reviewed["needs_llm_review"], "yes")
        self.assertEqual(reviewed["llm_review_status"], "auto_resolved")
        self.assertEqual(reviewed["llm_decision"], "keep")

    def test_clean_mid_tier_creator_keeps(self) -> None:
        row = {
            "creator_handle": "janeworkflows",
            "display_name": "Jane Workflows",
            "bio": "Independent creator sharing research workflows and productivity systems.",
            "followers_count": "42000",
            "overall_score": "76",
            "topic_match_score": "68",
            "contact_value": "",
        }

        reviewed = evaluate_l3_row(row, min_followers=2000)

        self.assertEqual(reviewed["script_decision"], "keep")
        self.assertEqual(reviewed["recommended_action"], "keep")
        self.assertEqual(reviewed["needs_llm_review"], "no")

    def test_low_follower_person_brand_does_not_jump_to_keep(self) -> None:
        row = {
            "creator_handle": "avaaicreator",
            "display_name": "Ava",
            "bio": "AI creator sharing content systems.",
            "followers_count": "1153",
            "overall_score": "71",
            "topic_match_score": "68",
            "contact_value": "<YOUR_ACCOUNT_EMAIL>",
            "contact_signals": "bio_email | creator",
        }

        reviewed = evaluate_l3_row(row, min_followers=2000)

        self.assertNotEqual(reviewed["recommended_action"], "keep")

    def test_dirty_email_drops_even_if_scores_are_good(self) -> None:
        row = {
            "creator_handle": "spamcreator",
            "display_name": "Spam Creator",
            "bio": "Independent creator",
            "followers_count": "12000",
            "overall_score": "79",
            "topic_match_score": "71",
            "contact_value": "<YOUR_ACCOUNT_EMAIL>",
        }

        reviewed = evaluate_l3_row(row, min_followers=2000)

        self.assertEqual(reviewed["script_decision"], "drop")
        self.assertEqual(reviewed["recommended_action"], "drop")
        self.assertIn("blocked_domain:skool.com", reviewed["decision_reason"])


if __name__ == "__main__":
    unittest.main()
