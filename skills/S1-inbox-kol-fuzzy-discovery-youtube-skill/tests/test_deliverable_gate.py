from __future__ import annotations

import unittest

from youtube_kol_discovery.pipelines.deliverable_gate import deliverable_gate_decision


class TestDeliverableGate(unittest.TestCase):
    def test_llm_drop_row_is_blocked_from_deliverable(self) -> None:
        row = {
            "creator_handle": "UC_ORG",
            "display_name": "Brand Media Lab",
            "final_decision": "drop",
            "llm_entity_type": "org_or_media",
            "llm_decision": "drop",
            "llm_review_status": "auto_resolved",
        }

        decision = deliverable_gate_decision(row)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "blocked_llm_drop")

    def test_missing_llm_screen_is_blocked_from_deliverable(self) -> None:
        row = {
            "creator_handle": "UC_SUSPECT",
            "display_name": "Newsletter Growth Club",
            "final_decision": "keep",
            "llm_entity_type": "",
            "llm_decision": "",
            "llm_review_status": "",
        }

        decision = deliverable_gate_decision(row)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "blocked_llm_missing")

    def test_clean_keep_row_is_allowed_into_deliverable(self) -> None:
        row = {
            "creator_handle": "UC_PERSON",
            "display_name": "Jane Creator",
            "final_decision": "keep",
            "llm_entity_type": "person_led_creator",
            "llm_decision": "keep",
            "llm_review_status": "auto_resolved",
        }

        decision = deliverable_gate_decision(row)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "allowed_keep")


if __name__ == "__main__":
    unittest.main()
