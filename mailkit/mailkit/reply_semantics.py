"""Bounded semantic summarization for inbound replies.

Generates a structured summary plus a bounded preview that the
follow-up worker hands to the Console as an ArtifactEnvelope. The model
may only choose values from allow-lists defined here; any timeout,
schema drift, or unsafe content degrades to a deterministic
manual-review envelope so send paths stay gated.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


_ALLOWED_NEXT_ACTIONS = frozenset({
    "send_brief", "follow_up", "ask_clarification", "respond",
    "archive", "manual_review",
})
_ALLOWED_LANGUAGES = frozenset({"en", "zh-CN"})
_MAX_PREVIEW = 160
_MAX_CONDITIONS = 5
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_URL_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class ReplySummary:
    summary: str
    conditions: tuple[str, ...] = ()
    next_action: str = "manual_review"
    language: str = "en"
    confidence: float = 0.0
    manual_review: bool = True
    redacted: tuple[str, ...] = ()

    def to_artifact(self) -> dict[str, Any]:
        data = asdict(self)
        data["conditions"] = list(self.conditions)
        # The redacted list describes *which* tokens were scrubbed but never
        # includes the raw PII — only a count, so audit logs can confirm
        # redaction ran without echoing addresses/phones/URLs.
        redacted_count = len(self.redacted)
        data.pop("redacted", None)
        return {
            "stage": "s3.summary",
            "payload": data,
            "validation": {
                "ok": not self.manual_review,
                "errors": [] if not self.manual_review else ["manual_review"],
                "warnings": [f"redacted:{redacted_count}"] if redacted_count else [],
            },
        }


def _preview(text: str) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:_MAX_PREVIEW].rstrip()


def _redact(text: str) -> tuple[str, tuple[str, ...]]:
    matches: list[str] = []
    for pattern in (_EMAIL_RE, _PHONE_RE, _URL_RE):
        for match in pattern.findall(text):
            matches.append(match)
    redacted = text
    for hit in matches:
        redacted = redacted.replace(hit, "[REDACTED]")
    return redacted, tuple(dict.fromkeys(matches))


def _clean_conditions(values: Iterable[Any]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.split())[:120]
        if text and text not in seen:
            seen.append(text)
        if len(seen) >= _MAX_CONDITIONS:
            break
    return tuple(seen)


def _bounded(value: Any, max_chars: int) -> Any:
    if isinstance(value, str):
        return value[:max_chars]
    return value


def summarize_reply(text: str, *, client: Any = None, model: str = "gpt-4o-mini") -> ReplySummary:
    """Produce a bounded semantic summary; never invoke the network without client."""
    preview = _preview(text)
    redacted_preview, redacted = _redact(preview)
    if client is None or not (text or "").strip():
        return ReplySummary(summary=redacted_preview, conditions=(),
                            next_action="manual_review", language="en",
                            confidence=0.0, manual_review=True, redacted=redacted)
    try:
        prompt = (
            "Extract a short summary, conditions, next action, language, and "
            "confidence from the reply. Respond as JSON with keys: summary, "
            "conditions, next_action, language, confidence.\n\n"
            f"<reply>\n{preview}\n</reply>"
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system",
                 "content": "Always return JSON with summary, conditions, next_action, language, confidence."},
                {"role": "user", "content": prompt},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model returned no JSON object")
        data = json.loads(content[start:end + 1])
    except (TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return ReplySummary(summary=redacted_preview, conditions=(),
                            next_action="manual_review", language="en",
                            confidence=0.0, manual_review=True, redacted=redacted)
    summary_text = _bounded(str(data.get("summary", "")).strip(), _MAX_PREVIEW)
    summary_clean, more_redactions = _redact(summary_text)
    next_action = str(data.get("next_action", "")).strip()
    if next_action not in _ALLOWED_NEXT_ACTIONS:
        next_action = "manual_review"
        manual_review = True
    else:
        manual_review = next_action == "manual_review"
    language = str(data.get("language", "en")).strip() or "en"
    if language not in _ALLOWED_LANGUAGES:
        language = "en"
    confidence = float(data.get("confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    return ReplySummary(
        summary=summary_clean, conditions=_clean_conditions(data.get("conditions") or []),
        next_action=next_action, language=language, confidence=confidence,
        manual_review=manual_review, redacted=redacted + more_redactions,
    )
