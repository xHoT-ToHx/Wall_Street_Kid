# PS (플레이스테이션)

## 하드웨어/이미지 요점
- CPU MIPS R3000A(리틀엔디언, 32비트 포인터, 주소 $80000000 대). 디스크는 ISO9660 Mode2 (BIN/CUE, 2352B 섹터).
- **파일 단위 작업**: `dumpsxiso` 로 파일 + 레이아웃 XML 추출 → 파일 수정 → `mkpsxiso` 로 재빌드(EDC/ECC 자동). 원본 섹터 순서 유지가 중요.
- 실행파일 `SLPS_xxx.xx`(PS-X EXE): 헤더 0x800, 로드 주소는 헤더 +0x18. → 파일오프셋 = 주소 - 로드주소 + 0x800.
- 그래픽: TIM(4/8/16bpp), VRAM 1024x512 16비트. 폰트는 4bpp(`ps4bpp`, 하위 니블=왼쪽)나 1bpp 가 흔함.
- 일부 게임은 파일 LBA/크기를 실행파일이나 인덱스 파일에 하드코딩 → 파일 크기 변경 시 갱신 필요(가능하면 크기 유지/패딩).

## 주소 변환 (spec.json, 대상 파일 = 추출된 개별 파일)
- EXE 내부 포인터: `{"type":"linear","cpu_base":"<로드주소>","file_base":"0x800"}`, size 4, little.
- 데이터 파일 내부 상대 오프셋: `cpu_base:"0"`, `file_base:"<테이블 기준>"`.
- project.json 의 `rom` 은 작업 대상 파일(예: `rom/extracted/DATA/MSG.BIN`), 디스크 재빌드는 `commands` 에 mkpsxiso 등록.

## 텍스트 엔진 특징
- Shift-JIS 원문이 대부분. 텍스트는 별도 데이터 파일(아카이브 내부 압축 LZ 계열 다수)이나 EXE 내부.
- 폰트: BIOS 내장 SJIS 폰트를 쓰는 게임(Krom) / 자체 폰트 TIM.

## 한글 폰트 전략
1. SJIS 2바이트 영역을 한글 코드로 재배정(예: 리드바이트 0x88~0x9F 범위에 2350자 매핑) + 자체 폰트 TIM 교체.
2. BIOS 폰트 사용 게임: 폰트 읽기 루틴을 후킹해 롬(디스크) 내 한글 폰트로 우회.
3. VRAM 여유가 크므로 상주 폰트로 충분한 경우가 많음.

## 패치 배포
- 디스크 단위 패치는 xdelta3 (원본 bin ↔ 빌드 bin). IPS 불가(16MB 제한), romkr 의 BPS 는 대용량에서 느리므로 비권장.

## 도구
- dumpsxiso/mkpsxiso, armips (`.psx`, `.open`, `.org`), TIM 툴(Tim2View 등), 압축 형식 식별 후 전용 도구.
- 디버거: Mednafen 포크(emucap, `status.memory_types` 확인).
