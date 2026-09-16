from __future__ import annotations

import argparse
from pathlib import Path

from x_kol_discovery.io_utils import read_csv, read_json, write_csv, write_json
from x_kol_discovery.layer1.dedupe import dedupe_raw_rows
from x_kol_discovery.layer1.normalize import aggregate_to_layer1_candidates, raw_search_rows_to_records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize batch1 L1/L2 files from existing MVP artifacts.")
    parser.add_argument("--run-date", required=True, help="Date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch1", help="Batch name, e.g. batch1")
    return parser.parse_args()


def _to_int(value) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _best_raw_by_url(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    by_url: dict[str, dict[str, object]] = {}
    for row in rows:
        url = str(row.get("tweet_url") or "").strip()
        if not url:
            continue
        score = _to_int(row.get("views_count")) * 1000 + _to_int(row.get("likes")) + _to_int(row.get("retweets")) * 3 + _to_int(row.get("comments")) * 2
        existing = by_url.get(url)
        if existing is None:
            by_url[url] = row
            by_url[f"{url}::__score"] = {"score": score}
            continue
        existing_score = int(by_url.get(f"{url}::__score", {}).get("score", 0))
        if score > existing_score:
            by_url[url] = row
            by_url[f"{url}::__score"] = {"score": score}
    return {k: v for k, v in by_url.items() if not k.endswith("::__score")}


def main() -> int:
    args = _parse_args()
    out_dir = Path("workbench") / args.run_date
    print(f"📍 Routing to: {out_dir.resolve()}")

    raw_payload = read_json(out_dir / f"x_kol_mvp_raw_candidates_{args.run_date}.json")
    legacy_enriched = read_csv(out_dir / f"x_kol_mvp_normalized_candidates_{args.run_date}.csv")
    search_meta = raw_payload.get("search_meta", [])
    raw_rows = raw_payload.get("rows", [])

    l1_raw = dedupe_raw_rows(raw_rows)
    l1_candidates = aggregate_to_layer1_candidates(l1_raw)
    raw_by_url = _best_raw_by_url(l1_raw)

    l1_by_username = {row["username"]: row for row in l1_candidates}
    l2_enriched: list[dict[str, object]] = []
    for row in legacy_enriched:
        username = str(row.get("username") or "").strip().lower()
        l1 = l1_by_username.get(username, {})
        merged = dict(row)
        merged["max_views"] = _to_int(l1.get("max_views"))
        merged["max_likes"] = _to_int(l1.get("max_likes"))
        merged["max_retweets"] = _to_int(l1.get("max_retweets"))
        merged["max_comments"] = _to_int(l1.get("max_comments"))
        merged["tweet_count"] = _to_int(row.get("tweet_count") or l1.get("tweet_count"))
        merged["matched_queries"] = row.get("matched_queries") or l1.get("matched_queries") or ""
        merged["sample_posts"] = row.get("sample_posts") or l1.get("sample_posts") or ""
        merged["top_tweet_url"] = row.get("top_tweet_url") or l1.get("top_tweet_url") or ""
        top_raw = raw_by_url.get(str(merged["top_tweet_url"]).strip(), {})
        merged["top_tweet_timestamp"] = row.get("top_tweet_timestamp") or l1.get("top_tweet_timestamp") or top_raw.get("timestamp") or ""
        merged["top_tweet_text"] = row.get("top_tweet_text") or l1.get("top_tweet_text") or top_raw.get("text") or ""
        merged["source_tweet_ids"] = row.get("source_tweet_ids") or l1.get("source_tweet_ids") or ""
        l2_enriched.append(merged)

    write_json(
        out_dir / f"x_kol_L1_raw_{args.batch}_{args.run_date}.json",
        {
            "source_file": str(out_dir / f"x_kol_mvp_raw_candidates_{args.run_date}.json"),
            "search_meta": search_meta,
            "rows": l1_raw,
        },
    )
    write_csv(out_dir / f"x_kol_L1_raw_{args.batch}_{args.run_date}.csv", l1_raw)
    write_csv(out_dir / f"x_kol_L1_candidates_{args.batch}_{args.run_date}.csv", l1_candidates)
    write_json(
        out_dir / f"x_kol_L1_runlog_{args.batch}_{args.run_date}.json",
        {
            "source_file": str(out_dir / f"x_kol_mvp_raw_candidates_{args.run_date}.json"),
            "raw_rows": len(l1_raw),
            "candidate_rows": len(l1_candidates),
        },
    )

    write_json(
        out_dir / f"x_kol_L2_raw_{args.batch}_{args.run_date}.json",
        {
            "source_file": str(out_dir / f"x_kol_mvp_normalized_candidates_{args.run_date}.csv"),
            "items": l2_enriched,
        },
    )
    write_csv(out_dir / f"x_kol_L2_enriched_{args.batch}_{args.run_date}.csv", l2_enriched)
    write_csv(
        out_dir / f"x_kol_L2_contact_stub_{args.batch}_{args.run_date}.csv",
        [
            {
                "username": row.get("username", ""),
                "email": "",
                "email_source": "",
                "normalized_followers_text": row.get("followers_count", ""),
                "merged_links": "",
            }
            for row in l2_enriched
        ],
    )
    write_json(
        out_dir / f"x_kol_L2_runlog_{args.batch}_{args.run_date}.json",
        {
            "source_file": str(out_dir / f"x_kol_mvp_normalized_candidates_{args.run_date}.csv"),
            "enriched_rows": len(l2_enriched),
        },
    )
    print(out_dir / f"x_kol_L2_enriched_{args.batch}_{args.run_date}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
