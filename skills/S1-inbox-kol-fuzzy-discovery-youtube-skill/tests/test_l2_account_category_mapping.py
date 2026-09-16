from __future__ import annotations

import unittest

from youtube_kol_discovery.layer2.youtube_enrichment import map_account_category_platform


class TestLayer2AccountCategoryMapping(unittest.TestCase):
    def test_scrapecreators_tags_are_written_to_platform_category(self) -> None:
        self.assertEqual(
            map_account_category_platform("Technology, Gadgets, Apps"),
            "Technology, Gadgets, Apps",
        )

    def test_missing_scrapecreators_tags_stays_blank(self) -> None:
        self.assertEqual(map_account_category_platform(""), "")


if __name__ == "__main__":
    unittest.main()
