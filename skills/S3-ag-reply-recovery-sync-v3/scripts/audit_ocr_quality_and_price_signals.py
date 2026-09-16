#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PRICE_RE = re.compile(
    r"(?i)(?:"
    r"(?P<currency1>US?\$|USD|EUR|€|£|GBP)\s*(?P<amount1>\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"|"
    r"(?P<amount2>\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?P<currency2>US?\$|USD|EUR|€|£|GBP|dollars?|euros?|pounds?)"
    r")"
)
PRICE_HINT_WORDS = re.compile(
    r"(?i)\b(rate|rates|pricing|price|package|bundle|dedicated|integration|reel|story|post|video|shorts?|cross[\s-]?post|youtube|instagram|tiktok|ig|yt)\b"
)
ANALYTICS_HINT_WORDS = re.compile(
    r"(?i)\b(views?|followers?|audience|analytics|watch time|profile views|likes?|comments?|shares?|subscribers?|geography|age ranges|male|female)\b"
)
LETTER_RE = re.compile(r"[A-Za-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
NOISE_RE = re.compile(r"[^\w\s$€£.,:%@()+/\-]")
TOKEN_RE = re.compile(r"[A-Za-z]{2,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit OCR quality and extract normalized price candidates.")
    parser.add_argument("--reports-root", required=True, help="Root directory containing attachment_extraction_report.csv files.")
    parser.add_argument("--output-dir", required=True, help="Directory for audit outputs.")
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def normalize_currency(raw: str) -> str:
    token = (raw or "").strip().lower()
    if token in {"$", "us$", "usd", "dollar", "dollars"}:
        return "$"
    if token in {"€", "eur", "euro", "euros"}:
        return "€"
    if token in {"£", "gbp", "pound", "pounds"}:
        return "£"
    return raw.strip()


def parse_amount(raw: str) -> float | None:
    if not raw:
        return None
    value = raw.strip().replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        left, right = value.rsplit(",", 1)
        if len(right) == 3 and left.replace(",", "").isdigit():
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")
    elif "." in value:
        left, right = value.rsplit(".", 1)
        if len(right) == 3 and left.replace(".", "").isdigit():
            value = value.replace(".", "")
    try:
        return float(value)
    except ValueError:
        return None


def format_amount(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def extract_price_candidates(text: str) -> Tuple[List[str], List[str]]:
    raw_hits: List[str] = []
    normalized_hits: List[str] = []
    seen_normalized = set()
    for match in PRICE_RE.finditer(text or ""):
        currency = normalize_currency(match.group("currency1") or match.group("currency2") or "")
        amount_raw = match.group("amount1") or match.group("amount2") or ""
        raw_phrase = match.group(0).strip()
        raw_hits.append(raw_phrase)
        amount = parse_amount(amount_raw)
        if amount is None:
            continue
        normalized = f"{currency}{format_amount(amount)}"
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            normalized_hits.append(normalized)
    return raw_hits, normalized_hits


def assess_quality(text: str) -> Tuple[str, Dict[str, float]]:
    compact = re.sub(r"\s+", "", text or "")
    chars = len(compact)
    letters = len(LETTER_RE.findall(compact))
    noise = len(NOISE_RE.findall(compact))
    words = TOKEN_RE.findall(text or "")
    word_count = len(words)
    letter_ratio = letters / chars if chars else 0.0
    noise_ratio = noise / chars if chars else 0.0

    if chars == 0:
        quality = "empty"
    elif chars < 60 and letter_ratio < 0.45:
        quality = "garbled"
    elif noise_ratio > 0.18 or letter_ratio < 0.50:
        quality = "garbled"
    elif chars < 140 or word_count < 12:
        quality = "weak"
    elif chars >= 250 and letter_ratio >= 0.72 and noise_ratio <= 0.08:
        quality = "good"
    else:
        quality = "usable"

    return quality, {
        "chars": chars,
        "letter_ratio": round(letter_ratio, 4),
        "noise_ratio": round(noise_ratio, 4),
        "word_count": word_count,
    }


def summarize_pricing_signal(text: str, raw_prices: List[str], normalized_prices: List[str]) -> str:
    has_hint_words = bool(PRICE_HINT_WORDS.search(text or ""))
    if normalized_prices:
        return "price_detected"
    if raw_prices or has_hint_words:
        return "pricing_like_noisy"
    return "no_price_signal"


def assess_price_confidence(filename: str, text: str, normalized_prices: List[str]) -> str:
    if not normalized_prices:
        return "none"
    filename_l = (filename or "").lower()
    has_price_words = bool(PRICE_HINT_WORDS.search(text or ""))
    has_analytics_words = bool(ANALYTICS_HINT_WORDS.search(text or ""))
    filename_hint = any(token in filename_l for token in ["rate", "pricing", "price", "media kit", "mediakit", "rate card", "kit"])
    if has_price_words or filename_hint:
        return "high"
    if len(normalized_prices) >= 3 and not has_analytics_words:
        return "medium"
    if has_analytics_words:
        return "low"
    return "medium"


def build_markdown_summary(rows: List[Dict[str, str]], summary: Dict[str, object]) -> str:
    top_price = [r for r in rows if r["pricing_signal"] == "price_detected"][:12]
    top_garbled = [r for r in rows if r["ocr_quality"] == "garbled"][:12]
    lines = [
        "---",
        "tags: [ocr, audit, pricing, v3]",
        "date: 2026-03-27",
        "status: done",
        "---",
        "",
        "# OCR 全量审计摘要",
        "",
        f"- 附件总数: `{summary['attachments_total']}`",
        f"- 可读文本文件: `{summary['text_files_found']}`",
        f"- OCR 质量 good/usable/weak/garbled/empty: `{summary['quality_breakdown']}`",
        f"- 检出价格附件数: `{summary['price_detected_count']}`",
        f"- 其中可信价格附件数: `{summary['price_detected_trusted_count']}`",
        f"- 疑似价格但 OCR 噪音较大: `{summary['pricing_like_noisy_count']}`",
        "",
        "## 价格命中样本",
        "",
    ]
    if not top_price:
        lines.append("- 当前附件里未检出稳定价格文本。")
    else:
        for row in top_price:
            lines.append(
                f"- `{row['filename']}` | `{row['from_email']}` | raw=`{row['price_raw']}` | normalized=`{row['price_normalized']}`"
            )
    lines.extend(["", "## OCR 噪音样本", ""])
    if not top_garbled:
        lines.append("- 当前没有被判定为 `garbled` 的样本。")
    else:
        for row in top_garbled:
            lines.append(
                f"- `{row['filename']}` | quality=`{row['ocr_quality']}` | preview=`{row['text_preview_clean'][:100]}`"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    reports_root = Path(args.reports_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_paths = sorted(reports_root.rglob("attachment_extraction_report.csv"))
    audit_rows: List[Dict[str, str]] = []
    quality_counter: Counter[str] = Counter()
    pricing_counter: Counter[str] = Counter()

    for report_path in report_paths:
        for row in read_csv(report_path):
            text_file = Path(row.get("text_file", ""))
            text = safe_read(text_file)
            quality, metrics = assess_quality(text)
            raw_prices, normalized_prices = extract_price_candidates(text)
            pricing_signal = summarize_pricing_signal(text, raw_prices, normalized_prices)
            price_confidence = assess_price_confidence(row.get("filename", ""), text, normalized_prices)
            quality_counter[quality] += 1
            pricing_counter[pricing_signal] += 1
            audit_rows.append(
                {
                    **row,
                    "text_preview_clean": re.sub(r"\s+", " ", text[:300]).strip(),
                    "ocr_quality": quality,
                    "pricing_signal": pricing_signal,
                    "price_confidence": price_confidence,
                    "price_raw": " | ".join(raw_prices[:12]),
                    "price_normalized": " | ".join(normalized_prices[:12]),
                    "chars": str(metrics["chars"]),
                    "letter_ratio": str(metrics["letter_ratio"]),
                    "noise_ratio": str(metrics["noise_ratio"]),
                    "word_count": str(metrics["word_count"]),
                }
            )

    audit_rows.sort(key=lambda r: (r["pricing_signal"] != "price_detected", r["ocr_quality"], -(int(r["chars"] or "0"))))
    fieldnames = list(audit_rows[0].keys()) if audit_rows else []
    audit_csv = output_dir / "ocr_quality_audit.csv"
    write_csv(audit_csv, audit_rows, fieldnames)

    price_rows = [r for r in audit_rows if r["pricing_signal"] == "price_detected"]
    price_csv = output_dir / "ocr_price_candidates.csv"
    if price_rows:
        write_csv(price_csv, price_rows, list(price_rows[0].keys()))
    else:
        write_csv(price_csv, [], fieldnames)

    trusted_price_rows = [r for r in price_rows if r["price_confidence"] in {"high", "medium"}]
    trusted_price_csv = output_dir / "ocr_price_candidates_trusted.csv"
    if trusted_price_rows:
        write_csv(trusted_price_csv, trusted_price_rows, list(trusted_price_rows[0].keys()))
    else:
        write_csv(trusted_price_csv, [], fieldnames)

    summary = {
        "attachments_total": len(audit_rows),
        "text_files_found": sum(1 for r in audit_rows if r.get("text_file")),
        "quality_breakdown": dict(quality_counter),
        "price_detected_count": pricing_counter.get("price_detected", 0),
        "price_detected_trusted_count": len(trusted_price_rows),
        "pricing_like_noisy_count": pricing_counter.get("pricing_like_noisy", 0),
        "no_price_signal_count": pricing_counter.get("no_price_signal", 0),
    }
    (output_dir / "ocr_quality_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "ocr_quality_summary.md").write_text(build_markdown_summary(audit_rows, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
