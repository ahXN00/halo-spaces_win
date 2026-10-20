# Inventar der Oberflächen

Erzeugt mit `python3 tests/ui_tour.py --inventar tests/inventar.md --out tests/shots/tour/vorher`
aus der Tabelle `SURFACES` in `tests/ui_tour.py` und dem Ergebnis des letzten
Rundgangs (hell und dunkel). Bilder: `tests/shots/tour/vorher/<hell|dunkel>-<id>.png`
(gitignored, nur Testprofil mit erfundenen Daten).

Arten: bereich (Hauptansicht/Tab), fenster (eigenes Fenster), dialog, menue, popup
(eigenes Widget, per `screencapture -l` der Test-PID aufgenommen), zustand (Variante
einer Ansicht: Hover, Fokus, schmal, leer …).

## Besonderheiten

- Menüleiste: unter macOS nativ (NSMenu) – weder gestaltbar noch aufnehmbar; Inhalt siehe Einträge `menueleiste-*`.
- Kontextmenüs sind in Thunderbird nicht nativ (`widget.macos.native-context-menus` = false) – sie laufen über `menupopup` und damit über das Menü-CSS von halo.spaces.
- Popups/Panels sind eigene Fenster: Menüs liegen auf Fensterebene 101, Panels (z. B. `mcNewPopup`, `mcQuickPanel`) als titellose Kindfenster auf Ebene 0 – `screencapture -l` liefert dort das Elternfenster mit, der Rundgang schneidet auf das Panel (plus 16 pt Rand) zu.
- Mailkopf: halo.spaces blendet die Symbolleiste im Mailkopf aus – „Mehr“-Menü, Kopf anpassen und deren Kontextmenü sind dadurch nicht erreichbar (Aktionen über Toolbar und Kontextmenü der Liste).
- App-Menü (≡): Knopf in halo.spaces ausgeblendet; der Rundgang öffnet das Menü am Suchfeld.
- Bereiche-Leiste anpassen: `gSpacesToolbar.showCustomize()` verankert das Panel am ausgeblendeten `collapseButton` und geht dann nicht auf (auch über das Kontextmenü der Leiste) – möglicher Fehler, prüfen.
- Bereiche-Knopf (`spacesPinnedButton`) ist in halo.spaces der Seitenleisten-Knopf; sein Menü wird blockiert.
- Kalender: Suchliste „Termine suchen“ (`#bottom-events-box`) ist bewusst ausgeblendet (gibt es bei Apple nicht).
- Toolbar: halo.spaces klappt bei wenig Platz Knöpfe ein (Verschieben, Markieren, Junk …); der Rundgang schließt dafür die Today-Pane und nutzt die volle Bildschirmbreite.
- Adressbuch-, Konto- und Einstellungsdialoge sind meist Unterdialoge im Tab (SubDialog), keine Fenster; neue Konten und Adressbücher öffnen den Account Hub (`<dialog>` im Hauptfenster).
- Mindestbreite: Mit den Testdaten lässt sich das Fenster in der Mailansicht nicht schmaler ziehen als rund 1490 px (min-width von halo.spaces, mit Today-Pane), im Kalender 1136 px – die „schmal“-Zustände zeigen daher die kleinste mögliche Breite.
- Ohne Konto mit Server sind „Abrufen“ (Toolbar, Ordnerliste) deaktiviert – deren Menüs bleiben unerreichbar.
- Druckvorschau und andere Systemzugriffe können macOS-Berechtigungsabfragen auslösen (Systemdialog eines anderen Prozesses, gilt für das ganze Thunderbird-Programm) – nie im Namen des Nutzers beantworten.
- Mails nur für einzelne Oberflächen (Einladung, Empfangsbestätigung, Betrugswarnung) legt der Rundgang mit Message-ID `halo-temp-…` an und löscht sie beim Aufräumen wieder (nur im Testprofil) – die übrigen Bilder behalten dieselbe Liste. Die Knöpfe dieser Leisten werden nie ausgelöst (sie würden antworten).
- Modale Dialoge (z. B. Suchordner) halten die Zeitgeber des Hauptfensters an: zweite Schritte darin laufen über `then=(URL-Teil, JS)` im Dialog selbst, das Aufräumen wartet über den Zeitgeber des Moduls und schließt die neuesten Fenster zuerst.
- Popups der HTML-Felder im Schnellfenster (Datum: `DateTimePickerPanel`, Auswahlliste: `#ContentSelectDropdown`) gehen nur nach `notifyUserGestureActivation()` auf; das Bild `-2` zeigt das Schnellfenster dazu.
- Tooltips (`aHTMLTooltip`, `itemTooltip`) füllen sich nur bei echter Zeigerbewegung: der Rundgang fährt per Marionette über das Element (`hoverAt`, S()-Parameter `after`/`hover`) und nimmt den offenen Tooltip auf.
- Anhang öffnen: ohne gespeicherte Aktion für den Dateityp zeigt Thunderbird nur den Dialog „Öffnen von …“ – der Rundgang prüft das vorher (sonst würde die Datei sofort mit einem Programm geöffnet) und schließt ohne OK.
- Einige Fenster (Filterprotokoll, Junk-Protokoll, „Öffnen von …“, OpenPGP-Assistent) kamen dunkel per `WebDriver:TakeScreenshot` nur als weiße Fläche mit hellem Text heraus, obwohl das Fenster auf dem Bildschirm dunkel ist – sie werden mit `screen=True` per `screencapture -l` (mit Titelleiste) aufgenommen.

## 1. Mailliste (`mailliste`)

CSS/Code: chrome/userChrome.css (Thread-Liste, Karten), extension/api/implementation.js (Karten, Listenkopf)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `mail-karten` | Mailliste als Karten, Posteingang mit ausgewählter Mail | bereich | ja |  |
| `mail-karten-ohne-auswahl` | Posteingang ohne Auswahl (leere Leseansicht) | zustand | ja |  |
| `mail-tabelle` | Mailliste als Tabelle | zustand | ja |  |
| `mail-tabelle-threads` | Tabelle nach Threads gruppiert, Threads aufgeklappt | zustand | ja |  |
| `mail-karten-threads` | Karten nach Threads gruppiert, Thread aufgeklappt | zustand | ja |  |
| `mail-hover` | Karte unter dem Mauszeiger (Hover mit Aktionen) | zustand | ja |  |
| `mail-fokusring` | Tastaturfokus in der Liste (Fokusring) | zustand | ja |  |
| `mail-auswahl-unfokussiert` | Ausgewählte Mail, Fokus in der Ordnerliste (ausgewählt-unfokussiert) | zustand | ja |  |
| `mail-mehrfachauswahl` | Mehrere Mails ausgewählt (Zusammenfassung) | zustand | ja |  |
| `mail-leerer-ordner` | Leerer Ordner | zustand | ja |  |
| `mail-entwuerfe` | Ordner Entwürfe | zustand | ja |  |
| `mail-gesendet` | Ordner Gesendet (Empfänger statt Absender) | zustand | ja |  |
| `mail-alle-posteingaenge` | Alle Posteingänge (Sammelordner) | zustand | ja |  |
| `mail-konto-startseite` | Konto-Startseite (Local Folders ausgewählt) | zustand | ja |  |
| `mail-schmal-1100` | Schmales Fenster (1100 px bzw. kleinste mögliche Breite) | zustand | ja |  |
| `mail-dichte-kompakt` | Dichte „kompakt“ | zustand | ja |  |
| `mail-dichte-gross` | Dichte „Touch“ (groß) | zustand | ja |  |
| `mail-layout-klassisch` | Layout „klassisch“ (Liste oben, Mail unten) | zustand | ja |  |
| `mail-layout-breit` | Layout „breit“ | zustand | ja |  |
| `mail-ohne-leseansicht` | Leseansicht ausgeblendet (nur Liste) | zustand | ja |  |
| `mail-schnellfilter` | Schnellfilter-Leiste offen | zustand | ja |  |
| `mail-schnellfilter-aktiv` | Schnellfilter „Ungelesen“ aktiv | zustand | ja |  |
| `mail-schnellfilter-text` | Schnellfilter mit Suchtext (Zeile „Absender / Empfänger / Betreff / Text“) | zustand | ja |  |
| `mail-schnellfilter-ohne-treffer` | Schnellfilter ohne Treffer: Hinweis „Enter: in allen Ordnern suchen“ | popup | ja | Tooltip #qfb-text-search-upsell (Gloda aktiv, Suchfeld fokussiert) |
| `mail-schnellfilter-schlagwoerter` | Schnellfilter „Schlagwörter“ (Zeile mit Schlagwort-Knöpfen) | zustand | ja |  |
| `mail-schnellfilter-schlagwort-modus` | Schnellfilter „Schlagwörter“: Menü „Beliebig / Alle / Keine“ | popup | ja |  |
| `mail-spaltenauswahl` | Tabelle: Spaltenauswahl (Listen-Spaltenmenü) | popup | ja |  |
| `mail-ansichtsoptionen` | Listenkopf: Ansichtsoptionen (…) | popup | ja |  |
| `mail-ansichtsoptionen-sortieren` | Listenkopf: Ansichtsoptionen → Sortieren nach | popup | ja |  |
| `mail-gruppiert` | Karten gruppiert nach Sortierung (Gruppenköpfe Heute, Gestern, Letzte 7 Tage …) | zustand | ja |  |
| `mail-gruppiert-tabelle` | Tabelle gruppiert nach Sortierung (Gruppenköpfe) | zustand | ja |  |

## 2. Leseansicht und Mailkopf (`lesen`)

CSS/Code: chrome/userChrome.css (Mailkopf, Anhänge, Hinweisleisten), extension/parts.css, extension/plaintext.css

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `lesen-text` | Leseansicht: Textmail mit Cc | bereich | ja |  |
| `lesen-newsletter` | HTML-Newsletter mit Abmelde-Hinweis (List-Unsubscribe) | zustand | ja |  |
| `lesen-thread-anhang` | Antwort im Thread mit einem Anhang | zustand | ja |  |
| `lesen-anhaenge-fremdinhalt` | Mail mit drei Anhängen und blockiertem Bild (Hinweisleiste) | zustand | ja |  |
| `lesen-anhaenge-liste` | Anhangsliste aufgeklappt | zustand | ja |  |
| `lesen-viele-empfaenger` | Mailkopf mit vielen Empfängern | zustand | ja |  |
| `lesen-alle-empfaenger` | Mailkopf: alle Empfänger ausgeklappt | zustand | ja |  |
| `lesen-langer-betreff` | Sehr langer Betreff und Absendername | zustand | ja |  |
| `lesen-junk` | Als Junk markierte Mail (Junk-Leiste) | zustand | ja |  |
| `lesen-entwurf` | Entwurf in der Leseansicht (Bearbeiten-Leiste) | zustand | ja |  |
| `lesen-html-tabelle` | HTML-Mail mit Tabelle | zustand | ja |  |
| `lesen-tab` | Mail im eigenen Tab | bereich | ja |  |
| `lesen-fenster` | Mail im eigenen Fenster | fenster | ja |  |
| `lesen-suchleiste` | Suchleiste in der Mail (Bearbeiten → Suchen) | zustand | ja |  |
| `lesen-quelltext` | Quelltext der Mail | fenster | ja |  |
| `lesen-mehr-menue` | Mailkopf: „Mehr“-Menü | popup | nein | Knopf ausgeblendet: halo.spaces blendet die Symbolleiste im Mailkopf aus (Aktionen über Toolbar und Kontextmenü) |
| `lesen-adresse-popup` | Mailkopf: Menü zur Absenderadresse | popup | ja |  |
| `lesen-kopf-anpassen` | Mailkopf anpassen (Panel) | popup | nein | Knopf ausgeblendet: halo.spaces blendet die Symbolleiste im Mailkopf (und damit „Anpassen“) aus |
| `lesen-anhaenge-speichern` | Anhänge: Menü „Alle speichern“ | popup | ja |  |
| `lesen-fremdinhalt-optionen` | Hinweisleiste: Optionen für entfernte Inhalte | popup | ja |  |
| `lesen-einladung` | Mail mit Kalender-Einladung (iMIP-Leiste: Zusagen, Vielleicht, Absagen, Mehr) | zustand | ja |  |
| `lesen-einladung-zusagen` | Einladung: Menü am Knopf „Zusagen“ | popup | ja |  |
| `lesen-einladung-mehr` | Einladung: Menü „Mehr“ | popup | ja |  |
| `lesen-empfangsbestaetigung` | Hinweisleiste „Absender bittet um Empfangsbestätigung“ | zustand | ja |  |
| `lesen-betrugswarnung` | Hinweisleiste „Diese Nachricht könnte Betrug sein“ | zustand | ja |  |
| `lesen-betrugswarnung-optionen` | Betrugswarnung: Menü am Knopf der Hinweisleiste | popup | ja |  |
| `lesen-kontakt-bearbeiten` | Mailkopf: Panel „Kontakt bearbeiten“ (über das Menü zur Absenderadresse) | popup | ja | Stern-Knopf im Mailkopf ist in halo.spaces ausgeblendet – erreichbar über das Menü zur Absenderadresse |

## 3. Verfassen (`verfassen`)

CSS/Code: chrome/userChrome.css (Verfassen-Fenster, Adresszeilen, Format-Leiste)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `verfassen-html` | Verfassen (HTML) mit Formatleiste | fenster | ja |  |
| `verfassen-text` | Verfassen (reiner Text) | fenster | ja |  |
| `verfassen-antwort` | Antworten (zitierter Text) | fenster | ja |  |
| `verfassen-cc-bcc` | Verfassen mit Cc und vielen Empfängern | fenster | ja |  |
| `verfassen-anhaenge` | Verfassen mit Anhängen | fenster | ja |  |
| `verfassen-kontakte` | Verfassen mit Kontakte-Seitenleiste | fenster | ja |  |
| `verfassen-absender-menue` | Verfassen: Absender-Auswahl | popup | ja |  |
| `verfassen-autovervollstaendigung` | Verfassen: Adress-Vorschläge beim Tippen | popup | ja |  |
| `verfassen-absatz-menue` | Formatleiste: Absatzformat | popup | ja |  |
| `verfassen-schrift-menue` | Formatleiste: Schriftart | popup | ja |  |
| `verfassen-einfuegen-menue` | Formatleiste: Einfügen | popup | ja |  |
| `verfassen-anhang-menue` | Symbolleiste: Anhängen-Menü | popup | ja |  |
| `verfassen-speichern-menue` | Symbolleiste: Speichern-Menü | popup | ja |  |
| `verfassen-rechtschreibung-menue` | Symbolleiste: Rechtschreibung/Sprache | popup | ja |  |
| `verfassen-weitere-felder` | Adressfelder: weitere Felder (…) | popup | ja |  |
| `verfassen-farbe` | Verfassen: Textfarbe wählen | dialog | ja |  |
| `verfassen-link` | Verfassen: Link einfügen | dialog | ja |  |
| `verfassen-tabelle` | Verfassen: Tabelle einfügen | dialog | ja |  |
| `verfassen-speichern-frage` | Verfassen schließen: „Speichern?“-Frage | dialog | ja |  |
| `verfassen-kontext-text` | Kontextmenü im Nachrichtentext (Verfassen) | popup | ja |  |
| `verfassen-kontext-anhang` | Kontextmenü eines Anhangs (Verfassen) | popup | ja |  |
| `verfassen-anhaenge-anordnen` | Panel „Anhänge neu anordnen“ | popup | ja |  |
| `verfassen-anhang-erinnerung` | Hinweisleiste „Anhang vergessen?“ (Schlüsselwort im Text) | zustand | ja |  |
| `verfassen-bild` | Verfassen: Bild einfügen | dialog | ja |  |
| `verfassen-rechtschreibung-dialog` | Verfassen: Rechtschreibung prüfen | dialog | ja |  |
| `verfassen-schriftgroesse-menue` | Formatleiste: Textgröße | popup | ja |  |
| `verfassen-ausrichtung-menue` | Formatleiste: Ausrichtung (mit Symbolen) | popup | ja |  |
| `verfassen-smiley-menue` | Formatleiste: Smileys | popup | ja |  |
| `verfassen-suchleiste` | Verfassen: Suchleiste im Nachrichtentext (Bearbeiten → Suchen) | zustand | ja |  |
| `verfassen-suchen-ersetzen` | Verfassen: Suchen und Ersetzen | dialog | ja |  |
| `verfassen-anker` | Verfassen: Einfügen → Anker | dialog | ja |  |
| `verfassen-toolbar-kontext` | Verfassen: Kontextmenü der Symbolleiste | popup | ja |  |
| `verfassen-toolbar-anpassen` | Verfassen: Symbolleiste anpassen (Sheet) | popup | ja |  |
| `verfassen-verschluesselung` | Verfassen: Verschlüsselungs-Panel | popup | nein | braucht einen OpenPGP-/S/MIME-Schlüssel – im Testprofil nicht vorhanden |

## 4. Ordnerliste, Toolbar, Suche, Bereiche-Leiste (`ordner`)

CSS/Code: chrome/userChrome.css (Ordnerliste, Unified Toolbar, Spaces), implementation.js (Suche, Today-Knopf)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `ordner-mehr-menue` | Ordnerliste: „…“-Menü (Ordner-Modi) | popup | ja |  |
| `ordner-modi` | Ordnerliste mit Modi „Ungelesen“ und „Markiert“ | zustand | ja |  |
| `ordner-kompakt` | Ordnerliste kompakt (ohne Kopf/Abrufen-Knöpfe) | zustand | ja |  |
| `ordner-ausgeblendet` | Ordnerliste ausgeblendet | zustand | ja |  |
| `ordner-abrufen-menue` | Ordnerliste: Abrufen-Knopf (Kontextmenü) | popup | nein | Knopf deaktiviert: kein Konto mit Server im Testprofil |
| `toolbar-verschieben` | Toolbar: „Verschieben“ (Ordnerauswahl) | popup | ja |  |
| `toolbar-markieren` | Toolbar: „Markieren“ | popup | ja |  |
| `toolbar-abrufen` | Toolbar: „Abrufen“ (Kontomenü) | popup | nein | Knopf deaktiviert: kein Konto mit Server im Testprofil |
| `toolbar-anpassen` | Toolbar anpassen | zustand | ja |  |
| `suche-ergebnisse` | Suche oben: Treffer in allen Postfächern | zustand | ja |  |
| `suche-globale-ergebnisse` | Globale Suche (Ergebnis-Tab) | bereich | ja |  |
| `suche-vorschlaege` | Suchfeld oben außerhalb der Mailansicht: Vorschlagsliste (Kalender-Tab) | popup | ja | PopupGlodaAutocomplete; im Mail-Tab ersetzt halo.spaces die Liste durch die eigene Suche |
| `today-pane-zu` | Mail ohne Today-Pane | zustand | ja |  |
| `spaces-eingeklappt` | Bereiche-Leiste eingeklappt | zustand | ja |  |
| `spaces-menue-knopf` | Bereiche-Leiste eingeklappt: Bereiche-Menü | popup | nein | von halo.spaces ersetzt: der Knopf blendet die Seitenleiste ein/aus, das Menü wird blockiert (implementation.js, hookSidebarButton) |
| `spaces-anpassen` | Bereiche-Leiste anpassen (Panel) | popup | ja | showCustomize() verankert das Panel am ausgeblendeten collapseButton – dort geht es nicht auf; der Rundgang öffnet es am Einstellungen-Knopf |
| `appmenu` | App-Menü (≡) | popup | ja | Knopf ≡ ist in halo.spaces ausgeblendet – der Rundgang öffnet das Menü am Suchfeld |
| `appmenu-ansicht` | App-Menü → Ansicht (Unteransicht) | popup | ja | Knopf ≡ ist in halo.spaces ausgeblendet – der Rundgang öffnet das Menü am Suchfeld |

## 5. Menüs und Kontextmenüs (`menues`)

CSS/Code: chrome/userChrome.css (Menüs & Popups); Menüleiste nativ (macOS)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `menueleiste-datei` | Menüleiste: Datei (Neu, Öffnen, Speichern unter, Abrufen für, Offline) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-bearbeiten` | Menüleiste: Bearbeiten (Auswählen, Suchen) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-ansicht` | Menüleiste: Ansicht (Symbolleisten, Layout, Ordner, Dichte, Zoom, Schriftgröße, Today-Pane, Kalender, Aufgaben, Sortieren, Nachrichten, Threads, Kopfzeilen, Nachrichteninhalt) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-gehe` | Menüleiste: Gehe (Weiter, Zurück, Ordner, Zuletzt geschlossene Tabs) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-nachricht` | Menüleiste: Nachricht (Weiterleiten als, Anhänge, Schlagwort, Markieren, Verschieben, Kopieren) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-termine` | Menüleiste: Termine und Aufgaben (Fortschritt, Priorität, Aufgabe verschieben) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-extras` | Menüleiste: Extras (Chat-Status, Entwicklerwerkzeuge) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-fenster` | Menüleiste: Fenster | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `menueleiste-hilfe` | Menüleiste: Hilfe (inkl. „halo.spaces …“) | menue | nein | nativ: macOS-Menüleiste (NSMenu) – weder gestaltbar noch per Fenster-ID aufnehmbar |
| `kontext-mailliste` | Kontextmenü: Mailliste | popup | ja |  |
| `kontext-mailliste-untermenue` | Kontextmenü: Mailliste → Schlagwort | popup | ja |  |
| `kontext-ordnerliste` | Kontextmenü: Ordnerliste | popup | ja |  |
| `kontext-mailtext` | Kontextmenü: Mailtext | popup | ja |  |
| `kontext-mailkopf` | Kontextmenü: Mailkopf (Symbolleiste) | popup | nein | Symbolleiste im Mailkopf von halo.spaces ausgeblendet – kein Ort für dieses Kontextmenü |
| `kontext-anhang` | Kontextmenü: Anhang | popup | ja |  |
| `kontext-tab` | Kontextmenü: Tab | popup | ja |  |
| `kontext-toolbar` | Kontextmenü: Toolbar | popup | ja |  |
| `kontext-bereich` | Kontextmenü: Bereiche-Leiste (Bereich) | popup | ja |  |
| `kontext-bereiche-leiste` | Kontextmenü: Bereiche-Leiste (leere Fläche) | popup | ja |  |
| `kontext-einstellungen-knopf` | Kontextmenü: Einstellungen-Knopf der Bereiche-Leiste | popup | ja |  |
| `kontext-schnellfilter` | Kontextmenü: Schnellfilter-Leiste | popup | ja |  |
| `kontext-verfassen-adresse` | Kontextmenü: Adresse im Verfassen-Fenster | popup | ja |  |
| `tooltip-toolbar` | Tooltip an einem Toolbar-Knopf („Verfassen“) | popup | ja | Standard-Tooltip des Dokuments (title-Attribut, anonymer Inhalt) – nicht #aHTMLTooltip; gemessen: appearance auto, grau, eckig |

## 6. Kalender und Today-Pane (`kalender`)

CSS/Code: chrome/spaces.css (Kalender), implementation.js (Schnellfenster, Today-Pane)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `kal-tag` | Kalender: Tag | bereich | ja |  |
| `kal-woche` | Kalender: Woche | bereich | ja |  |
| `kal-mehrwochen` | Kalender: Mehrere Wochen | bereich | ja |  |
| `kal-monat` | Kalender: Monat | bereich | ja |  |
| `kal-woche-auswahl` | Woche mit ausgewähltem Termin | zustand | ja |  |
| `kal-woche-leer` | Leere Woche | zustand | ja |  |
| `kal-schmal-1100` | Woche im schmalen Fenster (1100 px bzw. kleinste mögliche Breite) | zustand | ja |  |
| `kal-suche` | Kalender: Termine suchen (Liste oben) | zustand | nein | von halo.spaces bewusst ausgeblendet (Suchliste gibt es in Apple Kalender nicht) |
| `kal-today-pane` | Today-Pane in der Mailansicht | zustand | ja |  |
| `kal-schnellfenster` | Kalender: Schnellfenster „Neuer Termin“ | popup | ja |  |
| `kal-schnellfenster-datum` | Schnellfenster: Datumsauswahl (Datumsfeld „Beginn“) | popup | ja | DateTimePickerPanel (datetimepicker.xhtml) – in userChrome.css/spaces.css bisher ohne eigene Regeln |
| `kal-schnellfenster-auswahlliste` | Schnellfenster: aufgeklappte Auswahlliste „Wiederholen“ | popup | ja | Popup #ContentSelectDropdown – dasselbe erscheint für „Vorschauzeilen“ in den halo.spaces-Einstellungen |
| `kal-schnellfenster-kalender` | Schnellfenster: Kalendermenü mit Farbpunkten | popup | ja |  |
| `kal-neu-popover` | Today-Pane: „+“ → Neuer Termin / Neue Aufgabe | popup | ja |  |
| `kal-termin-dialog` | Neuer Termin (Dialog) | fenster | ja |  |
| `kal-termin-bearbeiten` | Termin bearbeiten (Ort, Beschreibung) | fenster | ja |  |
| `kal-termin-erinnerung-menue` | Termin-Dialog: Erinnerung (Auswahl) | popup | ja |  |
| `kal-wiederholung-dialog` | Termin: benutzerdefinierte Wiederholung | dialog | ja |  |
| `kal-teilnehmer-dialog` | Termin: Teilnehmer einladen | dialog | ja |  |
| `kal-termin-datum` | Termin-Dialog: Datumsauswahl (Minimonat im Datumsfeld) | popup | ja |  |
| `kal-termin-uhrzeit` | Termin-Dialog: Uhrzeit-Raster (Stunden und Minuten) | popup | ja |  |
| `kal-termin-kategorien` | Termin-Dialog: Kategorien (Auswahl mit Häkchen) | popup | ja |  |
| `kal-termin-privatsphaere` | Termin-Dialog: Symbolleiste „Privatsphäre“ (Menü) | popup | ja |  |
| `kal-termin-anhang-menue` | Termin-Dialog: Symbolleiste „Anhängen“ (Menü) | popup | ja |  |
| `kal-erinnerung-anpassen` | Termin: Erinnerungen anpassen (Erinnerung → Benutzerdefiniert…) | dialog | ja |  |
| `kal-zusammenfassung` | Termin aus schreibgeschütztem Kalender (Zusammenfassung) | fenster | ja |  |
| `kal-erinnerung` | Erinnerungsfenster (Alarm) | fenster | ja |  |
| `kal-erinnerung-spaeter` | Erinnerungsfenster: Menü „Später erinnern“ (Schlummern für alle) | popup | ja | nur geöffnet, kein Eintrag gewählt; Termin wird danach gelöscht |
| `kal-termin-tooltip` | Kalender: Tooltip eines Termins (Titel, Zeit, Ort, Kalender) | popup | ja |  |
| `kal-eigenschaften` | Kalender-Eigenschaften | dialog | ja |  |
| `kal-neuer-kalender` | Neuer Kalender (Assistent) | dialog | ja |  |
| `kal-wiederholung-frage` | Wiederholten Termin löschen: Nachfrage | dialog | ja |  |
| `kal-druck` | Kalender drucken (Druckvorschau) | zustand | ja |  |
| `kal-kontext-ansicht` | Kontextmenü: Kalenderansicht (leere Stelle) | popup | ja |  |
| `kal-kontext-termin` | Kontextmenü: Termin | popup | ja |  |
| `kal-kontext-kalenderliste` | Kontextmenü: Kalenderliste | popup | ja |  |
| `kal-kontext-today` | Kontextmenü: Termin in der Today-Pane | popup | ja |  |

## 7. Aufgaben (`aufgaben`)

CSS/Code: chrome/spaces.css (Aufgaben)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `aufg-liste` | Aufgaben mit ausgewählter Aufgabe | bereich | ja |  |
| `aufg-ueberfaellig` | Aufgaben: Filter „Überfällig“ | zustand | ja |  |
| `aufg-erledigt` | Aufgaben: Filter „Erledigt“ | zustand | ja |  |
| `aufg-leer` | Aufgaben: keine Treffer (Leeranzeige) | zustand | ja |  |
| `aufg-dialog` | Neue Aufgabe (Dialog) | fenster | ja |  |
| `aufg-bearbeiten` | Aufgabe bearbeiten | fenster | ja |  |
| `aufg-schnellfenster` | Aufgaben: Schnellfenster „Neue Aufgabe“ | popup | ja |  |
| `aufg-kontext` | Kontextmenü: Aufgabe | popup | ja |  |
| `aufg-prioritaet-menue` | Aufgabe: Priorität (Menü) | popup | ja |  |

## 8. Adressbuch (`kontakte`)

CSS/Code: chrome/spaces.css (Adressbuch), implementation.js (Avatare, Bearbeiten)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `ab-kontakt` | Adressbuch: Kontakt ansehen | bereich | ja |  |
| `ab-firma` | Adressbuch: Firma ansehen | zustand | ja |  |
| `ab-langer-name` | Adressbuch: langer Name und Firma | zustand | ja |  |
| `ab-geburtstag` | Adressbuch: Kontakt mit Geburtstag und Notiz | zustand | ja |  |
| `ab-bearbeiten` | Adressbuch: Kontakt bearbeiten | zustand | ja |  |
| `ab-neu` | Adressbuch: neuer Kontakt | zustand | ja |  |
| `ab-foto-dialog` | Adressbuch: Kontaktbild wählen (Dialog) | zustand | ja |  |
| `ab-verteiler` | Adressbuch: Verteilerliste | zustand | ja |  |
| `ab-leeres-buch` | Adressbuch: leeres Buch | zustand | ja |  |
| `ab-suche` | Adressbuch: Suche | zustand | ja |  |
| `ab-mehrfachauswahl` | Adressbuch: mehrere Kontakte ausgewählt | zustand | ja |  |
| `ab-schmal-1100` | Adressbuch im schmalen Fenster (1100 px bzw. kleinste mögliche Breite) | zustand | ja |  |
| `ab-sortieren` | Adressbuch: Listenoptionen (Sortieren) | popup | ja |  |
| `ab-tabelle` | Adressbuch als Tabelle (Listenoptionen → Tabellenansicht) | zustand | ja |  |
| `ab-tabelle-spalten` | Adressbuch-Tabelle: Spaltenauswahl | popup | ja |  |
| `ab-toolbar-neues-buch` | Adressbuch-Toolbar: „Neues Adressbuch“ (Menü) | popup | ja |  |
| `ab-account-hub` | Adressbuch hinzufügen (Account Hub, „+“ in der Bücherliste) | dialog | ja |  |
| `ab-neu-menue` | Adressbuch: „Neues Adressbuch“-Menü (Rechtsklick auf „+“) | popup | ja |  |
| `ab-kontext-kontakt` | Kontextmenü: Kontakt | popup | ja |  |
| `ab-kontext-buch` | Kontextmenü: Adressbuch | popup | ja |  |
| `ab-neue-liste` | Neue Verteilerliste (Unterdialog) | dialog | ja |  |
| `ab-neues-buch` | Neues Adressbuch (Unterdialog) | dialog | ja |  |
| `ab-carddav` | Neues CardDAV-Adressbuch (Unterdialog, ohne Netz) | dialog | ja |  |
| `ab-ldap` | Neues LDAP-Verzeichnis (Unterdialog, ohne Netz) | dialog | ja |  |
| `ab-adressen-suchen` | Adressen suchen (erweiterte Suche) | dialog | ja |  |

## 9. Chat (`chat`)

CSS/Code: chrome/spaces.css (Chat)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `chat-start` | Chat ohne Konto (Startseite) | bereich | ja |  |
| `chat-unterhaltung` | Chat-Unterhaltung, Kontaktliste, Status | bereich | nein | braucht ein Chat-Konto (Netzwerk) – im Testprofil nicht vorhanden |

## 10. Einstellungen (`einstellungen`)

CSS/Code: chrome/spaces.css (Einstellungen, Unterdialoge)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `einst-allgemein-1` | Einstellungen: Allgemein (1/4) | bereich | ja |  |
| `einst-allgemein-2` | Einstellungen: Allgemein (2/4, gescrollt) | bereich | ja |  |
| `einst-allgemein-3` | Einstellungen: Allgemein (3/4, gescrollt) | bereich | ja |  |
| `einst-allgemein-4` | Einstellungen: Allgemein (4/4, gescrollt) | bereich | ja |  |
| `einst-darstellung-1` | Einstellungen: Darstellung (1/2) | bereich | ja |  |
| `einst-darstellung-2` | Einstellungen: Darstellung (2/2, gescrollt) | bereich | ja |  |
| `einst-verfassen-1` | Einstellungen: Verfassen (1/3) | bereich | ja |  |
| `einst-verfassen-2` | Einstellungen: Verfassen (2/3, gescrollt) | bereich | ja |  |
| `einst-verfassen-3` | Einstellungen: Verfassen (3/3, gescrollt) | bereich | ja |  |
| `einst-datenschutz-1` | Einstellungen: Datenschutz & Sicherheit (1/4) | bereich | ja |  |
| `einst-datenschutz-2` | Einstellungen: Datenschutz & Sicherheit (2/4, gescrollt) | bereich | ja |  |
| `einst-datenschutz-3` | Einstellungen: Datenschutz & Sicherheit (3/4, gescrollt) | bereich | ja |  |
| `einst-datenschutz-4` | Einstellungen: Datenschutz & Sicherheit (4/4, gescrollt) | bereich | ja |  |
| `einst-chat-1` | Einstellungen: Chat (1/2) | bereich | ja |  |
| `einst-chat-2` | Einstellungen: Chat (2/2, gescrollt) | bereich | ja |  |
| `einst-kalender-1` | Einstellungen: Kalender (1/3) | bereich | ja |  |
| `einst-kalender-2` | Einstellungen: Kalender (2/3, gescrollt) | bereich | ja |  |
| `einst-kalender-3` | Einstellungen: Kalender (3/3, gescrollt) | bereich | ja |  |
| `einst-qr` | Einstellungen: Export für Mobilgeräte | bereich | ja |  |
| `einst-suche` | Einstellungen: Suche („font“) | zustand | ja |  |
| `einst-menue-darstellung` | Einstellungen: Auswahl Hell/Dunkel (halo.spaces) | popup | ja |  |
| `einst-menue-schrift` | Einstellungen: Auswahlliste Schriftart | popup | ja |  |
| `einst-menue-woche` | Einstellungen: Auswahlliste Wochenbeginn | popup | ja |  |
| `einst-dlg-schriften` | Einstellungen → Schriftarten (erweitert) | dialog | ja |  |
| `einst-dlg-dock` | Einstellungen → Dock-Optionen | dialog | ja |  |
| `einst-dlg-benachrichtigung` | Einstellungen → Benachrichtigung anpassen | dialog | ja |  |
| `einst-dlg-schlagwort` | Einstellungen → Neues Schlagwort | dialog | ja |  |
| `einst-dlg-empfangsbestaetigung` | Einstellungen → Empfangsbestätigungen | dialog | ja |  |
| `einst-dlg-updates` | Einstellungen → Update-Chronik | dialog | ja |  |
| `einst-dlg-verbindung` | Einstellungen → Verbindungs-Einstellungen | dialog | ja |  |
| `einst-dlg-offline` | Einstellungen → Offline-Einstellungen | dialog | ja |  |
| `einst-dlg-sprachen` | Einstellungen → Sprachen | dialog | ja |  |
| `einst-dlg-anhang-erinnerung` | Einstellungen → Anhang-Erinnerung: Schlüsselwörter | dialog | ja |  |
| `einst-dlg-fremdinhalte` | Einstellungen → Ausnahmen für entfernte Inhalte | dialog | ja |  |
| `einst-dlg-cookie-ausnahmen` | Einstellungen → Cookie-Ausnahmen | dialog | ja |  |
| `einst-dlg-cookies` | Einstellungen → Cookies | dialog | ja |  |
| `einst-dlg-passwoerter` | Einstellungen → Gespeicherte Passwörter | dialog | ja |  |
| `einst-dlg-zertifikate` | Einstellungen → Zertifikatverwaltung | dialog | ja |  |
| `einst-dlg-geraete` | Einstellungen → Kryptographie-Module | dialog | ja |  |
| `einst-dlg-kategorie` | Einstellungen → Kalender: Neue Kategorie | dialog | ja |  |
| `einst-dlg-systemintegration` | Einstellungen → Systemintegration (Standardprogramm) | dialog | ja |  |
| `einst-dlg-verzeichnisse` | Einstellungen → Verfassen → LDAP-Verzeichnisse verwalten | dialog | ja | Unterdialog pref-editdirectories.xhtml; der Rundgang hakt „Verzeichnisserver“ nur dafür an |
| `einst-dlg-junk-protokoll` | Einstellungen → Datenschutz → Junk-Protokoll anzeigen | dialog | ja | Fenster junkLog.xhtml; der Rundgang schaltet das Junk-Protokoll nur dafür ein |
| `einst-dlg-hauptpasswort` | Einstellungen → Hauptpasswort ändern | dialog | nein | verlangt vorher eine macOS-Anmeldung (Systempasswort) – bewusst ausgelassen |
| `einst-konfiguration` | Konfiguration bearbeiten (about:config) | bereich | ja |  |

## 11. Kontoeinstellungen und Kontoassistenten (`konten`)

CSS/Code: chrome/spaces.css (Kontoeinstellungen), chrome/userChrome.css (Dialoge)

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `konto-start` | Kontoeinstellungen: Local Folders | bereich | ja |  |
| `konto-server` | Kontoeinstellungen: Server-Einstellungen | bereich | ja |  |
| `konto-kopien` | Kontoeinstellungen: Kopien & Ordner | bereich | ja |  |
| `konto-verfassen` | Kontoeinstellungen: Verfassen & Adressieren | bereich | ja |  |
| `konto-junk` | Kontoeinstellungen: Junk | bereich | ja |  |
| `konto-speicher` | Kontoeinstellungen: Speicherplatz | bereich | ja |  |
| `konto-smtp` | Kontoeinstellungen: Postausgang-Server (SMTP) | bereich | ja |  |
| `konto-hinzufuegen-menue` | Kontoeinstellungen: Konto hinzufügen (Menü) | popup | ja |  |
| `konto-smtp-dialog` | Postausgang-Server hinzufügen (Dialog, ohne Speichern) | dialog | ja |  |
| `konto-archiv-optionen` | Kontoeinstellungen → Kopien & Ordner → Archiv-Optionen (Unterdialog) | dialog | ja |  |
| `konto-einrichten` | E-Mail-Konto einrichten (Account Hub, ohne Netz) | dialog | ja |  |
| `konto-feed-assistent` | Feed-Konto anlegen (Assistent, abgebrochen) | dialog | ja |  |
| `konto-news-assistent` | Newsgruppen-Konto (Assistent, abgebrochen) | dialog | ja |  |
| `konto-chat-assistent` | Chat-Konto (Assistent, abgebrochen) | dialog | ja |  |

## 12. Add-ons und halo.spaces-Fenster (`addons`)

CSS/Code: chrome/spaces.css (about:addons), extension/about/, extension/options/

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `addons-erweiterungen` | Add-ons: Erweiterungen | bereich | ja |  |
| `addons-themes` | Add-ons: Themes | bereich | ja |  |
| `addons-detail` | Add-ons: halo.spaces (Details) | bereich | ja |  |
| `addons-halo-einstellungen` | halo.spaces-Einstellungen (im Add-ons-Manager) | bereich | ja |  |
| `addons-karten-menue` | Add-ons: Menü einer Erweiterung (…) | zustand | ja |  |
| `addons-werkzeuge-menue` | Add-ons: Zahnrad-Menü (Updates, Add-on aus Datei installieren, Tastenkombinationen …) | zustand | ja |  |
| `halo-info` | Hilfe → halo.spaces … (Info-Fenster) | fenster | ja |  |
| `addons-empfehlungen` | Add-ons: Empfehlungen | bereich | nein | lädt Inhalte aus dem Netz (addons.thunderbird.net) – im Testprofil ausgelassen |

## 13. Seltene Dialoge (`dialoge`)

CSS/Code: chrome/userChrome.css (Dialoge, commonDialog), chrome/spaces.css

| id | Titel | Art | erreichbar | Hinweis |
|---|---|---|---|---|
| `dlg-ordner-eigenschaften` | Ordner-Eigenschaften | dialog | ja |  |
| `dlg-ordner-neu` | Neuer Ordner | dialog | ja |  |
| `dlg-ordner-umbenennen` | Ordner umbenennen | dialog | ja |  |
| `dlg-suchordner` | Neuer Suchordner (gespeicherte Suche) | dialog | ja |  |
| `dlg-filterliste` | Nachrichtenfilter (Liste) | fenster | ja |  |
| `dlg-filter-editor` | Filterregeln bearbeiten (Filter-Editor) | dialog | ja |  |
| `dlg-filterprotokoll` | Nachrichtenfilter → Filterprotokoll | fenster | ja | Bild per screencapture -l mit Titelleiste (dunkel lieferte TakeScreenshot nur eine weiße Fläche) |
| `dlg-suchordner-ordnerwahl` | Suchordner → Ordner auswählen (Ordnerliste zum Durchsuchen) | dialog | ja |  |
| `dlg-suche` | Nachrichten suchen (erweiterte Suche) | fenster | ja |  |
| `dlg-lesen-nach-datum` | Nach Datum als gelesen markieren | dialog | ja |  |
| `dlg-schlagwort` | Neues Schlagwort (aus der Mailliste) | dialog | ja |  |
| `dlg-druckvorschau` | Druckvorschau einer Mail | zustand | ja |  |
| `dlg-ueber` | Über Thunderbird | fenster | ja |  |
| `dlg-aktivitaeten` | Aktivitäten | fenster | ja |  |
| `dlg-downloads` | Gespeicherte Dateien (about:downloads) | bereich | ja |  |
| `dlg-openpgp` | OpenPGP-Schlüssel verwalten | fenster | ja |  |
| `dlg-openpgp-schluessel-erzeugen` | OpenPGP: Neues Schlüsselpaar erzeugen (Assistent) | dialog | ja | Test-Identität halo@example.invalid; geschlossen ohne „Schlüssel erzeugen“ |
| `dlg-ordner-komprimieren` | Rückfrage „Ordner komprimieren?“ (mit Kästchen und „Weitere Informationen“) | dialog | ja |  |
| `dlg-verlauf-loeschen` | Neueste Chronik löschen (nur ansehen) | dialog | ja |  |
| `dlg-fehlerbehebung` | Informationen zur Fehlerbehebung (about:support) | bereich | ja |  |
| `dlg-import` | Importieren (about:import) | bereich | ja |  |
| `dlg-export` | Exportieren | bereich | ja |  |
| `dlg-hinweis` | Hinweis (Services.prompt.alert) | dialog | ja |  |
| `dlg-fehler` | Fehlermeldung (Senden fehlgeschlagen, erfunden) | dialog | ja |  |
| `dlg-bestaetigung` | Bestätigung (OK/Abbrechen) | dialog | ja |  |
| `dlg-drei-knoepfe` | Frage mit drei Knöpfen und Kästchen | dialog | ja |  |
| `dlg-eingabe` | Eingabe (Text) | dialog | ja |  |
| `dlg-anmeldung` | Anmeldung (Benutzer und Passwort, leer) | dialog | ja |  |
| `dlg-abonnieren` | Abonnieren (Newsgruppen/IMAP-Ordner) | dialog | nein | braucht ein News- oder IMAP-Konto (Netzwerk) – im Testprofil nicht vorhanden |
| `dlg-anhang-oeffnen` | Anhang öffnen: Dialog „Öffnen von …“ (Programmauswahl) | dialog | ja | Fenster unknownContentType.xhtml; nur angesehen, nie OK – kein PDF (öffnet intern im Tab) |
| `dlg-dateiauswahl` | Dateiauswahl (Anhängen, Kontaktbild …) | dialog | nein | nativ: macOS-Dateidialog – nicht gestaltbar |

Gesamt: 304 Oberflächen, davon 282 mit Bild.
