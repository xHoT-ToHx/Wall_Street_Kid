"""스크립트 덤프/검사/삽입.

spec.json 구조 (projects/_template/spec.json 참고)
{
  "blocks": [
    {
      "name": "dialog",
      "type": "pointer",                     # pointer | fixed
      "pointer_table": {"offset": "0x1C010", "count": 200, "size": 2,
                        "endian": "little", "stride": 2},
      "address_map": {"type": "linear", "cpu_base": "0x8000", "file_base": "0x10010",
                      "window": "0x4000"},     # linear | lorom | hirom
      "text_region": {"start": "0x10010", "end": "0x13FFF"},   # 삽입 공간(포함 끝)
      "fill": "0xFF",
      "max_len": 2048
    },
    {
      "name": "items", "type": "fixed",
      "offset": "0x20000", "count": 64, "length": 8, "pad": "0x00"
    }
  ]
}
pointer_table 대신 흩어진 포인터: {"addrs": ["0x2B0E", ...], "size": 2, "endian": "little"}
  (각 원소 = 포인터 워드의 파일 오프셋. 스크립트 바이트코드에 박힌 포인터 등)
address_map
  linear : ptr - cpu_base + file_base  (FC/GB/SMS 뱅크, MD(0/0), PS-EXE)
  lorom  : SFC LoROM, "header": 0|512, 2바이트 포인터면 "bank": "0xC8"
  hirom  : SFC HiROM, 동일
"""
from __future__ import annotations

import json
import re

from . import parse_int
from .tbl import Table, TableError

CTRL_RE = re.compile(r"<[^<>]+>|\[[0-9A-Fa-f]{2,}\]|\n")


class SpecError(Exception):
    pass


class AddrMap:
    def __init__(self, spec: dict, ptr_size: int):
        self.t = spec.get("type", "linear")
        self.size = ptr_size
        self.header = parse_int(spec.get("header", 0))
        self.bank = parse_int(spec["bank"]) if "bank" in spec else None
        self.cpu_base = parse_int(spec.get("cpu_base", 0))
        self.file_base = parse_int(spec.get("file_base", 0))
        self.window = parse_int(spec["window"]) if "window" in spec else None
        self.bank_or = parse_int(spec.get("bank_or", 0x80 if self.t == "lorom" else 0xC0))

    def _full(self, raw):
        if self.t in ("lorom", "hirom") and self.size == 2:
            if self.bank is None:
                raise SpecError("2바이트 SFC 포인터에는 address_map.bank 필요")
            return (self.bank << 16) | raw
        return raw

    def to_file(self, raw):
        p = self._full(raw)
        if self.t == "linear":
            return p - self.cpu_base + self.file_base
        if self.t == "lorom":
            return self.header + (((p & 0x7F0000) >> 1) | (p & 0x7FFF))
        if self.t == "hirom":
            return self.header + (p & 0x3FFFFF)
        raise SpecError(f"알 수 없는 address_map.type {self.t}")

    def to_raw(self, off):
        if self.t == "linear":
            if self.window is not None and not (self.file_base <= off < self.file_base + self.window):
                raise SpecError(f"0x{off:X} 가 포인터 창(뱅크) 밖")
            p = off - self.file_base + self.cpu_base
        elif self.t == "lorom":
            o = off - self.header
            p = (((o >> 15) | self.bank_or) << 16) | 0x8000 | (o & 0x7FFF)
        else:
            p = ((self.bank_or | ((off - self.header) >> 16)) << 16) | ((off - self.header) & 0xFFFF)
        if self.t in ("lorom", "hirom") and self.size == 2:
            if (p >> 16) & 0x3F != self.bank & 0x3F:
                raise SpecError(f"0x{off:X} 가 고정 뱅크 {self.bank:02X} 밖")
            p &= 0xFFFF
        if p < 0 or p >= 1 << (8 * self.size):
            raise SpecError(f"포인터 범위 초과 0x{p:X}")
        return p


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- dump
def dump_block(rom: bytes, tbl: Table, b: dict) -> list[dict]:
    name = b["name"]
    entries = []
    if b.get("type", "pointer") == "fixed":
        off, n, L = parse_int(b["offset"]), b["count"], b["length"]
        for i in range(n):
            o = off + i * L
            pad = parse_int(b.get("pad", 0))
            # 끝 패딩 제거
            raw = rom[o:o + L].rstrip(bytes([pad]))
            text, _ = tbl.decode(raw, 0, limit=L, stop_at_end=False) if raw else ("", 0)
            entries.append({"id": f"{name}_{i:04d}", "offset": hex(o), "max_bytes": L,
                            "ja": text, "ko": "", "note": ""})
        return entries
    pt = b["pointer_table"]
    size, endian = pt.get("size", 2), pt.get("endian", "little")
    stride = pt.get("stride", size)
    if "addrs" in pt:   # 흩어진 포인터 목록(스크립트 바이트코드 안에 박힌 포인터 등): 파일 오프셋 리스트
        addrs = [parse_int(a) for a in pt["addrs"]]
    else:
        off, n = parse_int(pt["offset"]), pt["count"]
        addrs = [off + i * stride for i in range(n)]
    am = AddrMap(b["address_map"], size)
    seen = {}
    for i, pa in enumerate(addrs):
        raw = int.from_bytes(rom[pa:pa + size], endian)
        fo = am.to_file(raw)
        eid = f"{name}_{i:04d}"
        e = {"id": eid, "ptr_addr": hex(pa), "offset": hex(fo)}
        if fo in seen:
            e["alias_of"] = seen[fo]
        elif not (0 <= fo < len(rom)):
            e["error"] = "포인터가 롬 밖"
        else:
            text, used = tbl.decode(rom, fo, limit=b.get("max_len", 4096))
            seen[fo] = eid
            e.update({"orig_bytes": used, "ja": text, "ko": "", "note": ""})
        entries.append(e)
    return entries


# ---------------------------------------------------------------- check
def ctrl_tokens(s):
    return [t for t in CTRL_RE.findall(s) if t != "\n"]


def check_entries(entries, tbl: Table | None = None, line_width: int | None = None, max_lines: int | None = None):
    """번역 검사: 제어코드 보존, 미번역, 줄 길이, 테이블 미등록 문자."""
    problems = []
    for e in entries:
        if "alias_of" in e or "ja" not in e:
            continue
        ja, ko = e["ja"], e.get("ko", "")
        if not ko:
            problems.append((e["id"], "untranslated", ""))
            continue
        if ctrl_tokens(ja) != ctrl_tokens(ko):
            problems.append((e["id"], "control_codes", f"ja={ctrl_tokens(ja)} ko={ctrl_tokens(ko)}"))
        if line_width or max_lines:
            for page in re.split(r"<(?:PAGE|WAIT|CLEAR)[^>]*>", ko):
                lines = CTRL_RE.sub(lambda m: "\n" if m.group(0) == "\n" else "", page).split("\n")
                if max_lines and len([l for l in lines if l]) > max_lines:
                    problems.append((e["id"], "too_many_lines", f"{len(lines)}줄"))
                if line_width:
                    for ln in lines:
                        if len(ln) > line_width:
                            problems.append((e["id"], "line_too_long", f"{len(ln)}>{line_width}: {ln}"))
        if tbl is not None:
            try:
                enc = tbl.encode(ko)
                if "max_bytes" in e and len(enc) > e["max_bytes"]:
                    problems.append((e["id"], "too_long_bytes", f"{len(enc)}>{e['max_bytes']}"))
            except TableError as ex:
                problems.append((e["id"], "unencodable", str(ex)))
    return problems


# ---------------------------------------------------------------- insert
def insert_block(rom: bytearray, tbl: Table, b: dict, entries: list[dict], allow_untranslated=True):
    log = []
    if b.get("type", "pointer") == "fixed":
        pad = parse_int(b.get("pad", 0))
        for e in entries:
            text = e.get("ko") or e["ja"]
            data = tbl.encode(text)
            L = e["max_bytes"]
            if len(data) > L:
                raise SpecError(f"{e['id']}: {len(data)}바이트 > 고정 길이 {L}")
            o = parse_int(e["offset"])
            rom[o:o + L] = data + bytes([pad]) * (L - len(data))
        return log
    pt = b["pointer_table"]
    size, endian = pt.get("size", 2), pt.get("endian", "little")
    am = AddrMap(b["address_map"], size)
    region = b["text_region"]
    cur, end = parse_int(region["start"]), parse_int(region["end"])
    start = cur
    new_off = {}
    overflow = []
    for e in entries:
        if "alias_of" in e or "error" in e:
            continue
        text = e.get("ko") or ""
        if not text:
            if not allow_untranslated:
                raise SpecError(f"{e['id']} 미번역")
            text = e["ja"]
            log.append(f"{e['id']}: 미번역 - 원문 유지")
        data = tbl.encode(text)
        if tbl.ends and not tbl.ends_with_end(data):
            raise SpecError(f"{e['id']}: 종료 토큰이 없음 (ja의 마지막 제어코드를 유지할 것)")
        if cur + len(data) - 1 > end:
            overflow.append((e["id"], len(data)))
            continue
        rom[cur:cur + len(data)] = data
        new_off[e["id"]] = cur
        cur += len(data)
    if overflow:
        need = sum(n for _, n in overflow)
        raise SpecError(f"블록 {b['name']} 공간 부족: {len(overflow)}개 문자열, 추가 {need}바이트 필요 "
                        f"(영역 0x{start:X}-0x{end:X}). 재배치/확장/DTE 필요")
    fill = parse_int(b.get("fill", 0xFF))
    rom[cur:end + 1] = bytes([fill]) * (end + 1 - cur)
    off = parse_int(pt.get("offset", 0))
    stride = pt.get("stride", size)
    for i, e in enumerate(entries):
        if "error" in e:
            continue
        target = new_off[e.get("alias_of", e["id"])]
        pa = parse_int(e.get("ptr_addr", off + i * stride))
        rom[pa:pa + size] = am.to_raw(target).to_bytes(size, endian)
    log.append(f"{b['name']}: {cur - start}/{end + 1 - start} 바이트 사용 ({(cur - start) * 100 // (end + 1 - start)}%)")
    return log
