DEFAULT_SESSION_BY_PLATFORM = {
    "youtube": "yt-email-test",
    "tiktok": "tt-email-test",
    "instagram": "ins-email-test",
}


def normalize_platform(value: str) -> str:
    return str(value or "").strip().lower()


def parse_rows_spec(raw: str) -> list[int]:
    rows = []
    for chunk in str(raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            rows.extend(range(int(start), int(end) + 1))
        else:
            rows.append(int(chunk))
    return sorted(set(rows))


def finalize_note(status: str, current: str) -> str:
    if status == "hit":
        return "EasyKOL获取"
    if status == "no_email":
        return "EasyKOL无法获取"
    return current or "EasyKOL结果待人工复核"


def get_extractor_js(platform: str) -> str:
    if platform == "youtube":
        from .youtube_easykol import PROBE_JS
        return PROBE_JS
    if platform == "tiktok":
        from .tiktok_easykol import PROBE_JS
        return PROBE_JS
    if platform == "instagram":
        from .instagram_easykol import PROBE_JS
        return PROBE_JS
    raise ValueError(f"unsupported platform: {platform}")
