# 휴대폰 번역대 · 폰트작업대

| 것 | 번역대 | 폰트작업대 |
|---|---|---|
| 페이지 (비공개) | https://claude.ai/artifact/39psP3F3CMmKf5e9VALKZf | https://claude.ai/artifact/EyE9LvjMjVm9jNSoj5L59U |
| 대상 | scripts/*.json 13블록 약 430행 (대사·뉴스·종목·메뉴·고정 문자열) | 게임 원본 영문 8×8 글리프 55자 (bank0 파일 0x2375, 코드 0x00-0x36) |
| 굽기 | `python -X utf8 tools/text_desk.py build` → work/desk/text_desk.html | `python -X utf8 tools/pixel_desk_page.py` → work/desk/pixel_desk.html |
| 저장 (db) | `edits/<id>` {ko, base, at} — 입력 멈춘 뒤 0.8초 | `pixels/of_XX` {id, data(base64 64바이트 0/1), base(sha1), at} |
| 반영 | `python -X utf8 tools/text_desk.py apply <dir> [--dry]` | `python -X utf8 tools/pixel_desk.py apply <dir> [--dry]` → font/orig_font_overrides.json |

## "번역대 반영해줘"
1. ArtifactData list url=번역대 collection=edits out_dir=work/desk/edits_in
2. `python -X utf8 tools/text_desk.py apply work/desk/edits_in` — 건너뜀(제어 토큰 변경·원고 변경)은 사용자에게 알린다
3. `PYTHONPATH=tools python -m romkr check projects/Wall_Street_Kid` 후 `romkr build` (큰 변경이면 버전 규칙에 따라 `romkr version --bump`)
4. `python -X utf8 tools/text_desk.py build` → 같은 URL 로 Artifact 재발행(capabilities `{db:{}}` 유지)
5. 반영한 edits 문서 ArtifactData batch delete, work/desk/edits_in 삭제

## "폰트작업대 반영해줘"
1. ArtifactData list url=폰트작업대 collection=pixels out_dir=work/desk/pixels_in
2. `python -X utf8 tools/pixel_desk.py apply work/desk/pixels_in` → font/orig_font_overrides.json (롬 원본과 같아진 글자는 항목 삭제)
3. `romkr build` — project.json commands 의 `tools/apply_orig_font.py {rom}` 가 expand 직후 롬에 덮어쓴다
4. `python -X utf8 tools/pixel_desk_page.py` → 같은 URL 로 재발행
5. 반영한 pixels 문서 삭제, work/desk/pixels_in 삭제

## 8×16 영문·기호 (2026-11-26 추가)
- 폰트작업대의 `a16_XXXX`(XXXX = 유니코드) 86자 = 대사창(2행 피치)에서 영문·숫자·`$` 가 바뀌어 보이는 글리프. 바탕은 Galmuri11 Bold/Condensed.
- `pixel_desk.py apply` → font/kr16_ascii_overrides.json {"M": "32자리 hex"} (바탕과 같아지면 항목 삭제). build_font.py 가 build/font.bin 에 덮어쓴다(project.json 변경 없음). 번역대 미리보기에도 반영된다.
- 반영 절차는 "폰트작업대 반영해줘"와 같다.

## 검사 규칙
- 번역대: 제어 토큰(`<END>` `<WAIT>` `<PAGE>` `<VAR>` `[XX]`)은 원문(ja)과 같은 순서·개수. 대사창은 28칸 자동 줄바꿈·페이지당 6줄·페이지당 서로 다른 글자 107자 이하(권장 90). 고정 영역은 원문 칸 수 이하. 8×8 한글 세트(ui8_charset.txt 129자) 밖의 글자, 대사 폰트(charset.txt 708자) 밖의 글자는 경고 — 새 글자는 charset 뒤에만 추가한다.
- 매수·매도 목록 이름(stock_list_names_b5)은 영문·숫자만.
- 폰트작업대: 색은 0/1 만. 오버라이드는 빌드 때마다 롬에 다시 적용되며 한글 글리프에는 영향 없음.
- 미리보기의 글리프는 build_font.py 와 같은 인자로 work/desk 에 따로 렌더한 Galmuri(SIL OFL) 비트맵이다. 롬 데이터는 페이지에 올리지 않는다.
