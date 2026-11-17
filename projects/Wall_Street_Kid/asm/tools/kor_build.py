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
                if xcur + len(data) > 0x3FF0 or cur + 3 > r1:
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


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("tables")
    q = sp.add_parser("font")
    q.add_argument("rom")
    q = sp.add_parser("text")
    q.add_argument("rom", nargs="?")
    q.add_argument("--report")
    a = p.parse_args()
    {"tables": cmd_tables, "font": cmd_font, "text": cmd_text}[a.cmd](a)


if __name__ == "__main__":
    main()
