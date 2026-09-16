from __future__ import annotations

import re


COUNTRY_PATTERNS = [
    ("united states", "美国"),
    ("usa", "美国"),
    ("u.s.a", "美国"),
    ("u.s.", "美国"),
    ("canada", "加拿大"),
    ("united kingdom", "英国"),
    ("uk", "英国"),
    ("england", "英国"),
    ("australia", "澳大利亚"),
    ("new zealand", "新西兰"),
    ("singapore", "新加坡"),
    ("india", "印度"),
    ("dubai", "阿联酋"),
    ("uae", "阿联酋"),
    ("united arab emirates", "阿联酋"),
    ("germany", "德国"),
    ("france", "法国"),
    ("spain", "西班牙"),
    ("italy", "意大利"),
    ("netherlands", "荷兰"),
    ("sweden", "瑞典"),
    ("norway", "挪威"),
    ("denmark", "丹麦"),
    ("finland", "芬兰"),
    ("japan", "日本"),
    ("korea", "韩国"),
    ("south korea", "韩国"),
    ("china", "中国"),
    ("hong kong", "中国香港"),
    ("taiwan", "中国台湾"),
    ("malaysia", "马来西亚"),
    ("indonesia", "印度尼西亚"),
    ("philippines", "菲律宾"),
    ("thailand", "泰国"),
    ("vietnam", "越南"),
    ("brazil", "巴西"),
    ("mexico", "墨西哥"),
]



LANGUAGE_PATTERNS = [
    ("hindi", "Hindi"),
    ("english", "English"),
    ("urdu", "Urdu"),
    ("bengali", "Bengali"),
    ("tamil", "Tamil"),
    ("telugu", "Telugu"),
    ("marathi", "Marathi"),
    ("gujarati", "Gujarati"),
    ("kannada", "Kannada"),
    ("malayalam", "Malayalam"),
    ("punjabi", "Punjabi"),
    ("spanish", "Spanish"),
    ("french", "French"),
    ("german", "German"),
    ("japanese", "Japanese"),
    ("chinese", "Chinese"),
]


def infer_country_from_text(*texts: str) -> str:
    haystack = " \n ".join(texts).lower()
    haystack = re.sub(r"\s+", " ", haystack)
    for token, country in COUNTRY_PATTERNS:
        if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", haystack):
            return country
    return ""


def infer_language_from_text(*texts: str) -> str:
    haystack = " \n ".join(texts).lower()
    found = []
    for token, lang in LANGUAGE_PATTERNS:
        if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", haystack):
            if lang not in found:
                found.append(lang)
    return "/".join(found) if found else ""
