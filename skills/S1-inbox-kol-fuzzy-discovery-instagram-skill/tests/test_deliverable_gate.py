import unittest

from instagram_kol_discovery.pipelines.deliverable_gate import deliverable_gate_decision


class DeliverableGateTests(unittest.TestCase):
    def test_blocks_explicit_org_keyword_without_person_signal(self) -> None:
        row = {
            "creator_handle": "brandstudiohq",
            "display_name": "Brand Studio HQ",
            "bio": "Official studio for campaigns and brand partnerships",
            "recommended_action": "review",
        }
        decision = deliverable_gate_decision(row)
        self.assertFalse(decision.allowed)
        self.assertIn("blocked_", decision.reason)

    def test_keeps_person_led_creator_with_commercial_bio(self) -> None:
        row = {
            "creator_handle": "sharontseung",
            "display_name": "Sharon Tseung",
            "bio": "I retired at 31 and help you become financially free",
            "recommended_action": "keep",
        }
        decision = deliverable_gate_decision(row)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "allowed_creator")


if __name__ == "__main__":
    unittest.main()
