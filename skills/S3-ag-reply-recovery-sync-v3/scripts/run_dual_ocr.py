#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from ocr_dual_engine import run_dual_image_ocr, run_pdf_dual_ocr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run standalone dual OCR (macOS Vision + tesseract) on images or PDFs.")
    parser.add_argument("--input-path", required=True, help="Image, PDF, or directory path.")
    parser.add_argument("--output-dir", required=True, help="Directory for OCR text and summary outputs.")
    return parser.parse_args()


def collect_files(input_path: Path):
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        files = []
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.pdf"):
            files.extend(sorted(input_path.glob(ext)))
        return files
    raise FileNotFoundError(f"input path not found: {input_path}")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)
    text_dir = output_dir / "ocr_text"
    text_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for idx, file_path in enumerate(collect_files(input_path), start=1):
        txt_path = text_dir / f"{idx:03d}_{file_path.stem}.txt"
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            text, meta = run_pdf_dual_ocr(file_path, txt_path)
            method = "pdf_dual_ocr"
        else:
            text, meta = run_dual_image_ocr(file_path, txt_path)
            method = "image_dual_ocr"
        results.append(
            {
                "file_name": file_path.name,
                "input_path": str(file_path.resolve()),
                "text_file": str(txt_path.resolve()),
                "extract_method": method,
                "ocr_strategy": meta.get("ocr_strategy", ""),
                "ocr_score": meta.get("ocr_score", "0"),
                "ocr_candidates": meta.get("ocr_candidates", ""),
                "text_length": len(text),
                "text_preview": text[:280],
            }
        )

    summary = {
        "input_path": str(input_path.resolve()),
        "files_total": len(results),
        "output_dir": str(output_dir.resolve()),
        "results": results,
    }
    summary_path = output_dir / "dual_ocr_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
