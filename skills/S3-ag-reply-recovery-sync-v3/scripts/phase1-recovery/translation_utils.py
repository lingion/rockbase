#!/usr/bin/env python3
from __future__ import annotations

import re
from functools import lru_cache
from typing import List

from deep_translator import GoogleTranslator
from langdetect import DetectorFactory, LangDetectException, detect


DetectorFactory.seed = 0

DIRECT_TABLE_LANGS = {"en", "zh", "zh-cn", "zh-tw"}
CHUNK_LIMIT = 3500


def clean_text(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_language(lang: str) -> str:
    value = (lang or "").strip().lower()
    if value.startswith("zh"):
        return "zh"
    if value.startswith("en"):
        return "en"
    return value


def detect_language(text: str) -> str:
    sample = clean_text(text)
    if not sample:
        return ""
    if re.fullmatch(r"[\x00-\x7F\s\W_]+", sample):
        return "en"
    try:
        return normalize_language(detect(sample[:2000]))
    except LangDetectException:
        return ""


def needs_translation(text: str) -> bool:
    lang = detect_language(text)
    return bool(lang) and lang not in {"en", "zh"}


def _chunk_text(text: str, limit: int = CHUNK_LIMIT) -> List[str]:
    lines = clean_text(text).splitlines()
    if not lines:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line:
            candidate_len = current_len + 1
        else:
            candidate_len = current_len + len(line) + 1

        if current and candidate_len > limit:
            chunks.append("\n".join(current).strip())
            current = [line]
            current_len = len(line)
            continue

        if len(line) > limit:
            if current:
                chunks.append("\n".join(current).strip())
                current = []
                current_len = 0
            for idx in range(0, len(line), limit):
                chunks.append(line[idx : idx + limit])
            continue

        current.append(line)
        current_len = candidate_len

    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


@lru_cache(maxsize=1024)
def _translate_chunk(chunk: str, target: str) -> str:
    return GoogleTranslator(source="auto", target=target).translate(chunk)


def translate_text(text: str, target: str = "en") -> str:
    text = clean_text(text)
    if not text:
        return ""
    translated = []
    for chunk in _chunk_text(text):
        try:
            translated.append(_translate_chunk(chunk, target))
        except Exception:
            translated.append(chunk)
    return clean_text("\n".join(translated))


def english_for_logic(text: str) -> str:
    return translate_text(text, target="en") if needs_translation(text) else clean_text(text)


def table_safe_text(text: str) -> str:
    text = clean_text(text)
    if not text:
        return ""
    return translate_text(text, target="en") if needs_translation(text) else text
