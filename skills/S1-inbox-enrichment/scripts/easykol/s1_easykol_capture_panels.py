from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageOps
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[5]
BROWSER_INTERNAL_DIR = PROJECT_ROOT / ".agent/skills/S1-inbox-enrichment/scripts/browser/internal"
if str(BROWSER_INTERNAL_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_INTERNAL_DIR))

from browser_runtime import get_browser_context  # type: ignore


DEFAULT_VIEWPORT = {"width": 2048, "height": 1100}
DEFAULT_WAIT_MS = 10000
DEFAULT_NAV_TIMEOUT_MS = 45000
DEFAULT_RETRIES = 3

NAME_ALIASES = ["频道/作者名称", "author_name", "channel_name", "creator_name", "Channel Name"]
URL_ALIASES = ["账号链接", "profile_url", "channel_link", "Channel Link", "url"]
PLATFORM_ALIASES = ["平台", "platform", "Platform"]


@dataclass
class CaptureResult:
    row: int
    label: str
    url: str
    platform: str
    status: str
    attempt_count: int
    full_path: str = ""
    panel_path: str = ""
    emailbox_path: str = ""
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture EasyKOL side panel screenshots with per-row retries and cropped email boxes."
    )
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--rows", required=True, help="2-based row numbers, e.g. 2-4 or 2,4,6")
    parser.add_argument("--out-dir", default="", help="Defaults to workbench/{today}/easykol_capture_panels")
    parser.add_argument("--wait-ms", type=int, default=DEFAULT_WAIT_MS)
    parser.add_argument("--nav-timeout-ms", type=int, default=DEFAULT_NAV_TIMEOUT_MS)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--keep-open", action="store_true", help="Leave successful pages open for manual inspection.")
    return parser.parse_args()


def parse_rows(raw: str) -> list[int]:
    values: list[int] = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            values.extend(range(int(start), int(end) + 1))
        else:
            values.append(int(chunk))
    return values


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_")
    return cleaned[:48] or "row"


def resolve_output_dir(raw: str) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    date_dir = PROJECT_ROOT / "workbench" / pd.Timestamp.now().strftime("%Y-%m-%d")
    return date_dir / "easykol_capture_panels"


def find_first_column(columns: list[str], aliases: list[str]) -> str | None:
    for alias in aliases:
        if alias in columns:
            return alias
    normalized = {"".join(col.lower().split()): col for col in columns}
    for alias in aliases:
        key = "".join(alias.lower().split())
        if key in normalized:
            return normalized[key]
    return None


def load_rows(csv_path: Path, row_numbers: list[int]) -> list[dict[str, str]]:
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    columns = list(df.columns)
    name_col = find_first_column(columns, NAME_ALIASES)
    url_col = find_first_column(columns, URL_ALIASES)
    platform_col = find_first_column(columns, PLATFORM_ALIASES)
    if not url_col:
        raise RuntimeError(f"CSV 缺少 URL 列，尝试过这些别名: {URL_ALIASES}")

    rows: list[dict[str, str]] = []
    for row_no in row_numbers:
        idx = row_no - 2
        if idx < 0 or idx >= len(df):
            rows.append({"row": str(row_no), "status": "skip", "error": "row_out_of_range"})
            continue
        row = df.iloc[idx]
        rows.append(
            {
                "row": str(row_no),
                "label": str(row.get(name_col, "")).strip() if name_col else "",
                "url": str(row.get(url_col, "")).strip(),
                "platform": str(row.get(platform_col, "")).strip().lower() if platform_col else "",
            }
        )
    return rows


def _clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))
    return left, top, right, bottom


def crop_regions(
    img: Image.Image,
    platform: str,
    panel_rect: tuple[int, int, int, int] | None = None,
) -> tuple[Image.Image, Image.Image]:
    width, height = img.size
    platform = (platform or "").strip().lower()
    if panel_rect:
        panel = img.crop(_clamp_box(panel_rect, width, height))
    elif platform == "tiktok":
        panel = img.crop((int(width * 0.68), int(height * 0.02), width, int(height * 0.96)))
        pw, ph = panel.size
        email_box = panel.crop((int(pw * 0.06), int(ph * 0.08), int(pw * 0.88), int(ph * 0.42)))
        return panel, email_box
    elif platform == "instagram":
        panel = img.crop((int(width * 0.69), int(height * 0.04), width, int(height * 0.92)))
        pw, ph = panel.size
        email_box = panel.crop((int(pw * 0.06), int(ph * 0.10), int(pw * 0.88), int(ph * 0.38)))
        return panel, email_box
    elif platform == "youtube":
        panel = img.crop((int(width * 0.67), int(height * 0.02), width, int(height * 0.92)))
        pw, ph = panel.size
        email_box = panel.crop((int(pw * 0.05), int(ph * 0.10), int(pw * 0.88), int(ph * 0.36)))
        return panel, email_box
    else:
        panel = img.crop((int(width * 0.67), int(height * 0.02), width, int(height * 0.92)))
    pw, ph = panel.size
    email_box = panel.crop((int(pw * 0.05), int(ph * 0.10), int(pw * 0.88), int(ph * 0.36)))
    return panel, email_box


async def detect_easykol_panel_rect(page, platform: str) -> tuple[int, int, int, int] | None:
    platform = (platform or "").strip().lower()
    if platform != "youtube":
        return None

    rect = await page.evaluate(
        """() => {
            const textRe = /(邮箱|email|预估报价|最近10条|自动)/i;
            const all = Array.from(document.querySelectorAll("body *"));
            const candidates = [];
            for (const el of all) {
              const text = (el.innerText || "").trim();
              if (!text || text.length > 120) continue;
              if (!textRe.test(text)) continue;
              const r = el.getBoundingClientRect();
              if (r.width < 40 || r.height < 16) continue;
              if (r.right < window.innerWidth * 0.52) continue;
              if (r.bottom < 0 || r.top > window.innerHeight) continue;
              candidates.push({left: r.left, top: r.top, right: r.right, bottom: r.bottom});
            }
            if (!candidates.length) return null;
            const bounds = candidates.reduce((acc, r) => ({
              left: Math.min(acc.left, r.left),
              top: Math.min(acc.top, r.top),
              right: Math.max(acc.right, r.right),
              bottom: Math.max(acc.bottom, r.bottom),
            }), {left: candidates[0].left, top: candidates[0].top, right: candidates[0].right, bottom: candidates[0].bottom});
            const marginX = 28;
            const marginTop = 40;
            const marginBottom = 120;
            return {
              left: Math.max(0, Math.floor(bounds.left - marginX)),
              top: Math.max(0, Math.floor(bounds.top - marginTop)),
              right: Math.min(window.innerWidth, Math.ceil(bounds.right + marginX)),
              bottom: Math.min(window.innerHeight, Math.ceil(bounds.bottom + marginBottom)),
            };
        }"""
    )
    if not rect:
        return None
    return rect["left"], rect["top"], rect["right"], rect["bottom"]


async def center_easykol_panel(page, platform: str) -> tuple[int, int, int, int] | None:
    rect = await detect_easykol_panel_rect(page, platform)
    if not rect:
        return None
    left, top, right, bottom = rect
    height = bottom - top
    await page.evaluate(
        """({top, height}) => {
            const targetTop = Math.max(0, window.scrollY + top - Math.max(80, (window.innerHeight - height) / 2));
            window.scrollTo({top: targetTop, behavior: "instant"});
        }""",
        {"top": top, "height": height},
    )
    await page.wait_for_timeout(900)
    return await detect_easykol_panel_rect(page, platform)


def build_contact_sheet(paths: list[tuple[int, str, Path]], output_path: Path) -> None:
    if not paths:
        return
    thumbs: list[tuple[str, Image.Image]] = []
    for row_no, label, path in paths:
        img = Image.open(path).convert("RGB")
        thumbs.append((f"{row_no} {label}", img))

    cell_w = max(img.width for _, img in thumbs)
    cell_h = max(img.height for _, img in thumbs)
    title_h = 30
    cols = 2
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + title_h)), "white")
    draw = ImageDraw.Draw(sheet)

    for idx, (title, img) in enumerate(thumbs):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = row * (cell_h + title_h)
        sheet.paste(ImageOps.contain(img, (cell_w, cell_h)), (x, y + title_h))
        draw.text((x + 8, y + 7), title, fill="black")

    sheet.save(output_path)


async def prepare_page(page, url: str, wait_ms: int, nav_timeout_ms: int) -> None:
    await page.set_viewport_size(DEFAULT_VIEWPORT)
    await page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)
    await page.wait_for_load_state("domcontentloaded")
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeoutError:
        # YouTube often keeps background requests alive; treat this as best effort.
        pass
    await page.evaluate(
        """() => {
            document.body.style.zoom = '100%';
            document.documentElement.style.zoom = '100%';
            window.scrollTo(0, 0);
        }"""
    )
    for _ in range(2):
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(250)
    # YouTube sometimes keeps the left drawer expanded in a shared browser session.
    # A top-left click often restores the compact layout without disturbing the EasyKOL panel.
    await page.mouse.click(36, 28)
    await page.wait_for_timeout(400)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(250)
    await page.mouse.click(40, 40)
    await page.wait_for_timeout(250)
    await page.wait_for_timeout(wait_ms)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(800)


async def capture_one(
    *,
    context,
    row_no: int,
    label: str,
    url: str,
    platform: str,
    out_dir: Path,
    wait_ms: int,
    nav_timeout_ms: int,
    retries: int,
    keep_open: bool,
) -> CaptureResult:
    slug = slugify(label or url)
    last_error = ""
    for attempt in range(1, retries + 1):
        page = await context.new_page()
        try:
            print(f"[capture] row={row_no} attempt={attempt} open={url}", flush=True)
            await prepare_page(page, url, wait_ms, nav_timeout_ms)
            panel_rect = await center_easykol_panel(page, platform)
            title = await page.title()
            print(f"[capture] row={row_no} attempt={attempt} title={title}", flush=True)

            full_path = out_dir / f"row{row_no}_{slug}_a{attempt}_full.png"
            panel_path = out_dir / f"row{row_no}_{slug}_a{attempt}_panel.png"
            emailbox_path = out_dir / f"row{row_no}_{slug}_a{attempt}_emailbox.png"

            await page.screenshot(path=str(full_path), full_page=False, animations="disabled")
            img = Image.open(full_path).convert("RGB")
            panel, email_box = crop_regions(img, platform, panel_rect=panel_rect)
            panel.save(panel_path)
            email_box.save(emailbox_path)

            if not keep_open:
                await page.close()
            return CaptureResult(
                row=row_no,
                label=label,
                url=url,
                platform=platform,
                status="ok",
                attempt_count=attempt,
                full_path=str(full_path),
                panel_path=str(panel_path),
                emailbox_path=str(emailbox_path),
            )
        except (PlaywrightTimeoutError, PlaywrightError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            print(f"[capture] row={row_no} attempt={attempt} error={last_error}", flush=True)
            try:
                await page.close()
            except Exception:
                pass
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            print(f"[capture] row={row_no} attempt={attempt} error={last_error}", flush=True)
            try:
                await page.close()
            except Exception:
                pass

    return CaptureResult(
        row=row_no,
        label=label,
        url=url,
        platform=platform,
        status="error",
        attempt_count=retries,
        error=last_error,
    )


async def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    out_dir = resolve_output_dir(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    row_numbers = parse_rows(args.rows)
    input_rows = load_rows(csv_path, row_numbers)

    playwright = browser = context = None
    results: list[CaptureResult] = []
    emailbox_paths: list[tuple[int, str, Path]] = []
    try:
        playwright, browser, context = await get_browser_context()
        for item in input_rows:
            row_no = int(item["row"])
            if item.get("status") == "skip":
                results.append(
                    CaptureResult(
                        row=row_no,
                        label="",
                        url="",
                        platform="",
                        status="skip",
                        attempt_count=0,
                        error=item.get("error", "skip"),
                    )
                )
                continue
            url = item["url"]
            label = item["label"] or slugify(url)
            platform = item["platform"]
            if not url:
                results.append(
                    CaptureResult(
                        row=row_no,
                        label=label,
                        url="",
                        platform=platform,
                        status="skip",
                        attempt_count=0,
                        error="missing_url",
                    )
                )
                continue

            result = await capture_one(
                context=context,
                row_no=row_no,
                label=label,
                url=url,
                platform=platform,
                out_dir=out_dir,
                wait_ms=args.wait_ms,
                nav_timeout_ms=args.nav_timeout_ms,
                retries=args.retries,
                keep_open=args.keep_open,
            )
            results.append(result)
            if result.status == "ok":
                emailbox_paths.append((row_no, slugify(label), Path(result.emailbox_path)))
                print(f"{row_no}\t{label}\t{url}\t{result.emailbox_path}")
            else:
                print(f"{row_no}\t{label}\t{url}\tERROR\t{result.error}")
    finally:
        if playwright:
            await playwright.stop()

    if emailbox_paths:
        build_contact_sheet(emailbox_paths, out_dir / f"rows_{row_numbers[0]}_{row_numbers[-1]}_emailbox_sheet.png")

    report = {
        "csv_path": str(csv_path),
        "out_dir": str(out_dir),
        "rows": row_numbers,
        "wait_ms": args.wait_ms,
        "nav_timeout_ms": args.nav_timeout_ms,
        "retries": args.retries,
        "keep_open": args.keep_open,
        "results": [asdict(result) for result in results],
    }
    report_path = out_dir / "easykol_capture_panels_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
