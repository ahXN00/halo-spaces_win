#!/bin/zsh
# Testet halo.spaces mit der aktuellen Thunderbird Beta (macOS), damit wir
# Änderungen der nächsten Version vor den Nutzern sehen.
#   tests/beta.sh [weitere Optionen für halo_test.py]
# Die Beta wird von download.mozilla.org geholt (höchstens einmal pro Woche)
# und nur hier im Cache-Ordner abgelegt – nichts wird installiert.
set -e
ROOT="${0:A:h:h}"
CACHE="$HOME/Library/Caches/halo-spaces/tb-beta"
APP="$CACHE/Thunderbird Beta.app"
mkdir -p "$CACHE"
if [[ ! -d "$APP" || -n $(find "$APP" -maxdepth 0 -mtime +7) ]]; then
  echo "Lade Thunderbird Beta …"
  curl -sSfL -o "$CACHE/tb-beta.dmg" "https://download.mozilla.org/?product=thunderbird-beta-latest-SSL&os=osx&lang=en-US"
  MNT=$(mktemp -d)
  hdiutil attach -nobrowse -readonly -quiet -mountpoint "$MNT" "$CACHE/tb-beta.dmg"
  rm -rf "$APP"
  cp -R "$MNT/Thunderbird Beta.app" "$CACHE/"
  hdiutil detach -quiet "$MNT"
  rm -f "$CACHE/tb-beta.dmg"
  # nur von Mozilla signierte Programme starten
  codesign --verify --deep --strict "$APP"
  [[ $(codesign -dv "$APP" 2>&1 | grep TeamIdentifier) == "TeamIdentifier=43AQ936H96" ]] || { echo "Signatur ist nicht von Mozilla"; exit 1; }
fi
echo "Thunderbird Beta $(defaults read "$APP/Contents/Info.plist" CFBundleShortVersionString)"
python3 "$ROOT/tests/halo_test.py" --tb "$APP/Contents/MacOS/thunderbird" "$@"
