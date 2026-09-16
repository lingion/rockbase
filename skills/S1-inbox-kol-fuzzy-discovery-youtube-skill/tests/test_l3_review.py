from __future__ import annotations

import unittest
from unittest.mock import patch

from youtube_kol_discovery.pipelines.run_layer3_review import evaluate_l3_row


class TestLayer3Review(unittest.TestCase):
    def test_llm_drop_row_is_routed_to_drop(self) -> None:
        row = {
            "creator_handle": "UC_BIG",
            "display_name": "Growth Media Lab",
            "bio": "Media company sharing AI workflow breakdowns.",
            "followers_count": "450000",
            "recommended_action": "keep",
            "contact_value": "",
        }

        with patch("youtube_kol_discovery.pipelines.run_layer3_review.screen_entity") as screen_entity:
            screen_entity.return_value = {
                "llm_entity_type": "org_or_media",
                "llm_decision": "drop",
                "llm_confidence": "high",
                "llm_rationale": "媒体号，不进入最终表。",
                "llm_review_status": "auto_resolved",
                "needs_llm_review": "no",
            }
            reviewed = evaluate_l3_row(row)

        self.assertEqual(reviewed["script_decision"], "keep")
        self.assertEqual(reviewed["final_decision"], "drop")
        self.assertEqual(reviewed["llm_review_status"], "auto_resolved")
        self.assertEqual(reviewed["llm_decision"], "drop")

    def test_clean_creator_can_keep_without_email(self) -> None:
        row = {
            "creator_handle": "UC_CLEAN",
            "display_name": "Jane Creator",
            "bio": "Independent creator teaching research workflows for content planning.",
            "followers_count": "24000",
            "recommended_action": "keep",
            "contact_value": "",
        }

        with patch("youtube_kol_discovery.pipelines.run_layer3_review.screen_entity") as screen_entity:
            screen_entity.return_value = {
                "llm_entity_type": "person_led_creator",
                "llm_decision": "keep",
                "llm_confidence": "high",
                "llm_rationale": "个人创作者。",
                "llm_review_status": "auto_resolved",
                "needs_llm_review": "no",
            }
            reviewed = evaluate_l3_row(row)

        self.assertEqual(reviewed["script_decision"], "keep")
        self.assertEqual(reviewed["final_decision"], "keep")
        self.assertEqual(reviewed["needs_llm_review"], "no")

    def test_dirty_blocked_email_still_drops(self) -> None:
        row = {
            "creator_handle": "UC_DROP",
            "display_name": "Spam Creator",
            "bio": "Independent creator",
            "followers_count": "5000",
            "recommended_action": "keep",
            "contact_value": "<YOUR_ACCOUNT_EMAIL>",
        }

        with patch("youtube_kol_discovery.pipelines.run_layer3_review.screen_entity") as screen_entity:
            screen_entity.return_value = {
                "llm_entity_type": "person_led_creator",
                "llm_decision": "drop",
                "llm_confidence": "high",
                "llm_rationale": "脏邮箱。",
                "llm_review_status": "auto_resolved",
                "needs_llm_review": "no",
            }
            reviewed = evaluate_l3_row(row)

        self.assertEqual(reviewed["script_decision"], "drop")
        self.assertEqual(reviewed["final_decision"], "drop")
        self.assertIn("script_drop: dirty contact", reviewed["decision_reason"])

    def test_big_personal_brand_can_still_keep(self) -> None:
        row = {
            "creator_handle": "UC_KEEP",
            "display_name": "Alex Founder",
            "bio": "Founder and creator teaching AI workflow systems for operators.",
            "followers_count": "360000",
            "recommended_action": "keep",
            "contact_value": "",
        }

        with patch("youtube_kol_discovery.pipelines.run_layer3_review.screen_entity") as screen_entity:
            screen_entity.return_value = {
                "llm_entity_type": "personal_brand_with_org_signals",
                "llm_decision": "keep",
                "llm_confidence": "medium",
                "llm_rationale": "个人品牌，可保留。",
                "llm_review_status": "auto_resolved",
                "needs_llm_review": "no",
            }
            reviewed = evaluate_l3_row(row)

        self.assertEqual(reviewed["script_decision"], "keep")
        self.assertEqual(reviewed["final_decision"], "keep")
        self.assertEqual(reviewed["needs_llm_review"], "no")
        self.assertEqual(reviewed["llm_review_status"], "auto_resolved")
        self.assertEqual(reviewed["llm_decision"], "keep")


if __name__ == "__main__":
    unittest.main()
