#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


def clean_name(text: str) -> str:
    value = text.strip()
    value = re.sub(r"\bNow\b.*$", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s*@+\s*$", "", value).strip()
    value = re.sub(r"[®©™]+", "", value).strip()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_first_line(image_path: Path, language: str) -> tuple[str, list[str]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "ocr"
        subprocess.run(
            ["tesseract", str(image_path), str(base), "-l", language],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        txt_path = base.with_suffix(".txt")
        lines = txt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    raw_lines = [line.strip() for line in lines if line.strip()]
    first_line = raw_lines[0] if raw_lines else ""
    return clean_name(first_line), raw_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract X DM reply names from screenshots")
    parser.add_argument("--screenshots-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--language", default="eng+chi_sim")
    args = parser.parse_args()

    screenshots_dir = Path(args.screenshots_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    deduped_names = []
    seen = set()
    for image_path in sorted(screenshots_dir.glob("*.png")):
        extracted_name, raw_lines = extract_first_line(image_path, args.language)
        rows.append(
            {
                "file": image_path.name,
                "extracted_name": extracted_name,
                "raw_lines": raw_lines[:5],
            }
        )
        key = re.sub(r"\s+", "", extracted_name.lower())
        if extracted_name and key and key not in seen:
            seen.add(key)
            deduped_names.append(extracted_name)

    names_path = output_dir / "x_dm_second_reply_names.txt"
    report_path = output_dir / "x_dm_second_reply_ocr_report.json"
    names_path.write_text("\n".join(deduped_names) + ("\n" if deduped_names else ""), encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "screenshots_dir": str(screenshots_dir),
                "screenshot_count": len(rows),
                "deduped_name_count": len(deduped_names),
                "names_file": str(names_path),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "screenshots_dir": str(screenshots_dir),
                "screenshot_count": len(rows),
                "deduped_name_count": len(deduped_names),
                "names_file": str(names_path),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
