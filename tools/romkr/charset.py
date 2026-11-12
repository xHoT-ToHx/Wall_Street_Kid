"""번역문에서 필요한 한글 음절을 모아 빈도순 문자셋을 만든다."""
from __future__ import annotations

import json
from collections import Counter

from .script import CTRL_RE


def is_hangul(c):
    return 0xAC00 <= ord(c) <= 0xD7A3


def ksx1001_hangul():
    """KS X 1001 완성형 한글 2350자."""
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes((hi, lo)).decode("euc_kr"))
            except UnicodeDecodeError:
                pass
    return out


def collect(script_paths, include_non_hangul=True) -> Counter:
    cnt = Counter()
    for p in script_paths:
        with open(p, encoding="utf-8") as f:
            entries = json.load(f)
        for e in entries:
            ko = CTRL_RE.sub("", e.get("ko", "") or "")
            for c in ko:
                if is_hangul(c) or (include_non_hangul and not c.isspace() and ord(c) > 0x7F):
                    cnt[c] += 1
    return cnt


def write_charset(path, chars):
    with open(path, "w", encoding="utf-8") as f:
        for c in chars:
            f.write(c + "\n")


def read_charset(path):
    with open(path, encoding="utf-8-sig") as f:
        return [ln.rstrip("\r\n") for ln in f if ln.rstrip("\r\n")]
