"""폰트작업대 Python 쪽 도구 — 게임 원본 영문 8x8 폰트(bank0 파일 0x2375, 코드 0x00-0x36, 1bpp MSB-왼쪽)와
대사창 8x16 영문·기호(a16_XXXX → font/kr16_ascii_overrides.json, build_font.py 가 적용).
  python tools/pixel_desk.py build --out work/desk/pixel_data.json
  python tools/pixel_desk.py apply <dir|file.json> [--dry]
build: 롬 원본 + font/orig_font_overrides.json 을 합친 현재 글리프를 항목으로 만든다.
apply: 입력 {"id","data"(base64 w*h 인덱스 0/1),"base"(현재 data 의 sha1 hex),"at"}
  -> font/orig_font_overrides.json {"0A": "16자리 hex"} (롬 원본과 같으면 항목 삭제). 빌드에서 tools/apply_orig_font.py 가 롬에 넣는다.
  입력: 디렉터리(재귀 *.json, 파일명 stem 이 id) 또는 단일 JSON(목록 / {"documents":[...]} / 단일).
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROM = os.path.join(ROOT, "rom", "Wall Street Kid (USA).nes")
OVR = os.path.join(ROOT, "font", "orig_font_overrides.json")
FONT_OFF, NGLYPH = 0x2375, 55
OVR16 = os.path.join(ROOT, "font", "kr16_ascii_overrides.json")  # {"M": "32자리 hex"}


def doc_key(iid):
    """아티팩트 db 문서 id (ASCII) — tools/pixel_desk.html 의 docKey 와 같은 규칙."""
    return re.sub(r"[^A-Za-z0-9_\-.~:@+]", "", iid)


def sha(b):
    return hashlib.sha1(b).hexdigest()


def labels():
    out = {}
    for line in open(os.path.join(ROOT, "tables", "ja.tbl"), encoding="utf-8"):
        m = re.match(r"^([0-9A-Fa-f]{2})=(.+)$", line.rstrip("\n"))
        if m and int(m.group(1), 16) < NGLYPH:
            out[int(m.group(1), 16)] = m.group(2)
    return out


def rom_glyphs():
    rom = open(ROM, "rb").read()
    return [rom[FONT_OFF + 8 * i: FONT_OFF + 8 * i + 8] for i in range(NGLYPH)]


def overrides():
    return json.load(open(OVR, encoding="utf-8")) if os.path.exists(OVR) else {}


def to_idx(g):
    return bytes(1 if row & (0x80 >> x) else 0 for row in g for x in range(8))


def from_idx(a):
    return bytes(sum((1 << (7 - x)) for x in range(8) if a[y * 8 + x]) for y in range(len(a) // 8))


def overrides16():
    return json.load(open(OVR16, encoding="utf-8")) if os.path.exists(OVR16) else {}


def base16():
    """대사창 8x16 영문·기호의 오버라이드 전 글리프 {글자: 16B} — 빌드와 같은 인자로 렌더."""
    sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools"))
    from romkr.charset import read_charset
    out = os.path.join(ROOT, "work", "desk", "font16_base.bin")
    subprocess.run([sys.executable, os.path.join(ROOT, "font", "tools", "build_font.py"), "--overrides", "",
                    "--out", out, "--tbl-out", "", "--preview", ""],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    blob = open(out, "rb").read()
    chars = read_charset(os.path.join(ROOT, "font", "charset.txt"))
    return {c: blob[16 * i: 16 * i + 16] for i, c in enumerate(chars)
            if c.strip() and (ord(c) < 0x80 or c in "…·「」")}


def item(iid, group, label, g, note):
    return {"id": iid, "group": group, "label": label, "w": 8, "h": len(g), "palette": ["#000000", "#ffffff"],
            "data": base64.b64encode(to_idx(g)).decode(), "colors": [0, 1], "grid": 8, "note": note}


def make_items(b16):
    rg, ov, lab, o16 = rom_glyphs(), overrides(), labels(), overrides16()
    items = []
    for c, g0 in b16.items():
        g = bytes.fromhex(o16[c]) if c in o16 else g0
        items.append(item(f"a16_{ord(c):04X}", "ascii16", f"'{c}'", g, "대사창 8×16 영문·기호(위아래 타일 2장)."))
    for i in range(NGLYPH):
        g = bytes.fromhex(ov[f"{i:02X}"]) if f"{i:02X}" in ov else rg[i]
        items.append(item(f"of_{i:02X}", "font", f"'{lab.get(i, '?')}'", g,
                          f"원본 영문 글리프 코드 {i:02X} (롬 파일 0x{FONT_OFF + 8 * i:X}). 1 = 글자색."))
    return items


def cmd_build(a):
    items = make_items(base16())
    stamp = f"{datetime.datetime.now():%Y-%m-%d %H:%M} 기준: 글리프 {len(items)}자, 오버라이드 {len(overrides()) + len(overrides16())}개"
    out = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    groups = {"ascii16": "대사창 영문·기호 8×16", "font": "원본 영문 폰트 8×8"}
    json.dump({"stamp": stamp, "groups": groups, "items": items}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(items), "개 ->", out)
    return 0


def load_docs(src):
    docs = []

    def add(body, hint=None):
        if not isinstance(body, dict):
            return
        if isinstance(body.get("data"), dict):
            outer = body.get("id")
            body = dict(body["data"])
            if outer and not body.get("id"):
                body["id"] = outer
        if hint and body.get("id") and hint not in (body["id"], doc_key(body["id"])):
            print(f"경고: 파일명 id '{hint}' != 본문 id '{body['id']}' -> 건너뜀")
            return
        iid = body.get("id") or hint
        if iid and isinstance(body.get("data"), str):
            docs.append((iid, body))

    def add_any(body, hint=None):
        if isinstance(body, dict) and isinstance(body.get("documents"), list):
            body, hint = body["documents"], None
        if isinstance(body, list):
            for d in body:
                add(d)
        else:
            add(body, hint)

    if os.path.isdir(a_src := src):
        for r, _, fs in os.walk(a_src):
            for f in sorted(fs):
                if f.lower().endswith(".json"):
                    try:
                        add_any(json.load(open(os.path.join(r, f), encoding="utf-8")),
                                urllib.parse.unquote(os.path.splitext(f)[0]))
                    except Exception as e:
                        print(f"경고: {f} 읽기 실패 ({e})")
    else:
        add_any(json.load(open(src, encoding="utf-8")))
    return docs


def cmd_apply(a):
    b16 = base16()
    items = {i["id"]: i for i in make_items(b16)}
    rg, ov, ov16 = rom_glyphs(), overrides(), overrides16()
    latest = {}
    for iid, b in load_docs(a.src):
        if iid not in latest or str(b.get("at", "")) >= str(latest[iid].get("at", "")):
            latest[iid] = b
    n = 0
    for iid, b in latest.items():
        it = items.get(iid)
        if not it:
            print(f"경고: 알 수 없는 id {iid} -> 건너뜀"); continue
        try:
            raw = base64.b64decode(b["data"], validate=True)
        except Exception:
            print(f"경고: {iid} base64 오류 -> 건너뜀"); continue
        if len(raw) != it["w"] * it["h"] or set(raw) - {0, 1}:
            print(f"경고: {iid} 크기/색 위반 -> 건너뜀"); continue
        cur = base64.b64decode(it["data"])
        if b.get("base") not in (sha(cur), sha(it["data"].encode())):
            print(f"경고: {iid} base 불일치(다른 버전에서 편집됨) -> 건너뜀"); continue
        if raw == cur:
            print(f"{iid}: 변경 없음"); continue
        g = from_idx(raw)
        if it["group"] == "ascii16":
            c = chr(int(iid[4:], 16))
            table, key, orig = ov16, c, b16[c]
        else:
            i = int(iid[3:], 16)
            table, key, orig = ov, f"{i:02X}", rg[i]
        if g == orig:
            table.pop(key, None)
        else:
            table[key] = g.hex()
        print(f"{iid} {it['label']} 적용")
        n += 1
    if n and not a.dry:
        for path, table in ((OVR, ov), (OVR16, ov16)):
            if table or os.path.exists(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                json.dump(dict(sorted(table.items())), open(path, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(f"적용 {n}개{' (dry)' if a.dry else ''}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("--out", default="work/desk/pixel_data.json")
    p = sp.add_parser("apply"); p.add_argument("src"); p.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    sys.exit(cmd_build(a) if a.cmd == "build" else cmd_apply(a))


if __name__ == "__main__":
    main()
