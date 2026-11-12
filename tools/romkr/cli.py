"""romkr CLI.  사용: python -m romkr <command> ...  (tools/ 를 PYTHONPATH 에 두거나 tools/ 에서 실행)"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

from . import parse_int
from . import charset as cs
from . import font as fnt
from . import patch as pt
from . import platforms as pf
from . import relsearch as rs
from . import script as sc
from .tbl import Table


def _read(p):
    with open(p, "rb") as f:
        return f.read()


def _write(p, data):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def _jdump(obj, p=None):
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    if p:
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(s + "\n")
    else:
        print(s)


# ---------------------------------------------------------------- commands
def cmd_identify(a):
    _jdump(pf.detect_file(a.rom).to_dict())


def cmd_checksum(a):
    info = pf.detect_file(a.rom)
    plat = a.platform or info.platform
    print(f"{plat}: checksum_ok={info.checksum_ok}")
    if a.fix:
        d = bytearray(_read(a.rom))
        print(pf.fix_checksum(d, plat))
        _write(a.out or a.rom, d)


def cmd_relsearch(a):
    data = _read(a.rom)
    hits = rs.search(data, a.text, a.order, a.width, a.endian, a.max)
    if not hits:
        print("발견 없음. 다른 --order / --width 를 시도하거나, 압축·타일번호 인코딩 가능성 검토")
        return
    for pos, base in hits:
        print(f"0x{pos:06X}  base=0x{base:0{a.width * 2}X}  bytes={data[pos:pos + len(a.text) * a.width].hex(' ')}")
    if a.tbl_out:
        with open(a.tbl_out, "w", encoding="utf-8") as f:
            f.write("\n".join(rs.table_guess(hits[0][1], a.order, a.width)) + "\n")
        print(f"추정 테이블 → {a.tbl_out} (첫 결과 기준, 반드시 덤프로 검증)")


def cmd_dump(a):
    rom = _read(a.rom)
    tbl = Table.load(*a.tbl)
    spec = sc.load_spec(a.spec)
    for b in spec["blocks"]:
        if a.block and b["name"] not in a.block:
            continue
        ents = sc.dump_block(rom, tbl, b)
        out = os.path.join(a.out, f"{b['name']}.json")
        if os.path.exists(out) and not a.force:
            print(f"{out} 존재 - 번역 보호를 위해 건너뜀 (--force 로 덮어쓰기)")
            continue
        _jdump(ents, out)
        n = sum(1 for e in ents if "ja" in e)
        unk = sum(e.get("ja", "").count("[") for e in ents)
        print(f"{b['name']}: {len(ents)}개 포인터, 고유 {n}개 문자열, 미등록바이트 {unk}개 → {out}")


def cmd_check(a):
    tbl = Table.load(*a.tbl) if a.tbl else None
    total = 0
    for p in a.scripts:
        with open(p, encoding="utf-8") as f:
            ents = json.load(f)
        probs = sc.check_entries(ents, tbl, a.line_width, a.max_lines)
        if a.skip_untranslated:
            probs = [x for x in probs if x[1] != "untranslated"]
        done = sum(1 for e in ents if e.get("ko"))
        todo = sum(1 for e in ents if "ja" in e)
        print(f"== {p}: 번역 {done}/{todo}, 문제 {len(probs)}건")
        for pid, kind, msg in probs[: a.limit]:
            print(f"  {pid} [{kind}] {msg}")
        total += len(probs)
    sys.exit(1 if total and a.strict else 0)


def _insert_scripts(rom, tbl, spec, scripts_dir, allow_untranslated=True):
    logs = []
    for b in spec["blocks"]:
        if b.get("external"):
            logs.append(f"{b['name']}: external - 외부 도구가 삽입 (건너뜀)")
            continue
        p = os.path.join(scripts_dir, f"{b['name']}.json")
        if not os.path.exists(p):
            logs.append(f"{b['name']}: 스크립트 없음 - 건너뜀")
            continue
        with open(p, encoding="utf-8") as f:
            ents = json.load(f)
        logs += sc.insert_block(rom, tbl, b, ents, allow_untranslated)
    return logs


def cmd_insert(a):
    rom = bytearray(_read(a.rom))
    tbl = Table.load(*a.tbl)
    for line in _insert_scripts(rom, tbl, sc.load_spec(a.spec), a.scripts):
        print(line)
    _write(a.out, rom)


def cmd_charset(a):
    files = [f for p in a.scripts for f in glob.glob(p)]
    cnt = cs.collect(files)
    chars = [c for c, _ in cnt.most_common()]
    if a.ksx1001:
        have = set(chars)
        chars += [c for c in cs.ksx1001_hangul() if c not in have]
    if a.extra:
        chars = [c for c in a.extra if c not in chars] + chars
    cs.write_charset(a.out, chars)
    hangul = sum(1 for c in chars if cs.is_hangul(c))
    print(f"문자 {len(chars)}개 (한글 {hangul}) → {a.out}")
    if a.capacity and len(chars) > a.capacity:
        print(f"경고: 용량 {a.capacity} 초과 {len(chars) - a.capacity}자 - 어휘 조정/동적 로딩 필요")
        sys.exit(2)


def _font_from_cfg(c, base="."):
    j = lambda p: os.path.join(base, p)
    chars = cs.read_charset(j(c["charset"]))
    w, h = (int(x) for x in str(c.get("cell", "16x16")).lower().split("x"))
    blob, tbl, widths, bms = fnt.build(
        chars, j(c["ttf"]), c.get("size", 12), w, h, c["format"], parse_int(c.get("code_start", "0x100")),
        c.get("code_bytes", 2), c.get("offset_x", 0), c.get("offset_y", 0), c.get("fg", 1), c.get("bg", 0),
        c.get("shadow"), c.get("order", "row"), [parse_int(x) for x in c.get("skip_low", [])],
        c.get("threshold", 128))
    _write(j(c.get("bin_out", "build/font.bin")), blob)
    _write(j(c.get("widths_out", "build/font_widths.bin")), widths)
    with open(j(c.get("tbl_out", "tables/ko_font.tbl")), "w", encoding="utf-8") as f:
        f.write("\n".join(tbl) + "\n")
    fnt.preview(bms, j(c.get("preview_out", "build/font_preview.png")))
    return blob, widths, len(chars)


def cmd_font(a):
    cfg = dict(charset=a.charset, ttf=a.ttf, size=a.size, cell=a.cell, format=a.format,
               code_start=a.code_start, code_bytes=a.code_bytes, offset_x=a.ox, offset_y=a.oy,
               fg=a.fg, bg=a.bg, shadow=a.shadow, order=a.order, skip_low=a.skip_low or [],
               bin_out=a.out, tbl_out=a.tbl_out, preview_out=a.preview, widths_out=a.widths_out)
    blob, _, n = _font_from_cfg(cfg)
    print(f"{n}자, {len(blob)}바이트 → {a.out} / {a.tbl_out} / {a.preview}")


def cmd_patch(a):
    if a.action == "make":
        kind = a.kind or os.path.splitext(a.out)[1].lstrip(".").lower()
        p = pt.create(_read(a.orig), _read(a.mod), kind)
        _write(a.out, p)
        print(f"{kind.upper()} {len(p)}바이트 → {a.out}")
    else:
        _write(a.out, pt.apply(_read(a.orig), _read(a.mod)))
        print(f"적용 완료 → {a.out}")


def cmd_build(a):
    """project.json 기반 재현 가능한 전체 빌드."""
    proj = os.path.abspath(a.project)
    with open(os.path.join(proj, "project.json"), encoding="utf-8") as f:
        P = json.load(f)
    j = lambda p: os.path.join(proj, p)
    src = _read(j(P["rom"]))
    sha = hashlib.sha1(src).hexdigest()
    if P.get("rom_sha1") and P["rom_sha1"].lower() != sha:
        sys.exit(f"원본 롬 SHA1 불일치: {sha} (project.json: {P['rom_sha1']})")
    rom = bytearray(src)
    if "expand_to" in P:
        size = parse_int(P["expand_to"])
        rom += bytes([parse_int(P.get("expand_fill", 0xFF))]) * max(0, size - len(rom))
        print(f"확장: {len(src):#x} → {len(rom):#x}")
    if "font" in P:
        blob, widths, n = _font_from_cfg(P["font"], proj)
        if "insert_at" in P["font"]:
            o = parse_int(P["font"]["insert_at"])
            rom[o:o + len(blob)] = blob
            print(f"폰트 {n}자 {len(blob)}B @ {o:#x}")
        if "widths_at" in P["font"]:
            o = parse_int(P["font"]["widths_at"])
            rom[o:o + len(widths)] = widths
    for ins in P.get("inserts", []):
        d = _read(j(ins["file"]))
        o = parse_int(ins["offset"])
        if "max" in ins and len(d) > parse_int(ins["max"]):
            sys.exit(f"{ins['file']} 크기 초과")
        rom[o:o + len(d)] = d
        print(f"삽입 {ins['file']} {len(d)}B @ {o:#x}")
    if P.get("insert_scripts", True):
        tbl = Table.load(*[j(t) for t in P["tables"]["ko"]])
        for line in _insert_scripts(rom, tbl, sc.load_spec(j(P["spec"])), j(P.get("scripts_dir", "scripts")),
                                    not a.release):
            print(line)
    else:
        print("스크립트 삽입: project.json insert_scripts=false → commands 의 외부 도구가 담당")
    out = j(P.get("output", "build/output.bin"))
    _write(out, rom)
    for cmd in P.get("commands", []):
        argv = [c.replace("{rom}", out).replace("{project}", proj) for c in cmd]
        print("$", " ".join(argv))
        r = subprocess.run(argv, cwd=proj)
        if r.returncode:
            sys.exit(f"명령 실패({r.returncode})")
    rom = bytearray(_read(out))
    print(pf.fix_checksum(rom, P["platform"]))
    _write(out, rom)
    print(f"빌드 → {out}  sha1={hashlib.sha1(rom).hexdigest()}")
    if "patch" in P and P["platform"] != "ps":
        kind = P["patch"].get("format", "bps")
        pdata = pt.create(src, bytes(rom), kind)
        pout = P["patch"]["out"].replace("{version}", P.get("version", "0.0.0"))
        _write(j(pout), pdata)
        assert pt.apply(src, pdata) == bytes(rom), "패치 검증 실패"
        print(f"패치({kind}) {len(pdata)}B → {pout} (재적용 검증 OK)")


VERSION_RULE = "major = 릴리스, minor = 한글화 큰 변화(대사·타이틀 이미지·저장/입력 한글화 등), patch = 작은 업데이트(대사 일부·픽셀 수정·마이너 버그)"


def cmd_version(a):
    """project.json 의 version(Major.Minor.Patch) 확인·올리기."""
    p = os.path.join(os.path.abspath(a.project), "project.json")
    raw = open(p, "rb").read().decode("utf-8")
    P = json.loads(raw)
    v = P.get("version", "0.0.0")
    if not a.bump:
        print(f"v{v}  ({VERSION_RULE})")
        return
    ma, mi, pa = (int(x) for x in v.split("."))
    nv = {"major": f"{ma + 1}.0.0", "minor": f"{ma}.{mi + 1}.0", "patch": f"{ma}.{mi}.{pa + 1}"}[a.bump]
    P["version"] = nv
    s = json.dumps(P, ensure_ascii=False, indent=2) + "\n"
    if "\r\n" in raw:
        s = s.replace("\n", "\r\n")
    open(p, "wb").write(s.encode("utf-8"))
    print(f"v{v} → v{nv} ({a.bump})")


# ---------------------------------------------------------------- main
def main(argv=None):
    for s_ in (sys.stdout, sys.stderr):
        try:
            s_.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap =argparse.ArgumentParser(prog="romkr", description="레트로 롬 한글화 툴킷")
    s = ap.add_subparsers(dest="cmd", required=True)

    p = s.add_parser("identify", help="플랫폼/헤더/해시 식별")
    p.add_argument("rom"); p.set_defaults(f=cmd_identify)

    p = s.add_parser("checksum", help="체크섬 검사/수정")
    p.add_argument("rom"); p.add_argument("--fix", action="store_true")
    p.add_argument("--platform", choices=pf.PLATFORMS); p.add_argument("--out")
    p.set_defaults(f=cmd_checksum)

    p = s.add_parser("relsearch", help="상대 검색으로 텍스트 인코딩 찾기")
    p.add_argument("rom"); p.add_argument("text")
    p.add_argument("--order", default="gojuon", choices=list(rs.ORDERS))
    p.add_argument("--width", type=int, default=1, choices=(1, 2))
    p.add_argument("--endian", default="little"); p.add_argument("--max", type=int, default=50)
    p.add_argument("--tbl-out"); p.set_defaults(f=cmd_relsearch)

    p = s.add_parser("dump", help="spec 기반 스크립트 덤프 → scripts/<block>.json")
    p.add_argument("rom"); p.add_argument("--tbl", nargs="+", required=True)
    p.add_argument("--spec", required=True); p.add_argument("--out", default="scripts")
    p.add_argument("--block", nargs="*"); p.add_argument("--force", action="store_true")
    p.set_defaults(f=cmd_dump)

    p = s.add_parser("check", help="번역 검사(제어코드/줄길이/인코딩 가능성)")
    p.add_argument("scripts", nargs="+"); p.add_argument("--tbl", nargs="*")
    p.add_argument("--line-width", type=int); p.add_argument("--max-lines", type=int)
    p.add_argument("--skip-untranslated", action="store_true"); p.add_argument("--strict", action="store_true")
    p.add_argument("--limit", type=int, default=200); p.set_defaults(f=cmd_check)

    p = s.add_parser("insert", help="번역 삽입 + 포인터 재계산")
    p.add_argument("rom"); p.add_argument("--tbl", nargs="+", required=True)
    p.add_argument("--spec", required=True); p.add_argument("--scripts", default="scripts")
    p.add_argument("--out", required=True); p.set_defaults(f=cmd_insert)

    p = s.add_parser("charset", help="번역문에서 필요한 문자 집합 산출")
    p.add_argument("scripts", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--ksx1001", action="store_true", help="KS X 1001 2350자 전부 포함")
    p.add_argument("--extra", default="", help="항상 앞쪽에 넣을 문자")
    p.add_argument("--capacity", type=int); p.set_defaults(f=cmd_charset)

    p = s.add_parser("font", help="한글 폰트 타일 생성")
    p.add_argument("--charset", required=True); p.add_argument("--ttf", required=True)
    p.add_argument("--size", type=int, default=12); p.add_argument("--cell", default="16x16")
    p.add_argument("--format", required=True, help="fc2bpp sfc2bpp sfc4bpp gb2bpp sms4bpp md4bpp 1bpp 1bpp-linear ps4bpp")
    p.add_argument("--code-start", default="0x100"); p.add_argument("--code-bytes", type=int, default=2)
    p.add_argument("--skip-low", nargs="*", type=parse_int)
    p.add_argument("--ox", type=int, default=0); p.add_argument("--oy", type=int, default=0)
    p.add_argument("--fg", type=int, default=1); p.add_argument("--bg", type=int, default=0)
    p.add_argument("--shadow", type=int); p.add_argument("--order", default="row", choices=("row", "col"))
    p.add_argument("--out", default="build/font.bin"); p.add_argument("--tbl-out", default="tables/ko_font.tbl")
    p.add_argument("--widths-out", default="build/font_widths.bin")
    p.add_argument("--preview", default="build/font_preview.png"); p.set_defaults(f=cmd_font)

    p = s.add_parser("patch", help="IPS/BPS 생성(make)·적용(apply)")
    p.add_argument("action", choices=("make", "apply"))
    p.add_argument("orig"); p.add_argument("mod", help="make: 수정 롬 / apply: 패치 파일")
    p.add_argument("--out", required=True); p.add_argument("--kind", choices=("ips", "bps"))
    p.set_defaults(f=cmd_patch)

    p = s.add_parser("build", help="projects/<게임> 전체 빌드")
    p.add_argument("project"); p.add_argument("--release", action="store_true", help="미번역 있으면 실패")
    p.set_defaults(f=cmd_build)

    p = s.add_parser("version", help="버전 확인 / --bump major|minor|patch")
    p.add_argument("project"); p.add_argument("--bump", choices=("major", "minor", "patch"))
    p.set_defaults(f=cmd_version)

    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
