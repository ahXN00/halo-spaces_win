# Fortschritt der Design-Durchsicht

Zu Beginn jeder Runde lesen. Status je Oberfläche: `offen`, `erledigt` (mit Commit)
oder `übersprungen: Grund`. Reihenfolge = Priorität (siehe tests/inventar.md).

Vorher-Bilder: `tests/shots/tour/vorher/` (hell-*/dunkel-*), Paket `tests/shots/review-r1.xpi`.

## 1. Mailliste (`mailliste`)

- [x] `mail-karten` – Mailliste als Karten, Posteingang mit ausgewählter Mail: erledigt (Commit „Mailliste: …“ (Runde 1)) – Datum ungelesener Karten normal statt fett; zugeklappte Konversation mit Ungelesenem hat den Akzent-Punkt, Thread-Knopf als graue Kapsel ohne Stern/Akzentrahmen; Runde 1 Leseansicht: Uhrzeit/Datum der Karten im Format der Regionaleinstellungen wie im Mailkopf (Commit „Leseansicht: …“)
- [x] `mail-karten-ohne-auswahl` – Posteingang ohne Auswahl (leere Leseansicht): erledigt (Runde 1: geprüft, kein eigener Befund; Datum/Thread-Knopf wie bei mail-karten)
- [x] `mail-tabelle` – Mailliste als Tabelle: erledigt (Commit „Mailliste: …“ (Runde 1)) – Schrift 13 px wie Karten und Spaltenkopf; Ungelesen-Punkt in Akzentfarbe statt Grün/Ring; kein Funkelstern vor neuen Mails; Schlagwortfarben hell abgedunkelt, dunkel aufgehellt (Kontrast ≥ 4,5:1)
- [x] `mail-tabelle-threads` – Tabelle nach Threads gruppiert, Threads aufgeklappt: erledigt (Commit „Mailliste: …“ (Runde 1)) – wie mail-tabelle (13 px, Akzent-Punkt auch für zugeklappte Konversation mit Ungelesenem, kein Stern)
- [x] `mail-karten-threads` – Karten nach Threads gruppiert, Thread aufgeklappt: erledigt (Commit „Mailliste: …“ (Runde 1)) – Thread-Knopf ohne Stern/grünen Punkt und Akzentrahmen, 4 px Abstand zum Betreff; ausgewählt mit Fokus durchscheinend auf Akzent
- [x] `mail-hover` – Karte unter dem Mauszeiger (Hover mit Aktionen): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-fokusring` – Tastaturfokus in der Liste (Fokusring): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-auswahl-unfokussiert` – Ausgewählte Mail, Fokus in der Ordnerliste (ausgewählt-unfokussiert): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-mehrfachauswahl` – Mehrere Mails ausgewählt (Zusammenfassung): erledigt (Commit „Mailliste: …“ (Runde 1)) – Ungelesen-Punkt der Zusammenfassung in Akzentfarbe statt Grün (übrige Zusammenfassungsseite gehört zur Leseansicht)
- [x] `mail-leerer-ordner` – Leerer Ordner: erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-entwuerfe` – Ordner Entwürfe: erledigt (Commit „Mailliste: …“ (Runde 1)) – in Ordnern mit Entwurfs-Merkmal zeigt die Karte jetzt Bild und Namen des Empfängers wie Thunderbird; der Rundgang-Ordner „Drafts“ hat kein Merkmal, daher im Bild unverändert
- [x] `mail-gesendet` – Ordner Gesendet (Empfänger statt Absender): erledigt (Commit „Mailliste: …“ (Runde 1)) – Bild des Empfängers statt der eigenen Initialen, Empfänger nur mit Namen (Adresse im Tooltip); Mailkopf zeigt weiter den Absender. Der Rundgang-Ordner „Sent“ hat kein Gesendet-Merkmal (DATA_JS bewusst nicht geändert, sonst ändern sich Ordnerliste/Favoriten in allen Bildern) – geprüft in halo_test.py mit „Gesendet-Test“
- [x] `mail-alle-posteingaenge` – Alle Posteingänge (Sammelordner): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-konto-startseite` – Konto-Startseite (Local Folders ausgewählt): erledigt (Commit „Mailliste: …“ (Runde 1)) – eine ruhige Fläche (--mt-window) statt dreier getönter Bänder, Abschnitte mit Haarlinie, Kacheln als graue Knöpfe mit 6 px Radius ohne Akzentfläche beim Überfahren; Texte, Logo, Links, Wasserzeichen unverändert
- [x] `mail-schmal-1100` – Schmales Fenster (1100 px bzw. kleinste mögliche Breite): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-dichte-kompakt` – Dichte „kompakt“: erledigt (Runde 1: geprüft; Thread-Knopf und Datum wie bei mail-karten)
- [x] `mail-dichte-gross` – Dichte „Touch“ (groß): erledigt (Runde 1: geprüft; Thread-Knopf und Datum wie bei mail-karten)
- [x] `mail-layout-klassisch` – Layout „klassisch“ (Liste oben, Mail unten): erledigt (Commit „Mailliste: …“ (Runde 1)) – Haarlinie (--mt-pane-line) oben an der Leseansicht statt gar keiner Trennung
- [x] `mail-layout-breit` – Layout „breit“: erledigt (Commit „Mailliste: …“ (Runde 1)) – Haarlinie oben an der Leseansicht über die volle Breite (trennt auch die Ordnerliste ab)
- [x] `mail-ohne-leseansicht` – Leseansicht ausgeblendet (nur Liste): erledigt (Runde 1: geprüft, kein Befund; keine Linie ohne Leseansicht)
- [x] `mail-schnellfilter` – Schnellfilter-Leiste offen: erledigt (Commit „Mailliste: …“ (Runde 1)) – toter Selektor #quickFilterBar durch #quick-filter-bar ersetzt: Leiste auf der Listenfläche mit Haarlinie statt abgesetztem Band, Pin-Knopf bündig mit den Karten (8 px)
- [x] `mail-schnellfilter-aktiv` – Schnellfilter „Ungelesen“ aktiv: erledigt (Commit „Mailliste: …“ (Runde 1)) – Leiste wie mail-schnellfilter; zugeklappte Konversation zeigt Name passend zum Bild (neueste Mail)
- [x] `mail-schnellfilter-text` – Schnellfilter mit Suchtext (Zeile „Absender / Empfänger / Betreff / Text“): erledigt (Commit „Mailliste: …“ (Runde 1)) – Leiste wie mail-schnellfilter
- [x] `mail-schnellfilter-ohne-treffer` – Schnellfilter ohne Treffer: Hinweis „Enter: in allen Ordnern suchen“: erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-schnellfilter-schlagwoerter` – Schnellfilter „Schlagwörter“ (Zeile mit Schlagwort-Knöpfen): erledigt (Commit „Mailliste: …“ (Runde 1)) – Zeile „Any of“ bündig mit den Karten; Schlagwort-Knöpfe hell/dunkel mit Kontrast ≥ 4,5:1
- [x] `mail-schnellfilter-schlagwort-modus` – Schnellfilter „Schlagwörter“: Menü „Beliebig / Alle / Keine“: erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-spaltenauswahl` – Tabelle: Spaltenauswahl (Listen-Spaltenmenü): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-ansichtsoptionen` – Listenkopf: Ansichtsoptionen (…): erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-ansichtsoptionen-sortieren` – Listenkopf: Ansichtsoptionen → Sortieren nach: erledigt (Runde 1: geprüft, kein Befund)
- [x] `mail-gruppiert` – Karten gruppiert nach Sortierung (Gruppenköpfe Heute, Gestern, Letzte 7 Tage …): erledigt (Commit „Mailliste: …“ (Runde 1)) – Gruppenköpfe nicht mehr abgeschnitten („Yesterd“, „Last 7 D“): eine Spalte ohne Bild/Vorschau, unten direkt über der ersten Mail, Titel halbfett, Anzahl 11 px sekundärgrau
- [x] `mail-gruppiert-tabelle` – Tabelle gruppiert nach Sortierung (Gruppenköpfe): erledigt (Commit „Mailliste: …“ (Runde 1)) – wie mail-tabelle (13 px, Akzent-Punkt, kein Stern)

## 2. Leseansicht und Mailkopf (`lesen`)

- [x] `lesen-text` – Leseansicht: Textmail mit Cc: erledigt (Commit „Leseansicht: …“ (Runde 1)) – nur noch eine Linie zwischen Kopf und Mailtext (Thunderbirds zweite Linie an #mail-notification-top entfernt); Kommas in Cc tertiärgrau wie in An; Uhrzeit in Liste und Kopf im selben Format (Regionaleinstellungen). Verworfen: dunkler Mailgrund (#18181B) gegenüber Kopf (#1E1E1E) – kaum sichtbar, die Korrektur überschriebe eigene Hintergründe von Mails und bräuchte @-moz-document im Author-Sheet; verworfen: Ordner/Uhrzeit im Kopf in Sekundärgrau – Tertiärgrau für Nebeninfos ist im Projekt durchgängig gewählt (Token-Frage, keine Einzelkorrektur)
- [x] `lesen-newsletter` – HTML-Newsletter mit Abmelde-Hinweis (List-Unsubscribe): erledigt (Runde 1: geprüft, nichts geändert) – verworfen: 560 px breite Newsletter werden im 484-px-Lesebereich rechts ohne Hinweis abgeschnitten; Abhilfe wäre neues Verhalten (CSS-Zoom auf jede HTML-Mail mit ResizeObserver – Risiken mit Text-Zoom, nachgeladenen Bildern, Drucken, Resize-Schleifen). Offener Punkt: „Breite HTML-Mails auf Lesebreite verkleinern (wie Apple Mail) – nur mit Freigabe“
- [x] `lesen-thread-anhang` – Antwort im Thread mit einem Anhang: erledigt (Commit „Leseansicht: …“ (Runde 1)) – Anhangsleiste auf der Fläche der Mail mit Haarlinie statt grauem Band
- [x] `lesen-anhaenge-fremdinhalt` – Mail mit drei Anhängen und blockiertem Bild (Hinweisleiste): erledigt (Commit „Leseansicht: …“ (Runde 1)) – Anhangsleiste wie lesen-anhaenge-liste. Verworfen: gelbe Hinweisleiste auch im Dunkelmodus – bewusste Entscheidung (Commit 02cc7d6, Test „Hinweis über der Mail … Farbe unverändert“); verworfen: Linien inline angezeigter Anhänge – Thunderbirds Darstellung im Mailinhalt, kein harter Kontrastrahmen, Geschmacksfrage (bräuchte zudem @-moz-document im Author-Sheet)
- [x] `lesen-anhaenge-liste` – Anhangsliste aufgeklappt: erledigt (Commit „Leseansicht: …“ (Runde 1)) – Leiste und Liste auf --mt-window statt Zinkgrau bzw. dunkel #3F3F46, eine Haarlinie darüber; markierte Datei 6 px rund in Akzentfarbe ohne Rahmen und Outline, unfokussiert grau
- [x] `lesen-viele-empfaenger` – Mailkopf mit vielen Empfängern: erledigt (Commit „Leseansicht: …“ (Runde 1)) – „Mehr“ als graue Kapsel in 11 px („More“) statt blauer Pille mit 9,9-px-Versalien
- [x] `lesen-alle-empfaenger` – Mailkopf: alle Empfänger ausgeklappt: erledigt (Commit „Leseansicht: …“ (Runde 1)) – Kommas in Cc/Bcc/Antwort-an tertiärgrau wie in der An-Zeile (vorher fast schwarz bzw. dunkel fast weiß)
- [x] `lesen-langer-betreff` – Sehr langer Betreff und Absendername: erledigt (Commit „Leseansicht: …“ (Runde 1)) – im schmalen Mailbereich (< 768 px) bleibt der Kopf so breit wie der Mailbereich: langer Absendername endet mit „…“ vor Ordner und Uhrzeit, Betreff bricht vollständig um; Nachrichtenfenster unverändert
- [x] `lesen-junk` – Als Junk markierte Mail (Junk-Leiste): erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-entwurf` – Entwurf in der Leseansicht (Bearbeiten-Leiste): erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-html-tabelle` – HTML-Mail mit Tabelle: erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-tab` – Mail im eigenen Tab: erledigt (Commit „Leseansicht: …“ (Runde 1)) – im Nachrichten-Tab kein Listenkopf („Inbox – On My Mac / 25 messages“) und kein Seitenleisten-Grau oben und in der Statusleiste mehr; der Seitenleisten-Knopf sitzt wie in anderen Bereichen ohne Seitenleiste neben den Fensterknöpfen; zurück im Mail-Tab wie vorher
- [x] `lesen-fenster` – Mail im eigenen Fenster: erledigt (Runde 1: geprüft; nur die doppelte Linie unter dem Kopf entfällt) – verworfen: Knopfleiste im eigenen Fenster mittig über Ordner/Uhrzeit – nichts abgeschnitten oder überlappend, die Korrektur bräuchte mehrere abgestimmte Versätze und führte im Versuch zu einer Überlappung (eigene Runde zum Nachrichtenfenster)
- [x] `lesen-suchleiste` – Suchleiste in der Mail (Bearbeiten → Suchen): erledigt (Commit „Leseansicht: …“ (Runde 1)) – Leiste mit Haarlinie auf der Fläche der Mail, Suchfeld als graue Fläche ohne Rahmen (6 px); bei wenig Platz brechen die Optionen um statt rechts abgeschnitten zu werden (gilt auch im Verfassen-Fenster: „1 of 1 match“ jetzt ganz sichtbar). Nicht umgesetzt: Optionen ausblenden (Verhaltensänderung, nur mit Freigabe)
- [x] `lesen-quelltext` – Quelltext der Mail: erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-mehr-menue` – Mailkopf: „Mehr“-Menü: übersprungen: nicht erreichbar – Knopf ausgeblendet: halo.spaces blendet die Symbolleiste im Mailkopf aus (Aktionen über Toolbar und Kontextmenü)
- [x] `lesen-adresse-popup` – Mailkopf: Menü zur Absenderadresse: erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-kopf-anpassen` – Mailkopf anpassen (Panel): übersprungen: nicht erreichbar – Knopf ausgeblendet: halo.spaces blendet die Symbolleiste im Mailkopf (und damit „Anpassen“) aus
- [x] `lesen-anhaenge-speichern` – Anhänge: Menü „Alle speichern“: erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-fremdinhalt-optionen` – Hinweisleiste: Optionen für entfernte Inhalte: erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-einladung` – Mail mit Kalender-Einladung (iMIP-Leiste: Zusagen, Vielleicht, Absagen, Mehr): erledigt (Commit „Leseansicht: …“ (Runde 1)) – iMIP-Leiste als graue Kapsel (12 px Radius, ohne Schatten) statt hellblauer bzw. dunkel lila Fläche mit 2,3:1-Kontrast; Text über die ganze Zeile, Knöpfe als graue Kapseln darunter (Hauptknopf und Pfeil in einer Kapsel mit Haarlinie); Einladungsdetails als Karte mit feiner Linie und 10 px Radius in der Breite des Lesebereichs statt 600 px mit 3-px-Rahmen, Werte linksbündig
- [x] `lesen-einladung-zusagen` – Einladung: Menü am Knopf „Zusagen“: erledigt (Runde 1: geprüft; Menü unverändert, Knöpfe siehe lesen-einladung)
- [x] `lesen-einladung-mehr` – Einladung: Menü „Mehr“: erledigt (Runde 1: geprüft; Menü unverändert, Knöpfe siehe lesen-einladung)
- [x] `lesen-empfangsbestaetigung` – Hinweisleiste „Absender bittet um Empfangsbestätigung“: erledigt (Runde 1: geprüft, kein Befund; Farben der Hinweisleisten bewusst Thunderbirds, s. lesen-anhaenge-fremdinhalt)
- [x] `lesen-betrugswarnung` – Hinweisleiste „Diese Nachricht könnte Betrug sein“: erledigt (Runde 1: geprüft, kein Befund; Farben der Hinweisleisten bewusst Thunderbirds)
- [x] `lesen-betrugswarnung-optionen` – Betrugswarnung: Menü am Knopf der Hinweisleiste: erledigt (Runde 1: geprüft, kein Befund)
- [x] `lesen-kontakt-bearbeiten` – Mailkopf: Panel „Kontakt bearbeiten“ (über das Menü zur Absenderadresse): erledigt (Commit „Leseansicht: …“ (Runde 1)) – Panel mit neutraler Fläche und weichem Rand wie die Tooltips (hell #FFFFFF, dunkel #2C2C2E) statt Thunderbirds bläulichem Schiefergrau (#262D3B) mit hartem Rand

## 3. Verfassen (`verfassen`)

- [ ] `verfassen-html` – Verfassen (HTML) mit Formatleiste: offen
- [ ] `verfassen-text` – Verfassen (reiner Text): offen
- [ ] `verfassen-antwort` – Antworten (zitierter Text): offen
- [ ] `verfassen-cc-bcc` – Verfassen mit Cc und vielen Empfängern: offen
- [ ] `verfassen-anhaenge` – Verfassen mit Anhängen: offen
- [ ] `verfassen-kontakte` – Verfassen mit Kontakte-Seitenleiste: offen
- [ ] `verfassen-absender-menue` – Verfassen: Absender-Auswahl: offen
- [ ] `verfassen-autovervollstaendigung` – Verfassen: Adress-Vorschläge beim Tippen: offen
- [ ] `verfassen-absatz-menue` – Formatleiste: Absatzformat: offen
- [ ] `verfassen-schrift-menue` – Formatleiste: Schriftart: offen
- [ ] `verfassen-einfuegen-menue` – Formatleiste: Einfügen: offen
- [ ] `verfassen-anhang-menue` – Symbolleiste: Anhängen-Menü: offen
- [ ] `verfassen-speichern-menue` – Symbolleiste: Speichern-Menü: offen
- [ ] `verfassen-rechtschreibung-menue` – Symbolleiste: Rechtschreibung/Sprache: offen
- [ ] `verfassen-weitere-felder` – Adressfelder: weitere Felder (…): offen
- [ ] `verfassen-farbe` – Verfassen: Textfarbe wählen: offen
- [ ] `verfassen-link` – Verfassen: Link einfügen: offen
- [ ] `verfassen-tabelle` – Verfassen: Tabelle einfügen: offen
- [ ] `verfassen-speichern-frage` – Verfassen schließen: „Speichern?“-Frage: offen
- [ ] `verfassen-kontext-text` – Kontextmenü im Nachrichtentext (Verfassen): offen
- [ ] `verfassen-kontext-anhang` – Kontextmenü eines Anhangs (Verfassen): offen
- [ ] `verfassen-anhaenge-anordnen` – Panel „Anhänge neu anordnen“: offen
- [ ] `verfassen-anhang-erinnerung` – Hinweisleiste „Anhang vergessen?“ (Schlüsselwort im Text): offen
- [ ] `verfassen-bild` – Verfassen: Bild einfügen: offen
- [ ] `verfassen-rechtschreibung-dialog` – Verfassen: Rechtschreibung prüfen: offen
- [ ] `verfassen-schriftgroesse-menue` – Formatleiste: Textgröße: offen
- [ ] `verfassen-ausrichtung-menue` – Formatleiste: Ausrichtung (mit Symbolen): offen
- [ ] `verfassen-smiley-menue` – Formatleiste: Smileys: offen
- [ ] `verfassen-suchleiste` – Verfassen: Suchleiste im Nachrichtentext (Bearbeiten → Suchen): offen
- [ ] `verfassen-suchen-ersetzen` – Verfassen: Suchen und Ersetzen: offen
- [ ] `verfassen-anker` – Verfassen: Einfügen → Anker: offen
- [ ] `verfassen-toolbar-kontext` – Verfassen: Kontextmenü der Symbolleiste: offen
- [ ] `verfassen-toolbar-anpassen` – Verfassen: Symbolleiste anpassen (Sheet): offen
- [x] `verfassen-verschluesselung` – Verfassen: Verschlüsselungs-Panel: übersprungen: braucht einen OpenPGP-/S/MIME-Schlüssel – im Testprofil nicht vorhanden

## 4. Ordnerliste, Toolbar, Suche, Bereiche-Leiste (`ordner`)

- [ ] `ordner-mehr-menue` – Ordnerliste: „…“-Menü (Ordner-Modi): offen
- [ ] `ordner-modi` – Ordnerliste mit Modi „Ungelesen“ und „Markiert“: offen
- [ ] `ordner-kompakt` – Ordnerliste kompakt (ohne Kopf/Abrufen-Knöpfe): offen
- [ ] `ordner-ausgeblendet` – Ordnerliste ausgeblendet: offen
- [x] `ordner-abrufen-menue` – Ordnerliste: Abrufen-Knopf (Kontextmenü): übersprungen: nicht erreichbar – Knopf deaktiviert: kein Konto mit Server im Testprofil
- [ ] `toolbar-verschieben` – Toolbar: „Verschieben“ (Ordnerauswahl): offen
- [ ] `toolbar-markieren` – Toolbar: „Markieren“: offen
- [x] `toolbar-abrufen` – Toolbar: „Abrufen“ (Kontomenü): übersprungen: nicht erreichbar – Knopf deaktiviert: kein Konto mit Server im Testprofil
- [ ] `toolbar-anpassen` – Toolbar anpassen: offen
- [ ] `suche-ergebnisse` – Suche oben: Treffer in allen Postfächern: offen
- [ ] `suche-globale-ergebnisse` – Globale Suche (Ergebnis-Tab): offen
- [ ] `suche-vorschlaege` – Suchfeld oben außerhalb der Mailansicht: Vorschlagsliste (Kalender-Tab): offen
- [ ] `today-pane-zu` – Mail ohne Today-Pane: offen
- [ ] `spaces-eingeklappt` – Bereiche-Leiste eingeklappt: offen
- [x] `spaces-menue-knopf` – Bereiche-Leiste eingeklappt: Bereiche-Menü: übersprungen: von halo.spaces ersetzt: der Knopf blendet die Seitenleiste ein/aus, das Menü wird blockiert (implementation.js, hookSidebarButton)
- [ ] `spaces-anpassen` – Bereiche-Leiste anpassen (Panel): offen
- [ ] `appmenu` – App-Menü (≡): offen
- [ ] `appmenu-ansicht` – App-Menü → Ansicht (Unteransicht): offen

## 5. Menüs und Kontextmenüs (`menues`)

- [x] `menueleiste-datei` – Menüleiste: Datei (Neu, Öffnen, Speichern unter, Abrufen für, Offline): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-bearbeiten` – Menüleiste: Bearbeiten (Auswählen, Suchen): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-ansicht` – Menüleiste: Ansicht (Symbolleisten, Layout, Ordner, Dichte, Zoom, Schriftgröße, Today-Pane, Kalender, Aufgaben, Sortieren, Nachrichten, Threads, Kopfzeilen, Nachrichteninhalt): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-gehe` – Menüleiste: Gehe (Weiter, Zurück, Ordner, Zuletzt geschlossene Tabs): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-nachricht` – Menüleiste: Nachricht (Weiterleiten als, Anhänge, Schlagwort, Markieren, Verschieben, Kopieren): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-termine` – Menüleiste: Termine und Aufgaben (Fortschritt, Priorität, Aufgabe verschieben): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-extras` – Menüleiste: Extras (Chat-Status, Entwicklerwerkzeuge): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-fenster` – Menüleiste: Fenster: übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [x] `menueleiste-hilfe` – Menüleiste: Hilfe (inkl. „halo.spaces …“): übersprungen: nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar
- [ ] `kontext-mailliste` – Kontextmenü: Mailliste: offen
- [ ] `kontext-mailliste-untermenue` – Kontextmenü: Mailliste → Schlagwort: offen
- [ ] `kontext-ordnerliste` – Kontextmenü: Ordnerliste: offen
- [ ] `kontext-mailtext` – Kontextmenü: Mailtext: offen
- [x] `kontext-mailkopf` – Kontextmenü: Mailkopf (Symbolleiste): übersprungen: nicht erreichbar – Symbolleiste im Mailkopf von halo.spaces ausgeblendet – kein Ort für dieses Kontextmenü
- [ ] `kontext-anhang` – Kontextmenü: Anhang: offen
- [ ] `kontext-tab` – Kontextmenü: Tab: offen
- [ ] `kontext-toolbar` – Kontextmenü: Toolbar: offen
- [ ] `kontext-bereich` – Kontextmenü: Bereiche-Leiste (Bereich): offen
- [ ] `kontext-bereiche-leiste` – Kontextmenü: Bereiche-Leiste (leere Fläche): offen
- [ ] `kontext-einstellungen-knopf` – Kontextmenü: Einstellungen-Knopf der Bereiche-Leiste: offen
- [ ] `kontext-schnellfilter` – Kontextmenü: Schnellfilter-Leiste: offen
- [ ] `kontext-verfassen-adresse` – Kontextmenü: Adresse im Verfassen-Fenster: offen
- [ ] `tooltip-toolbar` – Tooltip an einem Toolbar-Knopf („Verfassen“): offen

## 6. Kalender und Today-Pane (`kalender`)

- [ ] `kal-tag` – Kalender: Tag: offen
- [ ] `kal-woche` – Kalender: Woche: offen
- [ ] `kal-mehrwochen` – Kalender: Mehrere Wochen: offen
- [ ] `kal-monat` – Kalender: Monat: offen
- [ ] `kal-woche-auswahl` – Woche mit ausgewähltem Termin: offen
- [ ] `kal-woche-leer` – Leere Woche: offen
- [ ] `kal-schmal-1100` – Woche im schmalen Fenster (1100 px bzw. kleinste mögliche Breite): offen
- [x] `kal-suche` – Kalender: Termine suchen (Liste oben): übersprungen: nicht erreichbar – von halo.spaces bewusst ausgeblendet (Suchliste gibt es in Apple Kalender nicht)
- [ ] `kal-today-pane` – Today-Pane in der Mailansicht: offen
- [ ] `kal-schnellfenster` – Kalender: Schnellfenster „Neuer Termin“: offen
- [ ] `kal-schnellfenster-datum` – Schnellfenster: Datumsauswahl (Datumsfeld „Beginn“): offen
- [ ] `kal-schnellfenster-auswahlliste` – Schnellfenster: aufgeklappte Auswahlliste „Wiederholen“: offen
- [ ] `kal-schnellfenster-kalender` – Schnellfenster: Kalendermenü mit Farbpunkten: offen
- [ ] `kal-neu-popover` – Today-Pane: „+“ → Neuer Termin / Neue Aufgabe: offen
- [ ] `kal-termin-dialog` – Neuer Termin (Dialog): offen
- [ ] `kal-termin-bearbeiten` – Termin bearbeiten (Ort, Beschreibung): offen
- [ ] `kal-termin-erinnerung-menue` – Termin-Dialog: Erinnerung (Auswahl): offen
- [ ] `kal-wiederholung-dialog` – Termin: benutzerdefinierte Wiederholung: offen
- [ ] `kal-teilnehmer-dialog` – Termin: Teilnehmer einladen: offen
- [ ] `kal-termin-datum` – Termin-Dialog: Datumsauswahl (Minimonat im Datumsfeld): offen
- [ ] `kal-termin-uhrzeit` – Termin-Dialog: Uhrzeit-Raster (Stunden und Minuten): offen
- [ ] `kal-termin-kategorien` – Termin-Dialog: Kategorien (Auswahl mit Häkchen): offen
- [ ] `kal-termin-privatsphaere` – Termin-Dialog: Symbolleiste „Privatsphäre“ (Menü): offen
- [ ] `kal-termin-anhang-menue` – Termin-Dialog: Symbolleiste „Anhängen“ (Menü): offen
- [ ] `kal-erinnerung-anpassen` – Termin: Erinnerungen anpassen (Erinnerung → Benutzerdefiniert…): offen
- [ ] `kal-zusammenfassung` – Termin aus schreibgeschütztem Kalender (Zusammenfassung): offen
- [ ] `kal-erinnerung` – Erinnerungsfenster (Alarm): offen
- [ ] `kal-erinnerung-spaeter` – Erinnerungsfenster: Menü „Später erinnern“ (Schlummern für alle): offen
- [ ] `kal-termin-tooltip` – Kalender: Tooltip eines Termins (Titel, Zeit, Ort, Kalender): offen
- [ ] `kal-eigenschaften` – Kalender-Eigenschaften: offen
- [ ] `kal-neuer-kalender` – Neuer Kalender (Assistent): offen
- [ ] `kal-wiederholung-frage` – Wiederholten Termin löschen: Nachfrage: offen
- [ ] `kal-druck` – Kalender drucken (Druckvorschau): offen
- [ ] `kal-kontext-ansicht` – Kontextmenü: Kalenderansicht (leere Stelle): offen
- [ ] `kal-kontext-termin` – Kontextmenü: Termin: offen
- [ ] `kal-kontext-kalenderliste` – Kontextmenü: Kalenderliste: offen
- [ ] `kal-kontext-today` – Kontextmenü: Termin in der Today-Pane: offen

## 7. Aufgaben (`aufgaben`)

- [ ] `aufg-liste` – Aufgaben mit ausgewählter Aufgabe: offen
- [ ] `aufg-ueberfaellig` – Aufgaben: Filter „Überfällig“: offen
- [ ] `aufg-erledigt` – Aufgaben: Filter „Erledigt“: offen
- [ ] `aufg-leer` – Aufgaben: keine Treffer (Leeranzeige): offen
- [ ] `aufg-dialog` – Neue Aufgabe (Dialog): offen
- [ ] `aufg-bearbeiten` – Aufgabe bearbeiten: offen
- [ ] `aufg-schnellfenster` – Aufgaben: Schnellfenster „Neue Aufgabe“: offen
- [ ] `aufg-kontext` – Kontextmenü: Aufgabe: offen
- [ ] `aufg-prioritaet-menue` – Aufgabe: Priorität (Menü): offen

## 8. Adressbuch (`kontakte`)

- [ ] `ab-kontakt` – Adressbuch: Kontakt ansehen: offen
- [ ] `ab-firma` – Adressbuch: Firma ansehen: offen
- [ ] `ab-langer-name` – Adressbuch: langer Name und Firma: offen
- [ ] `ab-geburtstag` – Adressbuch: Kontakt mit Geburtstag und Notiz: offen
- [ ] `ab-bearbeiten` – Adressbuch: Kontakt bearbeiten: offen
- [ ] `ab-neu` – Adressbuch: neuer Kontakt: offen
- [ ] `ab-foto-dialog` – Adressbuch: Kontaktbild wählen (Dialog): offen
- [ ] `ab-verteiler` – Adressbuch: Verteilerliste: offen
- [ ] `ab-leeres-buch` – Adressbuch: leeres Buch: offen
- [ ] `ab-suche` – Adressbuch: Suche: offen
- [ ] `ab-mehrfachauswahl` – Adressbuch: mehrere Kontakte ausgewählt: offen
- [ ] `ab-schmal-1100` – Adressbuch im schmalen Fenster (1100 px bzw. kleinste mögliche Breite): offen
- [ ] `ab-sortieren` – Adressbuch: Listenoptionen (Sortieren): offen
- [ ] `ab-tabelle` – Adressbuch als Tabelle (Listenoptionen → Tabellenansicht): offen
- [ ] `ab-tabelle-spalten` – Adressbuch-Tabelle: Spaltenauswahl: offen
- [ ] `ab-toolbar-neues-buch` – Adressbuch-Toolbar: „Neues Adressbuch“ (Menü): offen
- [ ] `ab-account-hub` – Adressbuch hinzufügen (Account Hub, „+“ in der Bücherliste): offen
- [ ] `ab-neu-menue` – Adressbuch: „Neues Adressbuch“-Menü (Rechtsklick auf „+“): offen
- [ ] `ab-kontext-kontakt` – Kontextmenü: Kontakt: offen
- [ ] `ab-kontext-buch` – Kontextmenü: Adressbuch: offen
- [ ] `ab-neue-liste` – Neue Verteilerliste (Unterdialog): offen
- [ ] `ab-neues-buch` – Neues Adressbuch (Unterdialog): offen
- [ ] `ab-carddav` – Neues CardDAV-Adressbuch (Unterdialog, ohne Netz): offen
- [ ] `ab-ldap` – Neues LDAP-Verzeichnis (Unterdialog, ohne Netz): offen
- [ ] `ab-adressen-suchen` – Adressen suchen (erweiterte Suche): offen

## 9. Chat (`chat`)

- [ ] `chat-start` – Chat ohne Konto (Startseite): offen
- [x] `chat-unterhaltung` – Chat-Unterhaltung, Kontaktliste, Status: übersprungen: braucht ein Chat-Konto (Netzwerk) – im Testprofil nicht vorhanden

## 10. Einstellungen (`einstellungen`)

- [ ] `einst-allgemein-1` – Einstellungen: Allgemein (1/4): offen
- [ ] `einst-allgemein-2` – Einstellungen: Allgemein (2/4, gescrollt): offen
- [ ] `einst-allgemein-3` – Einstellungen: Allgemein (3/4, gescrollt): offen
- [ ] `einst-allgemein-4` – Einstellungen: Allgemein (4/4, gescrollt): offen
- [ ] `einst-darstellung-1` – Einstellungen: Darstellung (1/2): offen
- [ ] `einst-darstellung-2` – Einstellungen: Darstellung (2/2, gescrollt): offen
- [ ] `einst-verfassen-1` – Einstellungen: Verfassen (1/3): offen
- [ ] `einst-verfassen-2` – Einstellungen: Verfassen (2/3, gescrollt): offen
- [ ] `einst-verfassen-3` – Einstellungen: Verfassen (3/3, gescrollt): offen
- [ ] `einst-datenschutz-1` – Einstellungen: Datenschutz & Sicherheit (1/4): offen
- [ ] `einst-datenschutz-2` – Einstellungen: Datenschutz & Sicherheit (2/4, gescrollt): offen
- [ ] `einst-datenschutz-3` – Einstellungen: Datenschutz & Sicherheit (3/4, gescrollt): offen
- [ ] `einst-datenschutz-4` – Einstellungen: Datenschutz & Sicherheit (4/4, gescrollt): offen
- [ ] `einst-chat-1` – Einstellungen: Chat (1/2): offen
- [ ] `einst-chat-2` – Einstellungen: Chat (2/2, gescrollt): offen
- [ ] `einst-kalender-1` – Einstellungen: Kalender (1/3): offen
- [ ] `einst-kalender-2` – Einstellungen: Kalender (2/3, gescrollt): offen
- [ ] `einst-kalender-3` – Einstellungen: Kalender (3/3, gescrollt): offen
- [ ] `einst-qr` – Einstellungen: Export für Mobilgeräte: offen
- [ ] `einst-suche` – Einstellungen: Suche („font“): offen
- [ ] `einst-menue-darstellung` – Einstellungen: Auswahl Hell/Dunkel (halo.spaces): offen
- [ ] `einst-menue-schrift` – Einstellungen: Auswahlliste Schriftart: offen
- [ ] `einst-menue-woche` – Einstellungen: Auswahlliste Wochenbeginn: offen
- [ ] `einst-dlg-schriften` – Einstellungen → Schriftarten (erweitert): offen
- [ ] `einst-dlg-dock` – Einstellungen → Dock-Optionen: offen
- [ ] `einst-dlg-benachrichtigung` – Einstellungen → Benachrichtigung anpassen: offen
- [ ] `einst-dlg-schlagwort` – Einstellungen → Neues Schlagwort: offen
- [ ] `einst-dlg-empfangsbestaetigung` – Einstellungen → Empfangsbestätigungen: offen
- [ ] `einst-dlg-updates` – Einstellungen → Update-Chronik: offen
- [ ] `einst-dlg-verbindung` – Einstellungen → Verbindungs-Einstellungen: offen
- [ ] `einst-dlg-offline` – Einstellungen → Offline-Einstellungen: offen
- [ ] `einst-dlg-sprachen` – Einstellungen → Sprachen: offen
- [ ] `einst-dlg-anhang-erinnerung` – Einstellungen → Anhang-Erinnerung: Schlüsselwörter: offen
- [ ] `einst-dlg-fremdinhalte` – Einstellungen → Ausnahmen für entfernte Inhalte: offen
- [ ] `einst-dlg-cookie-ausnahmen` – Einstellungen → Cookie-Ausnahmen: offen
- [ ] `einst-dlg-cookies` – Einstellungen → Cookies: offen
- [ ] `einst-dlg-passwoerter` – Einstellungen → Gespeicherte Passwörter: offen
- [ ] `einst-dlg-zertifikate` – Einstellungen → Zertifikatverwaltung: offen
- [ ] `einst-dlg-geraete` – Einstellungen → Kryptographie-Module: offen
- [ ] `einst-dlg-kategorie` – Einstellungen → Kalender: Neue Kategorie: offen
- [ ] `einst-dlg-systemintegration` – Einstellungen → Systemintegration (Standardprogramm): offen
- [ ] `einst-dlg-verzeichnisse` – Einstellungen → Verfassen → LDAP-Verzeichnisse verwalten: offen
- [ ] `einst-dlg-junk-protokoll` – Einstellungen → Datenschutz → Junk-Protokoll anzeigen: offen
- [x] `einst-dlg-hauptpasswort` – Einstellungen → Hauptpasswort ändern: übersprungen: verlangt vorher eine macOS-Anmeldung (Systempasswort) – bewusst ausgelassen
- [ ] `einst-konfiguration` – Konfiguration bearbeiten (about:config): offen

## 11. Kontoeinstellungen und Kontoassistenten (`konten`)

- [ ] `konto-start` – Kontoeinstellungen: Local Folders: offen
- [ ] `konto-server` – Kontoeinstellungen: Server-Einstellungen: offen
- [ ] `konto-kopien` – Kontoeinstellungen: Kopien & Ordner: offen
- [ ] `konto-verfassen` – Kontoeinstellungen: Verfassen & Adressieren: offen
- [ ] `konto-junk` – Kontoeinstellungen: Junk: offen
- [ ] `konto-speicher` – Kontoeinstellungen: Speicherplatz: offen
- [ ] `konto-smtp` – Kontoeinstellungen: Postausgang-Server (SMTP): offen
- [ ] `konto-hinzufuegen-menue` – Kontoeinstellungen: Konto hinzufügen (Menü): offen
- [ ] `konto-smtp-dialog` – Postausgang-Server hinzufügen (Dialog, ohne Speichern): offen
- [ ] `konto-archiv-optionen` – Kontoeinstellungen → Kopien & Ordner → Archiv-Optionen (Unterdialog): offen
- [ ] `konto-einrichten` – E-Mail-Konto einrichten (Account Hub, ohne Netz): offen
- [ ] `konto-feed-assistent` – Feed-Konto anlegen (Assistent, abgebrochen): offen
- [ ] `konto-news-assistent` – Newsgruppen-Konto (Assistent, abgebrochen): offen
- [ ] `konto-chat-assistent` – Chat-Konto (Assistent, abgebrochen): offen

## 12. Add-ons und halo.spaces-Fenster (`addons`)

- [ ] `addons-erweiterungen` – Add-ons: Erweiterungen: offen
- [ ] `addons-themes` – Add-ons: Themes: offen
- [ ] `addons-detail` – Add-ons: halo.spaces (Details): offen
- [ ] `addons-halo-einstellungen` – halo.spaces-Einstellungen (im Add-ons-Manager): offen
- [ ] `addons-karten-menue` – Add-ons: Menü einer Erweiterung (…): offen
- [ ] `addons-werkzeuge-menue` – Add-ons: Zahnrad-Menü (Updates, Add-on aus Datei installieren, Tastenkombinationen …): offen
- [ ] `halo-info` – Hilfe → halo.spaces … (Info-Fenster): offen
- [x] `addons-empfehlungen` – Add-ons: Empfehlungen: übersprungen: lädt Inhalte aus dem Netz (addons.thunderbird.net) – im Testprofil ausgelassen

## 13. Seltene Dialoge (`dialoge`)

- [ ] `dlg-ordner-eigenschaften` – Ordner-Eigenschaften: offen
- [ ] `dlg-ordner-neu` – Neuer Ordner: offen
- [ ] `dlg-ordner-umbenennen` – Ordner umbenennen: offen
- [ ] `dlg-suchordner` – Neuer Suchordner (gespeicherte Suche): offen
- [ ] `dlg-filterliste` – Nachrichtenfilter (Liste): offen
- [ ] `dlg-filter-editor` – Filterregeln bearbeiten (Filter-Editor): offen
- [ ] `dlg-filterprotokoll` – Nachrichtenfilter → Filterprotokoll: offen
- [ ] `dlg-suchordner-ordnerwahl` – Suchordner → Ordner auswählen (Ordnerliste zum Durchsuchen): offen
- [ ] `dlg-suche` – Nachrichten suchen (erweiterte Suche): offen
- [ ] `dlg-lesen-nach-datum` – Nach Datum als gelesen markieren: offen
- [ ] `dlg-schlagwort` – Neues Schlagwort (aus der Mailliste): offen
- [ ] `dlg-druckvorschau` – Druckvorschau einer Mail: offen
- [ ] `dlg-ueber` – Über Thunderbird: offen
- [ ] `dlg-aktivitaeten` – Aktivitäten: offen
- [ ] `dlg-downloads` – Gespeicherte Dateien (about:downloads): offen
- [ ] `dlg-openpgp` – OpenPGP-Schlüssel verwalten: offen
- [ ] `dlg-openpgp-schluessel-erzeugen` – OpenPGP: Neues Schlüsselpaar erzeugen (Assistent): offen
- [ ] `dlg-ordner-komprimieren` – Rückfrage „Ordner komprimieren?“ (mit Kästchen und „Weitere Informationen“): offen
- [ ] `dlg-verlauf-loeschen` – Neueste Chronik löschen (nur ansehen): offen
- [ ] `dlg-fehlerbehebung` – Informationen zur Fehlerbehebung (about:support): offen
- [ ] `dlg-import` – Importieren (about:import): offen
- [ ] `dlg-export` – Exportieren: offen
- [ ] `dlg-hinweis` – Hinweis (Services.prompt.alert): offen
- [ ] `dlg-fehler` – Fehlermeldung (Senden fehlgeschlagen, erfunden): offen
- [ ] `dlg-bestaetigung` – Bestätigung (OK/Abbrechen): offen
- [ ] `dlg-drei-knoepfe` – Frage mit drei Knöpfen und Kästchen: offen
- [ ] `dlg-eingabe` – Eingabe (Text): offen
- [ ] `dlg-anmeldung` – Anmeldung (Benutzer und Passwort, leer): offen
- [x] `dlg-abonnieren` – Abonnieren (Newsgruppen/IMAP-Ordner): übersprungen: braucht ein News- oder IMAP-Konto (Netzwerk) – im Testprofil nicht vorhanden
- [ ] `dlg-anhang-oeffnen` – Anhang öffnen: Dialog „Öffnen von …“ (Programmauswahl): offen
- [x] `dlg-dateiauswahl` – Dateiauswahl (Anhängen, Kontaktbild …): übersprungen: nativ: macOS-Dateidialog – nicht gestaltbar
