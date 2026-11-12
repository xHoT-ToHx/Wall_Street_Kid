# ROM 한글화 워크스페이스

FC · SFC · MD · SMS/GG · GB · GBC · PS 롬을 다중 에이전트로 한글화한다.
진입점: `/kor-patch <롬경로>` 스킬 (`.claude/skills/kor-patch/SKILL.md`). 메인 세션이 오케스트레이터.

## 구조
```
.claude/agents/         rom-analyst, script-engineer, translator, translation-reviewer,
                        font-engineer, asm-hacker, qa-tester
.claude/skills/kor-patch/SKILL.md         단계·게이트·배치 규칙
.claude/skills/kor-patch/platforms/*.md   fc / sfc / md / sms(GG) / gb(GB·GBC) / ps
tools/romkr/            공용 Python 툴킷 (python -m romkr --help)
projects/_template/     새 게임 프로젝트 템플릿
projects/<게임>/        rom/ tables/ scripts/ font/ asm/ build/ qa/ review/ release/
                        project.json spec.json glossary.tsv style.md analysis.md STATUS.md
```

## romkr 실행
`tools/` 에서 `python -m romkr <cmd>`, 또는 `PYTHONPATH=tools python -m romkr <cmd>` (Pillow 필요: `pip install -r tools/requirements.txt`).
명령: identify, checksum, relsearch, dump, check, insert, charset, font, patch, build.

## 버전 규칙
- `project.json` 의 `version` = `Major.Minor.Patch`, 패치 파일 이름 `release/<게임>_kr_v<버전>.bps` (`patch.out` 의 `{version}` 치환).
- **Major** = 릴리스됐을 때 · **Minor** = 한글화 큰 변화(대사 한글 적용, 타이틀 이미지 한글 적용, 저장·한글 입력 적용 등) · **Patch** = 작은 업데이트(대사 일부 수정, 이미지 픽셀 수정, 마이너 버그 수정 등).
- 올리기: `python -m romkr version projects/<g> --bump minor|patch|major` → `romkr build` → 새 이름의 패치 생성. 이전 버전 패치 파일은 남겨 둔다.

## 공통 규칙 (모든 에이전트)
- **원본 롬은 불변**. `projects/<g>/rom/` 은 읽기 전용, 실험은 `work/`, 산출물은 `build/`.
- 롬·디스크 이미지·빌드 산출물은 git 에 넣지 않고 배포하지 않는다. 배포물은 패치(BPS/IPS/xdelta)뿐. 사용자가 소유한 원본에서 덤프한 롬만 다룬다.
- 모든 변경은 재현 가능해야 한다: 수동 헥스 편집 금지 → spec.json / 테이블 / asm 소스 / project.json 으로 표현하고 `romkr build` 로 재생성.
- 텍스트 JSON 의 `id`, `ja`, `offset`, `ptr_addr`, `alias_of` 는 수정 금지. 번역은 `ko`, 메모는 `note`.
- 제어코드 토큰(`<...>`, `[XX]`)은 원문과 같은 순서·개수로 유지.
- 빈 공간(free space)은 analysis.md 의 목록에서 예약 표시 후 사용 (asm/CHANGES.md 에도 기록).
- emucap: `bootstrap()` 먼저, 포트 하드코딩·광역 프로세스 종료·GUI Pause 금지. 상태 변경은 emucap-track `log_intervention`, 판정은 `log_gate`.
- 보고는 짧게, 세부는 파일로. 추측은 추측이라고 적는다.
