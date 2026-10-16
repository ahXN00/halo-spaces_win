# halo.spaces

**Ein ruhiges, aufgeräumtes Design für Thunderbird auf dem Mac.**
Inspiriert von Apple Mail, mit eigener Note: farbige Bereiche links und
dasselbe Layout in jedem Bereich.

halo.spaces ist ein Komplettpaket für Thunderbird 128+ auf macOS: Design, eigene Symbole im
Apple-Stil und eine Erweiterung für alles, was CSS allein nicht kann.

- Layout, Farben, Größen und Animationen wie Apple Mail, Kalender, Kontakte,
  Nachrichten und Systemeinstellungen, mit farbigen Bereichen links
- Kartenansicht mit zweizeiliger Vorschau und Absenderbildern (Adressbuch,
  macOS-Kontakte, BIMI, Website-Icon, sonst Initialen)
- vereinigtes Adressbuch mit zusammengeführten Doppeleinträgen und
  Konto-Etiketten in den Kontofarben
- dieselbe Toolbar in jedem Bereich, Suchfeld oben rechts
- Hell und Dunkel folgen automatisch dem System
- Kalender laden schneller: Offline-Unterstützung für Online-Kalender wird
  eingeschaltet (nur wo die Einstellung nie geändert wurde)

## Installation

1. Die neueste `halo-spaces-<version>.xpi` unter **Releases** herunterladen.
2. In Thunderbird: **Add-ons und Themes → Zahnrad → Add-on aus Datei
   installieren…** und die Datei wählen.
3. Unter **Themes** „System – automatisch“ wählen.

Alternativ bei geschlossenem Thunderbird: `./install.sh pfad/zur/datei.xpi`.
Das setzt zusätzlich zwei Einstellungen wie in Apple Mail (nur Namen statt
Adressen, keine Schreibmaschinenschrift bei Textmails).

## Updates

Die Erweiterung bringt eine Update-Adresse mit. Thunderbird fragt dort
selbst regelmäßig nach neuen Versionen (Standard: alle 24 Stunden) und
installiert sie automatisch. Sofort prüfen: **Help → halo.spaces … → Nach Updates suchen**
(oder Add-ons und Themes → Zahnrad → Nach Updates suchen).

Das Design steckt in der Erweiterung. Eine `userChrome.css` im Profil ist
nicht mehr nötig; eine früher kopierte Version dieses Designs hätte Vorrang
und würde Updates verdecken (`install.sh` legt sie beiseite).

## Feedback

In Thunderbird: **Help → halo.spaces … → Feedback senden** öffnet eine neue Mail
an halo.cat@icloud.com. Dort gibt es auch „Danke sagen ☕“. Fehler und Wünsche gern auch als Issue hier auf GitHub.

## Entwickeln

| Ordner/Datei | Inhalt |
|---|---|
| `chrome/userChrome.css` | Design (Mail, Menüs, Dialoge) |
| `chrome/bereiche.css` | Kalender, Aufgaben, Adressbuch, Chat, Einstellungen – wird mit `chrome/merge_bereiche.py` eingefügt |
| `icons/make_icons.py` | Toolbar- und Ordnersymbole (`--inject` schreibt in userChrome.css) |
| `icons/make_iconvars.py` | Ersatz für Thunderbirds `--icon-*`-Symbole |
| `erweiterung/` | die Erweiterung (Manifest, `api/implementation.js`) |

```bash
./build.sh            # → dist/halo-spaces-<version>.xpi (inkl. theme.css)
./release.sh 2.11.0   # Version, Update-Adresse, updates.json – veröffentlicht nichts
```

`release.sh` braucht eine `repo.conf` (Vorlage: `repo.conf.example`) und gibt
am Ende die Befehle zum Veröffentlichen aus (`git push`, `gh release create`).
Abschalten lässt sich das mitgelieferte Design über die Einstellung
`extensions.mailcards.bundledTheme = false`, die eigenen Symbole über
`extensions.mailcards.appleIcons = false`, die automatische
Offline-Unterstützung für Kalender über `extensions.mailcards.calendarOffline = false`.

## Lizenz

Mozilla Public License 2.0 – siehe [LICENSE](LICENSE).
