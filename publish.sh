#!/bin/zsh
# Veröffentlicht die mit release.sh vorbereitete Version – ohne neu zu bauen.
#   ./publish.sh 3.0.95 notes.md
# Prüft vorher, dass Paket, Manifest und updates.json zusammenpassen, und
# danach, dass der Download von GitHub genau diesen Hash hat (sonst lehnt
# Thunderbird das automatische Update ab).
set -e
ROOT="${0:A:h}"
cd "$ROOT"
VERSION="$1"
NOTES="$2"
[[ -z "$VERSION" || ! -f "$NOTES" ]] && { echo "Aufruf: ./publish.sh <version> <notes.md>"; exit 1; }
source ./repo.conf
GH=$(command -v gh || echo "$HOME/.local/bin/gh")
[[ -x "$GH" ]] || { echo "gh (GitHub CLI) nicht gefunden"; exit 1; }
XPI="dist/halo-spaces-$VERSION.xpi"
[[ -f "$XPI" ]] || { echo "$XPI fehlt – zuerst ./release.sh $VERSION"; exit 1; }

MANIFEST=$(python3 -c "import json; print(json.load(open('extension/manifest.json'))['version'])")
[[ "$MANIFEST" == "$VERSION" ]] || { echo "Manifest hat $MANIFEST, nicht $VERSION"; exit 1; }
LOCAL=$(shasum -a 256 "$XPI" | cut -d' ' -f1)
LISTED=$(python3 - "$VERSION" <<'PY'
import json, sys
for addon in json.load(open("updates.json"))["addons"].values():
    for u in addon["updates"]:
        if u["version"] == sys.argv[1]:
            print(u["update_hash"].split(":", 1)[1])
PY
)
[[ "$LOCAL" == "$LISTED" ]] || { echo "Hash in updates.json passt nicht zum Paket (Paket neu gebaut?) – ./release.sh $VERSION erneut"; exit 1; }

git add -A
git commit -q -m "halo.spaces $VERSION" || true
git -c http.postBuffer=157286400 push -q
"$GH" release create "v$VERSION" "$XPI" --repo "$GITHUB_REPO" --title "$VERSION" --notes-file "$NOTES"

# Download prüfen (GitHub braucht ggf. einen Moment)
URL="https://github.com/$GITHUB_REPO/releases/download/v$VERSION/$(basename "$XPI")"
for i in {1..10}; do
  REMOTE=$(curl -sfL "$URL?check=$RANDOM" | shasum -a 256 | cut -d' ' -f1) || true
  if [[ "$REMOTE" == "$LOCAL" ]]; then
    echo "Veröffentlicht – Hash geprüft (${LOCAL[1,16]}…)"
    # zusätzlich auf addons.thunderbird.net, sobald die Schlüssel eingerichtet sind
    if [[ -f "$HOME/.config/halo-spaces/atn.env" && -z "$SKIP_ATN" ]]; then
      python3 store/atn_upload.py "$VERSION" || echo "WARNUNG: Hochladen auf addons.thunderbird.net fehlgeschlagen (SKIP_ATN=1 überspringt)"
    fi
    exit 0
  fi
  sleep 3
done
echo "WARNUNG: Download hat nicht den erwarteten Hash ($REMOTE statt $LOCAL)"
exit 1
