"""8x8 타일 인코더. 입력은 tile[y][x] = 팔레트 인덱스."""
from __future__ import annotations


def _row(t, y, p):
    return sum(((t[y][x] >> p) & 1) << (7 - x) for x in range(8))


def bpp1(t):          # 1bpp, 행당 1바이트
    return bytes(_row(t, y, 0) for y in range(8))


def nes2(t):          # FC: plane0 8바이트 → plane1 8바이트
    return bytes(_row(t, y, 0) for y in range(8)) + bytes(_row(t, y, 1) for y in range(8))


def gb2(t):           # GB/GBC, SFC 2bpp: 행마다 plane0, plane1 교차
    out = bytearray()
    for y in range(8):
        out += bytes((_row(t, y, 0), _row(t, y, 1)))
    return bytes(out)


def snes4(t):         # SFC 4bpp: (p0,p1)x8 → (p2,p3)x8
    out = bytearray()
    for y in range(8):
        out += bytes((_row(t, y, 0), _row(t, y, 1)))
    for y in range(8):
        out += bytes((_row(t, y, 2), _row(t, y, 3)))
    return bytes(out)


def sms4(t):          # SMS/GG: 행마다 p0,p1,p2,p3
    return bytes(_row(t, y, p) for y in range(8) for p in range(4))


def md4(t):           # MD: 4bpp packed, 상위 니블 = 왼쪽 픽셀
    return bytes((t[y][x] << 4) | t[y][x + 1] for y in range(8) for x in range(0, 8, 2))


TILE_FORMATS = {
    "1bpp": bpp1,
    "fc2bpp": nes2,
    "gb2bpp": gb2,
    "sfc2bpp": gb2,
    "sfc4bpp": snes4,
    "sms4bpp": sms4,
    "md4bpp": md4,
}

# 타일 분할 없이 글리프 전체를 선형으로 저장하는 포맷 (VWF/PS 폰트)
def linear1(glyph, w, h):      # 1bpp 행 단위, 행 폭 = ceil(w/8)바이트
    bpr = (w + 7) // 8
    out = bytearray()
    for y in range(h):
        row = [0] * (bpr * 8)
        row[:w] = [1 if v else 0 for v in glyph[y]]
        for i in range(bpr):
            out.append(sum(row[i * 8 + x] << (7 - x) for x in range(8)))
    return bytes(out)


def psx4(glyph, w, h):         # PS VRAM/TIM 4bpp: 하위 니블 = 왼쪽 픽셀
    out = bytearray()
    for y in range(h):
        row = list(glyph[y]) + [0] * (w & 1)
        for x in range(0, len(row), 2):
            out.append((row[x + 1] << 4) | row[x])
    return bytes(out)


LINEAR_FORMATS = {"1bpp-linear": linear1, "ps4bpp": psx4}

PLATFORM_DEFAULT = {"fc": "fc2bpp", "sfc": "sfc2bpp", "gb": "gb2bpp", "gbc": "gb2bpp",
                    "sms": "sms4bpp", "md": "md4bpp", "ps": "ps4bpp"}


def split_tiles(glyph, w, h, order="row"):
    """글리프를 8x8 타일로 분할. order=row: 좌→우, 위→아래 / col: 위→아래 먼저(8x16 스프라이트형)."""
    tw, th = w // 8, h // 8
    coords = [(tx, ty) for ty in range(th) for tx in range(tw)] if order == "row" else \
             [(tx, ty) for tx in range(tw) for ty in range(th)]
    return [[[glyph[ty * 8 + y][tx * 8 + x] for x in range(8)] for y in range(8)] for tx, ty in coords]


def encode_glyph(glyph, w, h, fmt, order="row"):
    if fmt in LINEAR_FORMATS:
        return LINEAR_FORMATS[fmt](glyph, w, h)
    if w % 8 or h % 8:
        raise ValueError("타일 포맷은 셀 크기가 8의 배수여야 함")
    enc = TILE_FORMATS[fmt]
    return b"".join(enc(t) for t in split_tiles(glyph, w, h, order))
