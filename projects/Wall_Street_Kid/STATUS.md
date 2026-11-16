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
| 1 분석 (rom-analyst) | 진행 중 | G1 대기 |
| 2 덤프 | 대기 | G2 |
| 3 번역·폰트·asm | 대기 | G3 |
| 4 검수 | 대기 | G4 |
| 5 폰트 확정 | 대기 | |
| 6 빌드 | 대기 | |
| 7 QA | 대기 | |
| 8 릴리스 | 대기 | |

## 결정 사항
- 원본 롬은 메인 체크아웃 `D:\Localization\projects\Wall_Street_Kid\rom` 에서 워크트리로 복사 (git 미포함).
- 패치 이름: `release/Wall_Street_Kid_kr_v{version}.bps`

## 남은 일
- G1 판정 후 덤프 → glossary.tsv / style.md 초안을 사용자와 확정.
