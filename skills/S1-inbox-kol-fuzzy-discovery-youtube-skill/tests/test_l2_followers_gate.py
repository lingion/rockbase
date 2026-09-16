from __future__ import annotations

import unittest

from youtube_kol_discovery.layer2.youtube_enrichment import evaluate_layer2_gate


class TestLayer2FollowersGate(unittest.TestCase):
    def test_below_min_followers_is_blocked(self) -> None:
        decision = evaluate_layer2_gate(followers_count=999, bad_keyword_hits=0)

        self.assertEqual(decision.layer2_eligible, "no")
        self.assertEqual(decision.layer2_skip_reason, "followers_below_1000")
        self.assertEqual(decision.recommended_action, "drop")

    def test_at_min_followers_can_still_be_reviewed(self) -> None:
        decision = evaluate_layer2_gate(followers_count=1000, bad_keyword_hits=0)

        self.assertEqual(decision.layer2_eligible, "yes")
        self.assertEqual(decision.layer2_skip_reason, "")
        self.assertEqual(decision.recommended_action, "review")


if __name__ == "__main__":
    unittest.main()
