"""bin 에서 글리프를 디코드해 화면 모의(대사창 28x6, 1행 피치 라벨)를 그린다 -> font/preview/*.png

프로젝트 루트에서:  python font/tools/render_sample.py
- 8x16 대사창: font/charset.txt + build/font.bin (1bpp 8x16). 원본 영어 8x8 폰트(ROM 0x2375)와 같은 창에 나란히.
- 8x8 라벨: font/ui8_charset.txt + build/font_ui8.bin (1bpp 8x8, Galmuri7).
bin 을 다시 읽어 그리므로 인코딩(비트 순서·타일 순서) 검증을 겸한다.
"""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools"))
from romkr.charset import read_charset  # noqa: E402

ROM = os.path.join(ROOT, "rom", "Wall Street Kid (USA).nes")
BG, FG = (0, 0, 120), (255, 255, 255)
CW = 28

SAMPLE = [
    "안녕하세요, 키드! 삼촌께서 남기신",
    "유산은 모두 1,000,000달러입니다.",
    "하지만 $5,000,000 를 30일 안에",
    "불리지 못하면 전부 날아갑니다.",
    "월가의 큰손이 될 준비는 되셨나요?",
    "주식 시장은 냉정합니다. 조심하세요!",
]


def load(binpath, chars, cw, ch_h, fmt_bytes):
    data = open(binpath, "rb").read()
    out = {}
    for i, c in enumerate(chars):
        g = data[i * fmt_bytes:(i + 1) * fmt_bytes]
        rows = []
        for y in range(ch_h):
            b = g[y]
            rows.append([(b >> (7 - x)) & 1 for x in range(8)])
        out[c] = rows
    return out


def orig_font():
    rom = open(ROM, "rb").read()
    o = 0x2375
    tiles = []
    for t in range(0x4A):
        if t < 55:
            tiles.append([[(rom[o + t * 8 + y] >> (7 - x)) & 1 for x in range(8)] for y in range(8)])
        else:
            tiles.append([[0] * 8 for _ in range(8)])
    return tiles


ORIG_MAP = {}
for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    ORIG_MAP[c] = i
ORIG_MAP.update({" ": 0x49, "(": 0x24, ")": 0x25, "'": 0x26, '"': 0x27, ",": 0x29, "$": 0x2A, "!": 0x2B,
                 "?": 0x2C, "-": 0x2D, ":": 0x2E, ".": 0x30, "/": 0x31, "%": 0x35, "&": 0x36})


def put(px, x0, y0, rows, scale, fg=FG):
    for y, r in enumerate(rows):
        for x, v in enumerate(r):
            if v:
                for sy in range(scale):
                    for sx in range(scale):
                        px[(x0 + x) * scale + sx, (y0 + y) * scale + sy] = fg


def wrap(text, width):
    lines, cur = [], ""
    for ch in text:
        cur += ch
    return [cur[i:i + width] for i in range(0, len(cur), width)]


def dialog_8x16(glyphs, lines, scale=3):
    W, H = CW * 8 + 16, 6 * 16 + 16
    img = Image.new("RGB", (W * scale, H * scale), BG)
    px = img.load()
    for r, line in enumerate(lines):
        for c, ch in enumerate(line[:CW]):
            if ch == " ":
                continue
            put(px, 8 + c * 8, 8 + r * 16, glyphs[ch], scale)
    return img


def dialog_orig(tiles, lines, scale=3):
    W, H = CW * 8 + 16, 6 * 16 + 16
    img = Image.new("RGB", (W * scale, H * scale), BG)
    px = img.load()
    for r, line in enumerate(lines):
        for c, ch in enumerate(line[:CW]):
            t = ORIG_MAP.get(ch)
            if t is None or ch == " ":
                continue
            put(px, 8 + c * 8, 8 + r * 16, tiles[t], scale)
    return img


def stack(imgs, gap=8):
    W = max(i.width for i in imgs)
    H = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGB", (W, H), (30, 30, 30))
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def main():
    out = os.path.join(ROOT, "font", "preview")
    os.makedirs(out, exist_ok=True)
    chars = read_charset(os.path.join(ROOT, "font", "charset.txt"))
    g16 = load(os.path.join(ROOT, "build", "font.bin"), chars, 8, 16, 16)
    missing = {c for l in SAMPLE for c in l if c != " " and c not in g16}
    if missing:
        print("샘플에 charset 밖 글자:", "".join(missing))
        SAMP = [("".join(c if c in g16 or c == " " else " " for c in l)) for l in SAMPLE]
    else:
        SAMP = SAMPLE
    ko = dialog_8x16(g16, SAMP)
    eng = dialog_orig(orig_font(), ["WELCOME TO WALL STREET, KID.", "UNCLE LEFT YOU $1,000,000.",
                                    "BUT IF YOU DON'T TURN IT INTO", "$5,000,000 IN 30 DAYS, IT ALL",
                                    "GOES TO CHARITY. READY?", "THE MARKET IS COLD. BE CAREFUL!"])
    stack([eng, ko]).save(os.path.join(out, "dialog_28x6.png"))
    print("dialog_28x6.png")

    # 빽빽한 글자(겹받침·ㅐㅔ·ㅢ 계열) 8x16 가독성 확인
    dense = ["꽝뷁쫿읊뿕짧웨왜쉥퀭괜뽂휑씻닭읽",
             "않았없값밝섞젊훑핥꿇뺨쏟쐈쌩쑥뚫",
             "주가가 폭등하면 즉시 팔아야 합니다",
             "빚을 갚지 못하면 압류당합니다 !?"]
    d = dialog_8x16(g16, [("".join(c if c in g16 else " " for c in l)) for l in dense] + ["", ""])
    d.save(os.path.join(out, "dense_8x16.png"))
    print("dense_8x16.png")

    # 1행 피치 라벨(8x8)
    p8 = os.path.join(ROOT, "font", "ui8_charset.txt")
    b8 = os.path.join(ROOT, "font", "out", "font_ui8.bin")
    if not os.path.exists(b8):
        b8 = os.path.join(ROOT, "build", "font_ui8.bin")
    if os.path.exists(p8) and os.path.exists(b8):
        c8 = read_charset(p8)
        g8 = load(b8, c8, 8, 8, 8)
        orig = orig_font()
        scale = 3
        rows = [
            ("  STOCK       CUR. ORIG. LOTS ", "  종목        현재 매입 수량  "),
            ("  STOCK        PRICE  %CHANGE ", "  종목         가격   등락률 "),
            (" CASH:", " 현금:"),
            (" STOCKS:", " 보유:"),
            ("SUN MON TUE WED THU FRI SAT", "일  월  화  수  목  금  토 "),
            ("SPECULATIVE  BLUE CHIP", "투기주      우량주"),
            ("", "주식 매도  주식 매수  정보"),
            ("", "포트폴리오  대출 신청 대출 상환"),
            ("", "경매 대금 소풍 쇼핑 축제 취소"),
            ("", "예 아니오 둘 다 싫어요! 수영 헬스 등산"),
            ("", "래리 랄프 닥 스탠리 코니 캘 프리실라"),
            ("", "디온 아트 줄리 오스틴 파멜라 테드 루스"),
            ("", "주식을 팔려면 종목을 고르십시오."),
            ("", "보유 주식 없음  현금이 부족합니다"),
            ("", "포트폴리오가 가득 찼습니다"),
            ("", "몇 랏입니까? (까지) 성장주 경기순환주"),
            ("", "패스워드를 입력하십시오 패스워드 오류"),
            ("", "일생일대의 도전을 계속할 준비를 하십시오"),
            ("", "당신의 패스워드 시작가 현재가 등락률"),
            ("", "«주가» «종목 분류» «기업 개요» 등장인물"),
        ]
        img = Image.new("RGB", ((28 * 8 + 16) * scale, (len(rows) * 2 * 8 + 16) * scale), BG)
        px = img.load()
        for r, (en, kr) in enumerate(rows):
            for c, ch in enumerate(en):
                t = ORIG_MAP.get(ch)
                if t is not None and ch != " ":
                    put(px, 8 + c * 8, 8 + r * 16, orig[t], scale)
            for c, ch in enumerate(kr):
                if ch == " ":
                    continue
                if ch in g8:
                    put(px, 8 + c * 8, 8 + r * 16 + 8, g8[ch], scale)
                elif ch in ORIG_MAP:
                    put(px, 8 + c * 8, 8 + r * 16 + 8, orig[ORIG_MAP[ch]], scale)
        img.save(os.path.join(out, "ui8_labels.png"))
        print("ui8_labels.png")
        # 전체 글리프 격자(16열, 4배, 글자 사이 1칸 간격 없음 = 실제 화면 밀도)
        cols = 16
        rws = (len(c8) + cols - 1) // cols
        im2 = Image.new("RGB", ((cols * 8 + 16) * 4, (rws * 8 + 16) * 4), BG)
        px2 = im2.load()
        for i, ch in enumerate(c8):
            put(px2, 8 + (i % cols) * 8, 8 + (i // cols) * 8, g8[ch], 4)
        im2.save(os.path.join(out, "ui8_all.png"))
        print("ui8_all.png")


if __name__ == "__main__":
    main()
