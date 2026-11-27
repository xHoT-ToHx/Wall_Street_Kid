"""Wall Street Kid 한글 폰트 생성기 (charset 파일 -> 글리프 bin / tbl / 미리보기).

프로젝트 루트(projects/Wall_Street_Kid)에서 실행:
  python font/tools/build_font.py                      # 기본: 8x16 1bpp, 글리프당 16B
  python font/tools/build_font.py --charset font/charset.txt --out build/font.bin ...
  python font/tools/build_font.py --ttf font/Galmuri7.ttf --size 8 --cell 8x8 --oy 0 \
         --charset font/ui8_charset.txt --out build/font_ui8.bin --tbl-out "" --preview build/font_ui8_preview.png

바이너리 포맷(asm/DESIGN.md "폰트 인터페이스" 확정 전 기본값, 모두 인자로 변경 가능)
- --format 1bpp : 타일 1장 = 8B (행당 1B, MSB=왼쪽 픽셀, 1=글자). --format fc2bpp : 타일 16B(plane0 8B + plane1 8B).
- --cell 8x16   : 글리프 = 위 타일 -> 아래 타일 순(--order row). 1bpp 면 글리프 16B.
- 글리프는 charset 순서대로 연속 배치: bin[i*glyph_bytes:(i+1)*glyph_bytes] = charset 의 i 번째 글자.
- tbl 코드는 --code-start 부터 순차(잠정). --code-bytes 1|2, --skip-low 로 하위 바이트 제외.
검사: 셀 밖으로 잉크가 넘치는 글리프(잘림), 폰트에 없는(빈) 글리프를 보고한다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools"))
from romkr import font as fnt  # noqa: E402
from romkr.charset import read_charset  # noqa: E402
from romkr.tiles import encode_glyph  # noqa: E402


def p(rel):
    return rel if os.path.isabs(rel) else os.path.join(ROOT, rel)


def clipped(chars, ttf, size, w, h, ox, oy):
    """셀을 넉넉히(2배) 키워 렌더해 셀 밖(x>=w 또는 y>=h, x<0 포함 불가) 잉크가 있는 글자를 찾는다."""
    big = fnt.render(chars, ttf, size, w * 2, h * 2, ox, oy)
    bad = []
    for c, bm in zip(chars, big):
        if any(v for row in bm for x, v in enumerate(row) if x >= w) or any(any(row) for row in bm[h:]):
            bad.append(c)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--charset", default="font/charset.txt")
    ap.add_argument("--ttf", default="font/Galmuri11-Condensed.ttf")
    ap.add_argument("--ascii-ttf", default="font/Galmuri11-Bold.ttf",
                    help="ASCII/기호(0x21-0x7E, …·「」) 전용 폰트. 빈 문자열이면 --ttf 사용. 한글은 8px 폭에 Condensed 만 들어가고 "
                         "Condensed 숫자는 4~5px 로 자간이 벌어져 굵은 Bold(6px) 를 쓴다")
    ap.add_argument("--size", type=int, default=12)
    ap.add_argument("--cell", default="8x16")
    ap.add_argument("--ox", type=int, default=0)
    ap.add_argument("--oy", type=int, default=3)
    ap.add_argument("--format", default="1bpp")
    ap.add_argument("--order", default="row")
    ap.add_argument("--fg", type=int, default=1)
    ap.add_argument("--bg", type=int, default=0)
    ap.add_argument("--code-start", default="0x5000", help="잠정: 리드바이트 0x50-0x59(원본 텍스트 미사용 0x37-0x7F 안). 글리프 번호 = 코드 - code-start")
    ap.add_argument("--code-bytes", type=int, default=2)
    ap.add_argument("--skip-low", nargs="*", default=[])
    ap.add_argument("--out", default="build/font.bin")
    ap.add_argument("--tbl-out", default="tables/ko_font.tbl", help='"" 이면 tbl 생략')
    ap.add_argument("--preview", default="build/font_preview.png")
    ap.add_argument("--meta-out", default="", help="글리프 목록 json (선택)")
    ap.add_argument("--narrow-left", default=",.'`;:!\"",
                    help="좁은 구두점: 잉크 왼쪽 끝을 셀 x=0 으로 붙인다(A4: `$500,000` 에서 쉼표 앞이 벌어져 보이던 문제). 빈 문자열이면 생략")
    ap.add_argument("--tag", default="잠정", help="tbl 머리말에 적는 코드 배정 상태")
    ap.add_argument("--overrides", default="font/kr16_ascii_overrides.json",
                    help='8x16 1bpp 글자별 덮어쓰기 {"M": "32자리 hex"} (폰트작업대). 빈 문자열이면 생략')
    a = ap.parse_args()

    w, h = (int(x) for x in a.cell.lower().split("x"))
    chars = read_charset(p(a.charset))
    ttf = p(a.ttf)
    bms = fnt.render(chars, ttf, a.size, w, h, a.ox, a.oy)
    asc_bold = []
    if a.ascii_ttf:
        # Bold 로 그렸을 때 셀(8x16)에 들어가는 글자만 채택. 아래로 넘치면 1~2px 올려 재시도, 안 되면 Condensed 유지.
        for i, c in enumerate(chars):
            if not (ord(c) < 0x80 or c in "…·「」"):
                continue
            for dy in (0, -1, -2):
                if not clipped([c], p(a.ascii_ttf), a.size, w, h, a.ox, a.oy + dy):
                    bms[i] = fnt.render([c], p(a.ascii_ttf), a.size, w, h, a.ox, a.oy + dy)[0]
                    asc_bold.append(c)
                    break
    print("ASCII Bold 채택 %d자, Condensed 유지: %s" % (len(asc_bold), "".join(
        c for c in chars if (ord(c) < 0x80 or c in "…·「」") and c not in asc_bold)))
    for i, c in enumerate(chars):
        if c in a.narrow_left and ord(c) < 0x80:
            bm = bms[i]
            xs = [x for row in bm for x, v in enumerate(row) if v]
            if xs and min(xs) > 0:
                d = min(xs)
                bms[i] = [row[d:] + [0] * d for row in bm]
    empty = [c for c, b in zip(chars, bms) if not any(map(any, b))]
    if empty:
        print("경고: 폰트에 없는(빈) 글자 %d자: %s" % (len(empty), "".join(empty[:60])))
    clip = [c for c in clipped(chars, ttf, a.size, w, h, a.ox, a.oy) if c not in asc_bold]
    print("셀 밖 넘침(잘림) 글자: %d자 %s" % (len(clip), "".join(clip[:60])))

    blob = b"".join(encode_glyph(fnt.colorize(b, a.fg, a.bg), w, h, a.format, a.order) for b in bms)
    gb = len(blob) // max(1, len(chars))
    if a.overrides and (w, h, a.format) == (8, 16, "1bpp") and os.path.exists(p(a.overrides)):
        ov = json.load(open(p(a.overrides), encoding="utf-8"))
        patched, n = bytearray(blob), 0
        for i, c in enumerate(chars):
            if c in ov:
                g = bytes.fromhex(ov[c])
                assert len(g) == gb, f"잘못된 오버라이드 {c!r}"
                patched[i * gb:(i + 1) * gb] = g
                n += 1
        blob = bytes(patched)
        print(f"8x16 오버라이드 {n}자")
    os.makedirs(os.path.dirname(p(a.out)), exist_ok=True)
    open(p(a.out), "wb").write(blob)

    if a.tbl_out:
        start = int(a.code_start, 0)
        skip = {int(x, 0) for x in a.skip_low}
        codes, c = [], start
        while len(codes) < len(chars):
            if a.code_bytes == 1 or (c & 0xFF) not in skip:
                codes.append(c)
            c += 1
        if codes and codes[-1] >= 1 << (8 * a.code_bytes):
            sys.exit("코드 공간 부족")
        os.makedirs(os.path.dirname(p(a.tbl_out)), exist_ok=True)
        with open(p(a.tbl_out), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# 한글 코드표 [{a.tag}] 글리프 순서 = {a.charset}. 코드 배정은 asm/DESIGN.md 폰트 인터페이스 확정 전 잠정값.\n")
            f.write(f"# 생성: font/tools/build_font.py (code-start {a.code_start}, {a.code_bytes}바이트)\n")
            for ch, code in zip(chars, codes):
                f.write(f"{code:0{a.code_bytes * 2}X}={ch}\n")

    if a.preview:
        os.makedirs(os.path.dirname(p(a.preview)), exist_ok=True)
        fnt.preview(bms, p(a.preview), cols=32, scale=2)
    if a.meta_out:
        json.dump({"chars": "".join(chars), "cell": [w, h], "format": a.format, "glyph_bytes": gb},
                  open(p(a.meta_out), "w", encoding="utf-8"), ensure_ascii=False)
    hangul = sum(1 for c in chars if 0xAC00 <= ord(c) <= 0xD7A3)
    print(f"{len(chars)}자 (한글 {hangul}) / 글리프 {gb}B / bin {len(blob)}B -> {a.out}")


if __name__ == "__main__":
    main()
