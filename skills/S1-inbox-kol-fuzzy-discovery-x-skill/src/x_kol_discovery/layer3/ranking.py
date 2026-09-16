from __future__ import annotations

import re
from typing import Any

from x_kol_discovery.io_utils import safe_text


COUNTRY_HINTS = {
    "us": [
        "usa",
        "united states",
        "new york",
        "san francisco",
        "california",
        "texas",
        "seattle",
        "austin",
        "brooklyn",
        "baltimore",
        "solana beach",
    ],
    "gb": ["uk", "united kingdom", "london", "england", "manchester"],
    "ca": ["canada", "toronto", "vancouver", "montreal"],
    "au": ["australia", "sydney", "melbourne", "brisbane"],
    "in": ["india", "bangalore", "bang-lore", "bengaluru", "mumbai", "delhi", "noida", "pilani"],
    "sg": ["singapore"],
    "mx": ["mexico", "mexico city"],
    "eg": ["egypt", "cairo"],
    "pk": ["pakistan"],
    "cn": ["china"],
}


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def infer_primary_language(sample_posts: str, bio: str = "") -> tuple[str, str]:
    text = f"{safe_text(sample_posts)} {safe_text(bio)}".strip()
    if not text:
        return "", ""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh", "cjk_chars"
    alpha_chars = sum(ch.isalpha() for ch in text)
    ascii_chars = sum(ord(ch) < 128 and ch.isalpha() for ch in text)
    if alpha_chars and ascii_chars / max(alpha_chars, 1) >= 0.85:
        return "en", "ascii_alpha_majority"
    return "", ""


def infer_country(location_raw: str, bio: str = "") -> tuple[str, str]:
    text = f"{safe_text(location_raw)} {safe_text(bio)}".lower()
    if not text:
        return "", ""
    raw_text = f"{safe_text(location_raw)} {safe_text(bio)}"
    flag_hints = {
        "🇺🇸": "US",
        "🇬🇧": "GB",
        "🇨🇦": "CA",
        "🇦🇺": "AU",
        "🇮🇳": "IN",
        "🇸🇬": "SG",
        "🇲🇽": "MX",
        "🇪🇬": "EG",
        "🇵🇰": "PK",
        "🇨🇳": "CN",
    }
    for flag, code in flag_hints.items():
        if flag in raw_text:
            return code, flag
    for code, hints in COUNTRY_HINTS.items():
        for hint in hints:
            if hint in text:
                return code.upper(), hint
    return "", ""


def build_matched_signals(row: dict[str, Any]) -> str:
    parts: list[str] = []
    if safe_text(row.get("matched_queries")):
        parts.append(f"queries={safe_text(row.get('matched_queries'))}")
    if safe_text(row.get("top_tweet_url")):
        parts.append(f"proof={safe_text(row.get('top_tweet_url'))}")
    if _to_int(row.get("max_views")) > 0:
        parts.append(f"max_views={_to_int(row.get('max_views'))}")
    if _to_int(row.get("followers_count")) > 0:
        parts.append(f"followers={_to_int(row.get('followers_count'))}")
    return " | ".join(parts)


def build_decision_reason(row: dict[str, Any]) -> str:
    action = safe_text(row.get("recommended_action"))
    followers = _to_int(row.get("followers_count"))
    max_views = _to_int(row.get("max_views"))
    lang = safe_text(row.get("primary_language"))
    snippets = [f"action={action}" if action else ""]
    if followers:
        snippets.append(f"followers={followers}")
    if max_views:
        snippets.append(f"max_views={max_views}")
    if lang:
        snippets.append(f"lang={lang}")
    return " | ".join(part for part in snippets if part)


def apply_layer3_followers_gate(
    rows: list[dict[str, Any]],
    min_followers: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        if _to_int(row.get("followers_count")) >= min_followers:
            eligible.append(dict(row))
        else:
            skipped.append(dict(row))
    return eligible, skipped


def rank_enriched_candidates(rows: list[dict[str, Any]], shortlist_target: int = 100) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        primary_language, language_signal = infer_primary_language(
            safe_text(row.get("sample_posts")),
            safe_text(row.get("bio")),
        )
        country_inferred, country_signal = infer_country(
            safe_text(row.get("location_raw")),
            safe_text(row.get("bio")),
        )
        enriched["primary_language"] = primary_language
        enriched["language_mix"] = ""
        enriched["country_inferred"] = country_inferred
        enriched["country_confidence"] = "medium" if country_inferred else ""
        enriched["matched_signals"] = build_matched_signals(enriched)
        enriched["decision_reason"] = build_decision_reason(
            {
                **enriched,
                "primary_language": primary_language,
            }
        )
        enriched["language_signal"] = language_signal
        enriched["country_signal"] = country_signal
        ranked.append(enriched)

    ranked.sort(
        key=lambda row: (
            -_to_int(row.get("followers_count")),
            -float(row.get("overall_score") or 0),
            -_to_int(row.get("activity_score")),
            safe_text(row.get("username")),
        )
    )
    shortlist = [row for row in ranked if str(row.get("recommended_action") or "") in {"keep", "review"}][:shortlist_target]
    return ranked, shortlist
