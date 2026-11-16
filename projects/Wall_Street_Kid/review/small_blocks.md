# 소형 블록 10개 검수 (stock_desc_b5, stock_ui_b5, stock_names_b5, stock_cat_b5, menu_b7, password_b7, title_featuring, weekdays, status_cash, status_stocks)

검수 항목: 번역 항목 104개(alias 6 제외; 20+8+21+4+37+4+1+7+1+1 + 열 정렬 줄 점검). 직접 수정 1건, 반려 0건.

## 기계 검사
- `romkr check` (ja.tbl + ko_font.tbl, stock_ui 는 --line-width 30, 나머지 28) 전 파일 문제 0건.
- work/tools/check_widths.py 문제 0건 (열 머리 위치: stock_ui 1~6 줄4 와 stock_names_0000 줄3 이 원문과 동일 열).

## 직접 수정
| id | 변경 | 사유 |
|---|---|---|
| menu_b7_0020 | "둘 다 싫어!" -> "둘 다 싫어요!" | 상점 (A)(B) 선택지에서 주인공이 점원(파멜라 등)에게 하는 말. style.md 는 프리실라 외에는 해요체이고 dialog_b4 도 주인공이 "보고 싶은데요" 로 말함. 반말이면 점원에게 무례. 7칸(<=13). |

## 확인 결과(수정 없음)
- 종목명 20개: glossary 와 일치, news_b6 0059-0078 목록과 철자 동일(앞 공백 가운데 정렬은 news 쪽 별도). 유일한 차이는 stock_names 가 "REEBOK INT'L", news 가 "REEBOK INTERNATIONAL" 로 원문 차이(INT'L/INTERNATIONAL)를 그대로 따른 것 — 정상. 23칸 이내(최장 CARNIVAL CRUISE LINES 21). 원문보다 긴 것: BOEING +1, CATERPILLAR +2, CHRYSLER +2 — 정보 화면 23칸 안이라 문제없음.
- stock_desc_b5 26칸 자동 줄바꿈 추정: 타당. 원문에서 `\n` 없이 이어진 줄(0004 "EXPANDED|INTO", 0007 "SUCCESSFUL|FOREIGN BUILDER, INSURANCE|DIVISION", 0009 "FIRM,|HEADING", 0010 "ASSETS,|EXPERIMENTING", 0014 "BACK|BY", 0015 "ORDER|TO")이 전부 정확히 26칸에서 끊김. 줄 맞춤이 26칸 폭에서만 성립하므로 폭 26 은 사실상 확정(원문 증거). 번역은 줄당 최대 16칸, 3줄 이하로 폭·행 모두 여유.
  - 단, 26칸 줄 뒤에 `\n` 을 쓰면 빈 줄 가능성(대사창과 같은 엔진 추정) — 번역은 26칸 줄이 없어 해당 없음.
- 기업 개요 내용: 원문 문장과 의미 일치, 누락 없음, 종목 순서(1~20)와 설명 대응 확인(0006 정부 대출=CHRYSLER, 0018=IBM 컴퓨터 지배, 0019=APPLE 의 IBM 경쟁). 원문에 없는 비방·사실 추가 없음. 부정적 서술(적자, 부채, 불황 타격)은 모두 원문 그대로이며 1980년대 게임 설정의 허구 요약임. 0019 "IBM과" 조사 정상.
- stock_ui_b5: 30칸 줄(열 머리 4줄, 수량 입력 줄) 길이 30 유지, 열 시작 위치 원문과 동일. 수량 입력 줄은 `(` 가 20열, 숫자 칸 21~25 유지; `MAX)`(4칸) -> `까지)`(3칸)+뒤 공백 1로 총 30칸 유지, `)` 위치만 1칸 앞(숫자 그리는 코드는 21~25 고정으로 추정, QA 확인).
- 용어: 주식 매수/매도, 정보, 포트폴리오, 현재가/매입가/수량, 등락률, 시작가, 기업 개요, 경매 대금, 축제, 헬스, 등산, 취소(0004/0013 및 alias 0024 모두 동일) 전부 glossary 일치. 같은 원문(CANCEL)이 갈라진 곳 없음. 다른 파일(dialog/news)에는 해당 열 머리 용어가 없음.
- 허용 문자: 소문자·물결·가운뎃점 없음. 고정 길이: 요일 3칸, 현금: 5, 주식: 7(여유), FEATURING 12칸(앞 공백 포함 8자) 모두 초과 없음.
- 패스워드 화면: 앞 공백으로 가운데 위치 재계산이 원문과 일치(중심열 동일).

## 반려
없음.

## 참고(REVIEW, 번역자 재작업 불필요 — asm/폰트 결정 후 확인)
1. weekdays: "일  "(한글1+공백2)는 1바이트 8x8 정적 세트 경로(font/DESIGN.md 93행)에서만 3바이트에 맞는다. 2바이트 한글 경로가 되면 "일 "(공백 1)로 줄여야 한다. title_featuring/status 의 note 는 2바이트 가정이라 가정이 서로 다름 — 최종 한글 바이트 수 확정 시 일괄 재검.
2. stock_ui_0000 "(     까지)": MAX 의 뜻은 "최대 구매 가능 수". "까지"는 "12랏까지" 로 자연스러우나 숫자 정렬 방향(좌/우)은 QA 에서 확인.
3. title_featuring "등장인물...": FEATURING 의 "출연" 뉘앙스보다 "등장인물"(캐릭터 소개 데모) 이 화면 맥락에 맞다고 판단해 유지.

## 용어집 추가 제안
- NEITHER! = 둘 다 싫어요! (메뉴, 상점 선택지)
- NEED LOAN = 대출 신청 / LOAN PAYMENT = 대출 상환 / NOT ENOUGH MONEY(매매 화면) = 현금이 부족합니다 (dialog 의 "NOT ENOUGH CASH" 류와 통일)
- PICNIC = 소풍, SHOPPING = 쇼핑, SWIMMING = 수영
