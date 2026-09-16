#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIXES = {
    "19e6cda9fa64e168": {
        "latest_price_raw": "\n".join(
            [
                "Instagram Reel (Collaboration): 2.2K USD",
                "Instagram Reel (Non-collaboration): 1.8K USD",
                "Instagram Story: 300 USD",
                "YouTube Shorts: 300 USD",
                "LinkedIn Post: 450 USD",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: Reel (Collaboration) = 2,200 USD",
                "· Instagram: Reel (Non-collaboration) = 1,800 USD",
                "· Instagram: Story = 300 USD",
                "· YouTube: Shorts = 300 USD",
                "· LinkedIn: Post = 450 USD",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19d058b1d062bb24": {
        "latest_price_raw": "€1,300 for 1 video or €2,200 for 2 videos. The price includes cross-posting.",
        "latest_price_normalized": "\n".join(
            [
                "· Instagram/TikTok: 1 cross-posted video = 1,300 EUR",
                "· Instagram/TikTok: 2 cross-posted videos = 2,200 EUR",
            ]
        ),
        "current_price_summary": "Prior structured quote preserved; latest inbound was a follow-up without a new numeric revision.",
        "latest_price_basis": "Fallback to prior structured quote because latest inbound contained no fresh numeric price.",
    },
    "19e6cdb45437a1be": {
        "latest_price_raw": "\n".join(
            [
                "Short Form Video $800",
                "Long Form Video $1,500",
                "3 Short Form Videos $2,100",
                "Long Form Video + Short Form Video $2,000",
                "30-day Spark Ads $300",
                "30 Day usage rights $300",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Unknown Platform: Short Form Video = 800 USD",
                "· Unknown Platform: Long Form Video = 1,500 USD",
                "· Unknown Platform: 3 Short Form Videos = 2,100 USD",
                "· Unknown Platform: Long Form Video + Short Form Video = 2,000 USD",
                "· Add-on / Usage Rights: 30-day Spark Ads = 300 USD",
                "· Add-on / Usage Rights: 30 Day usage rights = 300 USD",
            ]
        ),
        "current_price_summary": "OCR quote recovered with structured pricing.",
        "latest_price_basis": "Structured from Ben Kimball media kit OCR text.",
    },
    "19e6cdb338920668": {
        "latest_price_raw": "\n".join(
            [
                "Instagram Reel: $9,000, organic use only",
                "TikTok: $3,000, organic use only",
                "Instagram Story: $1,000 per frame",
                "30-day whitelisting / paid usage: $3,000 per platform",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: Reel = 9,000 USD [organic use only]",
                "· TikTok: Platform quote = 3,000 USD [organic use only]",
                "· Instagram: Story = 1,000 USD per frame",
                "· Add-on / Usage Rights: 30-day whitelisting / paid usage = 3,000 USD per platform",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19e6cda6bb292977": {
        "latest_price_raw": "\n".join(
            [
                "1x video (15s - 30s) with 3 hook variations (3 assets): $2,000 USD, includes 3 months usage.",
                "1x video (15 - 30s): $1,000 USD with 1 month usage.",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Unknown Platform: 1x video (15s-30s) with 3 hook variations (3 assets) = 2,000 USD [includes 3 months usage]",
                "· Unknown Platform: 1x video (15-30s) = 1,000 USD [includes 1 month usage]",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19e810f87e2c92cb": {
        "latest_price_raw": "\n".join(
            [
                "Dedicated TikTok Video: Starting at $400",
                "TikTok Integration: Starting at $250",
                "UGC Video (non-posted): Starting at $350",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· TikTok: Dedicated Video = 400 USD",
                "· TikTok: Integration = 250 USD",
                "· Unknown Platform: UGC Video (non-posted) = 350 USD",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19e8111477c43193": {
        "latest_price_raw": "\n".join(
            [
                "Instagram(1M Followers) Reel: $10,000",
                "TikTok(686K Followers) Post: $10,000",
                "Package deal for a cross-post on both platforms(1.7 Million Followers) is discounted to: $12,000",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: Reel = 10,000 USD",
                "· TikTok: Post = 10,000 USD",
                "· Bundle Package: Cross-post on Instagram + TikTok = 12,000 USD",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19e8112d0f68ce1a": {
        "latest_price_raw": "\n".join(
            [
                "Instagram (320k followers) Post/Reel: $1800",
                "TikTok Post (180K followers): $2,000",
                "TikTok UGC (USA-based): $800",
                "YouTube Shorts (70K followers): $1800",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: Post/Reel = 1,800 USD",
                "· TikTok: Post = 2,000 USD",
                "· TikTok: UGC (USA-based) = 800 USD",
                "· YouTube: Shorts = 1,800 USD",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from quoted prior inbound price block in latest thread body.",
    },
    "19e8114e969d3b96": {
        "latest_price_raw": "\n".join(
            [
                "1x reel £550",
                "1x story £300",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: 1 Reel = 550 GBP",
                "· Instagram: 1 Story = 300 GBP",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19e81150c65f565e": {
        "latest_price_raw": "\n".join(
            [
                "Dedicated Reel: $200 USD",
                "2 Dedicated Reels: $300 USD",
                "Integration within a Reel: $150 USD",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: Dedicated Reel = 200 USD",
                "· Instagram: 2 Dedicated Reels = 300 USD",
                "· Instagram: Integration within a Reel = 150 USD",
            ]
        ),
        "current_price_summary": "Body quote recovered with structured pricing.",
        "latest_price_basis": "Structured from latest inbound body quote.",
    },
    "19e811517e4203e1": {
        "latest_price_raw": "\n".join(
            [
                "Instagram Reel: 15,000 THB / 475 USD",
                "TikTok / YouTube Short: 10,000 THB / 310 USD",
                "Add On: Gen Code (Discount Code / Mandatory Hashtag): 4,000 THB / 125 USD",
                "Photo Album (6-10 Photos): 2,000 THB / 65 USD",
                "Buyout Assets 1 Month: 5,000 THB / 155 USD",
                "Buyout Assets 3 Months: 10,000 THB / 310 USD",
                "Additional revisions: 1,000 THB / 35 USD per revision",
            ]
        ),
        "latest_price_normalized": "\n".join(
            [
                "· Instagram: Reel = 15,000 THB / 475 USD",
                "· TikTok/YouTube: Short = 10,000 THB / 310 USD",
                "· Add-on: Gen Code (Discount Code / Mandatory Hashtag) = 4,000 THB / 125 USD",
                "· Unknown Platform: Photo Album (6-10 Photos) = 2,000 THB / 65 USD",
                "· Add-on / Usage Rights: Buyout Assets 1 Month = 5,000 THB / 155 USD",
                "· Add-on / Usage Rights: Buyout Assets 3 Months = 10,000 THB / 310 USD",
                "· Add-on: Additional revisions = 1,000 THB / 35 USD per revision",
            ]
        ),
        "current_price_summary": "OCR quote recovered with structured pricing.",
        "latest_price_basis": "Structured from New1sh rate card OCR text.",
    },
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True)
    parser.add_argument("--out-manifest", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.master))
    by_thread = {(row.get("Reply_Thread_ID") or "").strip(): row for row in rows if (row.get("Reply_Thread_ID") or "").strip()}

    fieldnames = [
        "manifest_status",
        "manifest_action",
        "match_basis",
        "Reply_Thread_ID",
        "频道/作者名称",
        "Reply_Contact_Email",
        "latest_price_raw",
        "latest_price_normalized",
        "latest_price_basis",
        "current_price_summary",
        "audit_note",
    ]
    manifest_rows: list[dict[str, str]] = []
    for thread_id, fix in FIXES.items():
        current = by_thread.get(thread_id)
        if not current:
            continue
        manifest_rows.append(
            {
                "manifest_status": "approved",
                "manifest_action": "update",
                "match_basis": "thread_id",
                "Reply_Thread_ID": thread_id,
                "频道/作者名称": current.get("频道/作者名称", ""),
                "Reply_Contact_Email": current.get("Reply_Contact_Email") or current.get("联系方式", ""),
                "latest_price_raw": fix["latest_price_raw"],
                "latest_price_normalized": fix["latest_price_normalized"],
                "latest_price_basis": fix["latest_price_basis"],
                "current_price_summary": fix["current_price_summary"],
                "audit_note": "repair_wf1_price_format_manifest",
            }
        )

    out_path = Path(args.out_manifest)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote manifest rows: {len(manifest_rows)} -> {out_path}")


if __name__ == "__main__":
    main()
