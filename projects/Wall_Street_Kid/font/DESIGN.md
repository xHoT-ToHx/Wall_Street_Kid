# 한글 폰트 설계 — Wall Street Kid (FC, UxROM, CHR-RAM 8KB)

작성: font-engineer. 근거: analysis.md §2·§4·§5·§7, scripts/README.md §2, 선행 프로젝트(Super_Express_Satsujin_Jiken/font/DESIGN.md), 롬 직접 판독.
표기: [확인] 실측 / [정적] 데이터 판독 / [추정]. 번역 미착수라 글자 수는 KS X 1001 임시 세트 기준.

## 0. 결론
- **대사창(28칸 x 6줄, 줄 사이 빈 행)**: 8x16 한글(8px 폭 x 16px = 세로 타일 2장), 줄당 28자 그대로. **Galmuri11 Condensed 12px** (OFL). 한글 7x11 을 셀 y4-14 에 배치(기준선 y14), x7 은 자간.
- **영문·숫자·기호**: 대사창에서는 8x16 글리프로 같은 bin 에 포함(원본 8x8 을 8x16 문자열에 섞으면 기준선·높이가 어긋남). 숫자·구두점은 **Galmuri11 Bold** (한글 Condensed 와 굵기가 다르지만 숫자 자간·굵기가 원본 폰트와 비슷해 금액이 또렷함). 1행 피치 화면의 숫자·영문은 원본 8x8 타일을 그대로 쓴다.
- **1행 피치 화면(종목 목록·열 머리·CASH:/STOCKS:·요일·분류)**: **8x8 한글(Galmuri7 7x7)** 을 화면 진입 시 정적 업로드(고정 라벨 ≈ 40자 + 종목명 ≈ 50~70자). 상세 §4.
- 포맷: 기본 **1bpp, 가로 8 x 세로 16, 글리프당 16B(위 타일 8B + 아래 타일 8B), 글리프 번호 순 연속**. 인자로 fc2bpp(32B) 등으로 바꿀 수 있다.
- 임시 코드 배정: 2바이트 `5000 + 글리프번호` (리드 0x50-0x59, 원본 텍스트가 안 쓰는 0x37-0x7F 안). **잠정**, asm 인터페이스 확정 시 `--code-start` 로 재생성.

## 1. 원본 폰트 실측 [확인]
- 원본 영문: bank0 파일 0x2375, 1bpp 8x8 55타일. 글자는 타일 안 x1-6 / y1-7(위 1행·오른쪽 1열 공백), 굵은 2px 획. 색 인덱스는 1bpp 이므로 글자=1 배경=0(업로드가 plane1=0).
- 대사창 2행 피치: 영문 글자는 한 타일행(8px), 그 아래 타일행이 비어 있음. 한글은 이 16px 전체를 쓰되 위 4px·아래 1px 를 비워 줄 사이 5px 확보.
- 한글 기준선: 셀 y14(아래 타일 y6). 원본 영문 기준선이 타일 y7 이므로 아래 타일에 놓이는 영문보다 1px 위. 숫자·기호 Bold 도 같은 oy 로 그려 한글과 y14 에 맞음.

## 2. 후보 비교와 가독성 판단 (font/preview/)
| 후보 | 구성 | 판단 |
|---|---|---|
| **A Galmuri11 Condensed 12px, 8x16** | 7x11 한글, 줄당 28자 | **채택**. 자소 구분 가능. 겹받침(밝·읽·젊)·ㅐ/ㅔ/ㅙ 계열은 빽빽하지만 문맥상 판독(preview/dense_8x16.png). 선행 FC 프로젝트에서 같은 설정 실사용 |
| B Galmuri7 7x7, 8x8 | 줄 높이 1타일 | 대사창에는 부적합(작고 획 뭉침). 1행 피치 라벨 전용으로 사용 |
| C Galmuri11 11x11 16x16 | 줄당 14자 | 기각: 대사창 28칸 기준 장문 번역이 지나치게 길어짐(분량 약 30,000자) |
- 판단: 획이 가늘고 키가 큰 편이라 원본 굵은 영문 폰트(밝은 2px 획)보다 옅어 보인다. 대사창에서 충분히 읽힌다. 장식 효과(굵게)는 8px 폭에 한글이 안 들어가 포기(Galmuri11 Bold 한글은 16자 중 다수가 8px 초과로 잘림).
- 숫자: Galmuri11 Condensed 숫자는 폭 4~5px 라 `1 , 0 0 0` 처럼 벌어짐 → Bold 채택. 셀 밖으로 넘치는 `M W m w % & # ~ …` 은 Bold 불가라 Condensed 유지(가는 선). 콤마 등 아래로 넘치는 Bold 글자는 1~2px 올림(build_font.py 가 자동 시험).
- 미리보기: `preview/dialog_28x6.png`(원본 영문 vs 한글, 28x6 모의), `dense_8x16.png`(어려운 음절), `ui8_labels.png`(1행 피치 8x8 라벨 vs 영문), `build/font_preview.png`(전체 2,436자).
- 잘림 검사: 2,436자 전부 셀 밖 넘침 0, 빈 글리프 0.

## 3. 생성기와 재현 (font/tools/)
```
# 모두 projects/Wall_Street_Kid 에서, 환경 PYTHONPATH=<워크트리>/tools PYTHONUTF8=1
# (A) 임시 문자셋(KS X 1001 + 기호): romkr charset 사용
python -m romkr charset "scripts/*.json" --out font/charset_ksx1001.txt --ksx1001 --extra "<ASCII 기호>"
cp font/charset_ksx1001.txt font/charset.txt
# (B) 8x16 대사 폰트 + 코드표 + 미리보기
python font/tools/build_font.py                      # 기본: --charset font/charset.txt, 8x16, 1bpp, code-start 0x5000
# (C) 1행 피치 8x8 라벨 폰트
python font/tools/build_font.py --ascii-ttf "" --charset font/ui8_charset.txt --ttf font/Galmuri7.ttf --size 8 \
       --cell 8x8 --oy 0 --out build/font_ui8.bin --tbl-out "" --preview build/font_ui8_preview.png
# (D) 모의 화면
python font/tools/render_sample.py
```
- `build_font.py` 인자: `--cell WxH --format 1bpp|fc2bpp --order row --code-start --code-bytes --skip-low --ttf --ascii-ttf --size --ox --oy --fg --bg --out --tbl-out --preview --meta-out`. 번역 확정 후에는 `romkr charset ... --capacity N` 으로 빈도순 `font/charset.txt` 를 다시 만들고 (B) 재실행. 포맷은 asm/DESIGN.md "폰트 인터페이스" 가 확정되면 인자만 바꿔 재생성.
- 산출(build/ 는 git 제외): `font.bin`(38,976B), `font_preview.png`, `font_ui8.bin`(344B), `tables/ko_font.tbl`(코드표, 머리말에 "잠정" 표시).
- 글리프 번호 i 의 위치: `bin[i*16 : i*16+16]`, 코드 = `0x5000 + i`. charset 순서: ASCII 기호 86자(숫자·대소문자·`!?.,:;-+*/()%&$#@'"~…·「」`) → KS X 1001 가나다순(임시). 최종은 빈도순.
- 라이선스: `font/Galmuri-OFL-LICENSE.txt` (Galmuri11-Condensed, Galmuri7, Galmuri11-Bold 모두 Lee Minseo, OFL 1.1). 패치 README 에 폰트명·저작권·OFL 표기 필요. 손질한 글리프(overrides) 없음.

## 4. 1행 피치 화면 평가
화면 별 줄 구조 (scripts/README.md, analysis.md §2):
| 화면 | 구조 | 권고 |
|---|---|---|
| 대사창·신문·뉴스·종목 설명(stock_desc COMMENTS 4줄, 26칸) | 2행 피치 [확인](대사창) / COMMENTS 는 [추정] | 8x16 |
| 매매 화면 안내문 ("IF YOU'D LIKE TO BUY STOCK,\n\n SELECT ONE NOW.\n\n") | 문장 줄 사이 빈 줄 있음 [정적] | 8x16 가능(asm 이 해당 창 모드 확인) |
| 열 머리 `STOCK CUR. ORIG. LOTS` / `STOCK PRICE %CHANGE`, CASH:/STOCKS: | 바로 아래 숫자 행 → 1행 피치 [정적] | **8x8**: 종목·현재·매입·수량 / 종목·가격·등락 |
| 종목 목록의 종목명(20개, 최대 23칸) | 1행 피치 [정적] | **8x8**, 번역 시 ≤6음절 권고 |
| 분류 4종(SPECULATIVE 등), 요일 7(3칸), 상태창 5/7칸 | 1행 | **8x8**. 요일=`일월화수목금토`(1칸씩, 3칸 안에 들어감), CASH:=`현금:`, STOCKS:=`보유:`(후보) |
| 메뉴(menu_b7: 17 항목+인물 이름표) | 줄 피치 미확인 | asm/QA 가 확인. 2행 피치면 8x16, 아니면 8x8 |
| 패스워드 화면 | 문자표가 0x00-0x40 전체 사용 | 문자(알파벳)는 영문 유지, 안내문 4줄만 번역 |
- 8x8 판독성: 2글자 단어(종목·현재·매입·수량·가격·등락·현금·보유·투기주·우량주)는 `preview/ui8_labels.png` 에서 읽힘. 종목명은 길이 늘면 위험 → 약어 사용.
- 8x8 필요 글자 후보 43자(font/ui8_charset.txt, 번역 확정 전 추정) ≈ 344B. 종목명 20개 추가 시 +50~70자(≈ 0.5KB). ROM 용량은 무시 가능, 문제는 **BG 타일 슬롯**: 8x8 한 글자 = 타일 1장. 매매 화면에서 BG 0x4A-0xFF 중 몇 장이 실제 비어 있는지 에뮬로 확인 필요(그림 타일 0x60-0xFF 는 장면별, 매매 화면은 그림이 없어 거의 비었을 가능성 [추정], 미검증). 합계 100~120장이 필요하다. 부족하면 종목명을 약어(2~3자)로 줄이고 목록을 페이지 분할.
- 8x16 을 1행 피치에 억지로 쓰는 안은 불가(아래 행 데이터와 겹침).

## 5. 그래픽 문자 조사
방법: work/dump_title/nametable.bin(데모 타이틀 화면 세이브스테이트)과 ROM 에서 판독. CHR 타일 실제 이미지는 에뮬 접근이 없어 렌더하지 못함(타일 데이터 위치도 미확인 — bank1-3 의 2bpp 판독은 비압축처럼 보이나 정렬·압축 여부 미확정). [정적]
| 대상 | 위치·크기 | 난이도 | 권장 |
|---|---|---|---|
| 타이틀 로고 "WALL $TREET KID" | 네임테이블 행2-10, 열4-29, 로고 타일 150칸(150종 전부 유일, 중복 없음)·붉은 바탕 EF·테두리 FE·하단선 60. 팔레트 4색 2종 사용(속성표 확인). 타일 00-09 는 로고가 폰트 숫자 타일 자리를 임시로 덮어씀 | **높음**: 타일 데이터 위치·압축 형식 확정, 150타일 재그리기, 로고 폭(26칸) 안에 영문 3D 글자(입체감·그림자)를 한글로 대체 시 시각 퀄리티 부담 | **유지 권장**. 대안: 로고 아래 빈 영역(행11-13, 열2-11 은 하늘 배경 빈 타일 49)에 한글 부제 "월스트리트 키드" 를 8x16 또는 8x8 로 추가(타일 7~14장) |
| "TM" 기호 | 행6 열28-29, 타일 34·35 | 낮음 | 유지 |
| 타이틀 메뉴 "NEW GAME  SAVED GAME" | bank4 0x10131, 20B 한 행 고정. 타이틀 전용 타일 13종(N E M W G A S V D © 1 9 0 = 0x24-0x32) 사용. 표시 표 $810D/$8111 | **낮음~중간**: 타이틀 전용 타일 슬롯 7개를 한글 8x8 `새 게 임 이 어 하 기` 로 덮으면 같은 20칸에 `새게임  이어하기`(2+8) 형태. 타일 업로드 데이터 위치 확인 필요 | **한글화 권장**(8x8 Galmuri7 7타일, 슬롯 13개 중 재사용). 대안 8x16(2행)은 아래 행이 비었는지 확인 후 |
| "©1990 SOFEL CORP.", "LICENSED BY", "NINTENDO OF AMERICA INC." | bank4 0x10145 17B / 0x10156 11B / 0x10161 24B, 일반 텍스트 | - | 법적 표기, 유지 |
| "FEATURING..." + 인물 소개 | 행23 텍스트(spec: title_featuring 12B 고정), 소개 줄은 대사 | 낮음 | 8x8 `출연:`(12칸 제한) 또는 유지 |
| SOFEL 로고 | 위치 미확인 (타이틀 이전 화면으로 추정, 세이브스테이트 없음) | 미상 | 유지(발매사 로고) |
| 장면 그림 속 글자(간판 등) | 전수 확인 못 함 | 미상 | 유지. QA 가 전 장면 스크린샷으로 영문 그림 문자 목록화 |
| 스태프 롤 | bank7 0x1EED7-, 텍스트 형식(별도) | 중간(33/34 구분자 형식 해석 필요) | 선택. 후순위 |
- 로고 교체를 하게 되면 선행 작업: (1) 로고 타일 데이터 위치·형식 확정(asm-hacker), (2) 원본 팔레트 4색으로 한글 로고 제작, (3) 타일맵 수정 목록(행2-10 열4-29, 150칸 중 변경될 칸)을 asm-hacker/script-engineer 에 전달. 메인 세션 결정 뒤 착수.

## 6. 용량 추정
글리프 1bpp 8x16 = 16B, 2bpp 변환은 업로드 시(plane1=0). ASCII 86자 포함.
| 시나리오 | 글자 수 | 1bpp 16B | 2bpp 32B |
|---|---|---|---|
| KS X 1001 전체 + ASCII (임시 bin) | 2,436 | **38,976B (≈ 2.4 뱅크)** | 77,952B |
| 실사용 600자 + ASCII 86 | 686 | 10,976B | 21,952B |
| 실사용 900자 + ASCII 86 | 986 | 15,776B (≈ 1 뱅크) | 31,552B |
- 같은 바이트라면 1bpp 로 저장하고 업로드 때 plane1 을 0 으로 채우는 쪽이 ROM 이 절반이다(NMI 쓰기는 글리프당 32B 동일).
- 8x8 라벨 폰트 100~120자 x 8B ≈ 0.8-1KB (정적 업로드 소스).
- 대사 본문 크기 [추정]: 영문 약 30,000자(원문 28,500B). 한글은 음절당 2B 코드 + 공백 1B + 제어 → 대략 한글 12,000~16,000자 x 2B ≈ 25~35KB(원문보다 약간 많음). 텍스트 뱅크 2~3개 + 폰트 1~3개 → 128KB 에서 256KB 확장 안에 충분.
- 동적 업로드 지연 [추정]: 글리프 32B/NMI 예산 100~160B → 프레임당 3~4자. 한 줄 28자 전부 새 글자여도 약 7~9프레임, 타자 출력 속도 안에서 체감 지연 작음. 페이지 단위로 미리 올릴 수도 있음.
- 슬롯: CHR-RAM SPR 테이블 227 타일 여유 [확인, analysis §4] → 8x16 글리프 약 113자까지 동시 상주. 한 페이지 최대 168칸이므로 고유 음절 ≤ 110 을 번역 지침으로 두면 거의 문제없음(통상 70~100). 초과 시 `<PAGE>` 분할 또는 asm 의 슬롯 교체 정책.

## 7. asm-hacker 와 맞출 사항 (폰트 인터페이스 제안)
1. 포맷: 1bpp 16B/글리프(위 타일 8행 → 아래 타일 8행, MSB=왼쪽, 1=글자), 번호 순 연속. fc2bpp/32B 가 필요하면 `--format fc2bpp` 로 즉시 재생성.
2. 코드: 임시 `5000+번호`. 리드 바이트 범위·제어코드(0xFB-0xFF) 충돌 여부, 1바이트 ASCII(숫자·`$`·`,` 등) 코드 체계를 확정해 알려 달라. ASCII 글리프를 1바이트로 둘지(원본 8x8 타일 코드와 분리 필요)에 따라 charset 의 앞 86자를 분리 생성 가능.
3. 대사창 8x16 / 1행 피치 8x8 두 경로가 필요: 대사창 = 동적 업로드, 1행 화면 = 화면 진입 시 8x8 정적 세트(`font_ui8.bin`) 업로드 + 문자열은 해당 타일 번호를 1바이트로 직접 출력.
4. 8x16 은 글자 하나가 위/아래 2개의 네임테이블 행을 쓴다(행 y 와 y+1, 사이 빈 행 없음). 대사창 기존 줄 피치(2행)와 일치 [확인].
5. 확인 요청: (a) 매매 화면·메뉴·상태창의 줄 피치와 BG 빈 타일 수, (b) 타이틀 전용 타일 업로드 데이터 위치/형식(메뉴 8x8 덮어쓰기용), (c) 요일 3칸·CASH: 5칸 등 고정폭 문자열이 8x8 1글자/칸으로 들어가는지.
6. project.json font 섹션 제안(미적용, asm 확정 후 반영):
```json
"font": {"charset": "font/charset.txt", "ttf": "font/Galmuri11-Condensed.ttf", "size": 12, "cell": "8x16",
         "format": "1bpp", "offset_y": 3, "fg": 1, "bg": 0, "order": "row",
         "code_start": "0x5000", "code_bytes": 2,
         "bin_out": "build/font.bin", "tbl_out": "tables/ko_font.tbl", "preview_out": "build/font_preview.png"}
```
   (romkr font 단독 실행은 ASCII Bold 선택·자동 올림을 하지 않으므로 최종 빌드는 font/tools/build_font.py 사용. 필요하면 build.commands 에 추가.)

## 8. 파일
- font/DESIGN.md, font/charset.txt(=임시 KS X 1001+ASCII 2,436자), font/charset_ksx1001.txt, font/ui8_charset.txt(8x8 후보 43자)
- font/tools/build_font.py, font/tools/render_sample.py
- font/Galmuri11-Condensed.ttf, font/Galmuri11-Bold.ttf, font/Galmuri7.ttf, font/Galmuri-OFL-LICENSE.txt
- font/preview/dialog_28x6.png, dense_8x16.png, ui8_labels.png
- build/font.bin, font_preview.png, font_ui8.bin, font_ui8_preview.png (git 제외), tables/ko_font.tbl (잠정 코드)
