#!/bin/zsh
# Installiert das Paket (Design + Erweiterung) in dein Thunderbird-Standardprofil.
# Vorher Thunderbird beenden.
#   ./install.sh [paket.xpi]     – ohne Angabe: neueste Datei in dist/
#   ./install.sh --uninstall
# Updates kommen danach automatisch über Thunderbird (Add-ons → Updates).

set -e

ROOT="${0:A:h}"
TB_DIR="$HOME/Library/Thunderbird"
INI="$TB_DIR/profiles.ini"
ADDON_ID="mail-cards@sebastian.local"
MARKER="Thunderbird im Stil von Apple Mail"
PREFS=(
  'user_pref("mail.addressDisplayFormat", 2);'      # nur Namen anzeigen, wie Apple Mail
  'user_pref("mail.fixed_width_messages", false);'  # Textmails nicht in Schreibmaschinenschrift
)

if [[ ! -f "$INI" ]]; then
  echo "Kein Thunderbird-Profil gefunden. Bitte Thunderbird einmal starten und ein Konto einrichten."
  exit 1
fi

if pgrep -xq thunderbird; then
  echo "Thunderbird läuft noch. Bitte zuerst beenden (⌘Q)."
  exit 1
fi

# Standardprofil: zuerst [Install…]-Abschnitt, sonst Profil mit Default=1
PROFILE_PATH=$(awk -F= '/^\[Install/{f=1;next} /^\[/{f=0} f&&$1=="Default"{print $2; exit}' "$INI")
if [[ -z "$PROFILE_PATH" ]]; then
  PROFILE_PATH=$(awk -F= '/^\[Profile/{p="";d=0} $1=="Path"{p=$2} $1=="Default"&&$2=="1"{d=1} d&&p{print p; exit}' "$INI")
fi
if [[ "$PROFILE_PATH" = /* ]]; then
  PROFILE="$PROFILE_PATH"
else
  PROFILE="$TB_DIR/$PROFILE_PATH"
fi
if [[ ! -d "$PROFILE" ]]; then
  echo "Profilordner nicht gefunden: $PROFILE"
  exit 1
fi

TARGET="$PROFILE/extensions/$ADDON_ID.xpi"
CHROME="$PROFILE/chrome"

if [[ "$1" == "--uninstall" ]]; then
  rm -f "$TARGET"
  [[ -f "$PROFILE/user.js" ]] && sed -i '' -e '/mail.addressDisplayFormat/d' -e '/mail.fixed_width_messages/d' "$PROFILE/user.js"
  if [[ -f "$CHROME/userChrome.css.vor-mail-cards" ]]; then
    mv "$CHROME/userChrome.css.vor-mail-cards" "$CHROME/userChrome.css"
    echo "Frühere userChrome.css wiederhergestellt."
  fi
  echo "Entfernt. Thunderbird neu starten."
  exit 0
fi

XPI="$1"
if [[ -z "$XPI" ]]; then
  XPI=$(ls -t "$ROOT"/dist/halo-spaces-*.xpi 2>/dev/null | head -1)
fi
if [[ -z "$XPI" || ! -f "$XPI" ]]; then
  echo "Kein Paket gefunden. Erst ./build.sh ausführen oder die .xpi von GitHub angeben."
  exit 1
fi

mkdir -p "$PROFILE/extensions"
cp "$XPI" "$TARGET"

# Das Design kommt jetzt aus der Erweiterung. Eine früher kopierte
# userChrome.css dieses Designs würde Vorrang haben und Updates verdecken –
# sie wird beiseitegelegt (eigene, fremde userChrome.css bleiben unberührt).
if [[ -f "$CHROME/userChrome.css" ]] && grep -q "$MARKER" "$CHROME/userChrome.css"; then
  mv "$CHROME/userChrome.css" "$CHROME/userChrome.css.alte-version"
  echo "Alte userChrome.css dieses Designs beiseitegelegt (userChrome.css.alte-version)."
fi

touch "$PROFILE/user.js"
for PREF in "${PREFS[@]}"; do
  grep -qF "${PREF%%,*}" "$PROFILE/user.js" || echo "$PREF" >> "$PROFILE/user.js"
done

echo "Installiert in: $PROFILE"
echo "Thunderbird starten und die Nachfrage „Erweiterung hinzugefügt“ bestätigen."
echo "Unter Add-ons und Themes → Themes „System – automatisch“ wählen."
