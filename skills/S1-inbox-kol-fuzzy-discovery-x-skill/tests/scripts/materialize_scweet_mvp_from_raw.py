from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common_env import load_simple_env, tests_root
from run_scweet_mvp import (
    RunConfig,
    _fetch_user_info,
    _normalize_rows,
    _root_paths,
    _safe_text,
    _workbench_dir,
    _write_csv,
    _write_summary,
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: materialize_scweet_mvp_from_raw.py RAW_JSON_PATH")

    raw_json_source = Path(sys.argv[1]).resolve()
    payload = json.loads(raw_json_source.read_text(encoding="utf-8"))
    raw_rows: list[dict[str, Any]] = payload["rows"]
    search_meta: list[dict[str, Any]] = payload.get("search_meta", [])

    config = RunConfig()
    tests_dir, project_root = _root_paths()
    out_dir = _workbench_dir(project_root)
    env = load_simple_env(tests_dir / ".env.layer1.local")
    auth_token = env["X_AUTH_TOKEN"]

    timestamp = "2026-03-31"
    raw_json_path = out_dir / f"x_kol_mvp_raw_candidates_{timestamp}.json"
    raw_csv_path = out_dir / f"x_kol_mvp_raw_candidates_{timestamp}.csv"
    normalized_csv_path = out_dir / f"x_kol_mvp_normalized_candidates_{timestamp}.csv"
    shortlist_csv_path = out_dir / f"x_kol_mvp_shortlist_{config.shortlist_target}_{timestamp}.csv"
    summary_md_path = out_dir / f"x_kol_mvp_summary_{timestamp}.md"
    user_info_db_path = out_dir / "scweet_userinfo_state_2026-03-31.db"
    if user_info_db_path.exists():
        user_info_db_path.unlink()

    candidate_usernames = sorted(
        {
            _safe_text(row.get("username")).lower()
            for row in raw_rows
            if _safe_text(row.get("username"))
        }
    )
    profile_map, user_info_meta = _fetch_user_info(auth_token, user_info_db_path, candidate_usernames, config)
    normalized_rows = _normalize_rows(raw_rows, profile_map, config)
    shortlist_rows = [row for row in normalized_rows if row["recommended_action"] in {"keep", "review"}][
        : config.shortlist_target
    ]

    raw_json_path.write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(UTC).isoformat(),
                "source_raw_json": str(raw_json_source),
                "search_meta": search_meta,
                "rows": raw_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_csv(raw_csv_path, raw_rows)
    _write_csv(normalized_csv_path, normalized_rows)
    _write_csv(shortlist_csv_path, shortlist_rows)
    _write_summary(
        summary_md_path,
        config,
        search_meta,
        user_info_meta,
        raw_rows,
        normalized_rows,
        shortlist_rows,
        {
            "raw_json": raw_json_path,
            "raw_csv": raw_csv_path,
            "normalized_csv": normalized_csv_path,
            "shortlist_csv": shortlist_csv_path,
            "summary_md": summary_md_path,
        },
    )
    print(summary_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
