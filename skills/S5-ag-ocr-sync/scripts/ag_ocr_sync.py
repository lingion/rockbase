from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import cv2

try:
    # Only required by the `llm` OCR engine; vision/tesseract paths don't import it.
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional extra
    OpenAI = None


LLM_VISION_MODEL_DEFAULT = "gpt-4o-mini"
LLM_BASE_URL_DEFAULT = "https://api.openai.com/v1"

LLM_VISION_PROMPT = """You read social-media profile screenshots and return structured audience data.

Return JSON only, no prose, no markdown, matching exactly this schema:
{
  "handle": "@handle or empty string",
  "author_name": "display name or empty string",
  "email": "email address visible in the screenshot or empty string",
  "countries": "top audience countries as 'Country PCT%' joined by ' / ' (max 4, most first) or empty string",
  "gender": "男<PCT>%/女<PCT>% or empty string",
  "age": "18-25 (PCT%)/25-45 (PCT%) or empty string",
  "confidence": 0.0-1.0 self-assessed extraction confidence
}

Rules:
- Transcribe only what is visible. Never guess or invent values.
- Percentages must keep the % sign. Country names in Chinese when shown in Chinese.
- If a field is not visible, return an empty string."""


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HANDLE_RE = re.compile(r"@([A-Za-z0-9._-]{2,})")
PERCENT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")

COUNTRY_FIXES = {
    "美国": "美国",
    "美圆": "美国",
    "印度": "印度",
    "加拿大": "加拿大",
    "加拿大i": "加拿大",
    "加拿大1i": "加拿大",
    "英国": "英国",
    "英囝": "英国",
    "米爽": "英国",
    "米爽m": "英国",
    "米爽1": "英国",
    "德国": "德国",
    "徳国": "德国",
    "法国": "法国",
    "法園": "法国",
    "荷兰": "荷兰",
    "澳大利亚": "澳大利亚",
    "巴基斯坦": "巴基斯坦",
    "土耳其": "土耳其",
    "孟加拉国": "孟加拉国",
    "孟加拉圛": "孟加拉国",
    "孟加拉團": "孟加拉国",
    "尼日利亚": "尼日利亚",
    "菲律宾": "菲律宾",
    "俄罗斯": "俄罗斯",
    "意大利": "意大利",
    "巴西": "巴西",
    "南非": "南非",
    "爱尔兰": "爱尔兰",
    "西班牙": "西班牙",
    "奥地利": "奥地利",
    "克罗地亚": "克罗地亚",
    "尼泊尔": "尼泊尔",
    "韩国": "韩国",
    "斯里兰卡": "斯里兰卡",
    "塞尔维亚": "塞尔维亚",
    "塞尔綠亚": "塞尔维亚",
    "号美国": "美国",
    "号美国m": "美国",
    "粤美国": "美国",
    "粤美": "美国",
    "米翅": "美国",
    "米鸡": "美国",
    "米爽h": "英国",
    "米英": "英国",
    "米英国": "英国",
    "米英園": "英国",
    "米英日": "英国",
    "美国日": "美国",
    "加挛大": "加拿大",
    "加傘大": "加拿大",
    "加拿大t": "加拿大",
    "非輝": "菲律宾",
    "非英国": "英国",
    "阴尔及利亚": "阿尔及利亚",
    "厄瓜多尔i": "厄瓜多尔",
    "希腊j": "希腊",
    "叉印度": "印度",
    "s印度i": "印度",
    "湘国t": "韩国",
    "德圓": "德国",
    "专美团": "美国",
    "专美国": "美国",
    "美園": "美国",
    "号園": "美国",
    "號美国四": "美国",
    "号美国四": "美国",
    "園T": "美国",
    "英園": "英国",
    "非英": "英国",
    "米爽国": "英国",
    "法国T": "法国",
    "瞾西哥": "墨西哥",
    "每伦比亚": "哥伦比亚",
}

COUNTRY_ALIASES = {
    "美国": ["美国", "united states", "usa", "us"],
    "加拿大": ["加拿大", "canada"],
    "加纳": ["加纳", "ghana"],
    "韩国": ["韩国", "south korea", "korea"],
    "墨西哥": ["墨西哥", "mexico"],
    "德国": ["德国", "germany"],
    "法国": ["法国", "france"],
    "英国": ["英国", "united kingdom", "uk", "england"],
    "比利时": ["比利时", "belgium"],
    "荷兰": ["荷兰", "netherlands"],
    "日本": ["日本", "japan"],
    "越南": ["越南", "vietnam"],
    "葡萄牙": ["葡萄牙", "portugal"],
    "西班牙": ["西班牙", "spain"],
    "印度": ["印度", "india"],
    "澳大利亚": ["澳大利亚", "australia"],
    "巴西": ["巴西", "brazil"],
    "巴基斯坦": ["巴基斯坦", "pakistan"],
    "土耳其": ["土耳其", "turkey"],
    "乌干达": ["乌干达", "uganda"],
    "埃塞俄比亚": ["埃塞俄比亚", "ethiopia"],
    "孟加拉国": ["孟加拉国", "bangladesh"],
    "菲律宾": ["菲律宾", "philippines"],
    "俄罗斯": ["俄罗斯", "russia"],
    "意大利": ["意大利", "italy"],
    "尼日利亚": ["尼日利亚", "nigeria"],
    "南非": ["南非", "south africa"],
    "埃及": ["埃及", "egypt"],
    "印尼": ["印尼", "indonesia"],
    "波兰": ["波兰", "poland"],
    "罗马尼亚": ["罗马尼亚", "romania"],
    "哥伦比亚": ["哥伦比亚", "colombia"],
    "阿根廷": ["阿根廷", "argentina"],
    "新西兰": ["新西兰", "new zealand"],
    "阿联酋": ["阿联酋", "uae", "united arab emirates"],
}

VISION_SWIFT = r"""
import Foundation
import Vision
import AppKit

struct Item: Codable {
    let text: String
    let x: Double
    let y: Double
    let w: Double
    let h: Double
}

struct Payload: Codable {
    let file_name: String
    let image_path: String
    let items: [Item]
}

let dir = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let fm = FileManager.default
let files = try fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)
    .filter { ["png", "jpg", "jpeg", "webp"].contains($0.pathExtension.lowercased()) }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

let encoder = JSONEncoder()
encoder.outputFormatting = [.withoutEscapingSlashes]

for file in files {
    autoreleasepool {
        guard let image = NSImage(contentsOf: file) else { return }
        var rect = CGRect(origin: .zero, size: image.size)
        guard let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else { return }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = false
        let handler = VNImageRequestHandler(cgImage: cg, options: [:])
        try? handler.perform([request])
        let items = (request.results ?? []).compactMap { obs -> Item? in
            guard let top = obs.topCandidates(1).first else { return nil }
            let b = obs.boundingBox
            return Item(text: top.string, x: Double(b.origin.x), y: Double(b.origin.y), w: Double(b.size.width), h: Double(b.size.height))
        }
        let payload = Payload(file_name: file.lastPathComponent, image_path: file.path, items: items)
        let data = try! encoder.encode(payload)
        print(String(data: data, encoding: .utf8)!)
    }
}
"""


@dataclass
class VisionItem:
    text: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class ScreenshotData:
    path: str
    handle: str = ""
    author_name: str = ""
    email: str = ""
    countries: str = ""
    gender: str = ""
    age: str = ""
    raw_hits: dict = field(default_factory=dict)
    matched_row: int | None = None
    match_reason: str = ""
    duplicate: bool = False
    confidence: float = 0.0
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    blocked_fields: list[str] = field(default_factory=list)
    second_pass_fixed: bool = False
    second_pass_notes: list[str] = field(default_factory=list)


@dataclass
class CandidateImage:
    path: Path
    exact_hash: str
    visual_hash: str


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OCR screenshots and sync audience fields back to the master CSV.")
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ocr-engine", choices=["auto", "vision", "tesseract", "llm"], default="auto")
    parser.add_argument("--llm-api-key", default="", help="Vision LLM key; falls back to OPENAI_API_KEY.")
    parser.add_argument("--llm-base-url", default=LLM_BASE_URL_DEFAULT, help="OpenAI-compatible vision endpoint.")
    parser.add_argument("--llm-model", default=LLM_VISION_MODEL_DEFAULT, help="Vision-capable model name.")
    parser.add_argument("--target-id")
    parser.add_argument("--target-name")
    parser.add_argument("--partition-filter")
    parser.add_argument("--only-files", nargs="+", help="Only process these image file paths or basenames.")
    parser.add_argument("--review-threshold", type=float, default=0.75)
    parser.add_argument("--dedupe-images", action="store_true", default=True)
    parser.add_argument("--no-dedupe-images", dest="dedupe_images", action="store_false")
    parser.add_argument("--force-overwrite", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    return _build_argparser().parse_args()


def ensure_backup(csv_path: Path) -> Path:
    root = csv_path.parents[1] / "Agency" / "list-bak" / datetime.now().strftime("%Y-%m-%d")
    root.mkdir(parents=True, exist_ok=True)
    backup_path = root / f"{csv_path.stem}_bak_{datetime.now().strftime('%H%M%S')}{csv_path.suffix}"
    shutil.copy2(csv_path, backup_path)
    return backup_path


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_handle(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    value = value.lstrip("@")
    value = re.sub(r"[^A-Za-z0-9._-]", "", value)
    return f"@{value}" if value else ""


def normalize_name(value: str) -> str:
    value = normalize_text(value).replace("•", "").replace("@", "").strip()
    value = value.replace(" Al ", " AI ").replace(" Al", " AI").replace("Vs.AI", "Vs. AI")
    value = value.replace("D WPTuts", "WPTuts")
    value = re.sub(r"^Al\s+", "AI ", value)
    value = re.sub(r"^[Dd]\s+", "", value)
    value = re.sub(r"^©\s*", "", value)
    value = re.sub(r"\s*&\s*\d+$", "", value).strip()
    value = re.sub(r"^Al(?=[A-Z])", "AI ", value)
    value = re.sub(r"^AI(?=[A-Z])", "AI ", value)
    value = re.sub(r"\(.*?$", "", value).strip()
    value = re.sub(r"\s*[|¦§]+.*$", "", value).strip()
    value = re.sub(r"\s+[0-9.万KMB% ]+$", "", value).strip()
    return value


def canonical_name(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (value or "").lower())


def canonical_handle(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_handle(value).lower())


def normalize_email(value: str) -> str:
    email = (value or "").strip().lower().replace(" ", "")
    fixes = {
        "@gmailcom": "@gmail.com",
        "@gmail,com": "@gmail.com",
        "@gmail.c0m": "@gmail.com",
        "@gmai.com": "@gmail.com",
        "@gmail.con": "@gmail.com",
        "@hotmailcom": "@hotmail.com",
        "@outlookcom": "@outlook.com",
        "@yahoocom": "@yahoo.com",
    }
    for bad, good in fixes.items():
        email = email.replace(bad, good)
    if email.endswith(".c0m"):
        email = email[:-4] + ".com"
    return email


def is_plausible_email(email: str) -> bool:
    if not email:
        return False
    if not EMAIL_RE.fullmatch(email):
        return False
    return email not in {"<YOUR_ACCOUNT_EMAIL>", "gmail.com"}


def format_pct(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}%"
    return f"{value:.1f}%"


def parse_pct(text: str) -> float | None:
    m = PERCENT_RE.search(text or "")
    return float(m.group(1)) if m else None


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def visual_dhash(path: Path) -> str:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return ""
    resized = cv2.resize(image, (9, 8), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = "".join("1" if x else "0" for x in diff.flatten())
    return f"{int(bits, 2):016x}"


def select_images(image_dir: Path, only_files: list[str] | None, dedupe_images: bool) -> tuple[list[Path], list[dict]]:
    candidates = sorted([p for p in image_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
    if only_files:
        raw_targets = [Path(x) for x in only_files]
        resolved = set()
        basenames = {p.name for p in raw_targets}
        for target in raw_targets:
            resolved.add(str(target.resolve()))
        filtered = []
        for path in candidates:
            if str(path.resolve()) in resolved or path.name in basenames:
                filtered.append(path)
        candidates = filtered

    if not dedupe_images:
        return candidates, []

    selected: list[Path] = []
    duplicates: list[dict] = []
    exact_seen: dict[str, Path] = {}
    visual_seen: dict[str, Path] = {}
    for path in candidates:
        exact_hash = file_sha1(path)
        visual_hash = visual_dhash(path)
        duplicate_of = None
        reason = ""
        if exact_hash in exact_seen:
            duplicate_of = exact_seen[exact_hash]
            reason = "exact-hash"
        elif visual_hash and visual_hash in visual_seen:
            duplicate_of = visual_seen[visual_hash]
            reason = "visual-hash"
        if duplicate_of:
            duplicates.append({
                "file_name": path.name,
                "image_path": str(path),
                "duplicate_of": duplicate_of.name,
                "duplicate_of_path": str(duplicate_of),
                "reason": reason,
                "exact_hash": exact_hash,
                "visual_hash": visual_hash,
            })
            continue
        selected.append(path)
        exact_seen[exact_hash] = path
        if visual_hash:
            visual_seen[visual_hash] = path
    return selected, duplicates


def run_vision_batch(image_dir: Path) -> dict[str, list[VisionItem]]:
    if platform.system() != "Darwin":
        return {}
    with tempfile.NamedTemporaryFile("w", suffix=".swift", delete=False, encoding="utf-8") as f:
        f.write(VISION_SWIFT)
        swift_path = Path(f.name)
    try:
        result = subprocess.run(["swift", str(swift_path), str(image_dir)], capture_output=True, text=True, check=True)
    except Exception:
        return {}
    finally:
        swift_path.unlink(missing_ok=True)
    decoder = json.JSONDecoder()
    text = result.stdout.strip()
    idx = 0
    payloads: dict[str, list[VisionItem]] = {}
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, end = decoder.raw_decode(text, idx)
        idx = end
        payloads[obj["image_path"]] = [VisionItem(**item) for item in obj["items"]]
    return payloads


def build_llm_client(api_key: str, base_url: str, timeout_seconds: float = 60.0):
    if OpenAI is None:
        raise RuntimeError("openai SDK is required for --ocr-engine llm")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)


def _llm_json_content(response) -> dict:
    content = response.choices[0].message.content or ""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = min((pos for pos in (text.find("{"), text.find("[")) if pos >= 0), default=-1)
        if start < 0:
            raise ValueError("vision LLM returned no JSON object")
        value = json.loads(text[start:])
    if not isinstance(value, dict):
        raise ValueError("vision LLM response must be a JSON object")
    return value


def run_llm_vision(image_path: Path, client, model: str) -> ScreenshotData:
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": LLM_VISION_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the visible profile and audience fields from this screenshot."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                ],
            },
        ],
    )
    payload = _llm_json_content(response)
    confidence = payload.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    return ScreenshotData(
        path=str(image_path),
        handle=normalize_handle(str(payload.get("handle") or "")),
        author_name=normalize_name(str(payload.get("author_name") or "")),
        email=str(payload.get("email") or "").strip(),
        countries=normalize_text(str(payload.get("countries") or "")),
        gender=normalize_text(str(payload.get("gender") or "")),
        age=normalize_text(str(payload.get("age") or "")),
        raw_hits={"engine": "llm", "payload": payload},
        confidence=round(confidence, 3),
    )


def ocr_file(path: Path) -> str:
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", "eng+chi_sim", "--psm", "6"],
        capture_output=True,
        text=True,
    )
    return result.stdout or ""


def run_tesseract(image_path: Path) -> list[str]:
    variants = [ocr_file(image_path)]
    image = cv2.imread(str(image_path))
    if image is None:
        return [v for v in variants if v.strip()]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scaled = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    temp = image_path.with_suffix(".ocr_tmp.png")
    cv2.imwrite(str(temp), thresh)
    variants.append(ocr_file(temp))
    temp.unlink(missing_ok=True)
    return [v for v in variants if v.strip()]


def extract_emails(texts: list[str]) -> tuple[str, list[str]]:
    candidates: list[str] = []
    for text in texts:
        joined = text.replace(" ", "")
        for source in [text, joined]:
            for match in EMAIL_RE.findall(source):
                email = normalize_email(match)
                if is_plausible_email(email):
                    candidates.append(email)
    if not candidates:
        return "", []
    return Counter(candidates).most_common(1)[0][0], list(dict.fromkeys(candidates))


def extract_handle(texts: list[str]) -> str:
    candidates: list[str] = []
    for text in texts:
        for match in HANDLE_RE.findall(text):
            handle = normalize_handle(match)
            if handle and ".com" not in handle.lower():
                candidates.append(handle)
    return Counter(candidates).most_common(1)[0][0] if candidates else ""


def extract_author_name(texts: list[str]) -> str:
    blocked = {"gender", "age", "audience", "性别", "年龄", "地区"}
    candidates: list[str] = []
    for text in texts:
        for line in [x.strip() for x in text.splitlines() if x.strip()][:5]:
            name = normalize_name(line)
            if not name or len(name) < 2:
                continue
            if any(token in name.lower() for token in blocked):
                continue
            candidates.append(name)
    return Counter(candidates).most_common(1)[0][0] if candidates else ""


def clean_country(text: str) -> str:
    value = (text or "").strip().replace("•", "").replace("@", "").replace("9 ", "")
    value = re.sub(r"T[123①I]|H1|1I|I1|（|）|\(|\)|\*", "", value)
    value = re.sub(r"[^A-Za-z\u4e00-\u9fff]", "", value).strip()
    value = COUNTRY_FIXES.get(value, value)
    value = COUNTRY_FIXES.get(value.lower(), value)
    if re.fullmatch(r"[A-Za-z]{1,3}", value):
        return ""
    return value if len(value) >= 2 else ""


def canonical_country_token(text: str) -> str:
    cleaned = clean_country(text)
    cleaned_lower = cleaned.lower()
    for country, aliases in COUNTRY_ALIASES.items():
        if cleaned == country:
            return country
        if any(alias.lower() == cleaned_lower for alias in aliases):
            return country
    for country, aliases in COUNTRY_ALIASES.items():
        if any(alias.lower() in cleaned_lower for alias in aliases):
            return country
    if "美" in cleaned:
        return "美国"
    if "英" in cleaned:
        return "英国"
    if "加" in cleaned:
        return "加拿大"
    if "德" in cleaned:
        return "德国"
    if "法" in cleaned:
        return "法国"
    if "荷" in cleaned:
        return "荷兰"
    if "菲" in cleaned:
        return "菲律宾"
    if "印尼" in cleaned or cleaned == "印":
        return "印尼"
    if "南非" in cleaned:
        return "南非"
    if "波" in cleaned:
        return "波兰"
    if "澳" in cleaned:
        return "澳大利亚"
    return cleaned


def extract_country_pct_pairs(text: str) -> list[tuple[str, float]]:
    text = normalize_text(text)
    if not text:
        return []
    pairs: list[tuple[str, float]] = []
    seen: set[str] = set()

    def add_pair(country_raw: str, pct_raw: str) -> None:
        country = canonical_country_token(country_raw)
        if not country or country in seen:
            return
        try:
            pct = float(pct_raw)
        except ValueError:
            return
        seen.add(country)
        pairs.append((country, pct))

    for pct_raw, country_raw in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%\s*([A-Za-z\u4e00-\u9fff]{1,16})", text):
        add_pair(country_raw, pct_raw)

    for country_raw, pct_raw in re.findall(r"([A-Za-z\u4e00-\u9fff]{1,16})\s*(\d{1,3}(?:\.\d+)?)\s*%", text):
        add_pair(country_raw, pct_raw)

    tokens = text.replace("/", " ").split()
    for idx, token in enumerate(tokens[:-1]):
        pct_match = re.fullmatch(r"(\d{1,3}(?:\.\d+)?)%", token)
        if not pct_match:
            continue
        add_pair(tokens[idx + 1], pct_match.group(1))

    return pairs[:4]


def find_pct_for_y(items: list[VisionItem], y: float, tol: float = 0.015) -> float | None:
    candidates = []
    for item in items:
        pct = parse_pct(item.text)
        if pct is None:
            continue
        if item.x < 0.72:
            continue
        if abs(item.y - y) <= tol:
            candidates.append((abs(item.y - y), pct))
    return min(candidates, default=(None, None))[1]


def extract_from_vision(image_path: Path, items: list[VisionItem]) -> ScreenshotData:
    texts = [item.text for item in sorted(items, key=lambda x: (-x.y, x.x))]
    top_candidates = [normalize_name(item.text) for item in items if item.y > 0.94 and len(normalize_name(item.text)) >= 2]
    author_name = top_candidates[0] if top_candidates else extract_author_name(["\n".join(texts)])
    email, email_candidates = extract_emails(["\n".join(texts)])
    handle = extract_handle(["\n".join(texts)])

    male = find_pct_for_y(items, 0.876)
    female = find_pct_for_y(items, 0.837)
    if male is None or female is None:
        male = find_pct_for_y(items, 0.87, tol=0.03)
        female = find_pct_for_y(items, 0.83, tol=0.03)
    gender = ""
    if male is not None and female is not None:
        if round(male) == 50 and round(female) == 50:
            male, female = 52, 48
        elif round(male + female) != 100:
            female = max(0.0, 100.0 - male)
        gender = f"男{int(round(male))}%/女{int(round(female))}%"

    age_18_25 = None
    age_25_45 = None
    age_labels = {"18-25": None, "25-45": None}
    for item in items:
        label = item.text.strip()
        if label not in age_labels:
            continue
        age_labels[label] = find_pct_for_y(items, item.y, tol=0.02)
    age_18_25 = age_labels["18-25"]
    age_25_45 = age_labels["25-45"]
    age = ""
    if age_18_25 is not None and age_25_45 is not None:
        age = f"18-25 ({format_pct(age_18_25)})/25-45 ({format_pct(age_25_45)})"

    countries: list[tuple[float, str, float]] = []
    seen = set()
    for item in sorted(items, key=lambda x: (-x.y, x.x)):
        if not (0.09 <= item.y <= 0.37 and item.x <= 0.45):
            continue
        country = clean_country(item.text)
        if not country or country in seen:
            continue
        pct = find_pct_for_y(items, item.y, tol=0.012)
        if pct is None:
            continue
        seen.add(country)
        countries.append((item.y, country, pct))
    countries_text = " / ".join(f"{country} {format_pct(pct)}" for _, country, pct in countries[:4])

    confidence = 0.0
    if author_name:
        confidence += 0.35
    if countries_text:
        confidence += 0.35
    if gender:
        confidence += 0.15
    if age:
        confidence += 0.15

    return ScreenshotData(
        path=str(image_path),
        handle=handle,
        author_name=author_name,
        email=email,
        countries=countries_text,
        gender=gender,
        age=age,
        raw_hits={"emails": email_candidates, "engine": "vision"},
        confidence=round(confidence, 3),
    )


def extract_countries_from_texts(texts: list[str]) -> str:
    hits: list[str] = []
    seen = set()
    for text in texts:
        for line in text.splitlines():
            lowered = line.strip().lower()
            if not lowered:
                continue
            pct = parse_pct(line)
            if pct is None:
                continue
            for country, aliases in COUNTRY_ALIASES.items():
                if country in seen:
                    continue
                if any(alias.lower() in lowered for alias in aliases):
                    hits.append(f"{country} {format_pct(pct)}")
                    seen.add(country)
                    break
    return " / ".join(hits[:4])


def normalize_countries_text(text: str) -> str:
    if not text:
        return ""
    direct_pairs = extract_country_pct_pairs(text)
    if direct_pairs:
        return " / ".join(f"{country} {format_pct(pct)}" for country, pct in direct_pairs[:4])
    normalized_parts: list[str] = []
    seen: set[str] = set()
    for raw_part in text.split("/"):
        part = raw_part.strip()
        if not part:
            continue
        pct = parse_pct(part)
        country_part = re.sub(r"(\d{1,3}(?:\.\d+)?)\s*%", "", part).strip()
        country_part = re.sub(r"^[^A-Za-z\u4e00-\u9fff]+", "", country_part)
        country = canonical_country_token(country_part)
        if not country or country in seen or pct is None:
            continue
        seen.add(country)
        normalized_parts.append(f"{country} {format_pct(pct)}")
    return " / ".join(normalized_parts[:4])


def normalize_gender_text(text: str) -> str:
    if not text:
        return ""
    matches = re.findall(r"(男|male|女性|女|female)\s*[:：]?\s*(\d{1,3}(?:\.\d+)?)\s*%", text, re.I)
    male = None
    female = None
    for label, pct_text in matches:
        pct = float(pct_text)
        label_l = label.lower()
        if label in {"男"} or "male" in label_l:
            male = pct
        elif label in {"女", "女性"} or "female" in label_l:
            female = pct
    if male is None and female is None:
        direct = re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
        if len(direct) >= 2:
            male = float(direct[0])
            female = float(direct[1])
    if male is None and female is None:
        return ""
    if male is None:
        male = max(0.0, 100.0 - female)
    if female is None:
        female = max(0.0, 100.0 - male)
    if round(male) == 50 and round(female) == 50:
        male, female = 52, 48
    elif round(male + female) != 100:
        female = max(0.0, 100.0 - male)
    return f"男{int(round(male))}%/女{int(round(female))}%"


def normalize_age_text(text: str) -> str:
    if not text:
        return ""
    m18 = re.search(r"18-25\D{0,8}(\d{1,3}(?:\.\d+)?)\s*%", text)
    m25 = re.search(r"25-45\D{0,8}(\d{1,3}(?:\.\d+)?)\s*%", text)
    if not (m18 and m25):
        return ""
    return f"18-25 ({format_pct(float(m18.group(1)))})/25-45 ({format_pct(float(m25.group(1)))})"


def extract_gender_from_texts(texts: list[str]) -> str:
    male = None
    female = None
    for text in texts:
        for line in text.splitlines():
            lowered = line.lower()
            pct = parse_pct(line)
            if pct is None:
                continue
            if "male" in lowered or "男性" in line:
                male = pct
            elif "female" in lowered or "女性" in line:
                female = pct
    if male is None and female is None:
        return ""
    if male is None:
        male = max(0.0, 100.0 - female)
    if female is None:
        female = max(0.0, 100.0 - male)
    return f"男{int(round(male))}%/女{int(round(female))}%"


def extract_age_from_texts(texts: list[str]) -> str:
    joined = "\n".join(texts)
    buckets = {}
    for label in ["18-25", "25-45"]:
        m = re.search(re.escape(label) + r"\D{0,10}(\d{1,2}(?:\.\d+)?)\s*%", joined, re.I)
        if m:
            buckets[label] = float(m.group(1))
    if "18-25" in buckets and "25-45" in buckets:
        return f"18-25 ({format_pct(buckets['18-25'])})/25-45 ({format_pct(buckets['25-45'])})"
    return ""


def evaluate_review_flags(data: ScreenshotData) -> list[str]:
    reasons: list[str] = []
    if not data.author_name:
        reasons.append("missing-author")
    if data.countries and re.search(r"[A-Za-z]{2,}", data.countries):
        reasons.append("raw-latin-country-token")
    if data.confidence < 0.75:
        reasons.append("low-confidence")
    return reasons


def get_blocked_fields(data: ScreenshotData) -> list[str]:
    blocked: list[str] = []
    countries = [part.strip() for part in data.countries.split("/") if part.strip()]
    if not data.countries:
        blocked.append("粉丝受众")
    elif re.search(r"[A-Za-z]{2,}", data.countries):
        blocked.append("粉丝受众")
    elif len(countries) < 2:
        blocked.append("粉丝受众")
    if not data.gender:
        blocked.append("粉丝性别")
    if not data.age:
        blocked.append("粉丝年龄")
    return blocked


def second_pass_candidate_score(data: ScreenshotData, row: dict[str, str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    data_name = canonical_name(data.author_name)
    row_name = canonical_name(row.get("频道/作者名称", ""))
    data_name_handle = canonical_handle(data.author_name)
    row_handle = canonical_handle(row.get("账号ID", ""))
    if data_name and row_name:
        ratio = SequenceMatcher(None, data_name, row_name).ratio()
        if ratio >= 0.72:
            score += int(ratio * 100)
            reasons.append(f"name~{ratio:.2f}")
    if data_name_handle and row_handle:
        ratio = SequenceMatcher(None, data_name_handle, row_handle).ratio()
        if ratio >= 0.72:
            score += int(ratio * 95)
            reasons.append(f"name-handle~{ratio:.2f}")
    if data.handle and normalize_handle(data.handle) == normalize_handle(row.get("账号ID", "")):
        score += 120
        reasons.append("handle")
    return score, reasons


def second_pass_match_row(
    data: ScreenshotData,
    rows: list[dict[str, str]],
    seen_matches: set[int],
    partition_filter: str,
) -> tuple[int | None, str]:
    partition_col = "分区" if rows and "分区" in rows[0] else "提报备注"
    candidate_indices = [
        idx for idx in range(len(rows))
        if idx not in seen_matches
    ]
    if partition_filter:
        target_partition = partition_filter.strip().lower()
        candidate_indices = [
            idx for idx in candidate_indices
            if str(rows[idx].get(partition_col, "")).strip().lower() == target_partition
        ]
    scored: list[tuple[int, int, str]] = []
    for idx in candidate_indices:
        score, reasons = second_pass_candidate_score(data, rows[idx])
        if score > 0:
            scored.append((idx, score, ",".join(reasons)))
    if not scored:
        return None, ""
    scored.sort(key=lambda x: x[1], reverse=True)
    best_idx, best_score, best_reason = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else -1
    if best_score < 72 or (second_score >= 0 and best_score - second_score < 12):
        return None, ""
    return best_idx, f"second-pass:{best_reason}"


def try_second_pass_fix(data: ScreenshotData) -> bool:
    changed = False
    normalized_countries = normalize_countries_text(data.countries)
    if normalized_countries and normalized_countries != data.countries:
        data.countries = normalized_countries
        data.second_pass_notes.append("normalized-countries")
        changed = True
    normalized_gender = normalize_gender_text(data.gender)
    if normalized_gender and normalized_gender != data.gender:
        data.gender = normalized_gender
        data.second_pass_notes.append("normalized-gender")
        changed = True
    normalized_age = normalize_age_text(data.age)
    if normalized_age and normalized_age != data.age:
        data.age = normalized_age
        data.second_pass_notes.append("normalized-age")
        changed = True
    data.review_reasons = evaluate_review_flags(data)
    data.blocked_fields = get_blocked_fields(data)
    data.review_required = (
        "missing-author" in data.review_reasons
        or ("raw-latin-country-token" in data.review_reasons and "粉丝受众" in data.blocked_fields)
    )
    if changed and not data.review_required:
        data.second_pass_fixed = True
    return changed


def extract_from_tesseract(image_path: Path) -> ScreenshotData:
    texts = run_tesseract(image_path)
    email, email_candidates = extract_emails(texts)
    return ScreenshotData(
        path=str(image_path),
        handle=extract_handle(texts),
        author_name=extract_author_name(texts),
        email=email,
        countries=extract_countries_from_texts(texts),
        gender=extract_gender_from_texts(texts),
        age=extract_age_from_texts(texts),
        raw_hits={"emails": email_candidates, "engine": "tesseract"},
        confidence=0.45 if texts else 0.0,
    )


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def match_row(
    data: ScreenshotData,
    rows: list[dict[str, str]],
    target_id: str,
    target_name: str,
    partition_filter: str,
) -> tuple[int | None, str]:
    partition_col = "分区" if rows and "分区" in rows[0] else "提报备注"
    candidate_indices = list(range(len(rows)))
    if partition_filter:
        target_partition = partition_filter.strip().lower()
        candidate_indices = [
            idx for idx, row in enumerate(rows)
            if str(row.get(partition_col, "")).strip().lower() == target_partition
        ]
    if target_id:
        target_id = normalize_handle(target_id)
        for idx in candidate_indices:
            row = rows[idx]
            if normalize_handle(row.get("账号ID", "")) == target_id:
                return idx, "target-id"
        return None, ""
    if target_name:
        target_key = canonical_name(target_name)
        for idx in candidate_indices:
            row = rows[idx]
            if canonical_name(row.get("频道/作者名称", "")) == target_key:
                return idx, "target-name"
        return None, ""
    best_score = -1
    second_score = -1
    best_idx: int | None = None
    reason = ""
    data_handle = normalize_handle(data.handle).lower()
    data_email = normalize_email(data.email)
    data_name = canonical_name(data.author_name)
    data_name_as_handle = canonical_handle(data.author_name)
    for idx in candidate_indices:
        row = rows[idx]
        score = 0
        reasons = []
        row_handle = normalize_handle(row.get("账号ID", "")).lower()
        row_handle_key = canonical_handle(row.get("账号ID", ""))
        row_email = normalize_email(row.get("联系方式", ""))
        row_name = canonical_name(row.get("频道/作者名称", ""))
        if data_handle and row_handle and data_handle == row_handle:
            score += 100
            reasons.append("handle")
        if data_email and row_email and data_email == row_email:
            score += 90
            reasons.append("email")
        if data_name and row_name:
            ratio = SequenceMatcher(None, data_name, row_name).ratio()
            if data_name == row_name:
                score += 85
                reasons.append("name")
            elif ratio >= 0.78:
                score += int(ratio * 70)
                reasons.append(f"name~{ratio:.2f}")
        if data_name_as_handle and row_handle_key:
            if data_name_as_handle == row_handle_key:
                score += 82
                reasons.append("name-as-handle")
            else:
                ratio = SequenceMatcher(None, data_name_as_handle, row_handle_key).ratio()
                if ratio >= 0.86:
                    score += int(ratio * 68)
                    reasons.append(f"name-handle~{ratio:.2f}")
        if score > best_score:
            second_score = best_score
            best_score = score
            best_idx = idx
            reason = ",".join(reasons)
        elif score > second_score:
            second_score = score
    if best_score < 70 or (second_score >= 0 and best_score - second_score < 15):
        return None, ""
    return best_idx, reason


def should_write(existing: str, new_value: str, force_overwrite: bool) -> bool:
    if not new_value:
        return False
    if force_overwrite:
        return True
    return not (existing or "").strip()


def build_summary_markdown(
    image_dir: Path,
    csv_path: Path,
    engine: str,
    selected_images: list[Path],
    duplicate_images: list[dict],
    extracted: list[ScreenshotData],
    issues: list[dict],
    row_updates: dict[int, dict[str, str]],
    dry_run: bool,
) -> str:
    duplicate_issue_count = sum(1 for item in issues if item.get("reason") == "duplicate")
    unmatched_issue_count = sum(1 for item in issues if item.get("reason") == "unmatched")
    review_count = sum(1 for item in extracted if item.review_required)
    second_pass_count = sum(1 for item in extracted if item.second_pass_fixed)
    lines = [
        "# OCR Sync Summary",
        "",
        f"- Image dir: `{image_dir}`",
        f"- CSV path: `{csv_path}`",
        f"- OCR engine: `{engine}`",
        f"- Dry run: `{dry_run}`",
        f"- Selected images: {len(selected_images)}",
        f"- Skipped duplicate images: {len(duplicate_images)}",
        f"- Matched rows: {len(row_updates)}",
        f"- Review-required images: {review_count}",
        f"- Second-pass auto-fixed images: {second_pass_count}",
        f"- Unmatched issues: {unmatched_issue_count}",
        f"- Duplicate-row issues: {duplicate_issue_count}",
        "",
        "## Duplicate Images",
    ]
    if duplicate_images:
        for item in duplicate_images:
            lines.append(f"- `{item['file_name']}` -> `{item['duplicate_of']}` ({item['reason']})")
    else:
        lines.append("- None")
    lines.extend(["", "## Review Queue"])
    review_items = [item for item in extracted if item.review_required]
    if review_items:
        for item in review_items:
            lines.append(
                f"- `{Path(item.path).name}` -> `{item.author_name or 'UNKNOWN'}` | reasons: {', '.join(item.review_reasons)}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Partial Writes"])
    partial_items = [item for item in extracted if item.blocked_fields and not item.review_required]
    if partial_items:
        for item in partial_items:
            lines.append(
                f"- `{Path(item.path).name}` -> `{item.author_name or 'UNKNOWN'}` | blocked fields: {', '.join(item.blocked_fields)}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Second-pass Fixes"])
    second_pass_items = [item for item in extracted if item.second_pass_fixed]
    if second_pass_items:
        for item in second_pass_items:
            lines.append(
                f"- `{Path(item.path).name}` -> `{item.author_name or 'UNKNOWN'}` | notes: {', '.join(item.second_pass_notes)}"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    # `auto` is capability-driven: native Vision is only meaningful on macOS;
    # on servers prefer multimodal OCR when configured, then deterministic
    # tesseract. Explicit engine choices remain authoritative.
    llm_api_key = args.llm_api_key or os.environ.get("OPENAI_API_KEY", "")
    effective_engine = args.ocr_engine
    if effective_engine == "auto":
        if platform.system() == "Darwin":
            effective_engine = "vision"
        elif llm_api_key:
            effective_engine = "llm"
        else:
            effective_engine = "tesseract"
    if effective_engine == "llm" and not llm_api_key:
        raise SystemExit("--llm-api-key or OPENAI_API_KEY is required for --ocr-engine llm")
    image_dir = Path(args.image_dir)
    csv_path = Path(args.csv_path)
    images, duplicate_images = select_images(image_dir, args.only_files, args.dedupe_images)
    if (args.target_id or args.target_name) and len(images) != 1:
        raise SystemExit("When using --target-id or --target-name, you must narrow the batch to exactly one image via --only-files.")
    rows = load_rows(csv_path)
    headers = list(rows[0].keys()) if rows else []

    vision_payloads: dict[str, list[VisionItem]] = {}
    llm_client = None
    if effective_engine == "vision":
        vision_payloads = run_vision_batch(image_dir)
    elif effective_engine == "llm":
        llm_client = build_llm_client(llm_api_key, args.llm_base_url)

    extracted: list[ScreenshotData] = []
    issues: list[dict] = []
    row_updates: dict[int, dict[str, str]] = defaultdict(dict)
    seen_matches: set[int] = set()
    pending_second_pass: list[ScreenshotData] = []

    for image in images:
        data = ScreenshotData(path=str(image))
        if llm_client is not None:
            data = run_llm_vision(image, llm_client, args.llm_model)
        vision_items = vision_payloads.get(str(image))
        if vision_items:
            data = extract_from_vision(image, vision_items)
        fallback = None
        if effective_engine == "tesseract":
            fallback = extract_from_tesseract(image)
            data = fallback
        data.review_reasons = evaluate_review_flags(data)
        data.blocked_fields = get_blocked_fields(data)
        data.review_required = (
            "missing-author" in data.review_reasons
            or ("raw-latin-country-token" in data.review_reasons and "粉丝受众" in data.blocked_fields)
        )

        match_idx, match_reason = match_row(
            data,
            rows,
            args.target_id or "",
            args.target_name or "",
            args.partition_filter or "",
        )
        data.match_reason = match_reason
        if match_idx is None:
            pending_second_pass.append(data)
            extracted.append(data)
            continue
        data.matched_row = match_idx + 2
        if match_idx in seen_matches:
            data.duplicate = True
            issues.append({
                "file_name": image.name,
                "image_path": str(image),
                "author_name": data.author_name,
                "reason": "duplicate",
                "matched_row": data.matched_row,
                "review_reasons": data.review_reasons,
                "blocked_fields": data.blocked_fields,
            })
            extracted.append(data)
            continue
        seen_matches.add(match_idx)
        row = rows[match_idx]
        updates = row_updates[match_idx]
        if data.review_required:
            pending_second_pass.append(data)
            extracted.append(data)
            continue
        if "粉丝受众" not in data.blocked_fields and should_write(row.get("粉丝受众", ""), data.countries, args.force_overwrite):
            updates["粉丝受众"] = data.countries
        if "粉丝性别" not in data.blocked_fields and should_write(row.get("粉丝性别", ""), data.gender, args.force_overwrite):
            updates["粉丝性别"] = data.gender
        if "粉丝年龄" not in data.blocked_fields and should_write(row.get("粉丝年龄", ""), data.age, args.force_overwrite):
            updates["粉丝年龄"] = data.age
        if data.blocked_fields:
            issues.append({
                "file_name": image.name,
                "image_path": str(image),
                "author_name": data.author_name,
                "reason": "partial-write",
                "matched_row": data.matched_row,
                "formatted": {"粉丝受众": data.countries, "粉丝性别": data.gender, "粉丝年龄": data.age},
                "confidence": data.confidence,
                "review_reasons": data.review_reasons,
                "blocked_fields": data.blocked_fields,
            })
        extracted.append(data)

    for data in pending_second_pass:
        try_second_pass_fix(data)
        if data.matched_row is None:
            match_idx, match_reason = second_pass_match_row(
                data,
                rows,
                seen_matches,
                args.partition_filter or "",
            )
            if match_idx is not None:
                data.matched_row = match_idx + 2
                data.match_reason = match_reason
                seen_matches.add(match_idx)
        if data.matched_row is not None and not data.review_required:
            row = rows[data.matched_row - 2]
            updates = row_updates[data.matched_row - 2]
            if "粉丝受众" not in data.blocked_fields and should_write(row.get("粉丝受众", ""), data.countries, args.force_overwrite):
                updates["粉丝受众"] = data.countries
                data.second_pass_fixed = True
                data.second_pass_notes.append("write-countries")
            if "粉丝性别" not in data.blocked_fields and should_write(row.get("粉丝性别", ""), data.gender, args.force_overwrite):
                updates["粉丝性别"] = data.gender
                data.second_pass_fixed = True
                data.second_pass_notes.append("write-gender")
            if "粉丝年龄" not in data.blocked_fields and should_write(row.get("粉丝年龄", ""), data.age, args.force_overwrite):
                updates["粉丝年龄"] = data.age
                data.second_pass_fixed = True
                data.second_pass_notes.append("write-age")
            if data.second_pass_fixed:
                continue
        issues.append({
            "file_name": Path(data.path).name,
            "image_path": data.path,
            "author_name": data.author_name,
            "reason": "review-required" if data.review_required else "unmatched",
            "matched_row": data.matched_row,
            "formatted": {"粉丝受众": data.countries, "粉丝性别": data.gender, "粉丝年龄": data.age},
            "confidence": data.confidence,
            "review_reasons": data.review_reasons,
            "blocked_fields": data.blocked_fields,
            "second_pass_notes": data.second_pass_notes,
        })

    report = {
        "image_dir": str(image_dir),
        "csv_path": str(csv_path),
        "engine": args.ocr_engine,
        "selected_images": [str(path) for path in images],
        "duplicate_images": duplicate_images,
        "images": [asdict(data) for data in extracted],
        "row_updates": {str(idx + 2): updates for idx, updates in row_updates.items()},
        "target_id": args.target_id or "",
        "target_name": args.target_name or "",
        "partition_filter": args.partition_filter or "",
    }
    issues_report = {
        "image_dir": str(image_dir),
        "csv_path": str(csv_path),
        "duplicate_images": duplicate_images,
        "issues": issues,
    }

    stamp = datetime.now().strftime('%H%M%S')
    report_path = image_dir / f"ocr_results_{stamp}.json"
    issues_path = image_dir / f"issues_{stamp}.json"
    duplicates_path = image_dir / f"duplicate_images_{stamp}.json"
    summary_path = image_dir / f"ocr_summary_{stamp}.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    issues_path.write_text(json.dumps(issues_report, ensure_ascii=False, indent=2), encoding="utf-8")
    duplicates_path.write_text(json.dumps({"image_dir": str(image_dir), "duplicate_images": duplicate_images}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(
        build_summary_markdown(image_dir, csv_path, args.ocr_engine, images, duplicate_images, extracted, issues, row_updates, args.dry_run),
        encoding="utf-8",
    )

    backup_path = None
    if not args.dry_run:
        backup_path = ensure_backup(csv_path)
        for idx, updates in row_updates.items():
            for key, value in updates.items():
                rows[idx][key] = value
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    print(json.dumps({
        "backup_path": str(backup_path) if backup_path else "",
        "report_path": str(report_path),
        "issues_path": str(issues_path),
        "duplicates_path": str(duplicates_path),
        "summary_path": str(summary_path),
        "matched": len(row_updates),
        "issues": len(issues),
        "selected_images": len(images),
        "skipped_duplicate_images": len(duplicate_images),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
