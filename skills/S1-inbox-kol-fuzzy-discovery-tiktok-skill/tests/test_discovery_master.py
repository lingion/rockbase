from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tiktok_kol_discovery.io_utils import write_csv
from tiktok_kol_discovery.layer2.discovery_master import DISCOVERY_MASTER_COLUMNS, route_candidates_with_discovery_master


def _master_row(**overrides: str) -> dict[str, str]:
    row = {column: "" for column in DISCOVERY_MASTER_COLUMNS}
    row.update(
        {
            "platform": "tiktok",
            "creator_handle": "janedoe",
            "display_name": "Jane Doe",
            "first_seen_date": "2026-05-12",
            "last_seen_date": "2026-05-12",
            "first_seen_project": "aully",
            "last_seen_project": "aully",
            "first_seen_batch": "aully_batch_01_content_creators",
            "last_seen_batch": "aully_batch_01_content_creators",
            "times_seen_after_views_gate": "1",
            "master_status": "active",
        }
    )
    row.update(overrides)
    return row


class TestDiscoveryMasterRouting(unittest.TestCase):
    def _write_master(self, rows: list[dict[str, str]]) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        target = tmpdir / "master.csv"
        write_csv(target, rows, preferred_fields=DISCOVERY_MASTER_COLUMNS)
        return target

    def test_same_batch_rerun_is_allowed(self) -> None:
        master_path = self._write_master([_master_row()])
        candidates = [{"creator_handle": "janedoe", "display_name": "Jane Doe", "max_views": "120000", "top_content_url": "https://example.com"}]

        to_enrich, blocked, audit_rows, _ = route_candidates_with_discovery_master(
            candidates,
            batch_name="aully_batch_01_content_creators",
            master_path=master_path,
        )

        self.assertEqual(len(to_enrich), 1)
        self.assertEqual(len(blocked), 0)
        self.assertEqual(audit_rows[0]["status"], "same_batch_rerun")

    def test_same_project_new_batch_is_soft_allowed(self) -> None:
        master_path = self._write_master([_master_row(last_seen_batch="aully_batch_01_content_creators")])
        candidates = [{"creator_handle": "janedoe", "display_name": "Jane Doe", "max_views": "120000", "top_content_url": "https://example.com"}]

        to_enrich, blocked, audit_rows, _ = route_candidates_with_discovery_master(
            candidates,
            batch_name="aully_batch_02_real_estate_professionals",
            master_path=master_path,
        )

        self.assertEqual(len(to_enrich), 1)
        self.assertEqual(len(blocked), 0)
        self.assertEqual(audit_rows[0]["status"], "same_project_seen")

    def test_suppressed_rows_still_block(self) -> None:
        master_path = self._write_master([_master_row(master_status="suppressed", first_seen_project="legacy", last_seen_project="legacy")])
        candidates = [{"creator_handle": "janedoe", "display_name": "Jane Doe", "max_views": "120000", "top_content_url": "https://example.com"}]

        to_enrich, blocked, audit_rows, _ = route_candidates_with_discovery_master(
            candidates,
            batch_name="aully_batch_04_investment_analysts_investors",
            master_path=master_path,
        )

        self.assertEqual(len(to_enrich), 0)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(audit_rows[0]["status"], "blocked_by_master")
        self.assertIn("hard_suppression", audit_rows[0]["reason"])


if __name__ == "__main__":
    unittest.main()
