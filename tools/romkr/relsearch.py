"""상대 검색(relative search): 문자 코드 간의 차이로 미지의 텍스트 인코딩을 찾는다.

게임 화면의 문장(예: 'はなしかける')을 입력하면, 정해진 문자 순서(오십음/SJIS/ASCII)에서의
상대 간격이 같은 바이트열을 롬에서 찾고, 발견 위치와 추정 테이블을 제시한다.
탁음/반탁음 등 순서에 없는 문자는 와일드카드로 취급된다.
"""
from __future__ import annotations

import re

GOJUON = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
ORDERS = {
    "gojuon": GOJUON,
    "gojuon-kata": "".join(chr(ord(c) + 0x60) for c in GOJUON),
    "sjis": "".join(chr(c) for c in range(0x3041, 0x3094)),
    "sjis-kata": "".join(chr(c) for c in range(0x30A1, 0x30F7)),
    "ascii": "".join(chr(c) for c in range(0x20, 0x7F)),
}


def indices(text, order):
    seq = ORDERS[order]
    return [seq.index(c) if c in seq else None for c in text]


def search(data: bytes, text: str, order="gojuon", width=1, endian="little", max_hits=50):
    idx = indices(text, order)
    known = [i for i, v in enumerate(idx) if v is not None]
    if len(known) < 3:
        raise ValueError("순서표에 있는 문자가 최소 3개 필요")
    hits = []
    if width == 1:
        # 차분 배열에서 정규식 검색 (빠름)
        diff = bytes((data[i + 1] - data[i]) & 0xFF for i in range(len(data) - 1))
        pat = b""
        for a, b in zip(idx, idx[1:]):
            pat += re.escape(bytes([(b - a) & 0xFF])) if a is not None and b is not None else b"."
        for m in re.finditer(pat, diff, re.DOTALL):
            pos = m.start()
            k0 = known[0]
            base = (data[pos + k0] - idx[k0]) & 0xFF
            hits.append((pos, base))
            if len(hits) >= max_hits:
                break
    else:
        n = len(text)
        k0 = known[0]
        for pos in range(0, len(data) - n * width + 1):
            vals = [int.from_bytes(data[pos + k * width:pos + (k + 1) * width], endian) for k in known]
            base = vals[0] - idx[k0]
            if all(v - idx[k] == base for v, k in zip(vals, known)):
                hits.append((pos, base))
                if len(hits) >= max_hits:
                    break
    return hits


def table_guess(base, order="gojuon", width=1):
    seq = ORDERS[order]
    lim = 1 << (8 * width)
    lines = []
    for i, c in enumerate(seq):
        v = base + i
        if 0 <= v < lim:
            lines.append(f"{v:0{width * 2}X}={c}")
    return lines
