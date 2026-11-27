"""빌드 단계: font/orig_font_overrides.json 의 원본 영문 8x8 글리프를 롬에 덮어쓴다 (파일 0x2375 + 8*코드).
    python tools/apply_orig_font.py <rom>      (project.json commands, expand 직후)
오버라이드 파일이 없거나 비어 있으면 아무것도 바꾸지 않는다."""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OVR = os.path.join(ROOT, "font", "orig_font_overrides.json")
FONT_OFF, NGLYPH = 0x2375, 55

rom_path = sys.argv[1]
ov = json.load(open(OVR, encoding="utf-8")) if os.path.exists(OVR) else {}
if ov:
    rom = bytearray(open(rom_path, "rb").read())
    for k, v in ov.items():
        i = int(k, 16)
        g = bytes.fromhex(v)
        assert i < NGLYPH and len(g) == 8, f"잘못된 오버라이드 {k}"
        rom[FONT_OFF + 8 * i: FONT_OFF + 8 * i + 8] = g
    open(rom_path, "wb").write(rom)
print(f"원본 영문 폰트 오버라이드 {len(ov)}자")
