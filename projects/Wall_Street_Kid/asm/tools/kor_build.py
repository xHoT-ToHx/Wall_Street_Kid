"""kor_build.py - Wall Street Kid 한글 엔진 빌드 보조 (projects/Wall_Street_Kid 에서 실행).

  python asm/tools/kor_build.py tables             → build/kor_tables.asm (엔진 뱅크 데이터: 슬롯 표, ASCII→글리프, 테두리 사본)
  python asm/tools/kor_build.py font <rom>         → build/font.bin 을 뱅크 8-10 에 배치
  python asm/tools/kor_build.py text <rom> [--check-only] [--report build/kor_text_report.txt]
        → scripts/dialog_b4.json, news_b6.json 의 ko 를 2바이트 코드로 인코딩해 뱅크 12/13(+넘침 11/14)에 삽입, 포인터 갱신
          + 슬롯 할당 모의 검사(화면에 보이는 글자의 슬롯이 덮이면 경고)

문자 코드(asm/DESIGN.md §4): 1바이트 원본(제어 FB-FF, 공백 49) + 한글·ASCII 글리프 = 2바이트 [0x50+hi][lo] (글리프 번호 = tables/ko_font.tbl 코드-0x5000)
넘침: [4F bank lo hi] = 다른 뱅크로 이어 읽기.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.abspath(os.path.join(PROJ, "..", "..", "tools")))
from romkr.tbl import Table  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ORIG_ROM = os.path.join(PROJ, "rom", "Wall Street Kid (USA).nes")
FONT_BIN = os.path.join(PROJ, "build", "font.bin")
KO_TBL = os.path.join(PROJ, "tables", "ko_font.tbl")
JA_TBL = os.path.join(PROJ, "tables", "ja.tbl")

NSLOT = 107
REFRESH = 40      # 적중한 슬롯이 다음 할당 위치에서 이 거리 안이면 새 슬롯으로 옮김 (kor_engine.asm 과 같게)
SLOT_TOPS = list(range(0x4A, 0xFF, 2))[:91] + list(range(0x20, 0x40, 2))   # A: 4A..FE (91) / B: 20..3E (16)
assert len(SLOT_TOPS) == NSLOT
FONT_BANK0 = 8
FONT_BANKS = 3
PER_BANK = 1018   # 뱅크당 글리프 수: 끝 6칸($BFA0-$BFFF)은 공유 코드(kcopy)·뱅크 표식


def gnum(i):
    """font.bin 글리프 순번 i → 엔진 글리프 번호 g (뱅크 8+(g>>10), $8000+(g&$3FF)*16)"""
    return (i // PER_BANK) * 1024 + i % PER_BANK
TEXT = [  # 블록, 원본 뱅크, 새 뱅크, 넘침 뱅크
    ("dialog_b4", 4, 12, 11),
    ("news_b6", 6, 13, 14),
]
SPLITTOP = 16
SUBST = {"«": "「", "»": "」", "‥": "…", "▶": ">"}   # 8x16 글리프가 없는 원본 기호의 대체 글리프


def bank_off(bank, cpu):
    return 0x10 + bank * 0x4000 + (cpu & 0x3FFF)


def pint(x):
    return int(x, 0) if isinstance(x, str) else x


def load_ko():
    """코드 테이블: 제어·공백 1바이트 우선, 나머지는 ko_font 2바이트."""
    t = Table()
    for k, s, end in ((b"\xff", "<END>", True), (b"\xfe", "\n", False), (b"\xfd", "<PAGE>", False),
                      (b"\xfc", "<WAIT>", False), (b"\xfb", "<VAR>", False), (b"\x49", " ", False)):
        t.add(k, s, end)
    ko = Table.load(KO_TBL)
    for k, s in ko.dec.items():
        code = int.from_bytes(k, "big")
        n = gnum(code - 0x5000)
        if not 0 <= n < FONT_BANKS * 1024:
            raise SystemExit(f"ko_font.tbl 코드 범위 밖: {k.hex()}")
        t.add(bytes([0x50 + (n >> 8), n & 0xFF]), s)
    ja = Table.load(JA_TBL)          # 폰트에 없는 원본 기호(« » 등)는 1바이트 원본 코드로
    for k, s in ja.dec.items():
        if len(k) == 1 and k[0] < 0x37:
            t.add(k, s)
    return t, ko


# ------------------------------------------------------------------ tables
def cmd_tables(a):
    src = open(ORIG_ROM, "rb").read()
    _, ko = load_ko()
    ja = Table.load(JA_TBL)
    lo, hi = [], []
    for c in range(0x37):
        ch = ja.dec.get(bytes([c]))
        ch = SUBST.get(ch, ch)
        k = ko.enc.get(ch) if ch else None
        if k is None:
            lo.append(0xFF), hi.append(0xFF)
        else:
            n = gnum(int.from_bytes(k, "big") - 0x5000)
            lo.append(n & 0xFF), hi.append(n >> 8)
    # $1000 타일 0x40(빈 감지 스프라이트) + 0x41-0x49 = BG $0000 테두리·공백 2bpp (bank0 $A2D5 = 파일 0x22E5, 업로드표 $801F)
    copy = bytes(16) + src[0x22E5:0x22E5 + 9 * 16]
    assert len(copy) == 160
    out = ["; 자동 생성: asm/tools/kor_build.py tables (수정 금지)",
           "SLOTTOP:", db(SLOT_TOPS), "ASC_LO:", db(lo), "ASC_HI:", db(hi), "COPYIMG:", db(copy)]
    os.makedirs(os.path.join(PROJ, "build"), exist_ok=True)
    p = os.path.join(PROJ, "build", "kor_tables.asm")
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    miss = [f"{c:02X}" for c in range(0x37) if hi[c] == 0xFF]
    print(f"tables: {p} (슬롯 {NSLOT}, ASCII 글리프 없음: {' '.join(miss) or '-'})")


def db(bs):
    lines = []
    for i in range(0, len(bs), 16):
        lines.append("  .db " + ",".join(f"${b:02X}" for b in bs[i:i + 16]))
    return "\n".join(lines)


# ------------------------------------------------------------------ font
def cmd_font(a):
    rom = bytearray(open(a.rom, "rb").read())
    f = open(FONT_BIN, "rb").read()
    n = len(f) // 16
    if n > FONT_BANKS * PER_BANK:
        raise SystemExit(f"글리프 {n} > {FONT_BANKS * PER_BANK}")
    for b in range(FONT_BANKS):
        chunk = f[b * PER_BANK * 16:(b + 1) * PER_BANK * 16]
        o = bank_off(FONT_BANK0 + b, 0x8000)
        rom[o:o + len(chunk)] = chunk
    open(a.rom, "wb").write(rom)
    print(f"font: {n}자 {len(f)}B → 뱅크 {FONT_BANK0}-{FONT_BANK0 + (n - 1) // PER_BANK} (뱅크당 {PER_BANK})")


# ------------------------------------------------------------------ text
def tokens(data):
    """인코딩된 바이트 → (kind, value) 목록. kind: g(글리프 n) / c(1바이트 문자) / nl / wait / page / var / end"""
    i, out = 0, []
    while i < len(data):
        b = data[i]
        if 0x50 <= b < 0x60:
            out.append(("g", (b - 0x50) << 8 | data[i + 1]))
            i += 2
            continue
        out.append({0xFF: ("end", 0), 0xFE: ("nl", 0), 0xFD: ("page", 0), 0xFC: ("wait", 0),
                    0xFB: ("var", 0)}.get(b, ("c", b)))
        i += 1
    return out


def simulate(data, width=28, lines=6):
    """엔진과 같은 원형 할당을 모의. 보이는 칸의 슬롯이 덮이면 위반."""
    slots = [None] * NSLOT     # 슬롯 → 글리프
    nxt = 0
    screen = [[]]              # 줄마다 슬롯 번호 목록
    x = 0
    worst = 0
    viol = []
    uniq_page = set()

    def newline():
        nonlocal x
        x = 0
        screen.append([])
        if len(screen) > lines:
            screen.pop(0)

    for kind, v in tokens(data):
        if kind == "g":
            uniq_page.add(v)
            worst = max(worst, len(uniq_page))
            s = slots.index(v) if v in slots else None
            if s is not None and (s - nxt) % NSLOT < REFRESH:   # 곧 덮일 슬롯이면 새로 할당(엔진과 동일)
                slots[s] = None
                s = None
            if s is None:
                s = nxt
                if any(s in ln for ln in screen):
                    viol.append(v)
                slots[s] = v
                nxt = (nxt + 1) % NSLOT
            if x >= width:
                newline()
            screen[-1].append(s)
            x += 1
        elif kind == "c":
            if x >= width:
                newline()
            x += 2 if v >= 0x80 else 1
        elif kind == "var":
            x += 10
        elif kind == "nl":
            newline()
        elif kind == "page":
            slots = [None] * NSLOT
            nxt = 0
            screen[:] = [[]]
            x = 0
            uniq_page = set()
    return worst, viol


def cmd_text(a):
    rom = bytearray(open(a.rom, "rb").read()) if a.rom else None
    spec = json.load(open(os.path.join(PROJ, "spec.json"), encoding="utf-8"))
    blocks = {b["name"]: b for b in spec["blocks"]}
    t, _ = load_ko()
    report = []
    total_viol = 0
    for name, ob, nb, xb in TEXT:
        b = blocks[name]
        ents = json.load(open(os.path.join(PROJ, "scripts", name + ".json"), encoding="utf-8"))
        reg = b["text_region"]
        fbase = pint(b["address_map"]["file_base"])
        r0, r1 = pint(reg["start"]) - fbase, pint(reg["end"]) - fbase     # 뱅크 내 오프셋
        r1 = min(r1, 0x3FF8)          # $BFF9 = 뱅크 번호 표식(kor_engine.asm BANKID)
        cur, xcur = r0, 0
        place = {}
        enc = {}
        for e in ents:
            if "alias_of" in e or "error" in e:
                continue
            text = e.get("ko") or e["ja"]
            if not e.get("ko"):
                report.append(f"{e['id']}: 미번역 → 원문")
                data = Table.load(JA_TBL).encode(text)
            else:
                data = t.encode(text)
            if data[-1:] != b"\xff":
                raise SystemExit(f"{e['id']}: <END> 로 끝나지 않음")
            enc[e["id"]] = data
            worst, viol = simulate(data)
            if viol:
                total_viol += 1
                report.append(f"{e['id']}: 슬롯 덮어씀 {len(viol)}회 (페이지 최대 고유 {worst})")
        # 배치: 1차 뱅크에 순서대로, 안 들어가면 4바이트 스텁 + 넘침 뱅크
        for e in ents:
            if e["id"] not in enc:
                continue
            data = enc[e["id"]]
            if cur + len(data) - 1 <= r1:
                place[e["id"]] = 0x8000 + cur
                if rom is not None:
                    o = bank_off(nb, 0x8000 + cur)
                    rom[o:o + len(data)] = data
                cur += len(data)
            else:
                xlim = (UI_OVF_BASE - 0x8000) if xb == UI_OVF_BANK else 0x3FF0   # 뱅크 11 의 $A000- 는 UI 넘침
                if xcur + len(data) > xlim or cur + 3 > r1:
                    raise SystemExit(f"{name}: 넘침 뱅크도 부족 ({e['id']})")
                stub = bytes([0x4F, xb, (0x8000 + xcur) & 0xFF, (0x8000 + xcur) >> 8])
                place[e["id"]] = 0x8000 + cur
                if rom is not None:
                    o = bank_off(nb, 0x8000 + cur)
                    rom[o:o + 4] = stub
                    o = bank_off(xb, 0x8000 + xcur)
                    rom[o:o + len(data)] = data
                cur += 4
                xcur += len(data)
        if rom is not None:
            o = bank_off(nb, 0x8000 + cur)
            rom[o:bank_off(nb, 0x8000 + r1) + 1] = bytes(r1 + 1 - cur)
        # 포인터 (원본 레이아웃 파일 오프셋; 뱅크 7 은 뱅크 15 로)
        for e in ents:
            if "error" in e:
                continue
            v = place[e.get("alias_of", e["id"])]
            pa = pint(e["ptr_addr"])
            if pa >= 0x1C010:
                pa += 0x20000
            if rom is not None:
                if "ptr_hi" in e:
                    ph = pint(e["ptr_hi"])
                    ph = ph + 0x20000 if ph >= 0x1C010 else ph
                    rom[pa] = v & 0xFF
                    rom[ph] = v >> 8
                else:
                    rom[pa:pa + 2] = v.to_bytes(2, "little")
        used = cur - r0
        report.insert(0, f"{name}: 뱅크 {nb} {used}/{r1 + 1 - r0}B, 넘침 뱅크 {xb} {xcur}B, 문자열 {len(enc)}")
    report.insert(0, f"슬롯 모의 위반 문자열 {total_viol}개 (슬롯 {NSLOT})")
    txt = "\n".join(report)
    print(txt if len(report) < 40 else "\n".join(report[:40]) + f"\n... ({len(report)}줄)")
    if a.report:
        open(a.report, "w", encoding="utf-8").write(txt + "\n")
    if rom is not None:
        open(a.rom, "wb").write(rom)


# ------------------------------------------------------------------ ui (대사창 외 화면, asm/DESIGN.md §10)
# 1행 피치 화면 문자열: 한글 = [60 ii] (8x8 글리프 ii, BG $0000 의 장면별 빈 타일에 동적 배치)
# 2행 피치 창(기업 개요 stock_desc_b5): 대사와 같은 8x16 2바이트 코드
UI8_BLOCKS = ["menu_b7", "stock_ui_b5", "stock_names_b5", "stock_cat_b5", "password_b7", "weekdays",
              "status_cash", "status_stocks"]
UI16_BLOCKS = ["stock_desc_b5"]
PASSWORD_KO = True           # 패스워드 화면 = 홈 장면 CHR(맵0 풀 36) 위라 8x8 경로 사용 가능(에뮬 확인, DESIGN §10.4)
UI_OVF_BANK = 11             # 넘침 뱅크(대사 넘침과 공유: 대사는 $8000-, UI 는 $A000-)
UI_OVF_BASE = 0xA000
UI_OVF_END = 0xBF9F          # $BFA0- 는 kcopy 사본 없음(뱅크 11)이지만 $BFF9 표식 보호
LABEL_TILE0 = 0x4A           # 상태창 라벨(CASH:/STOCKS:) 고정 타일 0x4A-0x4D
POOL_LO, POOL_HI = 0x4E, 0xDE   # 동적 8x8 풀 범위(0xDF-0xFF 는 idx6/7 이 쓰므로 제외)
POOL_MAX = 80                # RAM UGLY[80]
MENU_CODE_RESERVE = 96       # menu_b7 영역(고정 뱅크 $E017-$E121) 끝 96B = 엔진 고정부 2 (kor_engine.asm korig·kq·hkpre·kwdbox, $E0C2-$E121)
NOP_CODE = 0x4E              # 아무것도 그리지 않고 커서도 안 움직이는 1바이트(고정 길이 문자열 채움용, 요일)
UI8_TTF = os.path.join(PROJ, "font", "Galmuri7.ttf")
UI8_OFFICIAL = os.path.join(PROJ, "font", "ui8_charset.txt")
UI8_BIN = os.path.join(PROJ, "build", "font_ui8.bin")


def is_hangul(c):
    return 0xAC00 <= ord(c) <= 0xD7A3


def ui_entries(name):
    return json.load(open(os.path.join(PROJ, "scripts", name + ".json"), encoding="utf-8"))


def ui8_text(e, name):
    if name == "password_b7" and not PASSWORD_KO:
        return None
    return e.get("ko") or None


def ui8_charset():
    seen = []
    for name in UI8_BLOCKS:
        for e in ui_entries(name):
            t = ui8_text(e, name)
            if t is None and name == "password_b7":
                t = e.get("ko") or ""          # 글자 목록에는 포함(나중에 켤 때 재생성 불필요)
            for c in t or "":
                if is_hangul(c) and c not in seen:
                    seen.append(c)
    return seen


def scene_maps(src):
    """장면 그림 맵(bank3 $9020 14x14 x18, $9FE0 28x14 big0) → 맵별 사용 타일 집합 (DESIGN §10.2)"""
    b3 = lambda c: 0x10 + 3 * 0x4000 + (c - 0x8000)
    maps = []
    for t in range(0x12):
        o = b3(0x9020 + t * 196)
        maps.append(set(src[o:o + 196]))
    o = b3(0x9FE0)
    maps.append(set(src[o:o + 392]))
    return maps


def cmd_ui(a):
    from romkr import font as fnt
    src = open(ORIG_ROM, "rb").read()
    rom = bytearray(open(a.rom, "rb").read())
    ja = Table.load(JA_TBL)
    t16, ko = load_ko()
    report = []

    # ---- 8x8 글리프 세트: 정본 = font/ui8_charset.txt 순서 + build/font_ui8.bin (font/tools/build_font.py 가 commands 에서 생성)
    #      번역문에서 자동 수집한 글자(build/ui8_charset_auto.txt)는 누락 검사용
    from romkr.charset import read_charset
    chars = read_charset(UI8_OFFICIAL)
    if len(chars) > 255:
        raise SystemExit(f"8x8 글자 {len(chars)} > 255")
    font8 = open(UI8_BIN, "rb").read()
    if len(font8) != len(chars) * 8:
        raise SystemExit(f"{UI8_BIN} 크기 {len(font8)} != {len(chars)}자 x 8B (build_font.py 8x8 1bpp 확인)")
    idx8 = {c: i for i, c in enumerate(chars)}
    used = ui8_charset()
    open(os.path.join(PROJ, "build", "ui8_charset_auto.txt"), "w", encoding="utf-8").write(chr(10).join(used) + chr(10))
    miss = [c for c in used if c not in idx8]
    if miss:
        raise SystemExit("font/ui8_charset.txt 에 없는 글자(font-engineer 추가 필요): " + "".join(miss))
    report.append(f"8x8 글자 {len(chars)}자 (정본 font/ui8_charset.txt, 번역 사용 {len(used)}자 누락 0)")
    # 8x8 → 8x16 글리프 번호(2행 피치 분할 창에서 <VAR> 요일 등이 섞일 때)
    g_lo, g_hi = [], []
    for c in chars:
        k = ko.enc.get(c)
        if k is None:
            g_lo.append(0xFF), g_hi.append(0xFF)
            report.append(f"8x16 폰트에 없음: {c}")
        else:
            n = gnum(int.from_bytes(k, "big") - 0x5000)
            g_lo.append(n & 0xFF), g_hi.append(n >> 8)

    # ---- 상태창 라벨: 고정 타일
    labels = {}
    for name in ("status_cash", "status_stocks"):
        for c in (ui_entries(name)[0].get("ko") or ""):
            if is_hangul(c) and c not in labels:
                labels[c] = LABEL_TILE0 + len(labels)
    if len(labels) > 4:
        raise SystemExit(f"상태창 라벨 고정 타일 {len(labels)} > 4 (0x4A-0x4D)")
    labimg = bytearray()
    for c in sorted(labels, key=labels.get):
        labimg += bytes(8) + font8[idx8[c] * 8:idx8[c] * 8 + 8]      # 2bpp: plane0=0, plane1=글자 (원본 폰트와 같은 색)
    labimg += bytes(64 - len(labimg))

    # ---- 장면별 풀
    # QA V2: 맵이 참조하지 않아도 로드된 타일은 애니메이션 패치로 쓰일 수 있다(큰 맵 래리 얼굴 0x4C-0x5B, $D402).
    #   맵 1-$11: 로드 범위(CHR 항목 8+t, 0x60-) 전체 제외. 맵 0(홈, 0x50-0xFF 전부 로드): 로드 범위 안 미참조 타일만 사용
    #   (장면 로더의 패치는 장면 $13 만 — $D3AE, 정적 확인). 큰 맵($29, 0x4C-0xFF): 풀 없음(라벨도 안 올림 — 엔진 eng_chr).
    maps = scene_maps(src)
    pools = []
    for t, m in enumerate(maps):
        if t == 0x12:
            pools.append([])
            continue
        idx = 8 + t
        b = 0 if idx < 0x11 else 1
        o = 0x10 + b * 0x4000 + 0x10 + (idx - (0, 0x11)[b]) * 5
        lo = (src[o + 3] | src[o + 4] << 8) // 16
        loaded = set(range(lo, lo + src[o])) if t else set()
        p = [x for x in range(POOL_LO, POOL_HI + 1) if x not in m and x not in loaded][:POOL_MAX]
        pools.append(p)
    report.append("장면별 8x8 풀: " + " ".join(f"{i:X}:{len(p)}" for i, p in enumerate(pools)))

    # ---- 인코딩
    def enc8(text, eid):
        out = bytearray()
        i = 0
        while i < len(text):
            if text[i] == "<":
                j = text.index(">", i)
                tok = text[i:j + 1]
                out.append({"<END>": 0xFF, "<PAGE>": 0xFD, "<WAIT>": 0xFC, "<VAR>": 0xFB}[tok])
                i = j + 1
                continue
            c = text[i]
            if c == "\n":
                out.append(0xFE)
            elif c == " ":
                out.append(0x49)
            elif is_hangul(c):
                out += bytes([0x60, idx8[c]])
            else:
                k = ja.enc.get(c)
                if k is None or len(k) != 1 or k[0] >= 0x37:
                    raise SystemExit(f"{eid}: 1행 화면에서 쓸 수 없는 글자 {c!r}")
                out += k
            i += 1
        return bytes(out)

    def cells(text):
        return [len(ln) for ln in re.sub(r"<[^>]*>", "", text).split("\n")]

    ovf = UI_OVF_BASE

    def put_ovf(data, eid):
        nonlocal ovf
        if ovf + len(data) - 1 > UI_OVF_END:
            raise SystemExit(f"UI 넘침 뱅크 부족 ({eid})")
        o = bank_off(UI_OVF_BANK, ovf)
        rom[o:o + len(data)] = data
        addr = ovf
        ovf += len(data)
        return addr

    def remap(off):          # 원본 파일 오프셋 → 확장 롬 (고정 뱅크 7 → 15)
        return off + 0x20000 if off >= 0x1C010 else off

    spec = json.load(open(os.path.join(PROJ, "spec.json"), encoding="utf-8"))
    blocks = {b["name"]: b for b in spec["blocks"]}
    for name in [n for n in UI8_BLOCKS if blocks[n]["type"] == "pointer"] + UI16_BLOCKS:
        b = blocks[name]
        ents = ui_entries(name)
        fbase = pint(b["address_map"]["file_base"])
        cbase = pint(b["address_map"]["cpu_base"])
        enc = {}
        for e in ents:
            if "alias_of" in e or "error" in e:
                continue
            text = e.get("ko") if name in UI16_BLOCKS else ui8_text(e, name)
            if not text:
                continue
            enc[e["id"]] = t16.encode(text) if name in UI16_BLOCKS else enc8(text, e["id"])
            if enc[e["id"]][-1:] != b"\xff":
                raise SystemExit(f"{e['id']}: <END> 로 끝나지 않음")
        if not enc:
            report.append(f"{name}: 한글 없음 → 원문 유지")
            continue
        if name == "password_b7":
            # 제자리 스텁: 원래 문자열 자리(문자표와 섞여 있음)에 [4F bank lo hi], 본문은 넘침 뱅크. 포인터 불변.
            for e in ents:
                if e["id"] not in enc:
                    continue
                if e["orig_bytes"] < 4:
                    raise SystemExit(f"{e['id']}: 원래 자리 {e['orig_bytes']}B < 스텁 4B")
                ad = put_ovf(enc[e["id"]], e["id"])
                o = remap(pint(e["offset"]))
                rom[o:o + 4] = bytes([0x4F, UI_OVF_BANK, ad & 0xFF, ad >> 8])
            report.append(f"{name}: 제자리 스텁 {len(enc)}개 → 뱅크 {UI_OVF_BANK}")
            continue
        reg = b["text_region"]
        r0, r1 = remap(pint(reg["start"])), remap(pint(reg["end"]))
        bank_lim = (r0 - 0x10) // 0x4000 * 0x4000 + 0x10 + 0x3FF8      # $BFF9 뱅크 표식 보호
        r1 = min(r1, bank_lim)
        if name == "menu_b7" and r1 > 0x3E131 - MENU_CODE_RESERVE:    # spec(gen_spec.py)이 이미 끝 32B 를 뺐는지 확인
            raise SystemExit("menu_b7 text_region 이 엔진 예약($E102-$E121)과 겹침 — tools/gen_spec.py 확인")
        # 안전 검사(QA V1): 삽입 영역 안에서 문자열이 아닌 원본 데이터(0 이 아닌 바이트)는 덮지 않는다
        cov = set()
        for e in ents:
            if "offset" in e and "orig_bytes" in e:
                o = pint(e["offset"])
                cov.update(range(o, o + e["orig_bytes"]))
        raw = [x for x in range(pint(reg["start"]), min(pint(reg["end"]), r1 - (remap(0x1C010) - 0x1C010 if r0 >= 0x3C010 else 0)) + 1)
               if x not in cov and src[x] != 0]
        if raw:
            raise SystemExit(f"{name}: 삽입 영역 안에 문자열이 아닌 원본 데이터 0x{raw[0]:X}-0x{raw[-1]:X} — tools/gen_spec.py 영역 조정 필요")
        cur = r0
        place = {}
        nstub = 0
        # 이름표(menu_b7 의 $DCA4/$DDDB 표, 원래 PPU 레코드로 원시 복사 → 엔진 eng_ntag 가 변환)는 4F 스텁 불가 → 먼저 배치
        is_ntag = lambda e: name == "menu_b7" and pint(e["ptr_addr"]) >= 0x1DC00
        # 넘침 계획: 영역에 다 안 들어가면 (이름표 제외) 큰 문자열부터 4B 스텁 + 넘침 뱅크로 옮긴다
        order = [e for e in sorted(ents, key=lambda e: 0 if is_ntag(e) else 1) if e["id"] in enc]
        size = {e["id"]: len(enc[e["id"]]) for e in order}
        cap = r1 + 1 - cur
        stubbed = set()
        for e in sorted([e for e in order if not is_ntag(e)], key=lambda e: -size[e["id"]]):
            if sum(4 if i in stubbed else n for i, n in size.items()) <= cap:
                break
            if size[e["id"]] > 4:
                stubbed.add(e["id"])
        for e in order:
            data = enc[e["id"]]
            if e["id"] in stubbed:
                ad = put_ovf(data, e["id"])
                data = bytes([0x4F, UI_OVF_BANK, ad & 0xFF, ad >> 8])
                nstub += 1
            if cur + len(data) - 1 > r1:
                raise SystemExit(f"{name}: 자리 부족 ({e['id']})")
            rom[cur:cur + len(data)] = data
            place[e["id"]] = cur
            cur += len(data)
        # 번역 안 된(원문 유지) 항목도 영역을 다시 쓰므로 원문 바이트로 같이 배치
        for e in ents:
            if "alias_of" in e or "error" in e or e["id"] in enc:
                continue
            data = ja.encode(e["ja"])
            if cur + len(data) - 1 > r1:
                data_ad = put_ovf(data, e["id"])
                rom[cur:cur + 4] = bytes([0x4F, UI_OVF_BANK, data_ad & 0xFF, data_ad >> 8])
                place[e["id"]] = cur
                cur += 4
            else:
                rom[cur:cur + len(data)] = data
                place[e["id"]] = cur
                cur += len(data)
        rom[cur:r1 + 1] = bytes(r1 + 1 - cur)
        for e in ents:
            if "error" in e:
                continue
            v = place[e.get("alias_of", e["id"])] - remap(fbase) + cbase
            pa = remap(pint(e["ptr_addr"]))
            if "ptr_hi" in e:
                rom[pa] = v & 0xFF
                rom[remap(pint(e["ptr_hi"]))] = v >> 8
            else:
                rom[pa:pa + 2] = v.to_bytes(2, "little")
        report.append(f"{name}: {cur - r0}/{r1 + 1 - r0}B, 스텁 {nstub}")
        # 칸 수 검사 (원문 줄 칸 수 초과)
        for e in ents:
            if e["id"] in enc and name in UI8_BLOCKS:
                ko_c, ja_c = cells(e["ko"]), cells(e["ja"])
                over = [i for i, n in enumerate(ko_c) if i < len(ja_c) and n > max(ja_c[i], 1) and n > 0]
                if over:
                    report.append(f"  칸 초과 {e['id']}: 줄 {over} ko {ko_c} / 원문 {ja_c}")

    # ---- 고정 길이 (요일, 상태창 라벨)
    for name in ("weekdays",):
        b = blocks[name]
        for i, e in enumerate(ui_entries(name)):
            text = (e.get("ko") or "").rstrip()
            if not text:
                continue
            data = enc8(text, e["id"])
            if len(data) > b["length"]:
                raise SystemExit(f"{e['id']}: {len(data)}B > {b['length']}")
            data += bytes([NOP_CODE]) * (b["length"] - len(data))     # 요일은 <VAR> 로 출력 → 남는 칸은 NOP
            o = remap(pint(b["offset"])) + i * b["length"]
            rom[o:o + b["length"]] = data
    # 매수/매도 목록 종목명(bank5 0x17472, 20 x 12B 영문 고정, 한글 없음 — 뱅크 5 는 확장 롬에서도 같은 위치)
    b = blocks["stock_list_names_b5"]
    for i, e in enumerate(ui_entries("stock_list_names_b5")):
        text = e.get("ko") or e["ja"]
        data = b"".join(ja.encode(c) for c in text)    # 글자별 인코딩: "N " → 0x80|c 합자 방지(이 표는 엔진을 거치지 않는 원시 타일 복사)
        if len(data) > b["length"]:
            raise SystemExit(f"{e['id']}: {len(data)}B > {b['length']}")
        data += bytes([0x49]) * (b["length"] - len(data))
        o = pint(b["offset"]) + i * b["length"]
        rom[o:o + b["length"]] = data
    for name in ("status_cash", "status_stocks"):
        b = blocks[name]
        e = ui_entries(name)[0]
        text = e.get("ko") or ""
        data = bytearray()
        for c in text:
            if is_hangul(c):
                data.append(labels[c])
            else:
                data += ja.encode(c)
        if len(data) > b["length"]:
            raise SystemExit(f"{e['id']}: {len(data)} > {b['length']}")
        data += bytes([0x49]) * (b["length"] - len(data))
        o = remap(pint(b["offset"]))
        rom[o:o + b["length"]] = data
    report.append(f"UI 넘침 뱅크 {UI_OVF_BANK}: ${UI_OVF_BASE:04X}-${ovf - 1:04X} ({ovf - UI_OVF_BASE}B)")

    # ---- 엔진 표
    out = ["; 자동 생성: asm/tools/kor_build.py ui (수정 금지)",
           f"UI8N = {len(chars)}", "UI8FONT:", db(font8), "UI8G_LO:", db(g_lo), "UI8G_HI:", db(g_hi),
           "LABIMG:", db(labimg),
           "POOLCNT:", db([len(p) for p in pools]),
           "POOLLO:", "  .db " + ",".join(f"<POOL{i}" for i in range(len(pools))),
           "POOLHI:", "  .db " + ",".join(f">POOL{i}" for i in range(len(pools)))]
    for i, p in enumerate(pools):
        out += [f"POOL{i}:", db(p)]
    open(os.path.join(PROJ, "build", "kor_ui_tables.asm"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    open(a.rom, "wb").write(rom)
    txt = "\n".join(report)
    print(txt)
    if a.report:
        open(a.report, "w", encoding="utf-8").write(txt + "\n")


# ------------------------------------------------------------------ title (타이틀 메뉴·FEATURING, DESIGN §11)
# 타이틀 CHR = CHR 로더 항목 $2A (bank2 $8FF3, 2bpp 256타일 = BG $0000 전체). 타이틀 전용이라 데이터 자체를 바꾼다.
TITLE_CHR = 0x10 + 2 * 0x4000 + (0x8FF3 - 0x8000)
# 메뉴 20칸(bank4 $8121, PPU $22E7 = 23행 7열). 원문 "NEW GAME  SAVED GAME" 의 전용 타일 9개(V N E M W A S D G) 중 7개 재사용.
# 문구는 font/DESIGN.md §5 제안("새게임 / 이어하기") — 번역 검수 대상(스크립트 밖 고정 문자열)
TITLE_MENU = [("새 게임", 7), ("이어하기", 17)]      # (문구, 시작 열)
TITLE_MENU_TILES = [0x25, 0x26, 0x27, 0x28, 0x2A, 0x2B, 0x2C]
TITLE_MENU_OFF = [0x10131, 0x30131]                # bank4 원본 + bank12 사본(동일 유지)
# FEATURING... 12칸(bank5 $846A 레코드 [EA 22 0C]+12B): 한글은 메뉴에서 풀린 V(24) G(39) + 타이틀 미사용 기호 , (29) / (31)
FEAT_TILES = [0x24, 0x39, 0x29, 0x31]


def title_tile(bm, color):
    p0 = bytearray(8)
    p1 = bytearray(8)
    for y in range(8):
        for x in range(8):
            if bm[y][x]:
                if color & 1:
                    p0[y] |= 0x80 >> x
                if color & 2:
                    p1[y] |= 0x80 >> x
    return bytes(p0 + p1)


def cmd_title(a):
    from romkr import font as fnt
    rom = bytearray(open(a.rom, "rb").read())
    # 메뉴
    chars = []
    for s, _ in TITLE_MENU:
        for c in s:
            if is_hangul(c) and c not in chars:
                chars.append(c)
    if len(chars) > len(TITLE_MENU_TILES):
        raise SystemExit(f"타이틀 메뉴 글자 {len(chars)} > {len(TITLE_MENU_TILES)}")
    tmap = dict(zip(chars, TITLE_MENU_TILES))
    for c, bm in zip(chars, fnt.render(chars, UI8_TTF, 8, 8, 8, 0, 0)):
        o = TITLE_CHR + tmap[c] * 16
        rom[o:o + 16] = title_tile(bm, 2)          # 원래 메뉴 글자 색(2)
    line = [0x49] * 20
    for s, col in TITLE_MENU:
        for i, c in enumerate(s):
            line[col - 7 + i] = tmap[c] if is_hangul(c) else 0x49
    for off in TITLE_MENU_OFF:
        rom[off:off + 20] = bytes(line)
    # FEATURING
    e = ui_entries("title_featuring")[0]
    text = e.get("ko") or ""
    fchars = [c for c in dict.fromkeys(text) if is_hangul(c)]
    if len(fchars) > len(FEAT_TILES):
        raise SystemExit(f"FEATURING 한글 {len(fchars)} > {len(FEAT_TILES)}")
    fmap = dict(zip(fchars, FEAT_TILES))
    for c, bm in zip(fchars, fnt.render(fchars, UI8_TTF, 8, 8, 8, 0, 0)):
        o = TITLE_CHR + fmap[c] * 16
        rom[o:o + 16] = title_tile(bm, 1)          # FEATURING 글자 색(1)
    ja = Table.load(JA_TBL)
    data = bytearray()
    for c in text:
        data += bytes([fmap[c]]) if is_hangul(c) else ja.encode(c)
    if len(data) > 12:
        raise SystemExit(f"title_featuring {len(data)}B > 12")
    data += bytes([0x49]) * (12 - len(data))
    rom[0x1447C:0x1447C + 12] = data
    open(a.rom, "wb").write(rom)
    print(f"title: 메뉴 {''.join(chars)} → 타일 {' '.join(f'{tmap[c]:02X}' for c in chars)}, "
          f"FEATURING {''.join(fchars)} → {' '.join(f'{fmap[c]:02X}' for c in fchars)}")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("tables")
    q = sp.add_parser("font")
    q.add_argument("rom")
    q = sp.add_parser("text")
    q.add_argument("rom", nargs="?")
    q.add_argument("--report")
    q = sp.add_parser("ui")
    q.add_argument("rom")
    q.add_argument("--report")
    q = sp.add_parser("title")
    q.add_argument("rom")
    a = p.parse_args()
    {"tables": cmd_tables, "font": cmd_font, "text": cmd_text, "ui": cmd_ui, "title": cmd_title}[a.cmd](a)


if __name__ == "__main__":
    main()
