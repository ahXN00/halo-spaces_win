# Bericht: Design-Durchlauf auf `durchlauf/neon`

Stand 22.10.2026, Mac mini „neon“ (1920×1080 ohne Retina, Region en_US@rg=at),
Thunderbird 158.0 und Thunderbird Beta 159.0, Zweig `durchlauf/neon`, Basis `2853506`.
Nichts gepusht, nichts zusammengeführt.

## Überblick

- **Bereiche:** 13 – Mailliste, Leseansicht, Verfassen, Ordnerliste/Toolbar/Suche,
  Menüs, Kalender/Today-Pane, Aufgaben, Adressbuch, Chat, Einstellungen,
  Kontoeinstellungen, Add-ons, seltene Dialoge.
- **Oberflächen:** 304 im Rundgang (`tests/ui_tour.py`). Im Abschluss-Rundgang
  281 aufgenommen, 23 nicht erreichbar (macOS-Menüleiste und Dateidialog,
  Funktionen, die ein Netzwerkkonto oder einen Schlüssel brauchen, sowie Stellen,
  die halo.spaces bewusst ausblendet). Status je Oberfläche: `tests/fortschritt.md`.
  Alle Oberflächen haben dort einen Status. Offen ist nur `kal-teilnehmer-dialog`.
- **Runden:** Runde 1 (Befunde 0–11, 12–23, 24–…) in allen Bereichen, Runde 2 und 3
  als Nachlese mit neuen Aufnahmen. Mailliste, Leseansicht, Verfassen,
  Ordnerliste und Menüs wurden schon vor dieser Sitzung umgesetzt.
- **Umgesetzte Befunde dieser Sitzung:** 160 (Runde 1: 132, Runde 2: 14, Runde 3: 14), ohne die vorher umgesetzten Bereiche.
  Viele weitere Befunde waren schon erledigt oder Duplikate und sind in der
  Fortschrittsliste mit Grund vermerkt. 3 Befunde aus Runde 3 wurden verworfen
  (siehe unten).
- **Abschluss:** Ein Rückschritt nur in der Beta wurde behoben: Das Suchfeld im
  Add-ons-Manager hatte unter Thunderbird 159 wieder den Toolkit-Rahmen und war
  32 px hoch, weil die Beta die Werte unter neuen Namen liest.

### Testergebnisse (Paket `tests/shots/final2.xpi`, Version 3.2.0)

| Lauf | Port | Ergebnis |
|---|---|---|
| hell (`halo_test.py`) | 2862 | 165 von 165 OK |
| dunkel (`halo_test.py --dark`) | 2863 | 165 von 165 OK |
| Beta 159.0 (`beta.sh`) | 2864 | 165 von 165 OK |

Der erste Beta-Lauf (ohne die Korrektur) hatte zwei Fehler. „Anhänge: markierte Datei
in Akzentfarbe“ war ein Lastfehler: Zwei Rundgänge liefen gleichzeitig, und bei der
Wiederholung war die Prüfung grün. „Add-ons: … Suchfeld als Kapsel“ war ein echter
Fehler und trat bei der Wiederholung erneut auf. Er ist behoben (Commit „Add-ons: …“, Abschluss).
Logs: `tests/shots/final/` (`hell2.log`, `dunkel2.log`, `beta3.log`; erste Läufe `hell.log`,
`dunkel.log`, `beta.log`, `beta2.log`).

### Rundgang vorher/nachher

Vorher: `tests/shots/tour/vorher-mini/` (Ausgangsstand). Nachher:
`tests/shots/tour/nachher-mini/` (Paket `final.xpi`; die Beta-Korrektur ändert
unter Thunderbird 158 nichts). Den Pixelvergleich (Schwelle 40 wie `compare_shots`)
gibt es in `tests/shots/tour/diff-mini/*-diff.png`, geänderte Stellen sind rot: 367 Bilder
geändert, 97 mit anderer Größe, 108 gleich.
Die meisten Änderungen im Hauptfenster haben zwei Ursachen: Die Ordnerliste ist jetzt
206 statt 198 px breit, wodurch alles rechts davon 8 px weiter rechts steht, und Datum
und Uhrzeit sind vom 21. auf den 22.10. gerückt (Termine, „Heute“, Zeitlinie).
Die angesehenen Bilder mit anderer Größe oder großer Abweichung
(Dialoge kürzer durch 28-px-Felder, Termin-Dialog, Schriftart-Liste breiter,
Menüs mit gleichmäßiger Zeilenhöhe, Datumsauswahl, Suchvorschläge, Ordner-
Eigenschaften, Chronik löschen mit Haken, Filterprotokoll, Symbolleiste anpassen)
zeigen nur die beabsichtigten Änderungen. **Rückschritte an nicht absichtlich
geänderten Stellen wurden nicht gefunden.**

## Commits (`git log --reverse 2853506..HEAD`)

Darin sind auch die vorher übernommenen Zusammenführungen von `main` enthalten
(Bugfix-Durchlauf, Mac-mini-Testrechner, Version 3.2.0).

- `81e6823` Tests: Marionette-Port mit --port wählbar, damit mehrere Testläufe gleichzeitig laufen können
- `9abff8d` Tests: Mailkarten-Prüfung (Absender aus Domain) meldet bei fehlender Karte eine Diagnose statt einer Ausnahme
- `8416c8b` Tests: Rundgang durch alle Oberflächen (ui_tour.py) mit erfundenen Testdaten, Screenshots hell und dunkel, Popups und Rückfragen per Fenster-ID nur der Test-PID; Inventar und Fortschrittsliste; halo_test.py mit ausgelagertem Profil-Start und wählbaren Marionette-Fähigkeiten
- `0e9d792` Tests: Rundgang um 30 Oberflächen ergänzt – Mailliste gruppiert nach Sortierung (Karten und Tabelle), Einladung mit iMIP-Leiste und deren Menüs, Leisten für Empfangsbestätigung und Betrugswarnung samt Menü, Panel „Kontakt bearbeiten“, im Verfassen-Fenster Kontextmenüs für Text und Anhang, „Anhänge neu anordnen“, Anhang-Erinnerung, „Bild einfügen“ und „Rechtschreibung prüfen“, im Termin-Dialog Datums-, Uhrzeit- und Kategorienauswahl, Privatsphäre-/Anhängen-Menü und „Erinnerungen anpassen“, im Schnellfenster Datumsauswahl, Auswahlliste und Kalendermenü, Adressbuch als Tabelle mit Spaltenauswahl, Toolbar-Menü „Neues Adressbuch“, Archiv-Optionen, Filterprotokoll und Ordnerwahl für Suchordner; Testmails nur für einzelne Oberflächen werden danach wieder gelöscht; Aufräumen schließt modale Dialoge (neueste zuerst); Fortschrittsliste behält „erledigt“ beim Neuschreiben
- `50dc064` Tests: Rundgang um 22 Oberflächen ergänzt – Schnellfilter mit Suchtext, ohne Treffer (Hinweis auf die Suche in allen Ordnern) und mit Schlagwörtern samt Menü „Beliebig / Alle / Keine“, im Verfassen-Fenster Menüs für Textgröße, Ausrichtung und Smileys, Suchleiste, „Suchen und Ersetzen“, Anker, Kontextmenü und Anpassen-Sheet der Symbolleiste, Vorschlagsliste der Suche außerhalb der Mailansicht, Tooltips an einem Toolbar-Knopf und an einem Termin, Menü „Später erinnern“ im Erinnerungsfenster, LDAP-Verzeichnisse und Junk-Protokoll in den Einstellungen, Zahnrad-Menü im Add-ons-Manager, OpenPGP-Schlüsselassistent, Rückfrage „Ordner komprimieren?“ und der bisher übersprungene Dialog „Öffnen von …“ für Anhänge; Tooltips per echter Zeigerbewegung; Fenster, die dunkel nur als weiße Fläche aufgenommen wurden (auch Filterprotokoll), jetzt per Fenster-ID
- `18bd311` Mailliste: Gruppenköpfe („Heute“, „Gestern“ …) nicht mehr abgeschnitten, als halbfetter Abschnittstitel direkt über der ersten Mail; zugeklappte Konversation zeigt Name und Bild der neuesten Mail und den Ungelesen-Punkt, Thread-Knopf als graue Kapsel ohne Stern und Akzentrahmen; in Gesendet, Entwürfen und Vorlagen Bild und Name des Empfängers (nur der Name, im Mailkopf weiter der Absender); Datum ungelesener Karten nicht mehr fett; Tabelle in 13 px mit Ungelesen-Punkt in Akzentfarbe und ohne Stern vor neuen Mails, ebenso der Punkt in der Zusammenfassung; Schlagwortfarben in Tabelle und Schnellfilter hell und dunkel lesbar; Schnellfilter-Leiste auf der Listenfläche mit Haarlinie und bündig mit den Karten; Layout „klassisch“ und „breit“ mit Haarlinie über der Leseansicht; Konto-Startseite in einer ruhigen Fläche mit grauen Kacheln; Tests dafür
- `56e5fc6` halo.spaces 3.2.0
- `5001150` Tests: Marionette-Port mit --port wählbar, damit mehrere Testläufe gleichzeitig laufen können
- `9191654` Tests: keine SyntaxWarning mehr unter Python 3.12+ (ungültige Escape-Sequenzen in halo_test.py); CI mit actions/checkout und upload-artifact v6 auf Node 24 statt der auslaufenden Node-20-Fassung
- `a060fd2` Leseansicht: langer Absendername im schmalen Mailbereich endet mit „…“ vor Ordner und Uhrzeit, der Kopf bleibt so breit wie der Mailbereich und der Betreff wird nicht mehr abgeschnitten; Einladungsleiste als graue Kapsel mit Text über die ganze Zeile und grauen Knopf-Kapseln darunter statt hellblauer bzw. lila Fläche mit Schatten, Einladungsdetails als Karte mit feiner Linie in der Breite des Lesebereichs, Werte linksbündig; Anhangsleiste und -liste auf der Fläche der Mail mit Haarlinie, markierte Datei abgerundet in Akzentfarbe ohne Rahmen (unfokussiert grau); Suchleiste mit Haarlinie und grauem Suchfeld ohne Rahmen, Optionen brechen bei wenig Platz um statt abgeschnitten zu werden; Panel „Kontakt bearbeiten“ mit neutraler Fläche wie die Tooltips; Mail im eigenen Tab ohne Listenkopf und Seitenleisten-Grau; Uhrzeit und Datum in der Mailliste im Format der Regionaleinstellungen wie im Mailkopf; nur noch eine Linie zwischen Kopf und Mailtext; „Mehr“ bei vielen Empfängern als graue Kapsel in 11 px; Kommas in Cc grau wie in An; Tests dafür
- `f55a962` AGENTS.md: Verweise auf die offizielle Thunderbird-Doku (llms.txt, Markdown-Seiten, MV2-API-Referenz, Experiments, Update-Hinweise, Schemas)
- `df3cbd6` Standardprogramm-Dialog: angehakte Kästchen zeigen wieder den weißen Haken statt nur eines blauen Quadrats (der Dialog sperrt per Content-Security-Policy data:-Bilder, dort jetzt der Haken von Thunderbird selbst); Test dafür
- `08d0e83` Kontaktfotos: Ausschalten auf der Einstellungsseite bleibt dauerhaft aus (kein erneutes Auslesen der macOS-Kontakte, wenn schon eine Fotoliste im Profil liegt), die Einstellungsseite zeigt eingerichtete Fotos wie das Hilfe-Fenster als an; Fotos aus dem lokalen Adressbuch (Datei in <Profil>/Photos) erscheinen in der Mailliste statt Initialen oder Firmenlogo; Tests dafür
- `5e88a8b` Kalender: Monatsansicht mit „+N weitere“ kommt zur Ruhe statt den Text in jedem Bild neu zu setzen und endlos neu zu messen (Dauerlast auf der CPU); Test dafür
- `fe238fd` Absenderbilder: Umleitungen auf Adressen im lokalen Netz werden vor dem Verbinden gesperrt (Logos, Kontaktfotos, Ein-Klick-Abmeldung), öffentliche Umleitungen funktionieren weiter; Zeitlimit und Größengrenze gelten für die ganze Antwort, endlose oder stockende Downloads werden abgebrochen, von der Startseite wird nur der Anfang geladen; Test dafür
- `eeaa254` Schnellfenster: „für 2h“ zählt als Dauer statt als Uhrzeit 02:00 (auch vor der Uhrzeit oder dem Tag); „Freitag morgen 8 Uhr“ ist Freitag 8 Uhr statt morgen; zweistelliges Jahr („1.3.25“) bleibt im angegebenen Jahr 2025 statt 2026; Zeiträume „11-1pm“ ergeben 11–13 Uhr, „9-5“ 9–17 Uhr und „22-2 Uhr“ enden um 2 Uhr am Folgetag; ganztägiger Termin per Doppelklick nach 23 Uhr bleibt am angeklickten Tag; ganztägiges Ende vor dem Beginn wird ein Tag am Beginn; Erinnerung bei einer Aufgabe setzt die Fälligkeit (Ausschalten der Fälligkeit entfernt die Erinnerung) statt beim Anlegen verloren zu gehen; Tests dafür
- `a04b9ea` Erweiterung: Aus-/Einschalten oder Update ohne Neustart lässt keine Reste stehen (Ordnernamen, Reihenfolge und Einrückung der Ordnerliste, Überschrift „Adressbücher“, Erscheinungsbild-Auswahl in den Einstellungen) und gezogene Seitenleistenbreiten werden danach wieder gespeichert; Seitenleisten-Knopf, Today-Pane-Kopf und „+“ (Neuer Termin/Aufgabe) wirken bei mehreren Hauptfenstern im eigenen statt im zuletzt geöffneten Fenster; geschlossene Adressbuch-, Einstellungs- und Nachrichten-Tabs bleiben nicht bis zum Beenden im Speicher; Vorschauen laden weiter, wenn ein Mail-Tab kurz nach dem Anfordern geschlossen wird; Tests dafür
- `dedb37a` Mailkopf: bei eigener Adresse (mehrere Identitäten, kein Kontakt) nur der Name statt „Name <Adresse>“; lange Absender- und Ordnernamen enden mit „…“ vor Ordner und Uhrzeit statt darunter zu laufen; Test dafür
- `ae05e50` Tests: tests/mac-mini-setup.sh prüft einen Mac mini als Testrechner (Ruhezustand, Thunderbird, Python, Bildschirm ab 1600×1000, Bildschirmaufnahme mit Probeaufnahme nur eines eigenen Fensters, automatische Anmeldung, Tailscale, SSH, Hinweis bei MDM-Verwaltung) und richtet ein, was ohne Passwort geht, sonst nennt es Befehl bzw. Ort in den Systemeinstellungen; mit --check nur prüfen, zum Schluss Probelauf mit halo_test.py auf Port 2850; Wächter tests/mac-runner-hook.sh lässt auf dem GitHub-Runner nur Push auf main und Start von Hand zu
- `bc08d37` Tests: macOS-Job auf dem eigenen Mac mini (self-hosted runner, Label halo-mac) testet hell, dunkel und mit der Beta und lädt die Screenshots als Artefakt test-mac hoch; läuft nur bei Push auf main oder von Hand, nie bei Pull-Requests; Linux-Jobs unverändert
- `a260b9c` AGENTS.md: Abschnitt Testrechner (Mac mini); Anleitung tests/MAC-MINI.md mit eigenem Benutzer ohne echte Mails, Tailscale statt Portfreigabe, Runner als LaunchAgent im Testbenutzer samt Sicherheitssperren, Claude Code per SSH aus der Desktop-App, Umzug laufender Zweige per Push oder git bundle und Prüfung des Bildschirms ohne Monitor per SSH
- `bd6cf3f` Adressbuch: Änderungen an Kontakten im Hintergrund (gesammelte Adressen, CardDAV) überschreiben nicht mehr die Kopfzeile über der Mailliste; wiederverwendete Zeilen der Kontaktliste zeigen bei einem nicht ladbaren Foto die eigenen Initialen statt die des vorigen Kontakts; beim Zusammenführen von Dubletten bleibt die Auswahl beim gewählten Kontakt statt auf den Nachbarn zu rutschen (fällt die gewählte Dublette weg, ist der verbliebene Eintrag gewählt); das Absenderbild im Mailkopf bleibt nach einer Adressbuch-Änderung (Stern, CardDAV) statt Thunderbirds einzelnem Buchstaben; Tests dafür
- `02ec518` Verfassen: angehakte Kästchen in Dialogen und Kontoeinstellungen zeigen wieder den Haken; Nachrichtentext dunkel in der Fläche des Fensters statt bläulichem Grau, ohne helle Fuge unter der Formatleiste; Anhänge wie in der Leseansicht auf der Fläche des Fensters mit Haarlinie, markierte Datei abgerundet in Akzentfarbe (unfokussiert grau), Größe ohne blaue Plakette; „Später erinnern“ im Hinweis „Anhang vergessen?“ als Kapsel wie „Anhang hinzufügen“, Leiste ohne violettgrauen Rand; Kontakte-Seitenleiste durchgehend im Seitenleisten-Grau mit Adressbuch-Auswahl als Kapsel und Abstand zum Rand; „Symbolleiste anpassen“ mit ruhiger Palette und gestrichelten Platzhaltern; in Dialogen Eingabefelder 28 px hoch wie die Auswahllisten, Listen mit Haarlinie und runder Auswahl, Reiter als Segment-Kapseln, Trennlinie über OK/Abbrechen als Haarlinie; Rückfragen dunkel neutral statt violettgrau; Testprofil lädt kein veröffentlichtes Update nach; Tests dafür
- `0d00f98` Mailliste: Löschen und Archivieren per Knopf auf der Karte lassen sich mit Cmd+Z rückgängig machen; Mails mit Datum in der Zukunft zeigen das ganze Datum statt nur der Uhrzeit; in den Favoriten behalten Unterordner und Ordner unter den Kontozeilen ihren eigenen Namen statt des Kontonamens; „Auf meinem Mac“ klappt nach einer Suche wieder zu (der eigene Suchordner zählt nicht mehr als Inhalt); umbenannte oder neue Konten bekommen ihren Farbpunkt sofort statt erst nach einem Neustart; Tests dafür
- `5b612eb` Tests: mac-mini-setup.sh zeigt beim Ruhezustand „schläft nie“ statt „nach 0 min“
- `fe05543` Verfassen: „An“, „Cc“ und „Bcc“ auf der Höhe der ersten Empfänger-Pille bzw. des leeren Felds statt 4 px tiefer; umbrochene Pillenzeilen beginnen bündig mit der ersten; Pillen dunkel als helle Kapsel statt dunkler Löcher, Auswahl und Warnfarben unverändert; im schmalen Fenster zeigt die Symbolleiste nur Symbole statt gekürzter Beschriftungen („Se…“), die Formatleiste wird enger gesetzt bzw. bricht um statt rechts abgeschnitten zu werden; Tests dafür
- `812da5f` Tests: mac-mini-setup.sh erkennt beim Probelauf einen schon laufenden Test auf dem tatsächlich benutzten Port (ohne --port 2839 statt 2850) und zeigt bei einem Fehler die letzten Meldungen von Thunderbird; per SSH nennt es für die Bildschirmaufnahme den Weg am Bildschirm des Mac und „SSH-Verbindung neu aufbauen“; Anleitung: Push auf den ausgecheckten Zweig des Mini mit receive.denyCurrentBranch updateInstead
- `ced7a0f` Übersetzungen: Überschrift „Adressbücher“ und Titel der Heute-Leiste erscheinen auch auf Französisch, Spanisch und Italienisch übersetzt statt auf Englisch; das Suchfeld oben zeigt je Bereich seinen Platzhalter („Alle Postfächer durchsuchen“, „Kontakte durchsuchen“, „Aufgaben durchsuchen“, „Einstellungen durchsuchen“) statt immer nur „Suchen“, zu lang endet er mit „…“; der Platzhalter „Suchen“ ist auf Französisch, Spanisch und Italienisch übersetzt, in Sprachen ohne eigene Übersetzung bleibt Thunderbirds eigener Text statt „Search“; Test dafür
- `0e5886a` Tests: MAC-MINI.md hält fest, dass halo_test.py per SSH auf dem Mac mini läuft (alle Prüfungen OK), und warnt vor zwei Testläufen auf demselben Port
- `bfb25a5` Kalender: Geburtstage ohne Jahr aus Apple Kontakte/iCloud (X-APPLE-OMIT-YEAR=1604) erscheinen ohne „Geboren 1604“ und gelten nicht mehr als Jahr 1604; Termine wie „Koordination …“ bekommen kein Arzt-Emoji mehr („Koordinationsmeeting“ jetzt 👥) und „Steuerungsgruppe“ kein Geld-Emoji („Einkommensteuer“ weiterhin 💰); die Mailsuche nach „29.2“ ohne Jahr findet den letzten 29. Februar statt nichts; Tests dafür
- `7500798` Ordnerliste: Ordner mit neuen Mails ohne gelben Funkelstern und mit Namen in Textfarbe statt Blau; Abschnitte einheitlich ohne Linie darüber; die letzte Zeile lässt sich bei ausgeblendeter Bereiche-Leiste über den Bereiche-Knopf hinaus scrollen; „Anpassen…“ der Bereiche-Leiste entfernt (öffnete nicht und sperrte danach das Ein-/Ausblenden), die leere Leiste öffnet kein leeres Menü; beim Anpassen der Toolbar ragen Listenkopf, Today- und Bereiche-Knopf nicht mehr über das Anpassen-Fenster; globale Suche: Suchfeld oben nicht mehr unter dem Seitenleisten-Knopf, Ergebnis-Tab in den Flächen der übrigen Ansichten mit ruhigem grauem Leerhinweis statt großer blauer Lupe, Suchfeld im Tab als graue Kapsel; Vorschlagsliste der Suche wie die übrigen Menüs ohne harten Rand und Blaustich, Adressen grau statt in Linkblau; Tests dafür
- `32e256b` Tests: MAC-MINI.md empfiehlt als Runner-Namen den Tailscale-Namen und erklärt den Unterschied zwischen Name und Label
- `45870f4` Verteiler-Hinweis: „Abmelden“ per Abmelde-Mail (nur mailto-Link oder fehlgeschlagene Ein-Klick-Abmeldung) bereitet die Mail mit der Identität vor, an die die Verteiler-Mail ging, statt mit der Standard-Identität; Test dafür
- `97bcd80` Kontaktfotos: Fotodateien über 2 MB im lokalen Adressbuch (alte Profile mit unverändert kopiertem Kamerafoto) erscheinen nicht mehr oben abgeschnitten, sondern wie zu große Fotos aus dem Netz gar nicht (dann Foto aus macOS-Kontakte, Firmenlogo oder Initialen); Tests: Prüfung dafür, verdecktes Testfenster wird übersprungen statt als Fehler gemeldet, Testkontakt wird auch bei Fehlern entfernt
- `4c4b679` Verteiler-Hinweis: Ein-Klick-Abmeldung (List-Unsubscribe-Post) meldet auch unter Thunderbird 128 ESR direkt ab, statt dort immer auf Abmelde-Mail oder Browser auszuweichen (der Abruf nutzte eine Funktion, die es erst in neueren Thunderbird-Fassungen gibt)
- `68955a2` Schnellfenster: Nachtschichten wie „Schicht 18-7 Uhr“ oder „Dienst 17-7“ enden um 7 Uhr am Folgetag statt um 19 Uhr am selben Tag; „Standup 11-12am“ ist 11–12 Uhr statt bis Mitternacht; „Karfreitag morgen 10 Uhr“ oder „Rosenmontag morgen“ ist wieder morgen statt heute bzw. ohne Datum; „+“ der Today-Pane nach 23 Uhr schlägt wie die Symbolleiste morgen 0 Uhr vor statt 23 Uhr heute; Tests dafür
- `e7c9cc9` Erweiterung: geschlossene Adressbuch-Tabs bleiben auch über Kopfzeile, Kontaktliste und Teiler nicht mehr bis zum Beenden im Speicher (je Öffnen blieben drei Verweise auf das alte Adressbuch zurück); nach dem Update von 3.2.0 ohne Neustart werden gezogene Seitenleistenbreiten sofort wieder gespeichert statt erst nach einem Neustart; Tests dafür
- `607a1ec` Adressbuch: Zusammenführen vieler Dubletten (z. B. nach einem CardDAV-Abgleich mit hunderten doppelten Kontakten) friert das Adressbuch nicht mehr sekundenlang ein, die Liste wird einmal statt je Dublette neu gezeichnet; fällt die gewählte Dublette weg, zeigt die Detailansicht den verbliebenen Eintrag (mit Konto-Etiketten) statt weiter der ausgeblendeten Karte; Test dafür
- `44c8d0b` Tests: Mailkarten-Knopf „Archivieren“ geprüft samt Rückgängig (Cmd+Z); Farbpunkt neuer und umbenannter Konten geprüft; Favoriten-Namensprüfung wartet belegbar auf die Dekoration (verdecktes Testfenster wird übersprungen) und prüft „Alle Eingänge“, statt auch ohne Korrektur zu bestehen
- `7963744` Tests: Suchfeld-Prüfung liest das Adressbuch-Dokument bei jedem Versuch neu und meldet unter Last keinen Fehler mehr, wenn das Adressbuch nach 1,5 s noch lädt
- `96eca9f` Kalender: Termine wie „Steuerkreis Projekt X“, „Steuerkreissitzung“ oder „Steuergruppe“ bekommen kein Geld-Emoji mehr („Einkommensteuer“ und „Steuerunterlagen“ weiterhin 💰); Test dafür
- `334c970` Tests: Abmelde-Mail-Prüfung klickt erst, wenn der Verteiler-Hinweis zur Rundbrief-Mail gehört, statt unter Last den stehengebliebenen Ein-Klick-Knopf der vorigen Mail (offene Rückfrage, Folgefehler in der nächsten Prüfung)
- `841d451` Ordnerliste: Ordnermenüs („Verschieben“, „Kopieren“, „Verschieben nach“) mit denselben Umriss-Symbolen in Akzentfarbe wie Ordnerliste und Toolbar-Knopf statt grau gefüllter Ordner, im markierten Eintrag in der Schrift der Auswahl; Tastenkürzel in Menüs neutral grau statt blaugrau, im markierten Eintrag weiß statt blaugrau auf Blau; globale Suche: Treffer in Systemschrift statt Monospace, Betreff und Personen in Textfarbe statt Linkblau, Auszug klein und grau, Linien zwischen den Treffern als Haarlinie, Schlagwort als Plakette ohne Rand; Tests dafür
- `b9ed897` Menüs: im Kontextmenü der Mailliste und des Mailtexts sind „Archivieren“, „Als Spam markieren“ und „Nachricht löschen“ so hoch wie die übrigen Zeilen statt 2 px niedriger; Schlagwörter im Schlagwort-Menü (Kontextmenü, Toolbar-Knopf, Nachrichtenfenster) samt Häkchen in ihrer Farbe gemischt mit der Textfarbe statt in der reinen Grundfarbe, hell und dunkel lesbar (Kontrast mind. 4,5:1 statt 1,6:1), markiert weiter weiß auf Akzent; Tests dafür
- `43e1546` Kalender: Monatsansicht zeigt unter Thunderbird 159 wieder „+N weitere“ statt die Termine voller Tage unten abzuschneiden, und volle Tage rollen dort nicht mehr selbst (Thunderbird legt die Terminliste jetzt in einen eigenen Rollbereich); Test dafür
- `f971f83` Zusammenführung: Mac-mini-Testrechner (Anleitung, Einrichtungsskript, Runner-Hook) in main übernommen
- `17e4f24` Zusammenführung: Fehlerbehebungen aus dem Bugfix-Durchlauf vom 20.10. (Adressbuch, Kalender, Mailliste, Netz, Tests) in main übernommen
- `21ba46b` Zusammenführung: Design-Durchlauf (Mailliste, Leseansicht, Verfassen, Ordnerliste, Menüs, globale Suche) in main übernommen; langer Absendername kombiniert aus beiden Fassungen, Uhrzeit in der Mailliste im Systemformat und nur für heute
- `946282b` Zwischenstand Design-Durchlauf (abgebrochen beim Umzug auf neon, ungetestet): Terminbeschreibung mit eigenem Stilblatt, weitere Anpassungen in Kalender, Dialogen und Tests
- `6234b2b` Zusammenführung: Zwischenstand des Design-Durchlaufs in main übernommen; Pfeil des Neu-Popovers in der Today-Pane zeigt auf die Mitte des „+“
- `1dbdd33` Today-Pane: Pfeil des „+“-Popovers zeigt auch bei Fenster am rechten Bildschirmrand auf den Knopf (Popover wird nur so weit versetzt, wie Platz ist, statt von Gecko gespiegelt); Tests: Schnellfenster öffnet die Wiederholen-Auswahl per echtem Klick, da showPicker() im Chrome-Dokument nichts öffnet
- `1ca7e60` Verteiler-Hinweis: Ein-Klick-Abmeldung gilt auch dann als erledigt, wenn der Server auf eine Bestätigungsseite (http oder lokal) umleitet, statt zusätzlich Abmelde-Mail oder Browser zu öffnen; Test dafür
- `d2445e9` Schnellfenster: „Party 11-1am“ wird 23–1 Uhr statt eines 14-stündigen Termins ab 11 Uhr; „Meeting morgen für 2h“ wird ein zweistündiger Termin zur vorbelegten Uhrzeit statt ganztägig ohne Dauer; Tests dafür
- `a9dc711` Einstellungen/Adressbuch: Auswahl „Erscheinungsbild“ und Überschrift „Adressbücher“ einer älteren Fassung werden nach einem Update ohne Neustart ersetzt, sodass die Auswahl wieder abgeglichen wird und beim Deaktivieren beides verschwindet; Test dafür
- `9107e43` Ordnerliste: Prüfung, dass „Auf meinem Mac“ trotz Suchordner mit Treffern zuklappt, mit eigenen Mails aber nicht; Test dafür
- `417f774` Kalender: Tagesköpfe der Woche wieder in passender Lang- oder Kurzform („Wed Oct 21“ statt „Wednesday Oct…“), gekürzt mit „…“ nur im schmalen Fenster; Umsetzung der Kalender-Befunde (Tagesköpfe, Ganztags-Termine, Rasterlinien, Schnellfenster, Datumsauswahl, Auswahlliste, „+“-Popover, Termin-Dialog, Druck) geprüft und in der Fortschrittsliste vermerkt; Test dafür
- `c762d7c` Kalender: Titel mehrtägiger Ganztags-Termine in Monat und Mehrwochen läuft über den ganzen Balken statt nach einer Spalte mit „…“ abzubrechen; Termin-Dialog mit Trennlinien als Haarlinie, „Time as: Busy“ mit Abstand und dunkel lesbarer Beschreibung; Rückfrage zu Serienterminen mit ruhigem Titelkasten ohne alte Kalendersymbole; „Erinnerungen anpassen“ mit Liste und Trennern als Haarlinie; gewähltes Segment im Schnellfenster dunkel heller als die Spur; Plakette „Enable“ in der Kalenderliste als graue Kapsel; Tests dafür
- `6547ea9` Kalender: Today-Pane-Tage mit nur einem Eintrag so hoch wie ihre Tagesspalte, sodass „23“ nicht mehr an „SAT“ klebt; Monate der Wiederholungsvorschau mit Haarlinie und 10 px Radius statt Zinkgrau; Tests dafür
- `856000d` Kalender: „Ganztägig“ im Schnellfenster als macOS-Kästchen statt grauem Systemkästchen und Kalendername dicht am Farbpunkt; Wiederholungsdialog mit „Repeat“ mittig zur Liste und 28 px hohen Zahlenfeldern; Statuszeile im Termin-Dialog dunkel ohne verschwommenen Prägeschatten; Kategorie-Farbpunkte mit feinem Ring, sodass helle und dunkle Farben sichtbar bleiben; Tests dafür
- `6c8f874` Aufgaben: Beschreibung im Detailbereich in Systemschrift 13 px ohne Rand und dunkel hell lesbar statt schwarz auf Dunkelgrau; überfällige Aufgaben und „!“ hoher Priorität wieder rot; Spaltenköpfe ohne zweiten harten Strich und ausgewählte Zeile ohne eckiges Fokusrechteck; „Mark Completed“ mit schmalem Pfeil statt leerem Raum; Eingabehinweis bleibt grau nach Wechsel des Standardkalenders; Hinweis „schreibgeschützter Kalender“ endet im schmalen Fenster vor dem Suchfeld; Aufgaben-Fenster mit Feldern, Fläche und Haarlinien wie das Termin-Fenster, Zahlenfeld ohne Pfeile; Zeitkopplung in Termin- und Aufgaben-Fenster als sichtbares Kettensymbol zwischen Beginn und Ende statt leerem Knopf und altem „↵“; Beschreibung in beiden Fenstern schrumpft mit statt unten abgeschnitten; Tests dafür
- `86a778c` Aufgaben: erledigte Aufgaben aufrecht statt kursiv und mit Erledigt-Kreis in der Systemakzentfarbe statt fest Blau; ohne Auswahl keine doppelte Haarlinie über der Statusleiste; Suche ohne Treffer zeigt „No Results“ statt „No Tasks“; Kalenderliste im niedrigen Fenster mindestens drei Zeilen hoch, Monatskalender weicht unter 820 px Fensterhöhe; Test dafür
- `edc543c` Aufgaben: Leeranzeige in den Filtern „Überfällig“ und „Erledigt“ sagt „No tasks in this view.“ statt zu versprechen, dass neue Aufgaben dort erscheinen, und folgt auch einem Filterwechsel über das Menü; Test dafür
- `f4c78ed` Adressbuch: Verteilerliste und Mehrfachauswahl ohne leeren Kreis, Kopf mittig in 28 px, Liste mit Kreis im Initialen-Verlauf und Mitglieder-Kreise im Verlauf statt Thunderbird-Grau; Kontaktkopf auch im breiten Detailbereich mittig; Tabellenansicht mit 96-px-Foto und sichtbaren Datenkarten, „…“ nicht mehr über dem Suchfeld; Links in den Detailkarten in der Akzentfarbe ohne Unterstrich, Überschrift, Bezeichnungen und Werte an einer Kante; Verteilerlisten in der Bücherliste rund ohne Rahmen wie die Buchzeilen; leeres Buch mit kräftigem „New Contact“ statt halb durchsichtig; Bearbeiten-Layout greift auch direkt nach dem Öffnen des Tabs; Kontaktbild-Dialog zeigt Hinweis und Symbol statt leerer Fläche, Ablage als Karte statt Pille; Unterdialoge im Tab dunkel neutral statt Blaugrau; Tests dafür
- `4d9a0e4` Adressbuch: Fenster lässt sich ohne gewählten Kontakt wieder verkleinern statt auf der aktuellen Breite zu sperren; Notiz in 14 px wie die übrigen Werte; Verteilerlisten in der Kontaktliste mit weißem Symbol im Verlaufskreis statt frei stehendem Umriss; Darstellungsmenü mit Trennlinie vor „View“ und ohne Linien innerhalb; „Adressen suchen“ mit Bedingungen und Ergebnissen als Flächen mit Haarlinie und 8 px Radius statt eckigem Rahmen und schwarzer Liste, Teiler als eine Linie; Tests dafür
- `a5b65d1` Adressbuch: gewählte Buch- und Listenzeile mit Fokus akzentgetönt wie die Ordnerliste, Listensymbol in der Akzentfarbe statt Umriss in Textfarbe; Darstellungsmenü der Tabellenansicht ohne leeren Titel „Sort“ und ohne doppelte Linie; neuer Kontakt ohne Namen mit Personen-Silhouette im Verlaufskreis statt Initialen „NC“ aus der Platzhalter-Überschrift; Test dafür
- `1eb29cc` Chat: leere Startseite mit eigenem Info-Symbol in Tertiärgrau, Erklärtext 13 px grau und „Get started“ in voller Akzentfarbe statt 80 % Deckkraft, nach dem Öffnen ohne Dauer-Fokusring (Ring nur per Tastatur); Statuskapsel mit flachem 10-px-Punkt in Grün/Orange/Grau statt glänzender Kugel, Statustext 13 px wie „Add Contact“ und ohne Konto gedimmt wie die übrigen Knöpfe; deaktivierte Knöpfe werden beim Überfahren nicht mehr dunkler; langer Statustext endet nach 160 px mit „…“ statt unter das Suchfeld zu laufen; im schmaleren Fenster rücken die Chat-Knöpfe nach links und die Suche wird kürzer statt sich zu überlagern, die Mindestbreite im Chat berücksichtigt beides; Tests dafür
- `70dd070` Bereiche: Trennlinie der Seitenleiste läuft in der Toolbar-Zeile ohne 1-px-Versatz und ohne Farbsprung weiter (Chat, Kalender, Aufgaben, Adressbuch, Einstellungen); Test dafür
- `78e81d5` Einstellungen: Grundschrift 13 px (Erklärtexte 12 px) und Kategorienamen der Seitenleiste bündig mit „Account Settings“; Zahlenfelder mit Haarlinie statt macOS-Feldrahmen; Schlagwort-, Dateitypen-, Kategorien- und Filelink-Liste sowie Listen in Unterdialogen mit Haarlinie und 8 px statt hartem Rahmen, Tabellenkopf ohne Blaugrau; sicheres DNS als Karte mit ruhigen Optionskästen und sichtbaren Aufklapp-Pfeilen statt leerer grauer Scheiben; „Export for Mobile“ ohne Rahmen und Marineblau, Hinweise 11 px, „Select all“ ohne Versalien; leere Abstandhalter über der ersten Kalender-Karte und unter „Passwords“/„Spam“ entfernt; Offline-Einstellungen mit Optionen untereinander statt dreizeilig umbrochen; Test dafür
- `e752ab3` Einstellungen: Arbeitstage-Kästchen mittig über dem Tag und die Tage mit Abstand; Chat-Vorschau mit Abstand zu „Preview:“, Haarlinie und 8 px Radius, im Dunkelmodus als Standard die dunkle Variante des Stils statt weißer Fläche (eigene Wahl bleibt); Schlagwortnamen hell abgedunkelt und dunkel aufgehellt wie in der Mailliste; „Manage directories…“ und „Edit“ im LDAP-Dialog so hoch und normal wie die übrigen Knöpfe statt im Stil von „Bearbeiten“ im Adressbuch; Update-Chronik mit Abstand des Hinweises zum Listenrand; Port-Felder der Verbindungs-Einstellungen ohne Systempfeile, Wert mittig; im schmalsten Fenster nichts mehr rechts abgeschnitten, Auswahlzeilen in „Verfassen“ und die Sortier-Kacheln brechen um; Test dafür
- `fe7e89b` Einstellungen: Schriftgröße neben der Schriftart kompakt wie bei „Message formatting“ statt gleich breit, die Schriftart bekommt den Platz; Kryptographie-Module mit breiterer linker Liste und ungekürzten Namen, Dialog nicht breiter; Test dafür
- `1b27d59` Kontoeinstellungen: „Add-ons and Themes“ unten links einzeilig (schmal mit „…“) wie in den Einstellungen; Kontoseiten dunkel in Fensterfarbe statt blaustichigem #18181B; große Überschrift mit 12 px Abstand zur ersten Karte statt daraufzukleben, auch auf „Disk Space“; Junk mit 12 statt 48 px zwischen den Karten, Adressbuch-Zeilen 28 statt 40 px und Auswahl grau statt Akzentfläche, sodass ein angehaktes Kästchen sichtbar bleibt; Postausgang-Server mit „Default: 587“ im Abstand zum Port-Feld; Archiv-Beispiel mit Haarlinie und 8 px statt hartem Rahmen; Update-Prüfung im Test am Prozessstart gemessen statt an fester Laufzeit; Test dafür
- `a0ae88c` Kontoeinstellungen: Konto-Assistenten für Feeds, Newsgruppen und Chat mit flachen Knöpfen wie in den Dialogen (grau bzw. in Akzentfarbe, ohne Rahmen, 13 px, 28 px hoch) statt Toolkit-Grau mit Rahmen, dunkel „Cancel“ lesbar statt weiß auf Hellgrau; Felder mit Haarlinie und 7 px statt hartem Rahmen; Chat-Netzliste mit Haarlinie, 8 px und abgerundeter Auswahl statt eckigem Rahmen; Test dafür
- `29f3087` Add-ons: Seitenleiste mit 34-px-Zeilen in 13 px statt übergroßer Proton-Zeilen in zwei Schriftgrößen; Seite, Suchzeile und Überschrift dunkel in Fensterfarbe statt #18181B; Suchfeld als graue Kapsel ohne Rahmen statt hart umrandet mit Doppel-Fokusring; Werkzeug und „…“ im Kartenkopf gleich groß ohne Fläche; Schalter dunkel mit weißem Knopf; Menüs „…“ und Zahnrad wie die halo-Menüs mit 12 px Radius, 22-px-Zeilen und Akzent-Markierung statt blaustichiger Fläche und blauem Rechteckring; Detailansicht mit Haarlinien ohne Doppellinie unter den Reitern; eingebettete Einstellungen ohne eigene Fläche, keine weiße Insel bzw. dunkles Loch in der Karte; Emojis in Info-Fenster und Einstellungen in voller Farbe statt blass; Info-Fenster nicht mehr 3 px scrollbar; Tests dafür
- `4d34045` Fortschritt: Add-ons-Befunde 12–16 (Seitenleiste, eingebettete Einstellungen, Detail-Linien, Werkzeugknopf, blasse Emojis) als schon erledigt vermerkt, keine sichtbare Änderung
- `dbacbc4` Dialoge: Ordnerwahl der Suchordner in der Inhaltsfläche mit Haarlinie und Kästchen im macOS-Stil mit Haken statt schwarzer Fläche (dunkel) und grauer Systemkästchen; Filter- und Junk-Protokoll dunkel ohne weiße Insel, mit Haarlinie und 8 px; Fragezeichen in „Ordner komprimieren?“ in Akzentfarbe statt schwarz; Filterliste, Suchbedingungen und OpenPGP-Schlüsselliste mit Haarlinie und 8 px statt hartem eckigem Rahmen, Suchfelder dort mit Haarlinie; +/− im Suchordner mittig zur Bedingungszeile; Druckvorschau in der Systemakzentfarbe statt Proton-Blau bzw. Türkis; „Gespeicherte Dateien“ bekommt das Design (Kapsel-Knopf, Fensterfarbe statt Navy, Liste mit Haarlinie); „Öffnen von …“ mit flachen Kapseln (Cancel grau, OK in Akzentfarbe) statt nativem eckigem Knopf; Tests dafür
- `71a1b10` Dialoge: Auswahllisten in Bedingungs- und Aktionszeilen (Filter-Editor, Suchordner, Suche) einfach grau wie die übrigen statt doppelt gelegtem Grau bzw. Fensterfarbe mit Verlauf; +/− mit 4 px Lücke statt aneinander; Teiler in „Nachrichten suchen“ als eine Haarlinie statt Doppellinie; Aktivitäten mit „Clear List“ in Abstand zum Fensterrand und Haarlinie statt harter grauer Linie; Test dafür
- `f4a68f4` Dialoge: „Apply filter when:“ im Filter-Editor bündig mit „Filter name:“ und in dessen Größe halbfett statt größer, fett und eingerückt, die Kästchen behalten ihren Einzug; Test dafür
- `45cbbf5` Mailliste: Gruppenköpfe der Tabelle bei „Gruppiert nach Sortierung“ ganz lesbar samt Zählung („Yesterday (1/2)“ statt „Yesterday (1…“) und halbfett wie in der Kartenansicht; Betreff und Vorschau der Mailkarten bündig mit dem Absender statt 3 bzw. 1 px eingerückt, Thread-Knopf ebenso, in jeder Dichte; Tests dafür
- `f01d985` Verfassen: Panel „Anhänge anordnen“ neutral wie die Tooltips (dunkel #2C2C2E) mit Haarlinie statt blaugrauer Fläche mit bläulichem bzw. hartem grauem Rand; Adressvorschläge und Anpassen-Sheet mit Haarlinie statt blauem bzw. hartem grauem Rahmen; Test dafür
- `47d8ee3` Ordnerliste: im neuen Profil 206 px breit wie nach Doppelklick auf den Trenner statt Thunderbirds 198 px, sodass „Local Folders“ neben der Ungelesen-Zahl nicht gekürzt wird; Test dafür
- `5fe918e` Kalender: im aufgeklappten Schnellfenster liegen Uhrzeit und Uhrsymbol bei „Starts“/„Ends“ ganz auf der grauen Zeitkarte statt über deren Kante, die Labelspalte richtet sich nach der Sprache statt fester 96 px und bleibt für alle Zeilen bündig; Test dafür
- `0da0e16` Chat: Statuskapsel links und rechts gleich gepolstert wie „Add Contact“ (ca. 14 px vor dem Punkt und hinter dem Text) statt 9 px links und ca. 23 px rechts; Test dafür
- `5225e97` Einstellungen: unter „Learn more“ bei Secure DNS keine leere Statuskapsel mehr, solange kein DNS-Status gesetzt ist; verschachtelte Unterüberschriften wie „Card view options“ und „Enable DNS over HTTPS using:“ 13 px halbfett wie der Kartentitel statt 14,3 px; OCSP-Beschriftung einzeilig statt Umbruch nach „to“; im Device Manager 8 px Abstand zwischen linker Liste und Detailliste, sodass sich Rahmen und Fokusring nicht berühren; Tests dafür
- `0c8ef0d` Kontoeinstellungen: im Account Hub (Konto einrichten, Neues Adressbuch) wieder Thunderbirds eigene Felder mit 42 statt 26 px Höhe und Beschriftung in der Rahmenkerbe statt frei darüber, ohne zusätzlichen Fokusrahmen; übrige Dialogfelder bleiben 28 px; Test dafür
- `654cdd7` Dialoge: Spaltenköpfe in Filterliste, „Nachrichten suchen“ und OpenPGP-Schlüsselverwaltung mit Haarlinie unten und als Spaltentrenner statt Thunderbirds Systemlinie (dunkel hell leuchtend), erster Kopf ohne Trenner am Listenrand; Test dafür
- `d5e1d44` Mailliste: in „Gruppiert nach Sortierung“ stehen Betreff und Vorschau der Karten unter Heute, Gestern, Letzte 7 Tage … wieder bündig mit dem Absender statt 3 px rechts davon; Test dafür
- `a860428` Verfassen: Adressvorschläge beim Tippen mit neutraler Haarlinie statt bläulichem Rand (die Regel traf bisher nicht das tatsächlich geöffnete, namenlose Panel); Farbfelder für Text- und Hintergrundfarbe mit dezentem Rand und Ring in Fensterfarbe, dunkel kein weißer Fleck aus zwei verschmolzenen Feldern mehr; im Reintext nur noch eine Haarlinie unter dem Betreff statt einer doppelt starken; Tests dafür
- `6d9be4d` Kalender: im Druckfenster „Monat“ und „Jahr“ im Kopf der Minikalender „From“/„To“ ohne eigene graue Feldfläche; in der Rückfrage zum wiederholten Termin steht der Text der Knöpfe „Nur dieses …“/„Alle …“ mittig statt linksbündig; Tests dafür
- `4d15bcf` Aufgaben: in der Kalenderliste ist der Haken eines deaktivierten, aber eingeblendeten Kalenders (z. B. „Home“ mit „Enable“) grau statt weiß und damit auch hell sichtbar; Test dafür
- `a3efebd` Adressbuch: beim Bearbeiten steht der Papierkorb im Knopf „Delete“ mit 6 px Abstand zum Text statt fast daran klebend; in der Bücherliste steht der Name einer Verteilerliste so dicht hinter ihrem Symbol wie die Buchnamen; im leeren Buch ist die rechte Hälfte dunkel in der Fensterfarbe statt blaustichig dunkler; Test dafür
- `f39efd2` Einstellungen: Karte „Advanced settings“ ohne leere graue Fläche, Knopf rechtsbündig unter der letzten Karte; Texte der Ende-zu-Ende-Verschlüsselung 12 px grau wie die Nachbarkarten, ohne zusätzlichen Abstand oben, Trennlinie bei „OpenPGP Keyservers“ als Haarlinie; Rundgang scrollt die Einstellungen in TB 158 wieder; Test dafür
- `cce76fd` Dialoge: in Filterliste, „Nachrichten suchen“ und OpenPGP-Schlüsselverwaltung hat der Spaltenwahl-Knopf rechts im Listenkopf keinen dunkel hell leuchtenden Systemwinkel mehr, sondern einen Haarlinien-Trenner wie die übrigen Köpfe; Import und Export (about:import) dunkel in der Fensterfarbe wie Downloads und Add-ons statt Firefox-Blauschwarz; Tests dafür
- `84630da` Add-ons: Suchfeld „Search addons.thunderbird.net“ auch unter Thunderbird 159 Beta als graue Kapsel (28 px, ohne Rahmen) statt Toolkit-Feld mit Rand und 32 px Höhe, weil die Beta die Werte unter neuen Namen liest
- (dieser Commit) Tests: Bericht und Fortschritt des Design-Durchlaufs

Zusammen 94 Commits.

## Verworfen (Runde 2 und 3)

- **Mailliste:** Schlagwortsymbol der Karten ist dunkel kontrastarm. Das ist ein Duplikat eines schon
  verworfenen Befunds: Die Farbe wählt der Nutzer, das Symbol ist als Etikett erkennbar,
  und ein Eingriff in jedes Schatten-DOM wäre riskant.
- **Leseansicht:** Die Leiste der Empfangsbestätigung ist vierzeilig. Das ist eine bewusste Entscheidung
  (Commit 02cc7d6, Knopf neben dem Text, mit Prüfung). Abgeschnitten ist nichts.
- **Ordnerliste:** Das Panel „Bereiche anpassen“ hat einen Blaustich und einen harten Rand. Nutzer erreichen das Panel
  nicht mehr (Einstiege in Commit 7500798 entfernt), nur der Rundgang öffnet es künstlich.

## Offene Punkte

**Design (noch nicht bewertet oder nicht umgesetzt)**
- `kal-teilnehmer-dialog` (Termin → Teilnehmer einladen): Das Raster hat harte graue Linien
  statt Haarlinien, die Teilnehmerzeilen zeigen alte farbige Thunderbird-Symbole (Person,
  Visitenkarte), und die Legende ist in Toolkit-Optik. Gesehen im Abschluss-Rundgang, in keiner Runde
  bewertet. Kandidat für die nächste Runde.
- Breite HTML-Newsletter auf Lesebreite verkleinern (wie Apple Mail). Das wäre neues Verhalten
  und kommt nur mit Freigabe (aus Runde 1 Leseansicht).
- Optionen der Suchleiste in der Mail ausblenden. Das ist eine Verhaltensänderung und kommt nur mit Freigabe.

**Rundgang-Werkzeug (keine Design-Mängel)**
- `kal-neu-popover`: Der Rundgang nimmt jetzt das ganze Fenster auf (1516×900) statt nur
  des Popovers. Das Popover selbst ist richtig gestaltet.
- `verfassen-*` nach `verfassen-kontakte`: Die Kontakte-Seitenleiste bleibt in den folgenden
  Verfassen-Aufnahmen offen (Thunderbird merkt sich den Zustand). Das erklärt große Abweichungen bei
  `verfassen-speichern-frage`, `-suchleiste`, `-anhang-erinnerung` und `-toolbar-anpassen`.
- `kontext-bereiche-leiste` ist nicht mehr erreichbar. Das ist beabsichtigt (Commit 7500798),
  und der Eintrag im Rundgang könnte als „bewusst ausgeblendet“ markiert werden.

**Tests**
- Die Prüfung „Anhänge: markierte Datei in Akzentfarbe“ fällt unter hoher Last gelegentlich aus,
  weil der Fokus beim Wechsel fehlt. Bei der Wiederholung war sie grün.

## Bitte selbst ansehen

Alle Pfade liegen unter `/Users/neosky.cat/halo-runs/wt-durchlauf/tests/shots/tour/` auf neon:
links `vorher-mini/`, rechts `nachher-mini/`, Abweichungen in `diff-mini/<name>-diff.png`.

| Was | Bild |
|---|---|
| Termin-Dialog: Fenster jetzt 559×663 statt 473×561 px, Beschreibung und Kästchen ganz sichtbar (Ursache der neuen Größe nicht eindeutig zugeordnet) | `hell-kal-termin-dialog.png`, `dunkel-kal-termin-dialog.png`, ebenso `*-aufg-dialog.png` |
| Teilnehmer-Dialog (offener Punkt) | `dunkel-kal-teilnehmer-dialog.png`, `hell-kal-teilnehmer-dialog.png` |
| Filterprotokoll dunkel ohne weiße Insel | `dunkel-dlg-filterprotokoll.png` |
| Symbolleiste anpassen im Verfassen-Fenster | `dunkel-verfassen-toolbar-anpassen.png` |
| Ordner-Eigenschaften: Reiter als Segment, Haken sichtbar | `dunkel-dlg-ordner-eigenschaften.png` |
| Schmales Fenster: Mail jetzt wirklich 1100 px breit, Adressbuch 1294 statt 1488/1496 px | `hell-mail-schmal-1100.png`, `dunkel-ab-schmal-1100.png` |
| Dialoge mit 28-px-Feldern (kürzer) | `hell-verfassen-tabelle.png`, `hell-verfassen-bild.png`, `dunkel-dlg-anmeldung.png` |
| Kalender-Schnellfenster und Datumsauswahl | `hell-kal-schnellfenster.png`, `hell-kal-schnellfenster-datum.png` |
| Feed-/News-/Chat-Assistent | `dunkel-konto-news-assistent.png`, `dunkel-konto-chat-assistent.png` |
| Einstellungen Chat (Vorschau) | `dunkel-einst-chat-1.png` |
| Kontextmenü Mailliste: Archivieren/Spam/Löschen gleich hoch wie die übrigen Zeilen | `hell-kontext-mailliste.png` |
| Suchvorschläge oben | `hell-suche-vorschlaege.png` |
