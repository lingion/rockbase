#!/usr/bin/env python3
import json
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageFilter, ImageOps


PRICE_HINT_RE = re.compile(
    r"(?i)(?:"
    r"(US?\$|USD|EUR|€|£|GBP|\$)\s*(\d{1,3}(?:[,\d]{0,9})(?:\.\d{1,2})?)"
    r"|"
    r"(\d{1,3}(?:[,\d]{0,9})(?:\.\d{1,2})?)\s*(US?\$|USD|EUR|€|£|GBP|\$|dollars?|euros?|pounds?)"
    r")"
)
CHANNEL_HINT_RE = re.compile(
    r"(?i)\b("
    r"youtube|yt|tiktok|instagram|insta|ig|twitter|x\.com|shorts?|reels?|story|post|video|integration|dedicated|bundle|package|cross[\s-]?post"
    r")\b"
)

VISION_SWIFT_SINGLE = r"""
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
    let image_path: String
    let items: [Item]
}

let file = URL(fileURLWithPath: CommandLine.arguments[1])
guard let image = NSImage(contentsOf: file) else {
    fputs("{\"image_path\":\"\(file.path)\",\"items\":[]}", stderr)
    exit(1)
}
var rect = CGRect(origin: .zero, size: image.size)
guard let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
    fputs("{\"image_path\":\"\(file.path)\",\"items\":[]}", stderr)
    exit(1)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en-US", "ja-JP", "ko-KR"]
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try? handler.perform([request])
let items = (request.results ?? []).compactMap { obs -> Item? in
    guard let top = obs.topCandidates(1).first else { return nil }
    let b = obs.boundingBox
    return Item(text: top.string, x: Double(b.origin.x), y: Double(b.origin.y), w: Double(b.size.width), h: Double(b.size.height))
}
let payload = Payload(image_path: file.path, items: items)
let encoder = JSONEncoder()
encoder.outputFormatting = [.withoutEscapingSlashes]
let data = try! encoder.encode(payload)
print(String(data: data, encoding: .utf8)!)
"""


def normalized_text_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def score_extracted_text(text: str) -> int:
    normalized_len = normalized_text_length(text)
    if not normalized_len:
        return 0
    channel_hits = len(CHANNEL_HINT_RE.findall(text or ""))
    price_hits = len(PRICE_HINT_RE.findall(text or ""))
    line_hits = len([line for line in (text or "").splitlines() if line.strip()])
    return min(normalized_len, 5000) + (channel_hits * 80) + (price_hits * 220) + min(line_hits * 4, 120)


def merge_candidate_texts(candidates: List[Tuple[str, str]]) -> Tuple[str, str]:
    merged_lines: List[str] = []
    seen = set()
    labels = []
    for label, text in candidates:
        if not text.strip():
            continue
        labels.append(label)
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            key = line.lower()
            if not line or key in seen:
                continue
            seen.add(key)
            merged_lines.append(line)
    return "\n".join(merged_lines).strip(), "+".join(labels)


def build_ocr_variant(image_path: Path, output_path: Path) -> Path:
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("L")
        image = ImageOps.autocontrast(image)
        width, height = image.size
        image = image.resize((max(width * 2, 1200), max(height * 2, 1200)), Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.MedianFilter(size=3))
        image = image.filter(ImageFilter.SHARPEN)
        image = image.point(lambda px: 255 if px > 168 else 0)
        image.save(output_path)
    return output_path


def prepare_image_for_ocr(image_path: Path, temp_root: Path) -> Path:
    suffix = image_path.suffix.lower()
    if suffix not in {".heic", ".heif"}:
        return image_path
    converted = temp_root / f"{image_path.stem}_converted.png"
    subprocess.run(
        ["sips", "-s", "format", "png", str(image_path), "--out", str(converted)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return converted


def run_tesseract(image_path: Path, txt_base_path: Path, lang: str = "eng+chi_sim", psm: int = 6) -> str:
    subprocess.run(
        ["tesseract", str(image_path), str(txt_base_path), "-l", lang, "--psm", str(psm)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    txt_path = Path(f"{txt_base_path}.txt")
    return txt_path.read_text(encoding="utf-8", errors="replace")


def run_vision_ocr_single(image_path: Path) -> str:
    if platform.system() != "Darwin":
        raise RuntimeError("vision OCR only available on macOS")
    with tempfile.NamedTemporaryFile("w", suffix=".swift", delete=False, encoding="utf-8") as fh:
        fh.write(VISION_SWIFT_SINGLE)
        swift_path = Path(fh.name)
    try:
        result = subprocess.run(
            ["swift", str(swift_path), str(image_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = json.loads(result.stdout.strip())
        items = payload.get("items") or []
        return "\n".join((item.get("text") or "").strip() for item in items if (item.get("text") or "").strip()).strip()
    finally:
        swift_path.unlink(missing_ok=True)


def run_dual_image_ocr(image_path: Path, txt_path: Path) -> Tuple[str, Dict[str, str]]:
    temp_parent = txt_path.parent if txt_path.parent.exists() else image_path.parent
    with tempfile.TemporaryDirectory(prefix="reply_image_dual_ocr_", dir=str(temp_parent)) as temp_dir:
        temp_root = Path(temp_dir)
        source_for_ocr = prepare_image_for_ocr(image_path, temp_root)
        processed_path = build_ocr_variant(source_for_ocr, temp_root / f"{image_path.stem}_prep.png")
        candidates = []
        errors = []

        for label, source_path, psm in [
            ("tesseract_raw_psm6", source_for_ocr, 6),
            ("tesseract_preprocessed_psm11", processed_path, 11),
        ]:
            try:
                text = run_tesseract(source_path, temp_root / label, psm=psm)
                candidates.append((label, text, score_extracted_text(text)))
            except Exception as exc:
                errors.append(f"{label}:{exc}")

        try:
            vision_text = run_vision_ocr_single(processed_path)
            candidates.append(("macos_vision", vision_text, score_extracted_text(vision_text)))
        except Exception as exc:
            errors.append(f"macos_vision:{exc}")

        if not candidates:
            raise RuntimeError("all OCR engines failed: " + " | ".join(errors))

        ranked = sorted(candidates, key=lambda item: (item[2], normalized_text_length(item[1])), reverse=True)
        merged_text, merged_label = merge_candidate_texts([(label, text) for label, text, _ in ranked[:3]])
        merged_score = score_extracted_text(merged_text)
        best_label, best_text, best_score = ranked[0]
        final_text = merged_text if merged_score >= best_score else best_text
        final_label = f"dual_ocr:{merged_label}" if merged_score >= best_score else f"dual_ocr:{best_label}"
    txt_path.write_text(final_text, encoding="utf-8")
    return final_text, {
        "ocr_strategy": final_label,
        "ocr_score": str(max(best_score, merged_score)),
        "ocr_candidates": " | ".join([*(f"{label}:{score}" for label, _, score in ranked), *errors]),
    }


def run_pdf_dual_ocr(pdf_path: Path, txt_path: Path) -> Tuple[str, Dict[str, str]]:
    temp_parent = txt_path.parent if txt_path.parent.exists() else pdf_path.parent
    with tempfile.TemporaryDirectory(prefix="reply_pdf_dual_ocr_", dir=str(temp_parent)) as temp_dir:
        image_prefix = Path(temp_dir) / "page"
        subprocess.run(
            ["pdftoppm", "-f", "1", "-l", "5", "-png", str(pdf_path), str(image_prefix)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        page_texts = []
        page_meta = []
        for image_path in sorted(Path(temp_dir).glob("page-*.png")):
            page_txt_path = Path(temp_dir) / f"{image_path.stem}.txt"
            page_text, meta = run_dual_image_ocr(image_path, page_txt_path)
            if page_text.strip():
                page_texts.append(page_text)
            page_meta.append(f"{image_path.stem}:{meta.get('ocr_strategy', '')}:{meta.get('ocr_score', '0')}")
        merged = "\n\n".join(text for text in page_texts if text.strip())
    txt_path.write_text(merged, encoding="utf-8")
    return merged, {
        "ocr_strategy": "pdf_dual_ocr",
        "ocr_score": str(score_extracted_text(merged)),
        "ocr_candidates": " | ".join(page_meta),
    }
