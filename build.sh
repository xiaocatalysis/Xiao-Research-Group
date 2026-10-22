#!/usr/bin/env bash
# One-command local build + check + preview. Sources are never modified.
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/build.py --out build "$@"
python3 tools/check_site.py build || true
echo
echo "Preview:  python3 -m http.server -d build 8000   then open http://localhost:8000/"
