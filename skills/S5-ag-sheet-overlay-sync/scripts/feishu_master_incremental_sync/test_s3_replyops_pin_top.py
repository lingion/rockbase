import unittest

import feishu_s3_replyops_writeback as mod


class ReplyPinTopPlanTests(unittest.TestCase):
    def test_build_reply_pin_top_plan_keeps_stable_order(self):
        values = [
            ["账号ID", "频道/作者名称", "Mail1 邮件回复"],
            ["a", "Alpha", ""],
            ["b", "Beta", "Y"],
            ["c", "Gamma", ""],
            ["d", "Delta", "Y"],
        ]
        header_map = mod.build_header_map(values[0])

        plan = mod.build_reply_pin_top_plan(values, header_map)

        self.assertEqual(plan["reply_y_total"], 2)
        self.assertEqual(plan["top_block_expected"], 2)
        self.assertEqual(
            [row[0] for row in plan["reordered_rows"]],
            ["b", "d", "a", "c"],
        )
        self.assertEqual(
            plan["move_rows"][:2],
            [
                {"old_row_num": 3, "new_row_num": 2, "账号ID": "b", "频道/作者名称": "Beta", "Mail1 邮件回复": "Y"},
                {"old_row_num": 5, "new_row_num": 3, "账号ID": "d", "频道/作者名称": "Delta", "Mail1 邮件回复": "Y"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
