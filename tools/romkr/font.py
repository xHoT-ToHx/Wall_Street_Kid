"""TTF/OTF(픽셀 폰트 권장: Galmuri, 둥근모 등)로 한글 글리프를 렌더해 플랫폼 타일로 변환."""
from __future__ import annotations

from .tiles import encode_glyph


def render(chars, ttf, size, cell_w, cell_h, ox=0, oy=0, threshold=128):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(ttf, size)
    glyphs = []
    for ch in chars:
        img = Image.new("L", (cell_w, cell_h), 0)
        ImageDraw.Draw(img).text((ox, oy), ch, font=font, fill=255)
        px = img.load()
        glyphs.append([[1 if px[x, y] >= threshold else 0 for x in range(cell_w)] for y in range(cell_h)])
    return glyphs


def colorize(bm, fg=1, bg=0, shadow=None):
    h, w = len(bm), len(bm[0])
    out = [[fg if bm[y][x] else bg for x in range(w)] for y in range(h)]
    if shadow is not None:
        for y in range(h):
            for x in range(w):
                if not bm[y][x] and ((x > 0 and bm[y][x - 1]) or (y > 0 and bm[y - 1][x])
                                     or (x > 0 and y > 0 and bm[y - 1][x - 1])):
                    out[y][x] = shadow
    return out


def glyph_width(bm):
    """VWF용 실제 폭(오른쪽 끝 픽셀 + 1)."""
    w = 0
    for row in bm:
        for x, v in enumerate(row):
            if v:
                w = max(w, x + 1)
    return w


def assign_codes(n, start, nbytes, skip_low=()):
    codes, c = [], start
    while len(codes) < n:
        if nbytes == 1 or (c & 0xFF) not in skip_low:
            codes.append(c)
        c += 1
        if c >= 1 << (8 * nbytes):
            raise ValueError("코드 공간 부족")
    return codes


def build(chars, ttf, size, cell_w, cell_h, fmt, code_start, code_bytes=2, ox=0, oy=0,
          fg=1, bg=0, shadow=None, order="row", skip_low=(), threshold=128):
    bms = render(chars, ttf, size, cell_w, cell_h, ox, oy, threshold)
    codes = assign_codes(len(chars), code_start, code_bytes, skip_low)
    blob = bytearray()
    tbl, widths = [], bytearray()
    for ch, bm, code in zip(chars, bms, codes):
        blob += encode_glyph(colorize(bm, fg, bg, shadow), cell_w, cell_h, fmt, order)
        tbl.append(f"{code:0{code_bytes * 2}X}={ch}")
        widths.append(min(255, glyph_width(bm) + 1))
    return bytes(blob), tbl, bytes(widths), bms


def preview(bms, path, cols=16, scale=3):
    from PIL import Image
    h, w = len(bms[0]), len(bms[0][0])
    rows = (len(bms) + cols - 1) // cols
    img = Image.new("L", (cols * (w + 1), rows * (h + 1)), 40)
    px = img.load()
    for i, bm in enumerate(bms):
        bx, by = (i % cols) * (w + 1), (i // cols) * (h + 1)
        for y in range(h):
            for x in range(w):
                px[bx + x, by + y] = 255 if bm[y][x] else 0
    img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(path)
