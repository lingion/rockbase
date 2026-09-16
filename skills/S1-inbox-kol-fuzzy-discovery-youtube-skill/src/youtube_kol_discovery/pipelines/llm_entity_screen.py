from __future__ import annotations

import json
from typing import Any

from openai import APIError
from openai import OpenAI

from youtube_kol_discovery.io_utils import get_env_value, safe_text


ALLOWED_ENTITY_TYPES = {
    "person_led_creator",
    "personal_brand_with_org_signals",
    "org_or_media",
    "ambiguous",
}

ALLOWED_DECISIONS = {"keep", "drop"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def _provider_candidates() -> list[tuple[tuple[str, ...], str, str]]:
    ordered = [
        (("OMLX_API_KEY",), "http://127.0.0.1:8000/v1", "gemma-4-e4b-it-4bit"),
    ]
    return ordered


def _client_candidates() -> list[tuple[str, OpenAI, str]]:
    model_override = get_env_value("YOUTUBE_L3_LLM_MODEL", "OPENAI_MODEL", "LLM_MODEL")
    candidates: list[tuple[str, OpenAI, str]] = []
    for key_names, base_url, default_model in _provider_candidates():
        api_key = get_env_value(*key_names) or "1234"
        chosen_model = model_override or default_model
        provider_name = key_names[0]
        candidates.append((provider_name, OpenAI(api_key=api_key, base_url=base_url), chosen_model))
    return candidates


def _build_payload(row: dict[str, str]) -> dict[str, str]:
    return {
        "账号ID": safe_text(row.get("creator_handle") or row.get("账号ID")),
        "频道/作者名称": safe_text(row.get("display_name") or row.get("频道/作者名称")),
        "平台": safe_text(row.get("platform") or row.get("平台") or "YouTube"),
        "账号链接": safe_text(row.get("profile_url") or row.get("账号链接")),
        "粉丝数": safe_text(row.get("followers_count") or row.get("粉丝数")),
        "账号简介": safe_text(row.get("bio") or row.get("账号简介__平台抓取") or row.get("账号简介")),
        "外链": safe_text(row.get("external_links") or row.get("外链__平台抓取")),
        "contact_signals": safe_text(row.get("contact_signals")),
        "recommended_action": safe_text(row.get("recommended_action")),
        "account_risk_flags": safe_text(row.get("account_risk_flags")),
        "sample_contents": safe_text(row.get("sample_contents")),
        "top_content_url": safe_text(row.get("top_content_url")),
        "decision_reason_hint": safe_text(row.get("decision_reason")),
    }


def _parse_response(content: str) -> dict[str, Any]:
    text = safe_text(content)
    if not text:
        raise RuntimeError("LLM entity screen returned empty content.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def screen_entity(row: dict[str, str]) -> dict[str, str]:
    payload = _build_payload(row)
    last_error: Exception | None = None
    for provider_name, client, model in _client_candidates():
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=240,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strict YouTube creator entity screener for an agency outreach pipeline. "
                            "Decide whether the row is a person-led creator that can stay in the final deliverable, "
                            "or an org/media/brand account that must be dropped. "
                            "Ambiguous cases must be dropped. "
                            "Return only valid JSON with keys: llm_entity_type, llm_decision, llm_confidence, llm_rationale. "
                            "Allowed llm_entity_type values: person_led_creator, personal_brand_with_org_signals, org_or_media, ambiguous. "
                            "Allowed llm_decision values: keep, drop. "
                            "Allowed llm_confidence values: high, medium, low. "
                            "The rationale must be short and concrete. "
                            "Do not include markdown or any extra text."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, indent=2),
                    },
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = _parse_response(content)
            break
        except APIError as exc:
            last_error = exc
            continue
        except Exception as exc:  # pragma: no cover - provider specific fallback
            last_error = exc
            continue
    else:
        raise RuntimeError(f"LLM entity screen failed across all providers: {last_error}") from last_error

    llm_entity_type = safe_text(parsed.get("llm_entity_type")).lower()
    llm_decision = safe_text(parsed.get("llm_decision")).lower()
    llm_confidence = safe_text(parsed.get("llm_confidence")).lower()
    llm_rationale = safe_text(parsed.get("llm_rationale"))

    if llm_entity_type not in ALLOWED_ENTITY_TYPES:
        raise RuntimeError(f"Invalid llm_entity_type from LLM: {llm_entity_type!r}")
    if llm_decision not in ALLOWED_DECISIONS:
        raise RuntimeError(f"Invalid llm_decision from LLM: {llm_decision!r}")
    if llm_confidence not in ALLOWED_CONFIDENCE:
        raise RuntimeError(f"Invalid llm_confidence from LLM: {llm_confidence!r}")
    if not llm_rationale:
        raise RuntimeError("LLM entity screen returned empty rationale.")

    return {
        "llm_entity_type": llm_entity_type,
        "llm_decision": llm_decision,
        "llm_confidence": llm_confidence,
        "llm_rationale": llm_rationale,
        "llm_review_status": "auto_resolved",
        "needs_llm_review": "no",
    }
