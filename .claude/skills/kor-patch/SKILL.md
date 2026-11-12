---
name: kor-patch
description: 레트로 게임 롬(FC/SFC/MD/SMS/GG/GB/GBC/PS) 한글화 파이프라인을 다중 에이전트로 지휘한다. "이 롬 한글화", "/kor-patch <롬경로>", 한글화 프로젝트 진행 상황 이어서 하기 등에 사용.
argument-hint: <롬 경로 또는 projects/<게임>> [단계]
---

# 롬 한글화 오케스트레이션

너(메인 세션)가 **오케스트레이터**다. 서브에이전트는 다른 서브에이전트를 부를 수 없으므로 모든 배치·게이트 판정·재작업 지시는 메인 세션이 한다.
진행 상태의 정본은 `projects/<g>/STATUS.md` — 단계마다 갱신하고, 재개 시 먼저 읽는다.

## 팀
| 에이전트 | 역할 | 병렬 |
|---|---|---|
| rom-analyst | 플랫폼 식별, 테이블·포인터·압축·폰트 분석 | 1 |
| script-engineer | 덤프·삽입·포인터·공간 관리, 빌드 | 1 |
| translator | ja→ko 번역 | 파일별 N개 |
| translation-reviewer | 독립 검수 | 파일별 N개 |
| font-engineer | 한글 폰트 전략·생성, 그래픽 문자 | 1 |
| asm-hacker | 엔진 개조, 확장, 압축 | 1 (영역이 안 겹치면 2) |
| qa-tester | 에뮬레이터 실행 검증, 버그 리포트 | 범위별 N개 (포트 자동 분리) |

## 단계와 게이트

### 0. 인테이크 (메인 세션 직접)
- 롬 경로 확인. **사용자가 소유한 원본에서 덤프한 롬만** 다룬다는 점을 확인. 롬 파일은 커밋/배포하지 않는다.
- `projects/_template` 를 `projects/<게임-슬러그>` 로 복사, 원본을 `rom/` 에 둔다.
- `python -m romkr identify` 로 플랫폼 확인 → 플랫폼 문서 `platforms/<p>.md` 경로를 이후 모든 에이전트 프롬프트에 포함.
- PS 는 먼저 `dumpsxiso` 로 파일 추출 (platforms/ps.md).

### 1. 분석 → rom-analyst
게이트 G1: `ja.tbl` + `spec.json` 으로 덤프한 결과가 읽을 수 있는 원문이고, analysis.md 에 텍스트 엔진/폰트/공간 정보가 있음.
실패 시: 압축·특수 인코딩이면 asm-hacker 를 함께 투입해 루틴 분석.

### 2. 덤프 → script-engineer
게이트 G2: scripts/*.json 생성, `[XX]` 미등록 바이트 0 (또는 의미가 문서화된 것만), scripts/README.md 에 화면 제약 기재.
메인 세션은 이 시점에 사용자와 **glossary.tsv / style.md** 초안을 확정한다(고유명사, 말투). 이게 병렬 번역 품질을 좌우한다.

### 3. 병렬 작업 (한 메시지에서 동시에 Agent 호출)
- translator × N : 파일(또는 id 범위)별로 1개씩. 프롬프트에 담당 파일, 줄 제약, glossary/style 경로 명시. 서로 다른 파일만 수정.
- font-engineer : 전략 결정 + KS X 1001 임시 폰트로 선행 개발.
- asm-hacker : 2바이트 한글 처리/동적 로딩/확장 등 analysis.md 에서 필요한 개조.
게이트 G3: 번역률 100%, `romkr check --skip-untranslated` 0건 / 폰트 DESIGN.md / asm 빌드 성공.

### 4. 검수 → translation-reviewer × N (번역자와 다른 인스턴스)
반려 항목은 translator 에게 해당 id 목록으로 재작업 지시. 용어 제안은 메인 세션이 glossary 에 반영 여부를 결정(필요하면 사용자에게 질문).
게이트 G4: 반려 0, 기계 검사 0건.

### 5. 폰트 확정 → font-engineer
번역 확정 문자셋으로 재생성, 용량 초과 시 translator 에게 희귀 음절 대체 요청.

### 6. 빌드 → script-engineer
`python -m romkr build projects/<g>` 성공 (공간 부족 → script-engineer/asm-hacker 협업 루프).

### 7. QA → qa-tester (범위별 병렬: 오프닝·메뉴 / 초반 진행 / 상점·전투 / 엔딩 등)
bugs.md 의 "담당 추정"에 따라 해당 에이전트에게 재작업 → 6 으로. 치명/주요 버그 0 이 될 때까지 반복.

### 버전
빌드할 만한 변경마다 `python -m romkr version projects/<g> --bump minor|patch` 로 올린다(규칙은 CLAUDE.md "버전 규칙"). 릴리스 때만 major.

### 8. 릴리스 (메인 세션)
- `romkr build --release` → BPS(또는 IPS) 패치 생성·재적용 검증 자동 수행. PS 는 xdelta3 로 원본 bin ↔ 빌드 bin.
- `release/README.txt`: 대상 원본 롬 이름·CRC32·SHA1, 적용 방법, 크레딧, 폰트 라이선스.
- 롬 자체는 배포물에 포함하지 않는다.

## 에이전트 호출 규칙
- 프롬프트는 자급자족하게: 게임 슬러그, 플랫폼 문서 경로, 담당 파일/범위, 완료 조건(게이트), 산출물 경로.
- 결과 보고는 요약만 받는다. 세부는 파일로.
- 같은 파일을 두 에이전트가 동시에 수정하게 하지 않는다.
- emucap 을 쓰는 에이전트를 동시에 여러 개 돌릴 수 있다(포트 자동 분리). 단, 광역 프로세스 종료 금지.
- 각 단계 종료 시 STATUS.md 에 게이트 결과·남은 일·결정 사항 기록.
