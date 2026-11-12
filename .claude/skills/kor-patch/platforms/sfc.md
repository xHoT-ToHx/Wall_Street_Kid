# SFC (슈퍼 패미컴 / SNES)

## 하드웨어 요점
- CPU 65816. 맵핑: **LoROM**(뱅크당 32KB, $8000-$FFFF), **HiROM**(뱅크당 64KB, $C0-$FF), ExHiROM. `romkr identify` 가 판정.
- 복사기 헤더(512B)가 있으면 파일 오프셋 +0x200. 작업 전 헤더 제거 권장(통일).
- 타일: BG 2bpp(`sfc2bpp`, GB 와 동일 배치) / 4bpp(`sfc4bpp`) / 8bpp. VRAM 64KB 로 여유가 큼.
- DMA 로 VBlank 중 수 KB 전송 가능 → 16x16 한글 동적 로딩 용이.
- 특수칩(SA-1, SuperFX, S-DD1 압축, SPC7110)은 맵핑/압축이 달라짐 — analysis.md 에 명시.

## 주소 변환
- LoROM 3바이트 포인터: `{"type":"lorom","header":0}` (bank_or 기본 0x80; 원본 포인터가 $00-$7F 뱅크면 `"bank_or":"0x00"`).
- 2바이트 포인터 + 고정 뱅크: `{"type":"lorom","bank":"0xC8"}` → 32KB 창을 넘으면 오류.
- HiROM: `{"type":"hirom"}`, 2바이트면 `"bank"` 지정.

## 텍스트 엔진 특징
- 1바이트 가나 + 2바이트 한자(리드바이트) 혼합이 흔함 → 한자 리드바이트 경로를 한글용으로 재활용하기 좋음.
- 8x8, 8x16, 12x12/16x16 VWF 다양. DTE 압축·사전 압축(단어 테이블) 흔함.

## 한글 폰트 전략
1. **16x16 또는 12x12 + 2바이트 코드 + 동적 로딩**: 표준. KS X 1001 2350자 전체도 롬 공간만 있으면 가능(16x16 2bpp=64B/자 → 2350자 ≈ 150KB).
2. 8x16(가로 8): 원본이 8x16 영문/가나면 가로폭 부족 → 한글은 16폭 2셀 사용.
3. VWF 엔진이면 1bpp-linear + 폭 테이블.

## 확장 / 체크섬
- LoROM 최대 4MB(일반 32Mbit), 확장 시 헤더 ROM size($xxD7) 갱신. 체크섬은 `romkr build` 가 자동 수정.
- asar 의 `lorom`/`hirom`, `freespace`, `org` 사용.

## 도구
- 어셈블러: asar. 디버거: Mesen2 (emucap). 압축: Lunar Compress 류(LZ 형식 식별 후).
