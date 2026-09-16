from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from tiktok_kol_discovery.io_utils import get_env_value


BASE_URL = "https://api.scrapecreators.com"


@dataclass(slots=True)
class ScrapeCreatorsResult:
    items: list[dict[str, Any]]
    blockers: list[str]
    request_meta: dict[str, Any]


class TikTokScrapeCreatorsClient:
    def __init__(self, *, timeout_seconds: float = 25.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.api_key = get_env_value("SCRAPECREATORS_API_KEY")

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key}

    def _request(self, endpoint: str, *, params: dict[str, Any]) -> ScrapeCreatorsResult:
        if not self.api_key:
            return ScrapeCreatorsResult(
                items=[],
                blockers=["Missing SCRAPECREATORS_API_KEY."],
                request_meta={"endpoint": endpoint, "params": params},
            )

        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=self._headers(),
                params=params,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            return ScrapeCreatorsResult(
                items=[],
                blockers=[f"ScrapeCreators request failed: {type(exc).__name__}: {exc}"],
                request_meta={"endpoint": endpoint, "params": params},
            )

        if response.status_code != 200:
            return ScrapeCreatorsResult(
                items=[],
                blockers=[f"ScrapeCreators returned HTTP {response.status_code}: {response.text[:300]}"],
                request_meta={"endpoint": endpoint, "params": params},
            )

        payload = response.json()
        return ScrapeCreatorsResult(
            items=self._extract_items(payload),
            blockers=[],
            request_meta={
                "endpoint": endpoint,
                "params": params,
                "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
            },
        )

    def search_keyword(
        self,
        *,
        query: str,
        region: str = "US",
        sort_by: str = "most_likes",
        date_posted: int = 30,
    ) -> ScrapeCreatorsResult:
        return self._request(
            "/v1/tiktok/search/keyword",
            params={"query": query, "region": region, "sort_by": sort_by, "date_posted": date_posted},
        )

    def search_hashtag(
        self,
        *,
        query: str,
        region: str = "US",
        sort_by: str = "most_likes",
    ) -> ScrapeCreatorsResult:
        return self._request(
            "/v1/tiktok/search/hashtag",
            params={"query": query, "region": region, "sort_by": sort_by},
        )

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        candidate_keys = [
            "items",
            "item_list",
            "videos",
            "aweme_list",
            "data",
            "search_item_list",
        ]
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, list):
                extracted = [item for item in value if isinstance(item, dict)]
                if extracted:
                    return extracted

        data = payload.get("data")
        if isinstance(data, dict):
            for key in candidate_keys:
                value = data.get(key)
                if isinstance(value, list):
                    extracted = [item for item in value if isinstance(item, dict)]
                    if extracted:
                        return extracted

        return []
