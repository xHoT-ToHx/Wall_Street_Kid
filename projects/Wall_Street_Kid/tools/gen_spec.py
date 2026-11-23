"""Wall Street Kid (USA) spec.json 생성기 (정적 분석 초안).

사용: python projects/Wall_Street_Kid/tools/gen_spec.py [--report]
 - 원본 롬(rom/)을 읽기만 한다. spec.json 을 덮어쓴다.
 - 텍스트 뱅크 4/5/6/7 의 FF 종료 문자열을 가리키는 포인터를 찾는다.
   (1) 연속 2바이트 LE 포인터: 같은 표(클러스터)에 2개 이상 모여 있거나, 8바이트 창 디스크립터 형식인 것만 채택
   (2) 분리 포인터: LDX #lo / LDY #hi ($C12A/$C12D 호출 인자), LDA #lo STA $81 LDA #hi STA $82
 - 호출 뱅크 제한: bank4 텍스트 <- bank5 코드/스크립트 + bank6 $84F0 표(신문 헤드라인 6개),
   bank5 <- bank5, bank6 <- bank6, bank7(고정) <- bank5/6/7.
근거와 한계: analysis.md
"""
import json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROM = os.path.join(PROJ, "rom", "Wall Street Kid (USA).nes")
rom = open(ROM, "rb").read()

def B(b): return 0x10 + b * 0x4000
def bank_of(off): return (off - 0x10) // 0x4000
def cpu_base(b): return 0xC000 if b == 7 else 0x8000
def to_file(b, cpu): return cpu - cpu_base(b) + B(b)

def ok_byte(x):
    c = x & 0x7F
    return c <= 0x36 or c == 0x49 or x >= 0xFB

def string_at(off):
    """off 에서 FF 까지가 텍스트 문자열이면 (끝+1) 반환, 아니면 None."""
    b = bank_of(off)
    end = B(b) + 0x4000
    i = off
    while i < end and rom[i] != 0xFF:
        if not ok_byte(rom[i]): return None
        i += 1
    if i >= end or i == off: return None
    seg = rom[off:i]
    letters = sum(1 for x in seg if 0x0A <= (x & 0x7F) <= 0x23)
    if letters < 1: return None
    # 영단어 4글자 이상 연속(문자+공백 바이트는 단어 끝)
    run = best = 0
    for x in seg:
        if 0x0A <= x <= 0x23 or x in (0x26,): run += 1
        elif 0x8A <= x <= 0xA3: run += 1; best = max(best, run); run = 0; continue
        else: run = 0
        best = max(best, run)
    if best < 3 and len(seg) > 4: return None
    return i + 1

# 텍스트가 있는 범위(정적 스캔으로 확인한 영역; analysis.md 참조)
TEXT_RANGES = {
    4: [(0x10180, 0x13AC0)],
    5: [(0x1755A, 0x17FDA)],
    6: [(0x19280, 0x1BC90)],
    7: [(0x1E027, 0x1E130), (0x1E840, 0x1E880), (0x1E900, 0x1E960)],
}
def in_text(b, off): return any(a <= off < e for a, e in TEXT_RANGES[b])

def caller_ok(tb, k):
    cb = bank_of(k)
    # bank5 안: $8000-$9FEF(파일 0x14010-0x15FFF) 는 이벤트 스크립트(bank4 대사 참조),
    #           $A000-(파일 0x16010-) 는 주식 화면 코드/표(bank5 문자열 참조)
    if tb == 4: return (cb == 5 and k < 0x16010) or 0x18500 <= k < 0x1850C
    if tb == 5: return cb == 5 and k >= 0x16010
    if tb == 6: return cb == 6
    if tb == 7: return cb in (5, 6, 7)

# ---- (1) 연속 포인터 후보
cand = {}   # k -> (tb, target)
for tb in TEXT_RANGES:
    for k in range(0x10, len(rom) - 1):
        if not caller_ok(tb, k): continue
        v = rom[k] | rom[k + 1] << 8
        if not (cpu_base(tb) <= v < cpu_base(tb) + 0x4000): continue
        t = to_file(tb, v)
        if not in_text(tb, t): continue
        if string_at(t) is None: continue
        # 문자열 시작이어야 함: 직전 바이트가 FF 이거나 텍스트 아님
        if ok_byte(rom[t - 1]) and rom[t - 1] != 0xFF and t not in (0x10191, 0x1E027): continue
        if k in cand: print("WARN: 포인터 해석 충돌", hex(k), cand[k], (tb, t))
        cand[k] = (tb, t)

def is_desc(k):
    return (rom[k + 2] in (0x00, 0x40, 0x80, 0xC0) and rom[k + 3] < 32 and rom[k + 4] < 30
            and 0 < rom[k + 5] <= 32 and 0 < rom[k + 6] <= 30)

ks = sorted(cand)
clusters, cur = [], []
for k in ks:
    if cur and k - cur[-1] <= 6: cur.append(k)
    else:
        if cur: clusters.append(cur)
        cur = [k]
if cur: clusters.append(cur)
keep, dropped = [], []
for c in clusters:
    if len(c) >= 2:
        # 겹치는(1바이트 차) 후보는 클러스터 다수 패리티로 해소
        par = defaultdict(int)
        for k in c: par[k & 1] += 1
        major = max(par, key=par.get)
        cs = set(c)
        for k in c:
            if (k + 1 in cs or k - 1 in cs) and (k & 1) != major: dropped.append((k, "overlap")); continue
            keep.append(k)
    elif is_desc(c[0]):
        keep.append(c[0])
    else:
        dropped.append((c[0], "single"))

# ---- (2) 분리 포인터
split = []   # (lo_off, hi_off, tb, target)
pats = [(bytes([0xA2]), bytes([0xA0]), 2),   # LDX #lo ; LDY #hi
        (bytes([0xA0]), bytes([0xA2]), -2)]  # LDY #hi ; LDX #lo
for k in range(0x10, len(rom) - 8):
    for tb in TEXT_RANGES:
        if not caller_ok(tb, k): continue
        lo = hi = None
        if rom[k] == 0xA2 and rom[k + 2] == 0xA0: lo, hi = k + 1, k + 3
        elif rom[k] == 0xA0 and rom[k + 2] == 0xA2: lo, hi = k + 3, k + 1
        elif rom[k:k+1] == b"\xA9" and rom[k+2:k+4] == b"\x85\x81" and rom[k+4] == 0xA9 and rom[k+6:k+8] == b"\x85\x82":
            lo, hi = k + 1, k + 5
        if lo is None: continue
        v = rom[lo] | rom[hi] << 8
        if not (cpu_base(tb) <= v < cpu_base(tb) + 0x4000): continue
        t = to_file(tb, v)
        if not in_text(tb, t) or string_at(t) is None: continue
        if ok_byte(rom[t - 1]) and rom[t - 1] != 0xFF: continue
        split.append((lo, hi, tb, t))

# ---- 블록 조립
# (블록이름, 텍스트뱅크, 대상 파일범위, 삽입영역(start,end 포함), 설명)
BLOCKS = [
 ("dialog_b4", 4, (0x10180, 0x13AC0), (0x10191, 0x14009),
  "bank4 대사(엔딩/래리/랄프/닥/루스/프리실라 이벤트/상점/신문 헤드라인). 출력 $C12A(=$DB4A, X=lo Y=hi A=창모드). "
  "포인터: bank5 스크립트 표 + LDX/LDY 분리 포인터 + bank6 $84F0 헤드라인 표. 삽입영역 끝 = bank4 꼬리 빈공간(0x13AB9-0x14009) 포함, 벡터(0x1400A-)는 제외."),
 # bank5 텍스트 사이에 포인터 표가 끼어 있음(0x17562, 0x17C56, 0x17E3F, 0x17FAC) -> 표를 피해 4개 블록으로 분할
 ("stock_desc_b5", 5, (0x1758A, 0x17C56), (0x1758A, 0x17C55),
  "bank5 종목 설명문 20개(정보 화면 COMMENTS). 포인터표 0x17562(20개, 2바이트)."),
 ("stock_ui_b5", 5, (0x17C66, 0x17E2D), (0x17C66, 0x17E2C),
  "bank5 주식 매매/포트폴리오 화면 틀 문자열 8개. 포인터표 0x17C56. 줄 끝 공백·열 정렬이 숫자 출력 위치와 맞물림(주의). "
  "0x17E2D-0x17E3E 는 문자열이 아니라 매수 확인 'OK? YES / NO' 의 $D27F PPU 레코드 목록(bank5 $B2CE 가 X=$1D Y=$BE 로 참조) → 삽입 영역에서 제외(QA V1)."),
 ("stock_names_b5", 5, (0x17E67, 0x17FAC), (0x17E67, 0x17FAB),
  "bank5 종목명 20개(+정보 화면 틀 0x17F61). 포인터표 0x17E3F."),
 ("stock_cat_b5", 5, (0x17FB4, 0x17FDA), (0x17FB4, 0x18009),
  "bank5 종목 분류 4개(SPECULATIVE/GROWTH/CYCLICAL/BLUE CHIP). 포인터표 0x17FAC. 삽입영역 끝 = 꼬리 빈공간 포함."),
 ("news_b6", 6, (0x19280, 0x1BC90), (0x19291, 0x1C009),
  "bank6 신문(WALL STREET TIMES)·종목 뉴스·스탠리/코니/은행 대사. 출력 $C12D(=$DB51). 삽입영역 끝 = 꼬리 빈공간(0x1BC8D-0x1C009) 포함."),
 ("menu_b7", 7, (0x1E027, 0x1E131), (0x1E027, 0x1E0D1),
  "고정뱅크 메뉴 항목/선택지 (A)-(D)/인물 이름. 메뉴표 $C801-$C84F([x][y] 뒤 포인터 목록), 이름표 $DCA4(원시 복사 → asm eng_ntag). 영역 고정(뒤는 코드). "
  "삽입영역 끝 96B(0x1E0D2-0x1E131 = 확장 롬 $E0C2-$E121)는 asm 엔진 고정부(korig·kq·hkpre·kwdbox) 예약. 삽입은 asm/tools/kor_build.py ui."),
 ("password_b7", 7, (0x1E840, 0x1E960), (0x1E85C, 0x1E86F),
  "패스워드 화면 문구 4개. 원위치는 패스워드 문자표(0x1E874-, 1글자+FF x65)와 섞여 있음. 고정뱅크 꼬리 0x1FEA0- 는 G3 엔진이 사용 → "
  "삽입은 asm/tools/kor_build.py ui 가 문자열마다 제자리 [4F 0B lo hi] 스텁 + 뱅크 11 본문(포인터 불변, PASSWORD_KO). "
  "text_region 은 romkr insert 오용 방지용으로 첫 문자열 자리(20B)만 둔다(insert_scripts=false)."),
]
NOTES = {}
spec = {"_comment": "Wall Street Kid (USA) FC. tools/gen_spec.py 로 생성(정적 분석 초안). addrs = 포인터 파일 오프셋, {lo,hi} = 분리 포인터(LDX #lo/LDY #hi 또는 LDA #lo/STA $81/LDA #hi/STA $82). 근거는 analysis.md.",
        "blocks": []}
report = []
for name, tb, (ra, rb), (ia, ib), note in BLOCKS:
    ents = [(k, None) for k in keep if cand[k][0] == tb and ra <= cand[k][1] < rb]
    ents += [(lo, hi) for lo, hi, b, t in split if b == tb and ra <= t < rb]
    ents.sort()
    addrs = [hex(k) if hi is None else {"lo": hex(k), "hi": hex(hi)} for k, hi in ents]
    targets = sorted({cand[k][1] for k, h in ents if h is None} | {t for lo, hi, b, t in split if b == tb and ra <= t < rb})
    blk = {"name": name, "type": "pointer", "note": note,
           "pointer_table": {"addrs": addrs, "size": 2, "endian": "little"},
           "address_map": {"type": "linear", "cpu_base": hex(cpu_base(tb)), "file_base": hex(B(tb)), "window": "0x4000"},
           "text_region": {"start": hex(ia), "end": hex(ib)},
           "fill": "0x00", "max_len": 1024}
    spec["blocks"].append(blk)
    report.append((name, len(addrs), len(targets), hex(min(targets)), hex(max(string_at(t) for t in targets))))
    i = ra
    while i < rb:
        j = string_at(i) if (rom[i - 1] == 0xFF or i == ra) else None
        if j and i not in targets and j <= rb:
            report.append(("unref", name, hex(i)))
        i = j if j else i + 1

# ---- 고정 길이 문자열 (포인터 없음, 길이는 코드/레코드가 결정)
FIXED = [
 {"name": "title_featuring", "type": "fixed", "offset": "0x1447c", "count": 1, "length": 12, "pad": "0x49",
  "note": "타이틀 데모 'FEATURING...' PPU 레코드 [ea 22 0c]+12바이트 (bank5 $846A). 길이 바꾸려면 레코드 len 바이트(0x1447B)도 수정"},
 {"name": "weekdays", "type": "fixed", "offset": "0x1c417", "count": 7, "length": 3, "pad": "0x49",
  "note": "요일 SUN..SAT 3글자 고정 (bank7 $C407). 인덱스*3 으로 접근(추정)"},
 {"name": "status_cash", "type": "fixed", "offset": "0x1d091", "count": 1, "length": 5, "pad": "0x49",
  "note": "우상단 상태창 'CASH:' (bank7 $D081)"},
 {"name": "status_stocks", "type": "fixed", "offset": "0x1d096", "count": 1, "length": 7, "pad": "0x49",
  "note": "우상단 상태창 'STOCKS:' (bank7 $D086)"},
 {"name": "stock_list_names_b5", "type": "fixed", "offset": "0x17472", "count": 20, "length": 12, "pad": "0x49",
  "note": "매수/매도 목록 종목명 20개 x 12바이트(표시는 9칸 이내 권장, 뒤는 공백 패딩). bank5 파일 0x17472-0x17561, 바로 뒤가 포인터표 0x17562. 영문 원본 폰트 문자만(한글 불가). 삽입은 asm/tools/kor_build.py ui"},
]
spec["blocks"] += FIXED

with open(os.path.join(PROJ, "spec.json"), "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=1)
if "--report" in sys.argv:
    for r in report: print(r)
    for k, why in dropped:
        tb, t = cand[k]
        print("dropped", hex(k), why, "->", hex(t), "bank", tb)
