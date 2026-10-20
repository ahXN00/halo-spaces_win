# Fortschritt der Design-Durchsicht

Zu Beginn jeder Runde lesen. Status je Oberfläche: `offen`, `erledigt` (mit Commit)
oder `übersprungen: Grund`. Reihenfolge = Priorität (siehe tests/inventar.md).

Vorher-Bilder: `tests/shots/tour/vorher/` (hell-*/dunkel-*), Paket `tests/shots/review-r1.xpi`.

## 1. Mailliste (`mailliste`)

- [ ] `mail-karten` – Mailliste als Karten, Posteingang mit ausgewählter Mail: offen
- [ ] `mail-karten-ohne-auswahl` – Posteingang ohne Auswahl (leere Leseansicht): offen
- [ ] `mail-tabelle` – Mailliste als Tabelle: offen
- [ ] `mail-tabelle-threads` – Tabelle nach Threads gruppiert, Threads aufgeklappt: offen
- [ ] `mail-karten-threads` – Karten nach Threads gruppiert, Thread aufgeklappt: offen
- [ ] `mail-hover` – Karte unter dem Mauszeiger (Hover mit Aktionen): offen
- [ ] `mail-fokusring` – Tastaturfokus in der Liste (Fokusring): offen
- [ ] `mail-auswahl-unfokussiert` – Ausgewählte Mail, Fokus in der Ordnerliste (ausgewählt-unfokussiert): offen
- [ ] `mail-mehrfachauswahl` – Mehrere Mails ausgewählt (Zusammenfassung): offen
- [ ] `mail-leerer-ordner` – Leerer Ordner: offen
- [ ] `mail-entwuerfe` – Ordner Entwürfe: offen
- [ ] `mail-gesendet` – Ordner Gesendet (Empfänger statt Absender): offen
- [ ] `mail-alle-posteingaenge` – Alle Posteingänge (Sammelordner): offen
- [ ] `mail-konto-startseite` – Konto-Startseite (Local Folders ausgewählt): offen
- [ ] `mail-schmal-1100` – Schmales Fenster (1100 px bzw. kleinste mögliche Breite): offen
- [ ] `mail-dichte-kompakt` – Dichte „kompakt“: offen
- [ ] `mail-dichte-gross` – Dichte „Touch“ (groß): offen
- [ ] `mail-layout-klassisch` – Layout „klassisch“ (Liste oben, Mail unten): offen
- [ ] `mail-layout-breit` – Layout „breit“: offen
- [ ] `mail-ohne-leseansicht` – Leseansicht ausgeblendet (nur Liste): offen
- [ ] `mail-schnellfilter` – Schnellfilter-Leiste offen: offen
- [ ] `mail-schnellfilter-aktiv` – Schnellfilter „Ungelesen“ aktiv: offen
- [ ] `mail-schnellfilter-text` – Schnellfilter mit Suchtext (Zeile „Absender / Empfänger / Betreff / Text“): offen
- [ ] `mail-schnellfilter-ohne-treffer` – Schnellfilter ohne Treffer: Hinweis „Enter: in allen Ordnern suchen“: offen
- [ ] `mail-schnellfilter-schlagwoerter` – Schnellfilter „Schlagwörter“ (Zeile mit Schlagwort-Knöpfen): offen
- [ ] `mail-schnellfilter-schlagwort-modus` – Schnellfilter „Schlagwörter“: Menü „Beliebig / Alle / Keine“: offen
- [ ] `mail-spaltenauswahl` – Tabelle: Spaltenauswahl (Listen-Spaltenmenü): offen
- [ ] `mail-ansichtsoptionen` – Listenkopf: Ansichtsoptionen (…): offen
- [ ] `mail-ansichtsoptionen-sortieren` – Listenkopf: Ansichtsoptionen → Sortieren nach: offen
- [ ] `mail-gruppiert` – Karten gruppiert nach Sortierung (Gruppenköpfe Heute, Gestern, Letzte 7 Tage …): offen
- [ ] `mail-gruppiert-tabelle` – Tabelle gruppiert nach Sortierung (Gruppenköpfe): offen

## 2. Leseansicht und Mailkopf (`lesen`)

- [ ] `lesen-text` – Leseansicht: Textmail mit Cc: offen
- [ ] `lesen-newsletter` – HTML-Newsletter mit Abmelde-Hinweis (List-Unsubscribe): offen
- [ ] `lesen-thread-anhang` – Antwort im Thread mit einem Anhang: offen
- [ ] `lesen-anhaenge-fremdinhalt` – Mail mit drei Anhängen und blockiertem Bild (Hinweisleiste): offen
- [ ] `lesen-anhaenge-liste` – Anhangsliste aufgeklappt: offen
- [ ] `lesen-viele-empfaenger` – Mailkopf mit vielen Empfängern: offen
- [ ] `lesen-alle-empfaenger` – Mailkopf: alle Empfänger ausgeklappt: offen
- [ ] `lesen-langer-betreff` – Sehr langer Betreff und Absendername: offen
- [ ] `lesen-junk` – Als Junk markierte Mail (Junk-Leiste): offen
- [ ] `lesen-entwurf` – Entwurf in der Leseansicht (Bearbeiten-Leiste): offen
- [ ] `lesen-html-tabelle` – HTML-Mail mit Tabelle: offen
- [ ] `lesen-tab` – Mail im eigenen Tab: offen
- [ ] `lesen-fenster` – Mail im eigenen Fenster: offen
- [ ] `lesen-suchleiste` – Suchleiste in der Mail (Bearbeiten → Suchen): offen
- [ ] `lesen-quelltext` – Quelltext der Mail: offen
- [x] `lesen-mehr-menue` – Mailkopf: „Mehr“-Menü: übersprungen: nicht erreichbar – Knopf ausgeblendet: halo.spaces blendet die Symbolleiste im Mailkopf aus (Aktionen über Toolbar und Kontextmenü)
- [ ] `lesen-adresse-popup` – Mailkopf: Menü zur Absenderadresse: offen
- [x] `lesen-kopf-anpassen` – Mailkopf anpassen (Panel): übersprungen: nicht erreichbar – Knopf ausgeblendet: halo.spaces blendet die Symbolleiste im Mailkopf (und damit „Anpassen“) aus
- [ ] `lesen-anhaenge-speichern` – Anhänge: Menü „Alle speichern“: offen
- [ ] `lesen-fremdinhalt-optionen` – Hinweisleiste: Optionen für entfernte Inhalte: offen
- [ ] `lesen-einladung` – Mail mit Kalender-Einladung (iMIP-Leiste: Zusagen, Vielleicht, Absagen, Mehr): offen
- [ ] `lesen-einladung-zusagen` – Einladung: Menü am Knopf „Zusagen“: offen
- [ ] `lesen-einladung-mehr` – Einladung: Menü „Mehr“: offen
- [ ] `lesen-empfangsbestaetigung` – Hinweisleiste „Absender bittet um Empfangsbestätigung“: offen
- [ ] `lesen-betrugswarnung` – Hinweisleiste „Diese Nachricht könnte Betrug sein“: offen
- [ ] `lesen-betrugswarnung-optionen` – Betrugswarnung: Menü am Knopf der Hinweisleiste: offen
- [ ] `lesen-kontakt-bearbeiten` – Mailkopf: Panel „Kontakt bearbeiten“ (über das Menü zur Absenderadresse): offen

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
