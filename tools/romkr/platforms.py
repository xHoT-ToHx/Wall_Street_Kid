"""플랫폼 식별, 헤더 정보, 체크섬 검사/수정."""
from __future__ import annotations

import hashlib
import os
import zlib
from dataclasses import asdict, dataclass, field

PLATFORMS = ("fc", "sfc", "md", "sms", "gb", "gbc", "ps")
BIG_FILE = 64 * 1024 * 1024


@dataclass
class RomInfo:
    platform: str
    size: int
    sha1: str
    crc32: str
    header_size: int = 0
    title: str = ""
    details: dict = field(default_factory=dict)
    checksum_ok: bool | None = None

    def to_dict(self):
        return asdict(self)


def _txt(b: bytes) -> str:
    return b.decode("ascii", "replace").strip("\x00 \xff")


def hashes_of_file(path):
    h, c = hashlib.sha1(), 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            c = zlib.crc32(chunk, c)
    return h.hexdigest(), f"{c & 0xffffffff:08x}"


def detect_file(path) -> RomInfo:
    size = os.path.getsize(path)
    sha1, crc = hashes_of_file(path)
    with open(path, "rb") as f:
        data = f.read() if size <= BIG_FILE else f.read(0x20000)
    info = detect(data, path, base=dict(size=size, sha1=sha1, crc32=crc))
    return info


def detect(data: bytes, path: str = "", base: dict | None = None) -> RomInfo:
    if base is None:
        base = dict(size=len(data), sha1=hashlib.sha1(data).hexdigest(),
                    crc32=f"{zlib.crc32(data) & 0xffffffff:08x}")
    ext = os.path.splitext(path)[1].lower()
    if data[:4] == b"NES\x1a":
        return _fc(data, base)
    if data[:4] == b"FDS\x1a" or ext == ".fds":
        return RomInfo("fc", **base, title="(FDS disk)", details={"fds": True})
    ps = ps_layout(data)
    if ps:
        return _ps(data, base, ps)
    if len(data) >= 0x150 and data[0x104:0x10C] == bytes.fromhex("CEED6666CC0D000B"):
        return _gb(data, base)
    if len(data) >= 0x200 and b"SEGA" in data[0x100:0x105]:
        return _md(data, base)
    for off in (0x7FF0, 0x3FF0, 0x1FF0):
        if data[off:off + 8] == b"TMR SEGA":
            return _sms(data, base, off)
    sfc = _sfc(data, base)
    if sfc:
        return sfc
    guess = {".nes": "fc", ".sfc": "sfc", ".smc": "sfc", ".md": "md", ".gen": "md",
             ".sms": "sms", ".gg": "sms", ".gb": "gb", ".gbc": "gbc", ".iso": "ps"}.get(ext, "unknown")
    return RomInfo(guess, **base, details={"warning": "시그니처로 식별 실패 - 확장자 추정"})


# ---------------------------------------------------------------- FC (NES)
def _fc(d, base):
    prg, chr_ = d[4], d[5]
    mapper = (d[6] >> 4) | (d[7] & 0xF0)
    nes2 = (d[7] & 0x0C) == 0x08
    if nes2:
        mapper |= (d[8] & 0x0F) << 8
    det = {
        "format": "NES 2.0" if nes2 else "iNES",
        "mapper": mapper,
        "prg_rom": f"{prg} x 16KB",
        "chr_rom": f"{chr_} x 8KB" if chr_ else "없음 (CHR-RAM - 폰트를 런타임 업로드)",
        "mirroring": "vertical" if d[6] & 1 else "horizontal",
        "battery": bool(d[6] & 2),
        "trainer": bool(d[6] & 4),
        "prg_file_offset": hex(16 + (512 if d[6] & 4 else 0)),
        "chr_file_offset": hex(16 + (512 if d[6] & 4 else 0) + prg * 0x4000),
    }
    return RomInfo("fc", **base, header_size=16, details=det, checksum_ok=None)


# ---------------------------------------------------------------- GB / GBC
def gb_header_checksum(d):
    x = 0
    for b in d[0x134:0x14D]:
        x = (x - b - 1) & 0xFF
    return x


def gb_global_checksum(d):
    return (sum(d) - d[0x14E] - d[0x14F]) & 0xFFFF


def _gb(d, base):
    cgb = d[0x143]
    plat = "gbc" if cgb in (0x80, 0xC0) else "gb"
    title = _txt(d[0x134:0x143] if plat == "gbc" else d[0x134:0x144])
    ok = gb_header_checksum(d) == d[0x14D] and gb_global_checksum(d) == int.from_bytes(d[0x14E:0x150], "big")
    det = {"cgb_flag": hex(cgb), "cgb_only": cgb == 0xC0, "sgb": d[0x146] == 3,
           "cart_type": hex(d[0x147]), "rom_size": f"{32 << d[0x148]}KB" if d[0x148] < 9 else hex(d[0x148]),
           "ram_size_code": hex(d[0x149]), "bank_size": "0x4000 (bank0 고정 0000-3FFF, 스위칭 4000-7FFF)"}
    return RomInfo(plat, **base, title=title, details=det, checksum_ok=ok)


# ---------------------------------------------------------------- MD
def md_checksum(d):
    s = 0
    end = len(d) - (len(d) & 1)
    for i in range(0x200, end, 2):
        s += (d[i] << 8) | d[i + 1]
    if len(d) & 1:
        s += d[-1] << 8
    return s & 0xFFFF


def _md(d, base):
    det = {"system": _txt(d[0x100:0x110]), "domestic_title": d[0x120:0x150].decode("shift_jis", "replace").strip(),
           "serial": _txt(d[0x180:0x18E]), "region": _txt(d[0x1F0:0x1F3]),
           "rom_end": hex(int.from_bytes(d[0x1A4:0x1A8], "big")),
           "note": "SMD 인터리브(.smd)면 먼저 .bin으로 변환할 것"}
    ok = md_checksum(d) == int.from_bytes(d[0x18E:0x190], "big")
    return RomInfo("md", **base, title=_txt(d[0x150:0x180]), details=det, checksum_ok=ok)


# ---------------------------------------------------------------- SMS / GG
SMS_RANGE = {0xA: 0x1FF0, 0xB: 0x3FF0, 0xC: 0x7FF0, 0xD: 0xBFF0, 0xE: 0x10000,
             0xF: 0x20000, 0x0: 0x40000, 0x1: 0x80000, 0x2: 0x100000}


def sms_checksum(d, hdr):
    end = min(SMS_RANGE.get(d[hdr + 0xF] & 0x0F, len(d)), len(d))
    s = sum(d[0:min(end, 0x7FF0)])
    if end > 0x8000:
        s += sum(d[0x8000:end])
    return s & 0xFFFF


def _sms(d, base, hdr):
    region = d[hdr + 0xF] >> 4
    det = {"header": hex(hdr), "region_code": hex(region),
           "game_gear": region in (5, 6, 7),
           "mapper": "Sega mapper (FFFC-FFFF), 16KB 슬롯 0000/4000/8000"}
    ok = sms_checksum(d, hdr) == int.from_bytes(d[hdr + 0xA:hdr + 0xC], "little")
    if det["game_gear"]:
        det["note"] = "GG 실기는 체크섬 미검사"
    return RomInfo("sms", **base, details=det, checksum_ok=ok)


# ---------------------------------------------------------------- SFC
def sfc_strip(d):
    """복사기 헤더(512B) 크기 반환."""
    return 512 if len(d) % 1024 == 512 else 0


def sfc_header_candidates(rom):
    out = []
    for off, mode in ((0x7FC0, "lorom"), (0xFFC0, "hirom"), (0x40FFC0, "exhirom")):
        if off + 0x40 > len(rom):
            continue
        cmp_ = int.from_bytes(rom[off + 0x1C:off + 0x1E], "little")
        chk = int.from_bytes(rom[off + 0x1E:off + 0x20], "little")
        score = 0
        if cmp_ ^ chk == 0xFFFF:
            score += 4
        mm = rom[off + 0x15]
        if (mm & 0xE0) == 0x20:
            score += 1
            if (mode == "lorom") == ((mm & 1) == 0):
                score += 2
        if all(0x20 <= c < 0x7F or 0xA0 <= c <= 0xDF for c in rom[off:off + 21]):
            score += 2
        if int.from_bytes(rom[off + 0x3C:off + 0x3E], "little") >= 0x8000:
            score += 1
        out.append((score, off, mode))
    return sorted(out, reverse=True)


def sfc_checksum(rom):
    size = len(rom)
    p = 1
    while p * 2 <= size:
        p *= 2
    total = sum(rom[:p])
    if p < size:
        rest = rom[p:]
        total += sum(rest) * (p // len(rest))
    return total & 0xFFFF


def _sfc(d, base):
    hs = sfc_strip(d)
    rom = d[hs:]
    cands = sfc_header_candidates(rom)
    if not cands or cands[0][0] < 4:
        return None
    score, off, mode = cands[0]
    title = rom[off:off + 21].decode("shift_jis", "replace").strip()
    chk = int.from_bytes(rom[off + 0x1E:off + 0x20], "little")
    det = {"mapping": mode, "header_offset": hex(off + hs), "map_mode": hex(rom[off + 0x15]),
           "chip": hex(rom[off + 0x16]), "rom_size": f"{1 << rom[off + 0x17]}KB",
           "sram_size": f"{1 << rom[off + 0x18]}KB" if rom[off + 0x18] else "0",
           "fastrom": bool(rom[off + 0x15] & 0x10), "copier_header": hs}
    tmp = bytearray(rom)
    tmp[off + 0x1C:off + 0x20] = b"\xff\xff\x00\x00"
    return RomInfo("sfc", **base, header_size=hs, title=title, details=det,
                   checksum_ok=sfc_checksum(tmp) == chk)


# ---------------------------------------------------------------- PS
def ps_layout(d):
    if d[0x8001:0x8006] == b"CD001":
        return ("iso2048", 0x8000)
    off = 16 * 2352 + 24
    if d[off + 1:off + 6] == b"CD001":
        return ("raw2352_mode2", off)
    return None


def _ps(d, base, layout):
    kind, pvd = layout
    sysid = _txt(d[pvd + 8:pvd + 40])
    det = {"image": kind, "system_id": sysid, "volume_id": _txt(d[pvd + 40:pvd + 72]),
           "note": "파일 단위 작업: dumpsxiso로 추출 → 수정 → mkpsxiso로 재빌드 (EDC/ECC 재계산 포함)"}
    plat = "ps" if "PLAYSTATION" in sysid else "unknown-cd"
    return RomInfo(plat, **base, title=det["volume_id"], details=det, checksum_ok=None)


# ---------------------------------------------------------------- fix
def fix_checksum(data: bytearray, platform: str) -> str:
    if platform in ("gb", "gbc"):
        data[0x14D] = gb_header_checksum(data)
        g = gb_global_checksum(data)
        data[0x14E:0x150] = g.to_bytes(2, "big")
        return f"GB header={data[0x14D]:02X} global={g:04X}"
    if platform == "md":
        c = md_checksum(data)
        data[0x18E:0x190] = c.to_bytes(2, "big")
        return f"MD checksum={c:04X}"
    if platform == "sms":
        for hdr in (0x7FF0, 0x3FF0, 0x1FF0):
            if data[hdr:hdr + 8] == b"TMR SEGA":
                c = sms_checksum(data, hdr)
                data[hdr + 0xA:hdr + 0xC] = c.to_bytes(2, "little")
                return f"SMS checksum={c:04X} @ {hdr:X}"
        return "SMS 헤더 없음 - 생략"
    if platform == "sfc":
        hs = sfc_strip(data)
        rom = data[hs:]
        _, off, _ = sfc_header_candidates(rom)[0]
        a = hs + off
        data[a + 0x1C:a + 0x20] = b"\xff\xff\x00\x00"
        c = sfc_checksum(data[hs:])
        data[a + 0x1C:a + 0x1E] = (c ^ 0xFFFF).to_bytes(2, "little")
        data[a + 0x1E:a + 0x20] = c.to_bytes(2, "little")
        return f"SFC checksum={c:04X} complement={c ^ 0xFFFF:04X}"
    if platform == "fc":
        return "FC: 헤더 체크섬 없음"
    if platform == "ps":
        return "PS: mkpsxiso 재빌드가 EDC/ECC를 계산함 - 여기서는 처리 안 함"
    return f"{platform}: 지원 안 함"
