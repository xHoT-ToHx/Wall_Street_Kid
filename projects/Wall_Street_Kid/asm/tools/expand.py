"""expand.py - Wall Street Kid UxROM 128KB → UOROM 256KB 확장 (제자리 수정, 멱등).

사용: python asm/tools/expand.py <rom.nes> [--copy 4:12 --copy 6:13]
- 16KB 뱅크 0-6 그대로, 고정 뱅크 7 → 15 (마지막 뱅크가 $C000 고정 → 코드·벡터 수정 불필요).
- 뱅크 7 슬롯(이제 $8000 전환 뱅크)과 8-14 는 0xFF. --copy a:b 는 원본 뱅크 a 를 뱅크 b 로 복사(텍스트 뱅크 이전용).
- NES 2.0 헤더 byte4(PRG 16KB 단위) 8→16. 매퍼 2, 서브매퍼 2(버스충돌) 유지.
- 버스충돌 표 이전($F07E 0-6 → $FE90 0-15)과 훅은 asm/kor_engine.asm 이 담당.
"""
import argparse


def expand(rom, copies):
    rom = bytearray(rom)
    h = rom[:16]
    if h[:4] != b"NES\x1a":
        raise SystemExit("iNES 헤더 아님")
    if h[4] != 8 or len(rom) != 16 + 0x20000:
        print(f"expand: 이미 확장됐거나 예상과 다른 롬(PRG16={h[4]}) → 건너뜀")
        return rom
    banks = [bytes(rom[16 + i * 0x4000:16 + (i + 1) * 0x4000]) for i in range(8)]
    new = [b"\xff" * 0x4000 for _ in range(16)]
    for i in range(7):
        new[i] = banks[i]
    new[15] = banks[7]
    for a, b in copies:
        new[b] = banks[a]
    h[4] = 16
    print(f"expand: PRG 128→256KB (고정뱅크 7→15), 복사 {copies}")
    return bytearray(h + b"".join(new))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rom")
    p.add_argument("--copy", action="append", default=[], help="원본뱅크:새뱅크")
    a = p.parse_args()
    copies = [tuple(int(x) for x in c.split(":")) for c in a.copy]
    d = open(a.rom, "rb").read()
    open(a.rom, "wb").write(expand(d, copies))


if __name__ == "__main__":
    main()
