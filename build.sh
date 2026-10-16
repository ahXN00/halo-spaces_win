#!/bin/zsh
# Baut das Komplettpaket: Design (CSS) + Symbole + Erweiterung → dist/halo-spaces-<version>.xpi
# Aufruf: ./build.sh
set -e
ROOT="${0:A:h}"
cd "$ROOT"

# Bereiche-CSS in userChrome.css einfügen, dann als theme.css in die Erweiterung
python3 chrome/merge_bereiche.py >/dev/null
cp chrome/userChrome.css erweiterung/theme.css

VERSION=$(python3 -c "import json; print(json.load(open('erweiterung/manifest.json'))['version'])")
mkdir -p dist
OUT="dist/halo-spaces-$VERSION.xpi"
rm -f "$OUT"
(cd erweiterung && zip -qr "../$OUT" . -x '.*' -x '*/.*')
echo "$OUT"
