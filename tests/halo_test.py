#!/usr/bin/env python3
"""Automatischer Test von halo.spaces in einem frischen, temporären Thunderbird-Profil.

Legt ein leeres Profil an (keine Konten, keine echten Daten), installiert das
gebaute Paket, startet Thunderbird mit Marionette und prüft die Stellen, an
denen es früher Rückschritte gab: Listenbreite, Toolbar-Kanten und Kapseln,
Wochenansicht, Schnellfenster, Emojis, Trennlinien (Ziehen/Doppelklick),
Status-Symbol in der Kalenderliste und das Fehlerprotokoll.

Aufruf:  python3 tests/halo_test.py [--xpi dist/…xpi] [--keep] [--dark] [--shots ORDNER] [--tb …]
         (ohne --xpi wird vorher ./build.sh ausgeführt)
Ergebnis: eine Zeile je Prüfung (OK/FEHLER), Rückgabewert 0 nur wenn alles OK ist.
"""

import argparse
import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ADDON_ID = "mail-cards@sebastian.local"
PORT = 2839
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TB = {
    "darwin": "/Applications/Thunderbird.app/Contents/MacOS/thunderbird",
    "win32": r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe",
}.get(sys.platform, "thunderbird")


class Marionette:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port))
        self.id = 0
        self._read()
        self.cmd("WebDriver:NewSession", {"capabilities": {}})
        self.cmd("Marionette:SetContext", {"value": "chrome"})

    def _read(self):
        buf = b""
        while b":" not in buf:
            buf += self.sock.recv(1)
        n, rest = buf.split(b":", 1)
        n = int(n)
        while len(rest) < n:
            rest += self.sock.recv(n - len(rest))
        return json.loads(rest)

    def cmd(self, name, params=None):
        self.id += 1
        data = json.dumps([0, self.id, name, params or {}]).encode()
        self.sock.sendall(str(len(data)).encode() + b":" + data)
        reply = self._read()
        if reply[2]:
            raise RuntimeError(reply[2].get("message", reply[2]))
        return reply[3]

    def js(self, body):
        script = "return (async () => {" + PRELUDE + body + "})();"
        return self.cmd("WebDriver:ExecuteScript", {"script": script, "args": []}).get("value")

    def pointer(self, steps):
        self.cmd("WebDriver:PerformActions", {"actions": [
            {"type": "pointer", "id": "maus", "parameters": {"pointerType": "mouse"}, "actions": steps}]})
        self.cmd("WebDriver:ReleaseActions", {})


# gemeinsame Hilfen für alle Prüfungen (im Chrome-Kontext von Thunderbird)
PRELUDE = r"""
const w = Services.wm.getMostRecentWindow("mail:3pane"); const d = w.document;
const wait = ms => new Promise(r => w.setTimeout(r, ms));
const tm = d.getElementById("tabmail");
const { cal } = ChromeUtils.importESModule("resource:///modules/calendar/calUtils.sys.mjs");
const toMail = async () => { tm.switchToTab(0); await wait(900); return tm.currentAbout3Pane; };
const toCalendar = async () => { tm.openTab("calendar", {}); await wait(1500); };
const testCalendar = () => cal.manager.getCalendars().find(c => c.name == "Halo Test");
const items = async title => { const c = testCalendar(); return (await c.getItemsAsArray(Ci.calICalendar.ITEM_FILTER_ALL_ITEMS, 0, null, null)).filter(i => i.title == title); };
const rect = el => { const r = el.getBoundingClientRect(); return { l: Math.round(r.left), r: Math.round(r.right), w: Math.round(r.width) }; };
"""


def check(name, fn, results):
    try:
        ok, detail = fn()
    except Exception as e:  # Fehler in der Prüfung selbst zählen als Fehlschlag
        ok, detail = False, f"Ausnahme: {e}"
    results.append((name, ok, detail))
    print(f"{'OK     ' if ok else 'FEHLER '} {name}" + (f" – {detail}" if detail else ""), flush=True)


def wait_port(port, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xpi", help="Paket (Standard: neuestes dist/halo-spaces-*.xpi)")
    ap.add_argument("--tb", default=DEFAULT_TB, help="Thunderbird-Programm")
    ap.add_argument("--keep", action="store_true", help="Testprofil nicht löschen")
    ap.add_argument("--dark", action="store_true", help="im Dunkelmodus starten")
    ap.add_argument("--shots", help="Ordner für Screenshots aller Bereiche")
    args = ap.parse_args()

    if not args.xpi:
        # ohne Angabe immer den aktuellen Stand bauen (sonst testet man ein altes Paket)
        built = subprocess.run([os.path.join(ROOT, "build.sh")], capture_output=True, text=True, cwd=ROOT)
        if built.returncode != 0:
            sys.exit("build.sh fehlgeschlagen:\n" + built.stderr)
    xpi = args.xpi or max(glob.glob(os.path.join(ROOT, "dist", "halo-spaces-*.xpi")), key=os.path.getmtime, default=None)
    if not xpi or not os.path.exists(xpi):
        sys.exit("Kein Paket gefunden – zuerst ./build.sh")
    version = json.load(open(os.path.join(ROOT, "extension", "manifest.json")))["version"]

    profile = tempfile.mkdtemp(prefix="halo-test-")
    os.makedirs(os.path.join(profile, "extensions"))
    shutil.copy(xpi, os.path.join(profile, "extensions", f"{ADDON_ID}.xpi"))
    with open(os.path.join(profile, "user.js"), "w") as f:
        for pref, value in {
            "extensions.autoDisableScopes": 0,
            "marionette.port": PORT,
            "mail.shell.checkDefaultClient": False,
            "mail.provider.suppress_dialog_on_startup": True,
            "mail.rights.version": 1,
            "app.update.enabled": False,
            "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
            "toolkit.telemetry.reportingpolicy.firstRun": False,
            "calendar.timezone.useSystemTimezone": True,
            # das macOS-Adressbuch (echte Kontakte) nicht einbinden
            "ldap_2.servers.osx.position": 0,
            **({"ui.systemUsesDarkTheme": 1} if args.dark else {}),
        }.items():
            f.write(f"user_pref({json.dumps(pref)}, {json.dumps(value)});\n")

    print(f"halo.spaces {version} · Paket {os.path.basename(xpi)} · Profil {profile}", flush=True)
    proc = subprocess.Popen([args.tb, "-profile", profile, "-no-remote", "-marionette", "-remote-allow-system-access"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results = []
    try:
        if not wait_port(PORT):
            sys.exit("Thunderbird hat Marionette nicht geöffnet")
        time.sleep(8)  # Erweiterung und Fenster fertig aufbauen lassen
        m = Marionette(PORT)
        run_checks(m, version, profile, results)
        if args.shots:
            take_shots(m, args.shots, "dark" if args.dark else "light")
    finally:
        try:
            Marionette(PORT).js("Services.startup.quit(Ci.nsIAppStartup.eForceQuit); return 1;")
        except Exception:
            pass
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        if not args.keep:
            shutil.rmtree(profile, ignore_errors=True)

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} von {len(results)} Prüfungen OK" + (f", {len(failed)} FEHLER" if failed else ""))
    sys.exit(1 if failed else 0)


def take_shots(m, folder, scheme):
    """Screenshots aller Bereiche (Testprofil, keine echten Daten)."""
    import base64
    os.makedirs(folder, exist_ok=True)
    for name, js in [
        ("mail", "await toMail();"),
        ("calendar-week", 'await toCalendar(); w.switchToView("week"); await wait(800);'),
        ("calendar-month", 'await toCalendar(); w.switchToView("month"); await wait(800);'),
        ("tasks", 'tm.openTab("tasks", {}); await wait(1500);'),
        ("addressbook", 'tm.openTab("addressBookTab", {}); await wait(2000);'),
        ("settings", "w.openPreferencesTab(); await wait(2000);"),
    ]:
        m.js("w.resizeTo(1500, 900); " + js + " await wait(600); return 1;")
        data = m.cmd("WebDriver:TakeScreenshot", {})["value"]
        path = os.path.join(folder, f"{scheme}-{name}.png")
        open(path, "wb").write(base64.b64decode(data))
        print(f"Screenshot {path}", flush=True)


def run_checks(m, version, profile, results):
    # Vorbereitung: Fenstergröße, Testkalender, Fenster ohne Dialoge
    m.js("""
      for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
      w.moveTo(0, 0); w.resizeTo(1500, 900); await wait(500);
      if (!testCalendar()) { const c = cal.manager.createCalendar("storage", Services.io.newURI("moz-storage-calendar://")); c.name = "Halo Test"; c.setProperty("color", "#FF9500"); cal.manager.registerCalendar(c); }
      return 1;""")

    def addon():
        v = m.js("""const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
                    const a = await AddonManager.getAddonByID("%s"); return [a?.version, a?.isActive];""" % ADDON_ID)
        return v == [version, True], f"{v}"
    check("Erweiterung aktiv und richtige Version", addon, results)

    def list_width():
        res = m.js("""
          const out = {};
          for (const width of [1500, 2000, 2600]) { w.resizeTo(width, 900); await wait(1300);
            const a3 = await toMail(); out[width] = Math.round(a3.document.getElementById("threadPane").getBoundingClientRect().width); }
          w.resizeTo(1500, 900); await wait(800); return out;""")
        ok = all(abs(v - 460) <= 1 for v in res.values())
        return ok, f"Listenbreite je Fensterbreite {res} (soll 460)"
    check("Mailliste behält ihre Breite", list_width, results)

    def toolbar_edges():
        res = m.js("""
          const out = [];
          for (const width of [1280, 1500, 2400]) { w.resizeTo(width, 900); await wait(1300);
            const a3 = await toMail(); const off = a3.browsingContext.embedderElement.getBoundingClientRect();
            const row = d.getElementById("unifiedToolbarContainer"); const rl = row.getBoundingClientRect().left;
            const paneRight = Math.round(off.left + a3.document.getElementById("threadPane").getBoundingClientRect().right);
            const lineVar = parseFloat(getComputedStyle(row).getPropertyValue("--mc-list-right"));
            const spacer = d.querySelector('#unifiedToolbarContent > li[item-id="spacer"]').getBoundingClientRect().right;
            const search = Math.round(d.querySelector('#unifiedToolbarContent > li[item-id="search-bar"]').getBoundingClientRect().width);
            out.push({ width, line: Math.round(lineVar + rl) == paneRight || Math.abs(lineVar + rl - paneRight) <= 2, buttonsRightOfList: spacer >= paneRight, search }); }
          w.resizeTo(1500, 900); await wait(800); return out;""")
        ok = all(r["line"] and r["buttonsRightOfList"] and r["search"] >= 159 for r in res)
        return ok, " · ".join(f"{r['width']}px: Linie {'✓' if r['line'] else '✗'}, Knöpfe {'✓' if r['buttonsRightOfList'] else '✗'}, Suche {r['search']}" for r in res)
    check("Toolbar: Trennlinie, Knopfkante, Suchfeld", toolbar_edges, results)

    def capsules():
        res = m.js("""
          w.resizeTo(1280, 900); await wait(1300); await toMail();
          const GROUPS = [["get-messages","write-message"],["reply","reply-all","forward-inline"],["archive","delete","junk"],["move-to"],["mark-as"]];
          const bad = [];
          for (const g of GROUPS) {
            const vis = g.map(id => d.querySelector(`#unifiedToolbarContent > li[item-id="${id}"]`)).filter(li => li && li.getBoundingClientRect().width);
            if (!vis.length) continue;
            if (getComputedStyle(vis[0]).borderStartStartRadius != "999px") bad.push(vis[0].getAttribute("item-id") + " links eckig");
            if (getComputedStyle(vis.at(-1)).borderStartEndRadius != "999px") bad.push(vis.at(-1).getAttribute("item-id") + " rechts eckig");
          }
          w.resizeTo(1500, 900); await wait(800); return bad;""")
        return not res, ", ".join(res) or "alle Gruppen rund"
    check("Toolbar-Kapseln auch mit ausgeblendeten Knöpfen rund", capsules, results)

    def week_fits():
        res = m.js("""
          w.resizeTo(1280, 900); await wait(800); await toCalendar(); w.switchToView("week"); await wait(1200);
          const week = rect(d.getElementById("week-view")); const tab = rect(d.getElementById("tabmail"));
          const cols = d.querySelectorAll("#week-view .day-column-heading").length;
          w.resizeTo(1500, 900); await wait(600); return { week: week.r, tab: tab.r, cols };""")
        return res["week"] <= res["tab"] + 1 and res["cols"] == 7, f"Woche endet bei {res['week']}, Tab bei {res['tab']}, {res['cols']} Tage"
    check("Wochenansicht passt ins Fenster (alle 7 Tage)", week_fits, results)

    def quick_window():
        res = m.js("""
          await toCalendar();
          const li = [...d.querySelectorAll('#unifiedToolbarContent li[item-id="new-event"]')].find(l => l.getBoundingClientRect().width);
          li.querySelector("button").click(); await wait(900);
          const p = d.getElementById("mcQuickPanel"); const t = p.querySelector(".mc-qc-title");
          p.querySelector(".mc-qc-calsel").value = testCalendar().id; p.querySelector(".mc-qc-calsel").dispatchEvent(new w.Event("change"));
          t.value = "Halo Testtermin";
          t.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Enter", isComposing: true, bubbles: true })); await wait(600);
          const afterIme = (await items("Halo Testtermin")).length;
          t.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Enter", bubbles: true })); await wait(1200);
          return { opened: true, afterIme, created: (await items("Halo Testtermin")).length, closed: p.state };""")
        ok = res["afterIme"] == 0 and res["created"] == 1 and res["closed"] == "closed"
        return ok, f"nach IME-Enter {res['afterIme']}, nach Enter {res['created']} Termin, Fenster {res['closed']}"
    check("Schnellfenster: legt an, IME-Enter nicht", quick_window, results)

    def natural():
        res = m.js('''
          await toCalendar();
          const li = [...d.querySelectorAll('#unifiedToolbarContent li[item-id="new-event"]')].find(l => l.getBoundingClientRect().width);
          li.querySelector("button").click(); await wait(900);
          const p = d.getElementById("mcQuickPanel"); const t = p.querySelector(".mc-qc-title");
          p.querySelector(".mc-qc-calsel").value = testCalendar().id; p.querySelector(".mc-qc-calsel").dispatchEvent(new w.Event("change"));
          t.value = "Halo NL Essen morgen 12:30 für 90 min"; t.dispatchEvent(new w.Event("input", { bubbles: true })); await wait(300);
          p.querySelector(".mc-qc-primary").click(); await wait(1200);
          const it = (await items("Halo NL Essen"))[0];
          if (!it) return null;
          const s = cal.dtz.dateTimeToJsDate(it.startDate), e = cal.dtz.dateTimeToJsDate(it.endDate), tm2 = new Date(); tm2.setDate(tm2.getDate() + 1);
          return { tomorrow: s.getDate() == tm2.getDate(), start: s.getHours() * 60 + s.getMinutes(), minutes: (e - s) / 60000 };''')
        ok = bool(res) and res["tomorrow"] and res["start"] == 750 and res["minutes"] == 90
        return ok, f"{res}"
    check("Schnellfenster: natürliche Eingabe („morgen 12:30 für 90 min“)", natural, results)

    def emoji():
        res = m.js("""
          const { CalEvent } = ChromeUtils.importESModule("resource:///modules/CalEvent.sys.mjs");
          const e = new CalEvent(); e.title = "Geburtstag Testperson";
          const s = cal.dtz.now(); s.hour = 9; s.minute = 0; const en = s.clone(); en.hour = 10;
          e.startDate = s; e.endDate = en; await testCalendar().addItem(e);
          await toCalendar(); w.switchToView("week"); await wait(1500);
          const label = [...d.querySelectorAll("#view-box .event-name-label")].find(l => /Geburtstag Testperson/.test(l.textContent));
          const builtin = label?.getAttribute("data-mc-emoji") || null;
          // eigenes Stichwort aus den Einstellungen wirkt sofort und hat Vorrang
          Services.prefs.setStringPref("extensions.mailcards.emojiCustom", "Testperson = ⚽");
          await wait(600);
          const custom = label?.getAttribute("data-mc-emoji") || null;
          Services.prefs.clearUserPref("extensions.mailcards.emojiCustom"); await wait(400);
          return [builtin, custom, label?.getAttribute("data-mc-emoji") || null];""")
        return res == ["🎂", "⚽", "🎂"], f"eingebaut {res[0]}, eigenes Stichwort {res[1]}, wieder {res[2]}"
    check("Emoji vor Termintitel", emoji, results)

    def readstatus():
        res = m.js("""
          await toCalendar(); const c = testCalendar(); c.readOnly = true; await wait(800);
          const li = [...d.querySelectorAll("#calendar-list li")].find(l => /Halo Test/.test(l.textContent));
          const shown = getComputedStyle(li.querySelector(".calendar-readstatus")).opacity;
          c.readOnly = false; await wait(400); const hidden = getComputedStyle(li.querySelector(".calendar-readstatus")).opacity;
          return [shown, hidden];""")
        return float(res[0]) > 0 and float(res[1]) == 0, f"schreibgeschützt {res[0]}, normal {res[1]}"
    check("Kalenderliste zeigt Status bei Schreibschutz", readstatus, results)

    def splitter():
        pos = lambda: m.js("""const a3 = await toMail(); const off = a3.browsingContext.embedderElement.getBoundingClientRect();
          const s = a3.document.getElementById("folderPaneSplitter").getBoundingClientRect();
          return [Math.round(off.left + s.left + s.width / 2), Math.round(off.top + s.top + 300), Math.round(a3.document.getElementById("folderPane").getBoundingClientRect().width)];""")
        x, y, before = pos()
        m.pointer([{"type": "pointerMove", "x": x, "y": y, "origin": "viewport"}, {"type": "pointerDown", "button": 0}]
                  + [{"type": "pointerMove", "x": x + 5 * i, "y": y, "origin": "viewport", "duration": 20} for i in range(1, 9)]
                  + [{"type": "pointerUp", "button": 0}])
        time.sleep(1.2)
        x, y, dragged = pos()
        m.pointer([{"type": "pointerMove", "x": x, "y": y, "origin": "viewport"}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0},
                   {"type": "pause", "duration": 80}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}])
        time.sleep(1.2)
        reset = pos()[2]
        return dragged > before and reset == 206, f"{before} → gezogen {dragged} → Doppelklick {reset} (soll 206)"
    check("Ordnerleiste: Ziehen und Doppelklick", splitter, results)

    def double_click():
        x, y = m.js('''
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          await toCalendar(); w.switchToView("week"); await wait(1200);
          const col = [...d.querySelectorAll("#week-view calendar-event-column")].filter(c => c.getBoundingClientRect().width)[1];
          const lbl = [...d.querySelectorAll("#week-view .multiday-timebar-time")].find(l => /^\s*(14[:.]00|0?2:00\s*PM)\s*$/i.test(l.textContent));
          lbl.scrollIntoView({ block: "center" }); await wait(500);
          const r = col.getBoundingClientRect(); return [Math.round(r.left + r.width / 2), Math.round(lbl.getBoundingClientRect().top + 8)];''')
        time.sleep(1.2)
        m.pointer([{"type": "pointerMove", "x": x, "y": y, "origin": "viewport"}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0},
                   {"type": "pause", "duration": 80}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}])
        time.sleep(1.5)
        res = m.js('''const p = d.getElementById("mcQuickPanel");
          const r = { state: p?.state, line: p?.querySelector(".mc-qc-line1").textContent,
            dialogs: [...Services.wm.getEnumerator(null)].filter(x => /calendar-event-dialog/.test(x.location.href)).length };
          p?.hidePopup(); return r;''')
        ok = res["state"] == "open" and res["dialogs"] == 0 and ("14:" in res["line"] or "02:00 PM" in res["line"] or "2:00 PM" in res["line"])
        return ok, f"Fenster {res['state']}, {res['line']}, große Dialoge {res['dialogs']}"
    check("Doppelklick im Kalender öffnet das Schnellfenster", double_click, results)

    def hover_actions():
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Inbox")) { root.createSubfolder("Inbox", null); await wait(800); }
          const inbox = root.getChildNamed("Inbox"); const lf = inbox.QueryInterface(Ci.nsIMsgLocalMailFolder);
          for (const n of [1, 2]) lf.addMessage(`From - Sat Oct 17 10:00:00 2026\\r\\nFrom: Test ${n} <t${n}@example.invalid>\\r\\nSubject: Halo Karte ${n}\\r\\nDate: Sat, 17 Oct 2026 10:0${n}:00 +0200\\r\\nMessage-ID: <halo-card-${n}@example.invalid>\\r\\n\\r\\nTest\\r\\n`);
          const a3 = await toMail(); a3.displayFolder(inbox.URI); await wait(1500);
          const rows = a3.document.querySelectorAll('#threadTree tr[is="thread-card"]');
          const buttons = rows[0]?.querySelectorAll(".mc-action") || [];
          rows[0].querySelector(".mc-act-flag").click(); await wait(500);
          const flagged = a3.gDBView.getMsgHdrAt(0).isFlagged; const selected = a3.gDBView.selection.count;
          rows[0].querySelector(".mc-act-delete").click(); await wait(1200);
          const trash = root.getFolderWithFlags(Ci.nsMsgFolderFlags.Trash);
          return { buttons: buttons.length, flagged, selected, inbox: inbox.getTotalMessages(false), trash: trash?.getTotalMessages(false) };''')
        ok = res["buttons"] == 3 and res["flagged"] and res["selected"] == 0 and res["inbox"] == 1 and res["trash"] == 1
        return ok, f"{res}"
    check("Mailkarte: Aktionen beim Überfahren (Markieren, Löschen)", hover_actions, results)

    def birthdays():
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const { VCardUtils } = ChromeUtils.importESModule("resource:///modules/VCardUtils.sys.mjs");
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          const card = VCardUtils.vCardToAbCard("BEGIN:VCARD\\r\\nVERSION:4.0\\r\\nFN:Halo Testkontakt\\r\\nBDAY:1990-03-15\\r\\nEND:VCARD\\r\\n");
          book.addCard(card);
          // der Kalender wird 3 s nach der Änderung neu gefüllt
          let c = null;
          for (let i = 0; i < 30 && !c; i++) { await wait(500); c = cal.manager.getCalendarById(Services.prefs.getStringPref("extensions.mailcards.birthdayCalendarId", "")); }
          if (!c) return { calendar: false };
          await wait(800);
          const all = await c.getItemsAsArray(Ci.calICalendar.ITEM_FILTER_ALL_ITEMS, 0, null, null);
          const it = all.find(i => /Halo Testkontakt/.test(i.title));
          return { calendar: true, name: c.name, readOnly: c.readOnly, title: it?.title, yearly: it?.recurrenceInfo?.getRecurrenceItems()[0]?.type, allDay: it?.startDate.isDate };''')
        ok = res.get("calendar") and res.get("readOnly") and res.get("yearly") == "YEARLY" and res.get("allDay") and "Halo Testkontakt" in (res.get("title") or "")
        return ok, f"{res}"
    check("Geburtstage aus dem Adressbuch als Kalender", birthdays, results)

    def keyboard():
        res = m.js('''
          await toMail(); await wait(300);
          const ring = el => { el.focus({ focusVisible: true }); const cs = getComputedStyle(el); const r = cs.outlineStyle != "none" && parseFloat(cs.outlineWidth) >= 2; el.blur(); return r; };
          const own = ["mcSpacesToggle", "mcTodayToggle"].map(id => d.getElementById(id)).filter(Boolean);
          const unlabeled = own.filter(b => !b.getAttribute("aria-label")).map(b => b.id);
          const rings = own.filter(b => !ring(b)).map(b => b.id);
          const a3 = d.getElementById("tabmail").currentAbout3Pane;
          const acts = [...(a3?.document.querySelectorAll(".mc-action") || [])];
          return { own: own.length, unlabeled, noRing: rings, actions: acts.length, tabbable: acts.filter(b => b.tabIndex >= 0).length,
                   actionsLabeled: acts.every(b => b.getAttribute("aria-label")) };''')
        ok = res["own"] == 2 and not res["unlabeled"] and not res["noRing"] and res["tabbable"] == 0 and res["actionsLabeled"]
        return ok, f"{res}"
    check("Tastatur: Fokusring und Beschriftung eigener Knöpfe", keyboard, results)

    def errors():
        res = m.js("""
          const p = PathUtils.join(PathUtils.profileDir, "mail-cards-debug.log");
          let lines = []; try { lines = (await IOUtils.readUTF8(p)).split("\\n"); } catch {}
          return lines.filter(l => /error|fehler/i.test(l) && !/preview stats/.test(l)).slice(0, 5);""")
        return not res, "; ".join(res) or "keine Fehler im Protokoll"
    check("Fehlerprotokoll der Erweiterung leer", errors, results)


if __name__ == "__main__":
    main()
