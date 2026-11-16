# Wall Street Kid 한글화 STATUS

## 기본 정보
- 원본: `rom/Wall Street Kid (USA).nes` (FC/NES, 매퍼 2 UxROM, PRG 128KB, CHR-RAM)
- SHA1 `caba8f34159eba1ecff38dd7097218c63c240ad7` · CRC32 `e256aed4`
- 원문 언어: **영어** (툴 호환을 위해 테이블/스크립트 필드명은 `ja` 그대로 사용)
- 플랫폼 문서: `.claude/skills/kor-patch/platforms/fc.md`
- 버전: 0.0.0

## 단계
| 단계 | 상태 | 게이트 |
|---|---|---|
| 0 인테이크 | 완료 (2026-11-16) | 프로젝트 생성, identify 완료 |
| 1 분석 (rom-analyst) | 완료 (2026-11-16) | G1 통과: 12블록 덤프, 미등록 바이트 0, 영어 원문 가독. analysis.md 작성 |
| 2 덤프 (script-engineer) | 진행 중 | G2 대기 |
| 3 번역·폰트·asm | 대기 | G3 |
| 4 검수 | 대기 | G4 |
| 5 폰트 확정 | 대기 | |
| 6 빌드 | 대기 | |
| 7 QA | 대기 | |
| 8 릴리스 | 대기 | |

## 결정 사항
- 원본 롬은 메인 체크아웃 `D:\Localization\projects\Wall_Street_Kid\rom` 에서 워크트리로 복사 (git 미포함).
- 패치 이름: `release/Wall_Street_Kid_kr_v{version}.bps`

- [GitHub 2026-11-16] https://github.com/xHoT-ToHx/Wall_Street_Kid (main). 이 세션의 진행 내용은 단계마다 커밋 후 `bash projects/Wall_Street_Kid/tools/push_github.sh` 로 푸시한다. 스크립트는 임시 클론에서 다른 게임 프로젝트(projects/ 아래 _template·Wall_Street_Kid 외)를 이력에서 걸러 `HEAD:main` 으로 올린다(공용 툴킷·스킬은 포함, 롬은 제외). 로컬 원격 이름 `wallstreet` 은 참조용 — 직접 `git push wallstreet` 하지 말 것(다른 게임이 섞임).

- [G1] 공용 툴킷 `tools/romkr/script.py` 에 분리 포인터(`addrs` 의 `{"lo","hi"}`, 덤프 필드 `ptr_hi`) 지원 추가 — 기존 형식 호환. spec.json 은 `tools/gen_spec.py` 로 생성(수동 편집 금지).
- [G1] 핵심 난점: 대사창 28x6, BG 타일 꽉 참(SPR 테이블 227 여유), bank4/6 90%대 → 256KB 확장·텍스트 뱅크 이전 필요. 타이틀 메뉴·스태프 롤은 spec 밖(별도 형식).

## 남은 일
- G1 판정 후 덤프 → glossary.tsv / style.md 초안을 사용자와 확정.
