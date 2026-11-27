# asm 변경 기록 — Wall Street Kid

## 2026-11-17 G3 한글 엔진 (kor_engine.asm)
### 롬 구조 (asm/tools/expand.py)
- PRG 128→256KB, 고정 뱅크 7→15, 헤더 byte4=16. `--copy 4:12 --copy 6:13`.

### 훅 (고정 뱅크 15)
| 주소 | 원래 | 변경 | 목적 |
|---|---|---|---|
| $F076 | STA $F07E,X | STA $FE90,X | 버스충돌 표 이전(0-15) |
| $F8ED | STA $F07E,X | STA $FE90,X | NMI 작업 뱅크 전환 |
| $F962-$F96F | LDA $06/BEQ/OAM DMA | JSR kdma / JMP $F970 | NMI 시작: 분할 BG 복귀 + 원래 DMA |
| $F981 | LDA $0A / BEQ $F98E | JSR nmi_post / NOP | 작업 직후 감지 스프라이트·분할 대기 |
| $F197 | STA $02/STA $2001/RTS | JMP kmask | 렌더링 꺼지면 분할 해제 |
| $F03B | JMP ($FFDE) | JMP kinit | 리셋 시 엔진 변수 초기화 |
| $D7BC-$D7C6 | 뱅크 전환 | JSR kbank / JMP $D7C7 / NOP x5 | 4→12, 6→13 치환, 항상 복원 |
| $D7CB-$D7D0 | PLA/BMI/JSR $F066 | PLA / JSR fastsw / NOP x2 | 끝에서 원래 뱅크로(대기 없음) |
| $D90E-$D912 | TXA/CMP #$FB/BCC | JMP khook / NOP x2 | 2바이트 한글·점프·1바이트 변환 |
| $D948 | STY $0325 | JSR krows | 8x16 이면 2행 플러시 |
| $D8A8 | JSR $DA62 | JSR kpage | <PAGE> 시 슬롯 캐시 초기화 |

### 빈 공간 사용
| 위치 | 크기 | 내용 |
|---|---|---|
| 고정뱅크 $FE90-$FFBF (파일 0x3FEA0-0x3FFCF) | 304B | 버스표 16B + 고정부 코드. 원래 password_b7 예약분 → **패스워드 문자열은 $FFC0-$FFDD(30B) 또는 다른 뱅크 + 4F 점프 스텁으로 재배정 필요** |
| 뱅크 7 $8000- | 약 0.9KB | 엔진 코드·표(build/kor_tables.asm) |
| 뱅크 7·8·9·10 $BFA0-$BFF8 | 89B x4 | kcopy 공유 코드 |
| 뱅크 0-14 $BFF9 | 1B | 뱅크 번호 표식(원본 0 패딩) |
| 뱅크 8-10 $8000-$BF9F | 39KB | 폰트 |
| 뱅크 12 $8181-$BFF8, 13 $9281-$BFF8 | 원래 텍스트 영역 | 한글 텍스트 |
| RAM $0600-$06ED, $05C0-$05DF, $05F0-$05F7 | | 엔진 변수 |

### 검증용
- 롬: build/Wall_Street_Kid_kr.nes (sha1 은 빌드 로그). 세이브스테이트 work/g3_kr_larry_start.mss (NEW GAME 직후, 이 빌드 전용).
- 입력: 전원 → START(타이틀 메뉴) → START(NEW GAME) → 약 340프레임 → 래리 대사(qa/g3_kr_larry_dialog.png) → A 길게 6회 → 스크롤 후(qa/g3_kr_larry_scroll.png).
- 확장만 한 롬 시험: work/bus_only.asm (확장 + 버스표만), work/g3_expand_larry.mss.

## 2026-11-18 2차: 대사창 외 화면 (kor_engine.asm, kor_build.py ui/title) — 에뮬 미사용, 정적 모의만
### 훅 (고정 뱅크 15)
| 주소 | 원래 | 변경 | 목적 |
|---|---|---|---|
| $CBEB | JMP $CE03 | JMP ulab | CHR 로더($CB33) 끝: 8x8 풀 상태·라벨 타일 |
| $CCAA | JMP $CE03 | JMP ulab | CHR 로더($CBF2) 끝: 같음 |
| $DC82-$DC87 | LDY #0 / LDA ($8F),Y .. (복사 루프 앞 6B) | JSR ntag / JMP $DC90 | 이름표 [60 ii] → 풀 타일 |
| $DDB9-$DDBE | 같은 루프 | JSR ntag / JMP $DDC7 | 이름표 2 |
| khook 안 | CMP #$60 | CMP #$61 | 리드 60 = 8x8 |
| eng_split @out 분기(뱅크 7) | - | KDCLR/KDBUSY 증가 | 분할 건너뜀 원인 진단(DESIGN §12) |
| khook @orig | LDA KC / CMP #$FB / JMP $D918 | JMP korig | 4E = NOP |
| $F03B | JMP kinit (1차) | 그대로, kinit 을 $C003 로 이동 + USTATE=0 | |
| $D081-$D08C | "CASH:" "STOCKS:" | 4A 4B 2E 49 49 / 4C 4D 2E 49 49 49 49 | 상태창 라벨 고정 타일 |
| $C407-$C41B | SUN..SAT | [60 ii 4E] x7 | 요일 |
| 메뉴 표 $C801-, 이름표 $DCA4-, $DDDB- | 포인터 | 새 위치 | menu_b7 재배치 |

### 데이터 (ROM, 코드 아님)
| 위치 | 내용 |
|---|---|
| bank2 $8FF3 + 타일*16 (파일 0x8FF3+) | 타이틀 CHR: 25 26 27 28 2A 2B 2C = 새게임이어하기(색2), 24 39 29 31 = 등장인물(색1) |
| bank4 $8121 (0x10131, 20B) + bank12 사본(0x30131) | 타이틀 메뉴 문자열 |
| bank5 $846C (0x1447C, 12B) | FEATURING → 49 24 39 29 31 30 30 30 49 x4 |
| bank5 0x1758A-0x18009 (stock_desc/ui/names/cat 영역) | 한글 재배치 + 포인터표 갱신 |

### 빈 공간 사용
| 위치 | 크기 | 내용 |
|---|---|---|
| 고정뱅크 $C003-$C00D (파일 0x3C013-0x3C01D) | 11/13B | kinit (리셋 벡터 $C000 → JMP $C010 사이 0 패딩, 미실행) |
| 고정뱅크 $E102-$E114 (파일 0x3E112-0x3E124), 예약 $E102-$E121 | 19/32B | korig. menu_b7 영역 끝 32B 를 gen_spec.py 에서 제외 |
| 고정뱅크 $FF74-$FFD4 | (기존 $FE90-$FFBF 에서 확장, 끝 $FFDD) | ulab, ntag. 남은 $FFD5-$FFDD 9B |
| 뱅크 7 $8000-$8F7E | 약 3.9KB (1차 0.9KB 포함) | eng_ui8/u8tile/eng_ntag/eng_chr + UI8FONT(121자 968B)·UI8G·LABIMG·POOL 표 |
| 뱅크 11 $A000-$A03E | 63B (상한 $BF9F) | UI 문자열 넘침 본문. 대사 넘침은 $8000-$9FFF 로 제한 |
| RAM $0560-$05B9 | 90B | §8 |

### 검증용 (정적, 에뮬 아님)
- `python work/asm2/t_screens.py` / `t_var.py` / `t_render.py` / `t_title.py` (projects/Wall_Street_Kid 에서) → qa/asm2_sim_*.png.
- 에뮬 확인 대기 목록: DESIGN.md §13.

## 2026-11-18~23 QA 1차 수정 (DESIGN §15)
### 훅 추가·변경
| 주소 | 원래 | 변경 | 목적 |
|---|---|---|---|
| nmi_post 첫머리(고정) | - | JSR hkpre($E101) | $D2A3 훅을 분할 대기 전·메인 뱅크로 실행(A1/A2/A6) |
| $F210 | JSR $F489 | JSR kq($E0D5) | $F20F 원시 기록이 분할 구간이면 분할 해제+마지막 행 지우기 |
| $C463-$C468 | 요일 복사 루프 | JSR kwdbox / JMP $C471 | 날짜 상자 요일 8x8 |
| $CD73 | STA $40 / TYA | JSR kcls($FF5C) | 화면 전체 지우기 → 8x8 캐시 무효화 예약 |
| eng_split @clr(뱅크 7) | 분할 건너뜀 | 분할 줄 대기로 진행 | A3 |
| eng_nmipre(뱅크 7) | - | KACT=5 처리(wclr) | 창 마지막 행 지우기 |
| kdma(고정) | - | X 사용으로 2B 절약 | 고정 공간 |

### 빈 공간
| 위치 | 크기 | 내용 |
|---|---|---|
| 고정 $E0C2-$E121 (menu_b7 영역 끝 96B, gen_spec.py 에서 제외) | 90/96B | korig·kq·kwdbox·hkpre |
| 고정 $FF5C- (엔진 고정부, 끝 $FFDC) | | kcls 추가 |
| RAM $05BA KTHI, $05BB KINVF | 2B | |
| 뱅크 11 $A000-$A134 | 309B | UI 넘침(메뉴 스텁 14·패스워드 4 포함) |

### 검증 롬·상태 (work/asm2, git 제외)
- wsk_asm2j.nes(sha1 1978A31A…) 기준. 상태: j_news.mss(신문 시작), j_home.mss(랄프 전화 뒤 홈). **이 롬 전용**(다른 빌드에 로드하면 8x8 풀 포인터가 어긋남).
- 재현: 리셋 → 750프레임 → START(메뉴) → START(새 게임) → 900프레임 → A 탭(4프레임 누름, 300프레임 간격)으로 래리 대사·신문·랄프 전화 → 홈. 은행: 홈에서 왼쪽 6·아래 5 → A.

## 2026-11-23 QA 2차 V1 (DESIGN §16)
- tools/gen_spec.py: stock_ui_b5 삽입 영역 끝 0x17E3E → 0x17E2C (0x17E2D-0x17E3E = 확인 프롬프트 `$D27F` 레코드 목록 보존). spec.json 재생성.
- asm/tools/kor_build.py ui: 삽입 영역 안의 비문자열 원본 데이터 보호 검사(위반 시 빌드 실패).
- 코드·빈 공간 변경 없음. 검증 롬 work/asm2/wsk_v1fix.nes(sha1 3A509743…), 상태 work/asm2/v1fix_home.mss(이 롬 전용, 랄프 전화 뒤 홈).
- 재현(새 빌드): v1fix_home.mss → 왼쪽 3·위 2 → A(컴퓨터) → 아래 → A(주식 매수) → A(AT&T) → 오른쪽 3·위 1(수량 0001) → A → A(YES).

## 2026-11-23 QA 2차 V2 (DESIGN §17)
- kor_engine.asm eng_chr: USTATE=$13(큰 맵) 이면 상태창 라벨 업로드 생략(0x4C-0x5B 는 래리 얼굴 패치 `$D402` 가 씀).
- kor_build.py ui 풀: 맵 1-$11 은 CHR 로드 범위 전체 제외, 큰 맵 풀 0, 맵 0 은 기존대로.
- 빈 공간 변경 없음(엔진 뱅크 코드 +7B). 검증 롬 work/asm2/wsk_v2fix.nes(sha1 464AFDCA…), 상태 work/asm2/v2_fri.mss(금 4/14 신문, 이 롬 전용 아님 — v0.2.1 상태에서 이어진 것).
- M1: 수정 없음(8x8 글리프가 1-7행 사용, 폰트 한계).

## 2026-11-26 fix3 (DESIGN §18)
### 훅·데이터
| 주소 | 원래 | 변경 | 목적 |
|---|---|---|---|
| $C003 kinit | LDA #0 / STA KACT / STA USTATE / JMP ($FFDE) | LDA #0 / STA KMAG / JMP ($FFDE) | 첫 NMI 에서 eng_init(엔진 RAM 전체 초기화) |
| $F98E | JSR $DE67 | JSR ksnd | NMI 사운드 재진입 방지 |
| $D242 / $D246 | 04 / 06 | 05 / 07 | 데모·엔딩 카드 창 높이 +1(28행 지우기) |
| nmi_post(고정) | JSR eng_split | JSR eng_splitw | 분할 대기 KINW 표시 |
| $D8A8 kpage | JSR kreset | DEC KPGF | kreset 엔진 뱅크로 |
| eng_chr(뱅크 7) | 항목 1·2 → 풀 없음 | 풀 POOLFREE(0x50-0x9F), USTATE=$14 | 패스워드 표시 머리말 |
### 빈 공간
| 위치 | 내용 |
|---|---|
| 고정 $FFCD-$FFDB | ksnd (kreset 이동으로 생긴 자리 포함, 상한 $FFDD) |
| 고정 $E0C2-$E120 | 상한 $E121→$E120 (원본 코드 보호) |
| 뱅크 7 | kreset, eng_init, eng_splitw, KRDY 판정, POOLFREE 80B |
| RAM | $05BC-$05BF, $06EE-$06EF |
### 검증 (Mesen, headless)
- 롬 work/fix3/fix3b.nes (sha1 af4aea7c…) vs work/fix3/v022.nes (v0.2.2, 464AFDCA…). 같은 절차: 리셋 → $C000 실행 BP 에서 정지 → RAM $0000-$07FF=$FF → 진행.
- 리셋+500: 첫 카드. v0.2.2 26행 4B 4D 4F 51 4F 14 53 55 30 25 0F 30 37 16 …(잔상) / 새 빌드 49 공백 → qa/fix3_firstcard_ramff_after_r500.png.
- 리셋+1290: 스탠리 카드. v0.2.2 28행에 이전(루스) 설명 아래 타일 → qa/fix3_card_row28_before_f3071.png / 새 빌드 정상 → qa/fix3_card_row28_after_r1290.png.
- 타이틀 방치: v0.2.2 리셋+4990 에 붕괴(PC=$770B) / 새 빌드 리셋+11290 정상(qa/fix3_title_idle_ramff_after_r6290.png).
- 회귀: START → 타이틀 메뉴 잔상 없음, NEW GAME 래리 대사·스크롤(qa/fix3_reg_larry_scroll.png), 신문, 홈 컴퓨터 메뉴(qa/fix3_reg_menu.png), 리셋 → 이어하기 → 패스워드 입력 화면(qa/fix3_reg_password_entry.png, USTATE=1).

## 2026-11-27 ui16: 종목 화면 상단 8x16 (DESIGN §19)
### 훅·데이터
| 주소 | 원래 | 변경 | 목적 |
|---|---|---|---|
| khook@one(고정 $FEDC-) | STA KC / LDX KACT / CPX #3 / BNE @orig / … | STA KC / … (KACT 검사 삭제, 8B 절약) | 1바이트 문자는 모두 eng_one 이 판정(분할 8x16 / 상단 8x16 / 원래 경로) |
| $D248 | 02 | 01 | 창 6 [x2 y2 w28 h4] → y1 (행 1-4 지우기, bank5 $B33E·$B1AA 만 사용) |
| $D250-$D252 | 02 1E 05 | 01 1E 06 | 창 8 → [x1 y1 w30 h6] (정보 화면 진입 지우기, bank5 $ADF6 만) |
| bank5 $AE28/$AE4D/$AF07/$AF37 | 80 | 85 | 정보 화면 종목명·틀·값 줄·분류명 창 모드 = 상단 8x16(bit2)+2행 피치 |
| bank5 $B3C7-$B3CD | LDX #$2B / LDY #$03 / JSR $C0EB | JSR stub5 / NOP x4 | $B37C 금액 2줄 레코드 → 보유 주식 화면이면 8x16·한 행 위 |
| bank5·bank7 $BC26-$BC3B | (stock_desc_b5 영역 끝, 빈칸) | stub5 (두 뱅크 같은 바이트) | 뱅크 5 ↔ 7 전환 스텁(고정 뱅크 무사용) |
### 빈 공간·RAM
| 위치 | 내용 |
|---|---|
| bank5 $BC26-$BC45 (파일 0x17C36-0x17C55) | 예약 32B(kor_build.py STUB5_RESERVE, stock_desc_b5 영역에서 제외), 사용 22B |
| bank7 $BC26-$BC45 | stub5 사본 (bank7 $A000-$BF9F 는 그 밖에 비어 있음) |
| 뱅크 7 $8000- | t16ok/t16g/t16tile/eng_t16/eng_pfnum, uinval 확장, eng_one 재작성, 표 T16LO/HI/U8/TILE (엔진 끝 약 $9180) |
| 고정 | 순증가 없음(khook 8B 감소) |
| RAM | $0584-$05AF(UGLY[36..79]) = T16 캐시 앞 44칸, $05E0-$05E9 = 뒤 10칸, $06DB T16NEXT, $06DC T16I, $06DD KLAY, $06DE PFI (eng_init·uinval 초기화) |
### 검증 (Mesen headless, 최종 롬 sha1 f7eebc37…)
- 상태: work/ui16/t3_home.mss·t3_menu.mss·t3_menu_owned.mss(t3 롬, 처음부터 진행). 이후 롬에 로드할 때는 UPLO/UPHI($05B3)를 새 POOL0 주소로 써야 함(엔진 표 이동, §15.1 주의와 같음). 최종 롬은 $8FB7.
- 입력: 홈에서 왼쪽 32프레임 + 위 10프레임 → A(컴퓨터 메뉴). 메뉴 아래 1 → 매수, 2 → 정보, 3 → 포트폴리오. 수량은 위/아래/좌우 8프레임 누름.
- 화면: qa/ui16_buy_list, ui16_buy_qty, ui16_buy_confirm, ui16_buy_done_home, ui16_sell_list, ui16_sell_qty, ui16_sell_confirm, ui16_sell_done_home, ui16_portfolio, ui16_portfolio_empty, ui16_info_list, ui16_info_screen, ui16_info_screen_long, ui16_return_home_from_portfolio, ui16_return_home_from_info.
- 회귀: ui16_reg_title_card, ui16_reg_title_menu, ui16_reg_larry_dialog(이전 빌드와 같은 해시), ui16_reg_larry_scroll, ui16_reg_news, ui16_reg_ralph_call, ui16_reg_stock_menu.

## v0.2.5: 미사용 글자 삭제
- font/charset.txt: 영문 소문자 26자 삭제(708→682). 글리프 번호가 밀리므로 tables/ko_font.tbl 재생성(`python font/tools/build_font.py`).
- font/ui8_charset.txt: 상단 8x16 문자열에만 쓰던 한글 35자와 «» 삭제(129→92). kor_build.py ui8_charset() 은 상단 8x16 문자열을 수집하지 않는다.
- 결과: 상단 8x16 화면이 홈 외 장면에서 열리면(알려진 경로 없음) 해당 글자의 8x8 대체는 공백.

## v0.2.6
- 버그: 종목 정보를 연달아 보면 글자가 바뀜. 원인: 화면 지우기($CD70)를 거치지 않아 상단 8x16 캐시(54칸)가 누적, 원형 할당이 보이는 타일을 덮음.
- 수정: t16inval(8x16 캐시만 비움) 추가. [5F FF](목록·보유 주식 시작)와 새 표식 [5F FC](정보 화면 종목명 0001-0020 앞)에서 호출.
- 번역대·폰트작업대 수정분 반영(dialog_b4_0030 은 <WAIT> 추가로 보류).

## v0.2.7
- 원본 8x8 영문 글리프 수정분 반영(font/orig_font_overrides.json, 전 글자 맨 윗줄 비움 — v0.2.6 목록 줄 붙음 해결).

## v0.2.8
- dialog_b4_0030: 사용자 승인으로 <WAIT> 1개 추가(원문 4개 → 번역 5개, 제어 토큰 개수 규칙의 예외).
