#!/usr/bin/env bash
# 현재 브랜치를 Wall_Street_Kid GitHub 리포지토리(main)로 내보낸다.
# 워크스페이스에는 다른 게임 프로젝트도 있으므로 임시 클론에서
# projects/ 아래의 다른 게임을 이력에서 걸러낸 뒤 푸시한다. (롬은 .gitignore 로 제외)
# 필터는 결정적이라 같은 커밋은 항상 같은 해시가 되어 매번 fast-forward 푸시가 된다.
set -euo pipefail
URL=https://github.com/xHoT-ToHx/Wall_Street_Kid.git
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git clone -q --no-local --single-branch --branch "$BRANCH" "$ROOT" "$TMP/export"
cd "$TMP/export"
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --prune-empty --index-filter \
  'git ls-files -z "projects/*" | grep -zv -e "^projects/_template/" -e "^projects/Wall_Street_Kid/" | xargs -0 -r git rm -q --cached --ignore-unmatch --' HEAD
git ls-files | grep -Ei '\.(nes|fds|sfc|smc|bin|gb|gbc|iso)$' && { echo "롬/바이너리 파일이 포함됨 - 중단" >&2; exit 1; }
git push "$URL" HEAD:main
git log --oneline -3
