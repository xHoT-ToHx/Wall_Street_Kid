"""휴대폰 번역대 — 번역 확인·줄 맞춤 미리보기 (Super Express Satsujin Jiken 방식).

    python -X utf8 tools/text_desk.py build          -> work/desk/text_desk.html (아티팩트로 발행)
    python -X utf8 tools/text_desk.py apply <edits>  -> scripts/*.json 의 ko 갱신 (--dry 로 시험)

페이지는 비공개 아티팩트. 고친 내용은 입력하는 대로 db `edits/<id>` 문서 {ko, base, at} 에 저장된다.
"번역대 반영해줘": ArtifactData list collection=edits out_dir=work/desk/edits_in -> apply -> romkr build
  -> build 다시 굽기 -> 같은 URL 로 재발행 -> 반영한 edits 문서 삭제. (DESK.md)

검사(페이지와 apply 가 같다)
  · 제어 토큰(<END> <WAIT> <PAGE> <VAR> [XX])은 원문(ja)과 같은 순서·개수여야 한다.
  · 원고(base)가 그사이 바뀐 항목은 거부한다.
  · 칸 수·글자 수 한도는 페이지에서 경고하고, 정확한 검사는 romkr check / kor_build 가 한다.
올리는 것은 원문·번역문·배치 규칙·글리프(Galmuri, OFL)와 용어집뿐. 롬 데이터는 올리지 않는다.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(PROJ))
sys.path.insert(0, os.path.join(ROOT, "tools"))
TEMPLATE = os.path.join(PROJ, "tools", "text_desk.html")
OUT = os.path.join(PROJ, "work", "desk", "text_desk.html")

ORDER = ["dialog_b4", "news_b6", "stock_desc_b5", "stock_ui_b5", "stock_names_b5", "stock_cat_b5", "menu_b7",
         "password_b7", "title_featuring", "weekdays", "status_cash", "status_stocks", "stock_list_names_b5"]
LABELS = {"dialog_b4": "대사(은행·상점·전화·엔딩)", "news_b6": "뉴스·강의·정보", "stock_desc_b5": "종목 설명",
          "stock_ui_b5": "매매 화면 틀", "stock_names_b5": "정보 화면·종목명", "stock_cat_b5": "종목 분류",
          "menu_b7": "메뉴·이름표", "password_b7": "패스워드 화면", "title_featuring": "타이틀 자막",
          "weekdays": "요일", "status_cash": "상태·현금", "status_stocks": "상태·주식",
          "stock_list_names_b5": "매수·매도 목록 이름(영문 9칸)"}
DIALOG = {"dialog_b4", "news_b6"}
ASCII_ONLY = {"stock_list_names_b5"}
TOKRE = re.compile(r"<[^>]*>|\[[0-9A-Fa-f]{2}\]")


def load(block):
    p = os.path.join(PROJ, "scripts", block + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def widths(ja):
    s = ja.replace("<VAR>", "\x01" * 10)
    return [len(l) for l in TOKRE.sub("", s).split("\n")]


def limit_of(block, e):
    if block in DIALOG:
        return {"t": "dlg", "w": 28, "lines": 6}
    return {"t": "fix", "w": widths(e["ja"]), "ascii": block in ASCII_ONLY}


def rows():
    out = []
    for b in ORDER:
        for e in load(b):
            if "ja" not in e or "alias_of" in e:
                continue
            out.append([e["id"], b, e["ja"], e.get("ko", ""), limit_of(b, e)])
    return out


def build_glyphs():
    """게임이 쓰는 글리프(8x16 대사 / 8x8 화면) 비트맵 — font/tools/build_font.py 와 같은 인자로 work/desk 에 따로 만든다."""
    from romkr.charset import read_charset
    d = os.path.join(PROJ, "work", "desk")
    os.makedirs(d, exist_ok=True)
    bf = os.path.join(PROJ, "font", "tools", "build_font.py")
    q = {"cwd": PROJ, "check": True, "capture_output": True}
    subprocess.run([sys.executable, bf, "--tbl-out", "", "--preview", "", "--out", "work/desk/font16.bin"], **q)
    subprocess.run([sys.executable, bf, "--ascii-ttf", "", "--charset", "font/ui8_charset.txt", "--ttf", "font/Galmuri7.ttf",
                    "--size", "8", "--cell", "8x8", "--oy", "0", "--out", "work/desk/font8.bin",
                    "--tbl-out", "", "--preview", ""], **q)
    cs16 = "".join(read_charset(os.path.join(PROJ, "font", "charset.txt")))
    cs8 = "".join(read_charset(os.path.join(PROJ, "font", "ui8_charset.txt")))
    b16 = open(os.path.join(d, "font16.bin"), "rb").read()
    b8 = open(os.path.join(d, "font8.bin"), "rb").read()
    assert len(b16) == len(cs16) * 16 and len(b8) == len(cs8) * 8, "글리프 수 불일치"
    return cs16, cs8, base64.b64encode(b16).decode(), base64.b64encode(b8).decode()


def gloss():
    out = []
    for i, line in enumerate(open(os.path.join(PROJ, "glossary.tsv"), encoding="utf-8")):
        p = line.rstrip("\n").split("\t")
        if i and len(p) >= 2 and p[0]:
            out.append((p + ["", ""])[:4])
    return out


def cmd_build(a):
    tpl = open(TEMPLATE, encoding="utf-8").read()
    cs16, cs8, g16, g8 = build_glyphs()
    D = {"stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "rows": rows(), "labels": LABELS,
         "order": [b for b in ORDER if load(b)], "cs16": cs16, "cs8": cs8, "gloss": gloss(),
         "uniq": {"warn": 90, "max": 107}}
    data = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/", data).replace("__G16__", g16).replace("__G8__", g8)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8", newline="\n").write(html)
    print(f"{len(D['rows'])}행 → {a.out} ({os.path.getsize(a.out) // 1024} KB)")


# ---------------------------------------------------------------- apply
def ctrl_seq(s):
    return TOKRE.findall(s)


def read_edits(src):
    out = []
    if os.path.isdir(src):
        for f in sorted(glob.glob(os.path.join(src, "**", "*.json"), recursive=True)):
            body = json.load(open(f, encoding="utf-8"))
            body = body.get("data", body) if isinstance(body, dict) else {}
            out.append(dict(body, id=urllib.parse.unquote(os.path.splitext(os.path.basename(f))[0])))
        return out
    j = json.load(open(src, encoding="utf-8"))
    if isinstance(j, dict) and "documents" in j:
        j = j["documents"]
    for d in j:
        body = d.get("data", d)
        out.append(dict(body, id=d.get("id", body.get("id"))))
    return out


def cmd_apply(a):
    edits = read_edits(a.edits)
    files, where = {}, {}
    for b in ORDER:
        p = os.path.join(PROJ, "scripts", b + ".json")
        if not os.path.exists(p):
            continue
        raw = open(p, "rb").read().decode("utf-8")
        files[b] = (p, raw, json.loads(raw))
        for e in files[b][2]:
            where[e["id"]] = b
    ok, skip, changed = 0, [], set()
    for ed in edits:
        i, ko, base = ed.get("id"), ed.get("ko"), ed.get("base")
        if i not in where or not isinstance(ko, str):
            skip.append((i, "알 수 없는 id")); continue
        b = where[i]
        e = next(x for x in files[b][2] if x["id"] == i)
        cur = e.get("ko", "")
        if base is not None and base != cur:
            skip.append((i, "원고가 그사이 바뀜")); continue
        if ctrl_seq(ko) != ctrl_seq(e["ja"]):
            skip.append((i, "제어 토큰이 원문과 다름")); continue
        if ko == cur:
            continue
        e["ko"] = ko
        changed.add(b); ok += 1
        print(f"  {i}: {cur!r} -> {ko!r}")
    for i, why in skip:
        print(f"  건너뜀 {i}: {why}")
    if not a.dry:
        for b in changed:
            p, raw, data = files[b]
            s = json.dumps(data, ensure_ascii=False, indent=2)
            if raw.endswith("\n"):
                s += "\n"
            if "\r\n" in raw:
                s = s.replace("\n", "\r\n")
            open(p, "wb").write(s.encode("utf-8"))
    print(f"반영 {ok}건, 건너뜀 {len(skip)}건{' (dry)' if a.dry else ''}")
    return 1 if skip else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--out", default=OUT)
    p = sub.add_parser("apply"); p.add_argument("edits"); p.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return {"build": cmd_build, "apply": cmd_apply}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
