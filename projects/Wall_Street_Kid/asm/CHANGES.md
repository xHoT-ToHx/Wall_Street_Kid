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
