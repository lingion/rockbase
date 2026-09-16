from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(slots=True)
class TikTokRuntimePlan:
    provider_name: str
    provider_ready: bool
    blockers: list[str]
    notes: list[str]


def inspect_tiktok_runtime(*, has_ms_token: bool, proxy_enabled: bool) -> TikTokRuntimePlan:
    blockers: list[str] = []
    notes: list[str] = []

    package_installed = importlib.util.find_spec("TikTokApi") is not None
    if not package_installed:
        blockers.append("TikTokApi package is not installed in the current environment.")
        notes.append("Install path will need `pip install TikTokApi` and `python3 -m playwright install`.")

    if not has_ms_token:
        blockers.append("Missing TIKTOK_MS_TOKEN in skill-local .env.local.")
        notes.append("TikTok L1 should not begin real search validation until ms_token is provided.")

    if proxy_enabled:
        notes.append("Static proxy is enabled by default for TikTok L1 validation.")
    else:
        notes.append("Proxy is disabled for this run; this is not the default testing posture.")

    provider_ready = package_installed and has_ms_token
    return TikTokRuntimePlan(
        provider_name="TikTokApi",
        provider_ready=provider_ready,
        blockers=blockers,
        notes=notes,
    )
