"""romkr 스모크 테스트: 합성 롬으로 덤프→번역→삽입→체크섬→패치 왕복.  python -m pytest tools/tests  또는 python tools/tests/test_smoke.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from romkr import patch, platforms, relsearch, script, tiles  # noqa: E402
from romkr.tbl import Table  # noqa: E402

GOJ = relsearch.GOJUON


def make_gb():
    rom = bytearray(0x8000)
    rom[0x104:0x10C] = bytes.fromhex("CEED6666CC0D000B")
    rom[0x134:0x13C] = b"TESTGAME"
    # 텍스트: 0x10 + gojuon index, 0xFF 종료. 뱅크1(0x4000) 에 2개 문자열
    def enc(s):
        return bytes(0x10 + GOJ.index(c) for c in s) + b"\xff"
    s0, s1 = enc("はなしかける"), enc("ゆうしや")
    rom[0x4100:0x4100 + len(s0)] = s0
    rom[0x4100 + len(s0):0x4100 + len(s0) + len(s1)] = s1
    p0, p1 = 0x4100, 0x4100 + len(s0)
    rom[0x4000:0x4006] = p0.to_bytes(2, "little") + p1.to_bytes(2, "little") + p0.to_bytes(2, "little")
    platforms.fix_checksum(rom, "gb")
    return rom


def test_all():
    with tempfile.TemporaryDirectory() as d:
        rom = make_gb()
        info = platforms.detect(bytes(rom), "x.gb")
        assert info.platform == "gb" and info.checksum_ok, info

        hits = relsearch.search(bytes(rom), "はなしかける")
        assert hits and hits[0][0] == 0x4100 and hits[0][1] == 0x10, hits

        ja = os.path.join(d, "ja.tbl")
        with open(ja, "w", encoding="utf-8") as f:
            f.write("\n".join(relsearch.table_guess(0x10)) + "\n/FF=<END>\n")
        ko = os.path.join(d, "ko.tbl")
        with open(ko, "w", encoding="utf-8") as f:
            f.write("0100=말\n0101=걸\n0102=기\n0103=용\n0104=사\n/FFFF=<END>\n")
        block = {"name": "dlg", "pointer_table": {"offset": "0x4000", "count": 3, "size": 2},
                 "address_map": {"type": "linear", "cpu_base": "0x4000", "file_base": "0x4000", "window": "0x4000"},
                 "text_region": {"start": "0x4100", "end": "0x413F"}}
        ents = script.dump_block(bytes(rom), Table.load(ja), block)
        assert ents[0]["ja"] == "はなしかける<END>" and ents[2]["alias_of"] == "dlg_0000", ents
        ents[0]["ko"] = "말걸기<END>"
        ents[1]["ko"] = "용사<END>"
        assert not script.check_entries(ents, Table.load(ko))
        out = bytearray(rom)
        script.insert_block(out, Table.load(ko), block, ents)
        p1 = int.from_bytes(out[0x4002:0x4004], "little")
        assert p1 == 0x4100 + 8, hex(p1)
        assert int.from_bytes(out[0x4004:0x4006], "little") == 0x4100
        platforms.fix_checksum(out, "gb")
        assert platforms.detect(bytes(out), "x.gb").checksum_ok

        for kind in ("ips", "bps"):
            p = patch.create(bytes(rom), bytes(out), kind)
            assert patch.apply(bytes(rom), p) == bytes(out), kind

        t = [[(x + y) & 3 for x in range(8)] for y in range(8)]
        for name, fn in tiles.TILE_FORMATS.items():
            assert len(fn(t)) in (8, 16, 32), name

        # SFC LoROM 헤더 + 체크섬
        sfc = bytearray(0x80000)
        sfc[0x7FC0:0x7FD5] = b"TEST SFC GAME        "
        sfc[0x7FD5] = 0x20
        sfc[0x7FFC:0x7FFE] = (0x8000).to_bytes(2, "little")
        sfc[0x7FDC:0x7FE0] = b"\xff\xff\x00\x00"
        platforms.fix_checksum(sfc, "sfc")
        i = platforms.detect(bytes(sfc), "x.sfc")
        assert i.platform == "sfc" and i.checksum_ok and i.details["mapping"] == "lorom", i

        am = script.AddrMap({"type": "lorom"}, 3)
        assert am.to_file(0x818000) == 0x8000 and am.to_raw(0x8000) == 0x818000
    print("OK")


if __name__ == "__main__":
    test_all()
