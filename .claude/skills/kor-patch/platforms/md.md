# MD (메가 드라이브 / Genesis)

## 하드웨어 요점
- CPU 68000 (빅엔디언, 32비트 포인터) + 사운드 Z80. 롬은 $000000 부터 선형 매핑(최대 4MB, 그 이상은 SSF2 매퍼).
- `.smd` 는 인터리브 포맷 → 반드시 `.bin` 으로 변환 후 작업.
- 타일: **4bpp packed, 상위 니블=왼쪽 픽셀** (`md4bpp`), 32바이트/타일. VRAM 64KB, DMA 로 대량 전송 가능.
- 헤더 $100 "SEGA", 체크섬 $18E(빅엔디언) — 일부 게임은 부팅 시 검사. `romkr build` 가 수정.

## 주소 변환
- 4바이트 BE 포인터: `{"type":"linear","cpu_base":"0","file_base":"0"}`, pointer_table `"size":4,"endian":"big"`.
- 상대 오프셋(2바이트, 기준주소 + offset) 테이블도 흔함: 기준 주소를 `file_base`/`cpu_base` 로 맞춰 linear 처리(`cpu_base:"0"`, `file_base:"<기준>"`).

## 텍스트 엔진 특징
- Shift-JIS 원문 그대로 저장한 게임이 꽤 있음 → SJIS 바이트를 직접 검색. 그렇지 않으면 1바이트 독자 코드.
- 8x8 / 8x16 / 16x16 폰트, 1bpp 압축 폰트 다수(4bpp 로 펼쳐 VRAM 로드).
- 짝수 주소 정렬 주의: 68000 은 워드/롱 접근이 홀수 주소면 Address Error → 문자열 시작은 상관없지만 포인터 테이블·워드 데이터는 짝수 정렬 유지.

## 한글 폰트 전략
1. 16x16 1bpp 폰트를 롬에 두고 출력 시 4bpp 로 변환해 VRAM 업로드(동적). 롬 공간이 넉넉해 2350자 전체도 무난(32B/자 → 약 75KB).
2. 원본이 SJIS 2바이트면 SJIS 코드 영역(예: 0x88-0x9F 리드)을 한글 코드로 재배정.

## 도구
- 어셈블러: vasm (mot 문법) / asmx. 디버거: Mednafen 포크(emucap, `status.memory_types` 확인).
- 압축: Nemesis/Kosinski/Enigma(세가 퍼스트파티), LZSS 계열 — 식별 후 도구 선택.
