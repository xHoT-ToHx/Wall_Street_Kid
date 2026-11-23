# Wall Street Kid 한글화 STATUS

## 기본 정보
- 원본: `rom/Wall Street Kid (USA).nes` (FC/NES, 매퍼 2 UxROM, PRG 128KB, CHR-RAM)
- SHA1 `caba8f34159eba1ecff38dd7097218c63c240ad7` · CRC32 `e256aed4`
- 원문 언어: **영어** (툴 호환을 위해 테이블/스크립트 필드명은 `ja` 그대로 사용)
- 플랫폼 문서: `.claude/skills/kor-patch/platforms/fc.md`
- 버전: 0.2.0 (메뉴·매매 화면·요일·상태창·패스워드·타이틀 메뉴 한글, QA 1차 버그 수정, 폰트 확정 708자)

## 단계
| 단계 | 상태 | 게이트 |
|---|---|---|
| 0 인테이크 | 완료 (2026-11-16) | 프로젝트 생성, identify 완료 |
| 1 분석 (rom-analyst) | 완료 (2026-11-16) | G1 통과: 12블록 덤프, 미등록 바이트 0, 영어 원문 가독. analysis.md 작성 |
| 2 덤프 (script-engineer) | 완료 (2026-11-16) | G2 통과: scripts 12블록 434항목(약 30,000자), 미등록 바이트 0, README 화면 제약, 원문 재삽입 재덤프 일치 |
| 3 번역·폰트·asm | 완료 (2026-11-17) | G3 통과: 번역 100%·check 0건 / font DESIGN.md / asm 빌드 성공, 대사창 8x16 한글 표시 확인(qa/g3_kr_larry_dialog.png) |
| 4 검수 (translation-reviewer x3) | 완료 (2026-11-17) | G4 통과: 반려 0, 직접 수정 25건(dialog 19, news 5, 소형 1), 기계 검사 0건. review/*.md |
| 5 폰트 확정 | 완료 (2026-11-23) | 실사용 708자(ASCII 86 + 한글 622, 빈도순), font.bin 11,328B(뱅크 8 하나), 번역 한글 누락 0. 이후 새 글자는 charset.txt 뒤에만 추가 |
| 6 빌드 | v0.1.0 빌드 성공 (`romkr build`, BPS 재적용 검증 OK) | |
| 7 QA | 1차(v0.1.0): 치명1·주요1·경미5 → 전부 수정/해소(A4 쉼표는 폰트 개선만). 2차(v0.2.0) 진행 중 | |
| 8 릴리스 | 대기 | |

## 결정 사항
- 원본 롬은 메인 체크아웃 `D:\Localization\projects\Wall_Street_Kid\rom` 에서 워크트리로 복사 (git 미포함).
- 패치 이름: `release/Wall_Street_Kid_kr_v{version}.bps`

- [GitHub 2026-11-16] https://github.com/xHoT-ToHx/Wall_Street_Kid (main). 이 세션의 진행 내용은 단계마다 커밋 후 `bash projects/Wall_Street_Kid/tools/push_github.sh` 로 푸시한다. 스크립트는 임시 클론에서 다른 게임 프로젝트(projects/ 아래 _template·Wall_Street_Kid 외)를 이력에서 걸러 `HEAD:main` 으로 올린다(공용 툴킷·스킬은 포함, 롬은 제외). 로컬 원격 이름 `wallstreet` 은 참조용 — 직접 `git push wallstreet` 하지 말 것(다른 게임이 섞임).

- [G1] 공용 툴킷 `tools/romkr/script.py` 에 분리 포인터(`addrs` 의 `{"lo","hi"}`, 덤프 필드 `ptr_hi`) 지원 추가 — 기존 형식 호환. spec.json 은 `tools/gen_spec.py` 로 생성(수동 편집 금지).
- [G1] 핵심 난점: 대사창 28x6, BG 타일 꽉 참(SPR 테이블 227 여유), bank4/6 90%대 → 256KB 확장·텍스트 뱅크 이전 필요. 타이틀 메뉴·스태프 롤은 spec 밖(별도 형식).

- [G2] title_featuring 오프셋 0x1447C 로 정정(gen_spec.py). 번역 분할: dialog_b4 D1 0000-0043 / D2 0044-0073 / D3 0074-0128 / D4 0129-0193, news_b6 N1 0000-0010 / N2 0011-0078 / N3 0079-0108 / N4 0109-0129, 소형 블록 1명. D1·D2 는 같은 번역가, N3·N4 는 종목명 확정 후.
- [G2] 미확인: 28칸 꽉 찬 줄 뒤 줄바꿈 시 빈 줄 여부, <VAR> 최대 길이, roundtrip.nes 실행 검증.

- [사용자 결정 2026-11-16] 종목명은 패러디명 대신 **실제 회사명 영문 대문자**(IBM, BOEING, AT&T …). 말투는 캐릭터별 차등. 그 외 고유명사는 전부 한글 음역. → glossary.tsv / style.md 확정.
- [잠정] 번역 제약: 줄당 28칸(27칸 이하 권장), 페이지당 6줄, 페이지당 고유 한글 음절 90자 목표 — asm 엔진 수치 확정 뒤 조정.

- [G4] QA 확인 항목: dialog 0101 `<VAR>` 앞 공백, news 0122(악재 구역의 호재 어조 문장) 사용처, 매수·매도 목록 종목명 이름표, 수량 입력 줄 숫자 정렬, 패스워드 화면 가운데 정렬, 엔딩/소개 카드 22칸 가정.
- [G4] 한글 바이트 수 확정 뒤 고정 길이 항목(weekdays, status_*, title_featuring) 재조정 필요.

- [G3 엔진] UOROM 256KB(고정 뱅크 15), 뱅크 7 엔진 / 8-10 폰트 / 12·13 한글 텍스트(bank4·6 복사본) / 11·14 넘침. 대사창 구간은 스프라이트 오버플로 플래그로 BG 패턴테이블을 $1000 으로 분할. 창에 동시에 보이는 고유 글자 상한 107(권장 90) — 빌드가 `build/kor_text_report.txt` 로 검사.
- [G3 미구현] 메뉴·매매 화면 틀·종목명/분류·요일·상태창·패스워드·타이틀 메뉴·타이틀 데모 인물 카드는 아직 한글 미표시. password_b7 자리($FE90-) 재배정 필요. 원본 세이브스테이트는 확장 롬에서 못 씀.
- [사용자 지시 2026-11-17] 에뮬레이터 확인은 창 없이 백그라운드로.

- [v0.2.0] 대사창 외 화면 8x8 한글(장면별 빈 타일 풀, 큰 그림 장면은 16칸), password 한글 켬, 타이틀 메뉴 "새 게임 / 이어하기"(스크립트 밖 고정 문자열). 고정 뱅크 여유 거의 없음(약 9B) — 메뉴 문자열 14개를 뱅크 11 로 넘김.
- [v0.2.0] 빌드마다 세이브스테이트가 무효가 된다(글리프 캐시) — QA 는 스냅샷 롬별로 상태를 새로 만든다.
- [남은 과제] 매수·매도 목록 종목명 9자 고정 표(bank5 0x17472, 패러디명, spec 밖) 추가, 정보 화면 열 머리 정렬(stock_names_b5_0000).

## 남은 일
- G3: 번역 3건 완료 확인(`romkr check`), 종목명 칸 수 초과(CATERPILLAR 등) 처리 결정.
- font-engineer(8x16 한글 전략), asm-hacker(256KB 확장·2바이트 한글 엔진) 결과 확인.
