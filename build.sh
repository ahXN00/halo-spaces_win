#!/bin/zsh
# Baut das Komplettpaket: Design (CSS) + Symbole + Erweiterung → dist/halo-spaces-<version>.xpi
# Aufruf: ./build.sh
set -e
ROOT="${0:A:h}"
cd "$ROOT"

# Bereiche-CSS in userChrome.css einfügen, dann als theme.css in die Erweiterung
python3 chrome/merge_spaces.py >/dev/null
cp chrome/userChrome.css extension/theme.css

VERSION=$(python3 -c "import json; print(json.load(open('extension/manifest.json'))['version'])")
mkdir -p dist
OUT="dist/halo-spaces-$VERSION.xpi"
rm -f "$OUT"
(cd extension && zip -qr "../$OUT" . -x '.*' -x '*/.*')

# Variante für addons.thunderbird.net: ohne update_url – dort kommen Updates
# vom Store selbst (die GitHub-Variante behält ihre eigene Update-Adresse)
STORE="dist/halo-spaces-$VERSION-atn.xpi"
TMP=$(mktemp -d)
cp -R extension/ "$TMP/ext"
python3 - "$TMP/ext/manifest.json" <<'PY'
import json, sys
p = sys.argv[1]
m = json.load(open(p))
m["browser_specific_settings"]["gecko"].pop("update_url", None)
json.dump(m, open(p, "w"), indent=2, ensure_ascii=False)
PY
rm -f "$STORE"
(cd "$TMP/ext" && zip -qr "$ROOT/$STORE" . -x '.*' -x '*/.*')
rm -r "$TMP/ext" && rmdir "$TMP"
echo "$OUT"
