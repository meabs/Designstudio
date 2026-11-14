#!/usr/bin/env bash
# Build a single-file executable for the platform you run this on (PyInstaller cannot cross-compile).
# Needs Python 3.10+ and Node 20+. Output: dist/designstudio (designstudio.exe on Windows).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f apps/ui/dist/index.html ] || make ui-build
python3 -m venv .build-venv
. .build-venv/bin/activate 2>/dev/null || . .build-venv/Scripts/activate
pip install --quiet pyinstaller
SEP=:; case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) SEP=';';; esac
pyinstaller --onefile --name designstudio --noconfirm --clean \
  --paths "$PWD/apps/api" \
  --add-data "$PWD/apps/ui/dist${SEP}apps/ui/dist" \
  --distpath "$PWD/dist" --workpath "$PWD/.build-venv/work" --specpath "$PWD/.build-venv" \
  "$PWD/apps/api/server.py"
echo "Built: $(ls dist/designstudio*)"
