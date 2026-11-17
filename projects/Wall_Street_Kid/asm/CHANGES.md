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
