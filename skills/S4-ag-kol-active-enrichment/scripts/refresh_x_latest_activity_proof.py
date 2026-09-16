from __future__ import annotations

import asyncio
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

ROOT = Path("${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency")
CSV_PATH = ROOT / "Agency/list-master/【S2 Cold】Master-X-AI-EN-Batch1.csv"
OMNI_ROOT = Path("${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-omni-chrome")
sys.path.insert(0, str(OMNI_ROOT / "scripts"))

from omni_logic import get_omni_page  # type: ignore  # noqa: E402

BATCH_SIZE = 5
TARGET_PARTITION = "P1"
CUTOFF_DATE = "2026-01-01"


@dataclass
class ActivityResult:
    handle: str
    proof: str = ""
    note_append: str = ""
    raw_kind: str = ""
    raw_date: str = ""
    error: str = ""


def normalize_handle(value: str) -> str:
    return str(value or "").strip().lower()


def merge_note(existing: str, token: str) -> str:
    existing = str(existing or "").strip()
    if not token:
        return existing
    parts = [x.strip() for x in existing.split("|") if x.strip()]
    if token not in parts:
        parts.append(token)
    return " | ".join(parts)


def remove_note(existing: str, token: str) -> str:
    parts = [x.strip() for x in str(existing or "").split("|") if x.strip()]
    parts = [part for part in parts if part != token]
    return " | ".join(parts)


def extract_date(proof: str) -> str:
    m = re.search(r"【(\d{4}-\d{2}-\d{2})】", str(proof or ""))
    return m.group(1) if m else ""


def select_targets(rows: list[dict]) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for row in rows:
        if str(row.get("分区", "")).strip() != TARGET_PARTITION:
            continue
        current_date = extract_date(row.get("Latest Activity Proof", "") or "")
        if not current_date or current_date >= CUTOFF_DATE:
            continue
        handle = row.get("账号ID", "") or ""
        if not str(handle).strip():
            continue
        url = row.get("账号链接") or f"https://x.com/{str(handle).lstrip('@')}"
        targets.append((str(handle), str(url)))
        if len(targets) >= BATCH_SIZE:
            break
    return targets


async def extract_articles(page) -> list[dict]:
    await page.wait_for_timeout(2500)
    primary = page.locator("[data-testid='primaryColumn']")
    articles = primary.locator("article") if await primary.count() else page.locator("article")
    count = min(await articles.count(), 8)
    items = []
    for i in range(count):
        article = articles.nth(i)
        try:
            text = await article.inner_text(timeout=4000)
        except PlaywrightTimeoutError:
            continue
        time_locator = article.locator("time").first
        dt = ""
        if await time_locator.count():
            try:
                dt = await time_locator.get_attribute("datetime") or ""
            except PlaywrightTimeoutError:
                dt = ""
        items.append({"index": i, "text": text, "datetime": dt})
    return items


async def goto_with_retry(page, url: str, attempts: int = 2) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3500)
            return
        except Exception as exc:
            last_exc = exc
            if attempt == attempts:
                break
            await page.wait_for_timeout(2500)
    assert last_exc is not None
    raise last_exc


def classify_kind(text: str) -> str:
    lowered = text.lower()
    if "replying to" in lowered:
        return "Replied"
    if " reposted" in lowered or lowered.startswith("reposted"):
        return "Reposted"
    return "Posted"


def summarize_text(text: str, limit: int = 110) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"^pinned\s+", "", text, flags=re.I).strip()
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return text


def pick_latest_activity(items: list[dict], handle: str) -> ActivityResult | None:
    candidates: list[tuple[int, str, str, str]] = []
    expected_handle = handle.strip().lower()
    for item in items:
        text = item.get("text", "") or ""
        dt = item.get("datetime", "") or ""
        if not text or not dt:
            continue
        top_lines = [line.strip().lower() for line in text.splitlines()[:4] if line.strip()]
        if any(line == "pinned" or "置顶" in line for line in top_lines):
            continue
        if expected_handle and expected_handle not in text.lower():
            continue
        kind = classify_kind(text)
        candidates.append((item.get("index", 999), dt, kind, summarize_text(text)))
    if not candidates:
        return None
    _, dt, kind, summary = sorted(candidates, key=lambda x: x[0])[0]
    day = dt[:10]
    proof = f"【{day}】{kind}: {summary}"
    note_append = "活跃度低" if int(day[:4]) <= 2025 else ""
    return ActivityResult(handle="", proof=proof, note_append=note_append, raw_kind=kind, raw_date=day)


async def fetch_latest_activity(page, url: str, handle: str) -> ActivityResult:
    try:
        await goto_with_retry(page, url)
    except Exception as exc:
        return ActivityResult(handle=handle, error=f"goto failed: {exc}")

    items = await extract_articles(page)
    result = pick_latest_activity(items, handle)
    if result:
        result.handle = handle
        return result

    await page.mouse.wheel(0, 1800)
    await page.wait_for_timeout(2500)
    items = await extract_articles(page)
    result = pick_latest_activity(items, handle)
    if result:
        result.handle = handle
        return result

    return ActivityResult(handle=handle, error="No non-pinned visible activity found")


async def main() -> None:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    lookup = {normalize_handle(r.get("账号ID", "")): r for r in rows}
    targets = select_targets(rows)
    if not targets:
        print({"changed": 0, "results": [], "message": "No eligible P1 rows before cutoff found"})
        return

    results: list[ActivityResult] = []
    async with async_playwright() as p:
        _, context, page = await get_omni_page(p)
        for handle, url in targets:
            result = await fetch_latest_activity(page, url, handle)
            results.append(result)
        await context.close()

    changed = 0
    for result in results:
        row = lookup.get(normalize_handle(result.handle))
        if not row:
            continue
        if result.proof:
            current_proof = row.get("Latest Activity Proof", "") or ""
            current_date = extract_date(current_proof)
            browser_date = extract_date(result.proof)
            chosen_proof = current_proof
            if browser_date and (not current_date or browser_date > current_date):
                chosen_proof = result.proof
            row["Latest Activity Proof"] = chosen_proof
            row["备注"] = remove_note(row.get("备注", ""), "latest-proof-check-failed")
            final_date = extract_date(chosen_proof)
            if final_date and int(final_date[:4]) <= 2025:
                row["备注"] = merge_note(row.get("备注", ""), "活跃度低")
            elif final_date and int(final_date[:4]) >= 2026:
                row["备注"] = remove_note(row.get("备注", ""), "活跃度低")
            changed += 1
        elif result.error:
            if not (row.get("Latest Activity Proof", "") or "").strip():
                row["备注"] = merge_note(row.get("备注", ""), "latest-proof-check-failed")

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print({"changed": changed, "results": [result.__dict__ for result in results]})


if __name__ == "__main__":
    asyncio.run(main())
