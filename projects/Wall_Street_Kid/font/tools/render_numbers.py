"""숫자·좁은 구두점 간격 미리보기 -> font/preview/numbers.png (위: 수정 전 build/font.bin, 아래: font/out/font.bin)
프로젝트 루트에서: python font/tools/render_numbers.py"""
import os, sys
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools"))
from romkr.charset import read_charset
chars = read_charset(os.path.join(ROOT, "font", "charset.txt"))
idx = {c: i for i, c in enumerate(chars)}
LINES = ["$500,000  $1,000,000  $5,000,000", "12:30  3.5%  DON'T  1,234.50", "A: 100; B! 7,000원 5,000,000달러"]
S = 3
def load(p):
    return open(p, "rb").read()
def draw(data, lines):
    img = Image.new("RGB", ((34 * 8 + 16) * S, (len(lines) * 16 + 8) * S), (0, 0, 120))
    px = img.load()
    for r, l in enumerate(lines):
        for c, ch in enumerate(l):
            if ch not in idx: continue
            g = data[idx[ch] * 16: idx[ch] * 16 + 16]
            for y in range(16):
                for x in range(8):
                    if g[y] >> (7 - x) & 1:
                        for sy in range(S):
                            for sx in range(S):
                                px[(8 + c * 8 + x) * S + sx, (4 + r * 16 + y) * S + sy] = (255, 255, 255)
    return img
old = draw(load(os.path.join(ROOT, "build", "font.bin")), LINES)
new = draw(load(os.path.join(ROOT, "font", "out", "font.bin")), LINES)
out = Image.new("RGB", (old.width, old.height * 2 + 8), (30, 30, 30))
out.paste(old, (0, 0)); out.paste(new, (0, old.height + 8))
out.save(os.path.join(ROOT, "font", "preview", "numbers.png"))
