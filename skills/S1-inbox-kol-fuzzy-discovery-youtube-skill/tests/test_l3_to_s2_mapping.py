from __future__ import annotations

import unittest

from youtube_kol_discovery.pipelines.run_l3_to_s2_mapping import _parse_args, _followers_sort_key


class TestL3ToS2MappingArgs(unittest.TestCase):
    def test_only_required_args_remain(self) -> None:
        args = _parse_args(
            [
                "--input-csv",
                "workbench/2026-05-11/YouTube/youtube_kol_L3_shortlist_batch1_2026-05-11.csv",
                "--run-date",
                "2026-05-11",
            ]
        )

        self.assertEqual(args.batch, "batch1")

    def test_email_rows_sort_ahead_of_missing_email_rows(self) -> None:
        with_email = {"联系方式": "<YOUR_ACCOUNT_EMAIL>", "粉丝数": "1000", "账号ID": "b"}
        without_email = {"联系方式": "", "粉丝数": "900000", "账号ID": "a"}

        ordered = sorted([without_email, with_email], key=_followers_sort_key)

        self.assertEqual(ordered[0]["账号ID"], "b")


if __name__ == "__main__":
    unittest.main()
