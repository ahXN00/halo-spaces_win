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
import re
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
    def __init__(self, port, capabilities=None):
        self.sock = socket.create_connection(("127.0.0.1", port))
        # nie endlos warten: ein Befehl darf höchstens 11 Minuten dauern (--perf)
        self.sock.settimeout(660)
        self.id = 0
        self._read()
        self.cmd("WebDriver:NewSession", {"capabilities": capabilities or {}})
        self.cmd("Marionette:SetContext", {"value": "chrome"})

    def _recv(self, n):
        chunk = self.sock.recv(n)
        if not chunk:  # Thunderbird hat die Verbindung geschlossen (beendet/abgestürzt)
            raise ConnectionError("Marionette-Verbindung geschlossen")
        return chunk

    def _read(self):
        buf = b""
        while b":" not in buf:
            buf += self._recv(1)
        n, rest = buf.split(b":", 1)
        n = int(n)
        while len(rest) < n:
            rest += self._recv(n - len(rest))
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
// wartet, bis fn() etwas liefert (statt fester Wartezeiten – bei hoher Last zuverlässiger)
const until = async (fn, ms = 6000) => { for (let t = 0; t < ms; t += 100) { const v = fn(); if (v) return v; await wait(100); } return fn(); };
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


def local_https(host):
    """Lokaler HTTPS-Server (selbst signiert, für host) für die Netzprüfung der
    Absenderbilder, dazu ein „Gerät im lokalen Netz“ (http auf 127.0.0.1), das
    jeden Zugriff mitschreibt. Liefert Port, Zertifikat (DER, Base64), die
    Zugriffe aufs Gerät, die empfangenen POSTs und eine Funktion zum Beenden."""
    import base64
    import http.server
    import ssl
    import threading
    tmp = tempfile.mkdtemp(prefix="halo-netz-")
    key, crt = os.path.join(tmp, "key.pem"), os.path.join(tmp, "cert.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt, "-days", "2",
                    "-subj", f"/CN={host}", "-addext", f"subjectAltName=DNS:{host}",
                    "-addext", "basicConstraints=critical,CA:FALSE"], check=True, capture_output=True)
    hits, posts, stop = [], [], threading.Event()

    class Device(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    class Sender(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/umleitung":  # Absender leitet auf ein Gerät im lokalen Netz um
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{device.server_port}/geraet")
                self.end_headers()
            elif self.path == "/weiter":  # Umleitung auf eine öffentliche Adresse bleibt erlaubt
                self.send_response(302)
                self.send_header("Location", f"https://{host}:{server.server_port}/ziel")
                self.end_headers()
            elif self.path == "/ziel":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<head></head>Grüße".encode())
            elif self.path == "/anmelden":  # wie iCloud-Fotos: 401 ohne Anmeldedialog
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Halo"')
                self.end_headers()
            elif self.path == "/endlos":  # Daten ohne Ende (höchstens 20 MB)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                try:
                    for _ in range(320):
                        self.wfile.write(b"x" * 65536)
                except OSError:
                    pass
            elif self.path == "/stumm":  # nach den Kopfzeilen kommt nichts mehr
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(b"x" * 10)
                self.wfile.flush()
                stop.wait(30)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            posts.append(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode())
            if self.path == "/abmelden-umleitung":  # Abmeldung leitet auf eine Bestätigungsseite im lokalen Netz um
                self.send_response(303)
                self.send_header("Location", f"http://127.0.0.1:{device.server_port}/bestaetigt")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    device = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Device)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sender)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    for s in (device, server):
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
    der = base64.b64encode(ssl.PEM_cert_to_DER_cert(open(crt).read())).decode()

    def close():
        stop.set()
        for s in (device, server):
            s.shutdown()
            s.server_close()
        shutil.rmtree(tmp, ignore_errors=True)
    return server.server_port, der, hits, posts, close


def create_profile(xpi, port, dark=False, prefix="halo-test-"):
    """Legt ein leeres, temporäres Profil mit installiertem Paket an (keine Konten, keine echten Daten)."""
    profile = tempfile.mkdtemp(prefix=prefix)
    os.makedirs(os.path.join(profile, "extensions"))
    shutil.copy(xpi, os.path.join(profile, "extensions", f"{ADDON_ID}.xpi"))
    with open(os.path.join(profile, "user.js"), "w") as f:
        for pref, value in {
            "extensions.autoDisableScopes": 0,
            "marionette.port": port,
            "mail.shell.checkDefaultClient": False,
            "mail.provider.suppress_dialog_on_startup": True,
            "mail.rights.version": 1,
            "app.update.enabled": False,
            "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
            "toolkit.telemetry.reportingpolicy.firstRun": False,
            "calendar.timezone.useSystemTimezone": True,
            # Zeitgeber im Hintergrund nicht drosseln
            "widget.windows.window_occlusion_tracking.enabled": False,
            "dom.timeout.enable_budget_timer_throttling": False,
            "dom.min_background_timeout_value": 4,
            # das macOS-Adressbuch (echte Kontakte) nicht einbinden
            "ldap_2.servers.osx.position": 0,
            **({"ui.systemUsesDarkTheme": 1} if dark else {}),
        }.items():
            f.write(f"user_pref({json.dumps(pref)}, {json.dumps(value)});\n")
    return profile


def start_thunderbird(tb, profile, log=None):
    """Startet Thunderbird mit Marionette im angegebenen Profil."""
    out = open(log, "w") if log else subprocess.DEVNULL
    return subprocess.Popen([tb, "-profile", profile, "-no-remote", "-marionette", "-remote-allow-system-access"],
                            stdout=out, stderr=subprocess.STDOUT if log else subprocess.DEVNULL,
                            # ab Thunderbird 159 zusätzlich als Umgebungsvariable nötig
                            env={**os.environ, "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS": "1"})


def stop_thunderbird(port, proc):
    """Beendet das Test-Thunderbird (nur den selbst gestarteten Prozess)."""
    try:
        Marionette(port).js("Services.startup.quit(Ci.nsIAppStartup.eForceQuit); return 1;")
    except Exception:
        pass
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xpi", help="Paket (Standard: neuestes dist/halo-spaces-*.xpi)")
    ap.add_argument("--tb", default=DEFAULT_TB, help="Thunderbird-Programm")
    ap.add_argument("--keep", action="store_true", help="Testprofil nicht löschen")
    ap.add_argument("--tb-log", help="Ausgabe von Thunderbird in diese Datei schreiben (zur Fehlersuche)")
    ap.add_argument("--dark", action="store_true", help="im Dunkelmodus starten")
    ap.add_argument("--shots", help="Ordner für Screenshots aller Bereiche")
    ap.add_argument("--eval", help="nur dieses JavaScript ausführen (Chrome-Kontext, mit den Hilfen aus PRELUDE) und das Ergebnis ausgeben – zum Untersuchen")
    ap.add_argument("--perf", action="store_true", help="nur die Geschwindigkeit messen (5000 Mails, mit und ohne halo.spaces)")
    ap.add_argument("--port", type=int, default=PORT, help=f"Marionette-Port (Standard {PORT}; eigener Port erlaubt mehrere Testläufe gleichzeitig)")
    ap.add_argument("--compare", help="Ordner mit früheren Screenshots: zeigt, wo sich etwas verändert hat (braucht --shots)")
    args = ap.parse_args()

    if not args.xpi:
        # ohne Angabe immer den aktuellen Stand bauen (sonst testet man ein altes Paket)
        built = subprocess.run([os.path.join(ROOT, "build.sh")], capture_output=True, text=True, cwd=ROOT)
        if built.returncode != 0:
            sys.exit("build.sh fehlgeschlagen:\n" + built.stderr)
    xpi = args.xpi or max((x for x in glob.glob(os.path.join(ROOT, "dist", "halo-spaces-*.xpi")) if not x.endswith("-atn.xpi")),
                           key=os.path.getmtime, default=None)  # nicht die Store-Variante (ohne update_url)
    if not xpi or not os.path.exists(xpi):
        sys.exit("Kein Paket gefunden – zuerst ./build.sh")
    version = json.load(open(os.path.join(ROOT, "extension", "manifest.json")))["version"]

    profile = create_profile(xpi, args.port, args.dark)
    print(f"halo.spaces {version} · Paket {os.path.basename(xpi)} · Profil {profile}", flush=True)
    proc = start_thunderbird(args.tb, profile, args.tb_log)
    results = []
    try:
        if not wait_port(args.port):
            sys.exit("Thunderbird hat Marionette nicht geöffnet")
        time.sleep(8)  # Erweiterung und Fenster fertig aufbauen lassen
        m = Marionette(args.port)
        if args.perf:
            args.eval = open(os.path.join(ROOT, "tests", "perf.js")).read()
        if args.eval:
            m.cmd("WebDriver:SetTimeouts", {"script": 600000})
            print(json.dumps(m.js(args.eval), indent=1, ensure_ascii=False))
            return
        run_checks(m, version, profile, results)
        if args.shots:
            take_shots(m, args.shots, "dark" if args.dark else "light")
            if args.compare:
                compare_shots(m, args.compare, args.shots)
    finally:
        stop_thunderbird(args.port, proc)
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
        ("message", MESSAGE_JS),
        ("message-remote", """const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs"); await toMail(); const f = MailServices.accounts.localFoldersServer.rootFolder.getChildNamed("Schrift");
          const a3 = tm.currentAbout3Pane; a3.displayFolder(f.URI); await wait(800);
          for (let i = 0; i < a3.gDBView.rowCount; i++) if (a3.gDBView.getMsgHdrAt(i).subject == "Schrift 1") a3.threadTree.selectedIndex = i;
          await wait(6000);"""),
        ("mail-1280", "w.resizeTo(1280, 900); await wait(1200); await toMail();"),
        ("calendar-week", 'await toCalendar(); w.switchToView("week"); await wait(800);'),
        ("calendar-month", 'await toCalendar(); w.switchToView("month"); await wait(800);'),
        ("tasks", 'tm.openTab("tasks", {}); await wait(1500);'),
        ("addressbook", 'tm.openTab("addressBookTab", {}); await wait(2000);'),
        ("addressbook-edit", ADDRESS_EDIT_JS),
        ("settings", "w.openPreferencesTab(); await wait(2000);"),
        ("addon-settings", f'w.openAddonsMgr("addons://detail/" + encodeURIComponent("{ADDON_ID}") + "/preferences"); await wait(3000);'),
    ]:
        m.js(("" if "resizeTo" in js else "w.resizeTo(1500, 900); ") + js + " await wait(600); return 1;")
        data = m.cmd("WebDriver:TakeScreenshot", {})["value"]
        path = os.path.join(folder, f"{scheme}-{name}.png")
        open(path, "wb").write(base64.b64decode(data))
        print(f"Screenshot {path}", flush=True)
    # eigene Fenster: Verfassen und Termin-Dialog
    for name, js in [
        ("compose", COMPOSE_JS),
        ("event-dialog", 'await toCalendar(); w.switchToView("week"); w.createEventWithDialog(null, null, null, "Halo Dialog"); await wait(2500); return 1;'),
        ("calendar-properties", 'w.openDialog("chrome://calendar/content/calendar-properties-dialog.xhtml", "_blank", "centerscreen,chrome,titlebar,resizable", { calendar: testCalendar() }); await wait(2000); return 1;'),
    ]:
        handles = lambda: (lambda r: r["value"] if isinstance(r, dict) else r)(m.cmd("WebDriver:GetWindowHandles"))
        main = (lambda r: r["value"] if isinstance(r, dict) else r)(m.cmd("WebDriver:GetWindowHandle"))
        before = set(handles())
        m.js(js)
        new = [h for h in handles() if h not in before]
        if not new:
            print(f"Screenshot {name}: kein Fenster", flush=True)
            continue
        m.cmd("WebDriver:SwitchToWindow", {"handle": new[0]})
        m.cmd("WebDriver:ExecuteScript", {"script": "window.resizeTo(900, 700); return new Promise(r => setTimeout(r, 800));", "args": []})
        data = m.cmd("WebDriver:TakeScreenshot", {})["value"]
        path = os.path.join(folder, f"{scheme}-{name}.png")
        open(path, "wb").write(base64.b64decode(data))
        print(f"Screenshot {path}", flush=True)
        m.cmd("WebDriver:ExecuteScript", {"script": "window.close(); return 1;", "args": []})
        m.cmd("WebDriver:SwitchToWindow", {"handle": main})


# Testkontakt (example.invalid) im persönlichen Adressbuch anlegen und bearbeiten
ADDRESS_EDIT_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
  if (!book.childCards.some(c => c.displayName == "Anna Beispiel")) {
    const c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
    for (const [k, v] of Object.entries({ FirstName: "Anna", LastName: "Beispiel", Company: "Beispiel GmbH", JobTitle: "Leitung", WorkPhone: "+43 1 234" })) c.setProperty(k, v);
    c.displayName = "Anna Beispiel"; c.primaryEmail = "anna@example.invalid"; book.addCard(c);
  }
  tm.openTab("addressBookTab", {}); await wait(2000);
  const ab = tm.currentTabInfo.browser.contentWindow; const ad = ab.document;
  const list = ad.getElementById("cards");
  list.selectedIndex = [...Array(list.view.rowCount).keys()].find(k => list.view.getCardFromRow(k)?.displayName == "Anna Beispiel");
  await wait(800);
  ad.getElementById("editButton").click(); await wait(1200);
"""


# eine Test-Mail (example.invalid) in Local Folders öffnen – für die Leseansicht
MESSAGE_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
  const root = MailServices.accounts.localFoldersServer.rootFolder;
  if (!root.containsChildNamed("Lesen")) { root.createSubfolder("Lesen", null); await wait(800); }
  const f = root.getChildNamed("Lesen");
  if (!f.getTotalMessages(false)) {
    f.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage(unescape(encodeURIComponent("From - Sat Oct 17 10:00:00 2026\r\nFrom: Anna Beispiel <anna@example.invalid>\r\nTo: Halo Test <halo@example.invalid>\r\nCc: Ben Muster <ben@example.invalid>\r\nSubject: Treffen am Donnerstag\r\nDate: Sat, 17 Oct 2026 09:41:00 +0200\r\nMessage-ID: <halo-read@example.invalid>\r\nList-ID: Halo Neuigkeiten <news.example.invalid>\r\nList-Unsubscribe: <https://example.invalid/abmelden?id=1>, <mailto:abmelden@example.invalid?subject=unsubscribe>\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nHallo,\r\n\r\npasst dir Donnerstag um 10 Uhr? Ich bringe die Unterlagen mit.\r\n\r\nLiebe Grüße\r\nAnna\r\n")));
    await wait(800);
  }
  const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
  a3.threadTree.selectedIndex = 0; await wait(2000);"""


# Verfassen-Fenster mit einer reinen Test-Identität (example.invalid, kein Server)
COMPOSE_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
  const acc = MailServices.accounts.findAccountForServer(MailServices.accounts.localFoldersServer);
  if (!acc.identities.length) {
    const id = MailServices.accounts.createIdentity();
    id.fullName = "Halo Test"; id.email = "halo@example.invalid";
    acc.addIdentity(id);
  }
  const params = Cc["@mozilla.org/messengercompose/composeparams;1"].createInstance(Ci.nsIMsgComposeParams);
  const fields = Cc["@mozilla.org/messengercompose/composefields;1"].createInstance(Ci.nsIMsgCompFields);
  fields.to = "Anna Beispiel <anna@example.invalid>"; fields.subject = "Halo Entwurf";
  fields.body = "<p>Hallo Anna,</p><p>das ist ein Testentwurf.</p>";
  params.composeFields = fields; params.identity = acc.identities[0]; params.format = Ci.nsIMsgCompFormat.HTML;
  MailServices.compose.OpenComposeWindowWithParams(null, params);
  await wait(3000); return 1;"""


def compare_shots(m, before, after):
    """Vergleicht Screenshots Pixel für Pixel (in Thunderbird selbst, ohne Bildbibliothek).

    Nur zur Information, kein Fehlschlag: Tagesdatum, Uhrzeit und „in 18 min“
    ändern sich von selbst. Für jede Abweichung entsteht ein Bild …-diff.png,
    in dem die geänderten Stellen rot markiert sind.
    """
    import base64
    print("\nVergleich mit", before, flush=True)
    for path in sorted(glob.glob(os.path.join(after, "*.png"))):
        name = os.path.basename(path)
        if name.endswith("-diff.png"):
            continue
        old = os.path.join(before, name)
        if not os.path.exists(old):
            print(f"  neu       {name}", flush=True)
            continue
        res = m.js(f"""
          const load = async p => createImageBitmap(new w.Blob([await IOUtils.read(p)], {{ type: "image/png" }}));
          const [a, b] = [await load({json.dumps(os.path.abspath(old))}), await load({json.dumps(os.path.abspath(path))})];
          if (a.width != b.width || a.height != b.height) return {{ size: [a.width, a.height, b.width, b.height] }};
          const pixels = img => {{ const c = d.createElementNS("http://www.w3.org/1999/xhtml", "canvas"); c.width = img.width; c.height = img.height;
                                  const x = c.getContext("2d"); x.drawImage(img, 0, 0); return [c, x, x.getImageData(0, 0, c.width, c.height)]; }};
          const [, , pa] = pixels(a); const [cb, xb, pb] = pixels(b);
          const A = pa.data, B = pb.data, out = pb;
          let changed = 0, l = 1e9, t = 1e9, r = -1, bo = -1;
          for (let i = 0; i < A.length; i += 4) {{
            const diff = Math.max(Math.abs(A[i] - B[i]), Math.abs(A[i + 1] - B[i + 1]), Math.abs(A[i + 2] - B[i + 2]));
            if (diff > 40) {{
              changed++; const p = i / 4, px = p % b.width, py = (p - px) / b.width;
              l = Math.min(l, px); r = Math.max(r, px); t = Math.min(t, py); bo = Math.max(bo, py);
              out.data[i] = 255; out.data[i + 1] = 0; out.data[i + 2] = 0;
            }} else {{
              // unverändert: blass, damit die roten Stellen auffallen
              for (const k of [0, 1, 2]) out.data[i + k] = 255 - (255 - B[i + k]) * 0.25;
            }}
          }}
          if (!changed) return {{ changed: 0 }};
          xb.putImageData(out, 0, 0);
          return {{ changed: changed / (b.width * b.height), box: [l, t, r, bo], png: cb.toDataURL("image/png") }};""")
        if "size" in res:
            print(f"  Größe     {name}: {res['size'][0]}×{res['size'][1]} → {res['size'][2]}×{res['size'][3]}", flush=True)
        elif not res["changed"]:
            print(f"  gleich    {name}", flush=True)
        else:
            diff = path[:-4] + "-diff.png"
            open(diff, "wb").write(base64.b64decode(res["png"].split(",", 1)[1]))
            l, t, r, b = res["box"]
            print(f"  geändert  {name}: {res['changed'] * 100:.2f} % der Fläche, Bereich x {l}–{r}, y {t}–{b} → {os.path.basename(diff)}", flush=True)


# Mailliste: eigene Ordner mit erfundenen Mails (example.invalid) – Konversation
# (Wurzel gelesen, neuere Antwort ungelesen), Schlagwörter, verschiedene Tage,
# „Gesendet-Test“ mit Gesendet-Merkmal; dazu Hilfen für Farben und Kontrast
MAILLIST_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
  const root = MailServices.accounts.localFoldersServer.rootFolder;
  const pad = n => String(n).padStart(2, "0");
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const rfc = dt => { const o = -dt.getTimezoneOffset();
    return `${DAYS[dt.getDay()]}, ${pad(dt.getDate())} ${MONTHS[dt.getMonth()]} ${dt.getFullYear()} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:00 ${o >= 0 ? "+" : "-"}${pad(Math.floor(Math.abs(o) / 60))}${pad(Math.abs(o) % 60)}`; };
  // vor „days“ Tagen um h Uhr (heute höchstens 10 Minuten vor jetzt)
  const ago = (days, h) => { const dt = new Date(); dt.setDate(dt.getDate() - days); dt.setHours(h, 0, 0, 0); if (dt > new Date()) dt.setTime(Date.now() - 600000); return dt; };
  const raw = o => unescape(encodeURIComponent([`From: ${o.from}`, `To: ${o.to || "Halo Test <halo@example.invalid>"}`, `Subject: ${o.subject}`,
    `Date: ${rfc(o.date)}`, `Message-ID: <${o.id}@example.invalid>`, ...(o.ref ? [`In-Reply-To: <${o.ref}@example.invalid>`, `References: <${o.ref}@example.invalid>`] : []),
    "Content-Type: text/plain; charset=UTF-8", "", "Erfundene Testnachricht.", ""].join("\r\n")));
  const folder = async (name, mails, flag = 0) => {
    if (!root.containsChildNamed(name)) { root.createSubfolder(name, null); await wait(800); }
    const f = root.getChildNamed(name);
    if (flag) f.setFlag(flag);
    if (!f.getTotalMessages(false)) {
      const lf = f.QueryInterface(Ci.nsIMsgLocalMailFolder);
      for (const o of mails) lf.addMessage(raw(o));
      await wait(800);
      for (const o of mails) { const h = f.msgDatabase.getMsgHdrForMessageID(`${o.id}@example.invalid`); if (!h) continue;
        if (o.read) f.markMessagesRead([h], true); if (o.tag) f.addKeywordsToMessages([h], o.tag); }
      await wait(300);
    }
    return f;
  };
  const list = await folder("Mailliste", [
    { id: "halo-ml-1", from: "Ben Muster <ben@example.invalid>", subject: "Halo Faden", date: ago(3, 9), read: true },
    { id: "halo-ml-2", from: "Carla Ölmann <carla@example.invalid>", subject: "Re: Halo Faden", date: ago(2, 9), ref: "halo-ml-1" },
    { id: "halo-ml-3", from: "Dana Zöllner <dana@example.invalid>", subject: "Halo Schlagwort To Do", date: ago(0, 8), read: true, tag: "$label4" },
    { id: "halo-ml-4", from: "Frieda Lang <frieda@example.invalid>", subject: "Halo Schlagwort Work", date: ago(1, 9), read: true, tag: "$label2" },
    { id: "halo-ml-5", from: "Emil Kurz <emil@example.invalid>", subject: "Halo Ungelesen", date: ago(5, 9) },
    { id: "halo-ml-6", from: "Gustav Weit <gustav@example.invalid>", subject: "Halo Alt", date: ago(20, 9), read: true },
  ]);
  const sent = await folder("Gesendet-Test", [{ id: "halo-ml-sent", from: "Halo Test <halo@example.invalid>", to: "Anna Beispiel <anna@example.invalid>",
    subject: "Halo Gesendet", date: ago(1, 10), read: true }], Ci.nsMsgFolderFlags.SentMail);
  const a3 = await toMail(); const ad = a3.document;
  const cmd = name => a3.commandController.doCommand(name);
  const cs = (el, pseudo) => a3.getComputedStyle(el, pseudo);
  const showFolder = async (f = list) => { if (a3.gFolder?.URI != f.URI) { a3.displayFolder(f.URI); await until(() => a3.gFolder?.URI == f.URI && a3.gDBView, 6000); await wait(900); } };
  const cards = () => [...ad.querySelectorAll('#threadTree tr[is="thread-card"]')];
  const tableRows = () => [...ad.querySelectorAll('#threadTree tr[is="thread-row"]')];
  const props = r => (r.dataset.properties || "").split(" ");
  const subjectOf = r => r.querySelector(".subject, .subject-line span")?.textContent || "";
  // Farben: rgb()/rgba() und color(srgb …) auf 0–255, dazu die Deckkraft
  const rgba = c => { const v = (String(c).match(/-?[\d.]+(?:e-?\d+)?/g) || []).map(Number); const k = String(c).startsWith("color(") ? 255 : 1;
    return [v[0] * k, v[1] * k, v[2] * k, v.length > 3 ? v[3] : 1]; };
  const over = (fg, bg) => fg.slice(0, 3).map((x, i) => x * fg[3] + bg[i] * (1 - fg[3])).concat(1);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
  const same = (a, b) => { const [x, y] = [rgba(a), rgba(b)]; return x.every((v, i) => Math.abs(v - y[i]) <= (i == 3 ? 0.02 : 2)); };
  const accent = (() => { const e = ad.createElement("div"); e.style.color = "AccentColor"; ad.body.append(e); const c = cs(e).color; e.remove(); return c; })();
  const asCards = async () => { if (Services.prefs.getIntPref("mail.threadpane.listview", 0) != 0) { cmd("cmd_threadPaneViewCards"); await wait(1000); } };
  const asTable = async () => { if (Services.prefs.getIntPref("mail.threadpane.listview", 0) != 1) { cmd("cmd_threadPaneViewTable"); await wait(1200); } };"""


def maillist_checks(m, results):
    """Mailliste: Gruppenköpfe, Konversationen, Gesendet, Tabelle, Schlagwörter, Schnellfilter, Layouts, Konto-Startseite."""

    def group_headers():
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards();
          const v = a3.gViewWrapper; v.sort(Ci.nsMsgViewSortType.byDate, Ci.nsMsgViewSortOrder.descending);
          v.showGroupedBySort = true; await wait(1200);
          const heads = await until(() => { const h = cards().filter(r => props(r).includes("dummy")); return h.length >= 2 && h; }, 8000) || [];
          const out = heads.map(r => {
            const c = r.querySelector(".card-container").getBoundingClientRect();
            const main = r.querySelector(".card-container > .thread-card-column:not(.read-status-column)");
            const box = r.querySelector(".thread-card-subject-container"), sub = r.querySelector(".subject"), det = r.querySelector(".sort-header-details");
            return { title: sub.textContent, cut: box.scrollWidth > box.clientWidth + 1 || sub.getBoundingClientRect().right > box.getBoundingClientRect().right + 1,
                     main: Math.round(main.getBoundingClientRect().width / c.width * 100), avatar: cs(r.querySelector(".mc-avatar")).display,
                     detailsInside: det.getBoundingClientRect().right <= c.right + 1, weight: cs(sub).fontWeight, detailSize: cs(det).fontSize };
          });
          v.showGroupedBySort = false; v.showThreaded = true; await wait(800);
          return out;""")
        ok = len(res) >= 2 and all(not h["cut"] and h["main"] >= 60 and h["avatar"] == "none" and h["detailsInside"]
                                   and int(h["weight"]) >= 600 and h["detailSize"] == "11px" for h in res)
        return ok, f"{res}"
    check("Mailliste: Gruppenköpfe (Heute, Gestern …) ganz lesbar, halbfett, ohne Absenderbild", group_headers, results)

    def group_headers_table():
        # Tabelle gruppiert: Gruppenköpfe laufen über die leeren Nachbarzellen,
        # die Zählung „(ungelesen/gesamt)“ bleibt sichtbar (früher „Gestern (1…“)
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asTable();
          const v = a3.gViewWrapper; v.sort(Ci.nsMsgViewSortType.byDate, Ci.nsMsgViewSortOrder.descending);
          v.showGroupedBySort = true; await wait(1200);
          const out = [];
          try {
            const heads = await until(() => { const h = tableRows().filter(r => props(r).includes("dummy")); return h.length >= 2 && h; }, 8000) || [];
            const tree = ad.getElementById("threadTree").getBoundingClientRect();
            for (const r of heads) {
              const td = r.querySelector("td.subjectcol-column"), line = td.querySelector(".subject-line"), span = line.querySelector("span");
              const rg = ad.createRange(); rg.selectNodeContents(span); const t = rg.getBoundingClientRect();
              // jede Ebene zwischen Text und Zelle: entweder sichtbar überlaufend oder breit genug
              const clip = []; for (let e = span; e && e != r; e = e.parentElement) {
                const c = cs(e); if ((c.overflowX != "visible" || c.textOverflow == "ellipsis") && e.getBoundingClientRect().right < t.right - 1) clip.push(e.className || e.localName); }
              // Nachbarzellen unter dem überlaufenden Text: ohne eigene Fläche, die ihn verdecken könnte
              const cover = [...r.children].filter(c => c != td && !c.hidden && rgba(cs(c).backgroundColor)[3] > 0)
                .filter(c => { const b = c.getBoundingClientRect(); return b.right > t.left && b.left < t.right; }).map(c => c.className);
              out.push({ text: span.textContent, clip, cover, right: Math.round(t.right), treeRight: Math.round(tree.right), weight: cs(line).fontWeight });
            }
          } finally { v.showGroupedBySort = false; v.showThreaded = true; await wait(800); }
          return out;""")
        # Zählung „(n)“ bzw. „(ungelesen/gesamt)“; mindestens ein Kopf mit Ungelesenem
        ok = (len(res) >= 2 and any("/" in h["text"] for h in res)
              and all(not h["clip"] and not h["cover"] and h["right"] <= h["treeRight"] and re.search(r"\(\d+(/\d+)?\)$", h["text"])
                      and int(h["weight"]) >= 600 for h in res))
        return ok, f"{res}"
    check("Mailliste: Gruppenköpfe der Tabelle ganz lesbar samt Zählung, halbfett", group_headers_table, results)

    def card_alignment():
        # Betreff bündig mit Absender und Vorschau (früher 3 px eingerückt durch
        # Thunderbirds column-gap); Konversation: Abstand zum Thread-Knopf;
        # mit Stern: Abstand zwischen Betreff und Symbolen – je Dichte
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards(); a3.gViewWrapper.showThreaded = true; await wait(600); cmd("cmd_collapseAllThreads"); await wait(800);
          const hdr = list.msgDatabase.getMsgHdrForMessageID("halo-ml-4@example.invalid"); list.markMessagesFlagged([hdr], true); await wait(600);
          const L = (r, sel) => r.querySelector(sel).getBoundingClientRect();
          const out = {};
          try {
            for (const density of [0, 1, 2]) {
              Services.prefs.setIntPref("mail.uidensity", density); await wait(1200);
              const single = await until(() => cards().find(r => !r.classList.contains("children") && !props(r).includes("dummy")
                                                          && subjectOf(r).includes("Halo Ungelesen") && r.querySelector(".mc-preview")?.textContent), 6000);
              const conv = cards().find(r => r.classList.contains("children") && r.classList.contains("collapsed") && subjectOf(r).includes("Halo Faden"));
              const star = cards().find(r => subjectOf(r).includes("Halo Schlagwort Work"));
              if (!single || !conv || !star) { out[density] = { fehlt: [!!single, !!conv, !!star] }; continue; }
              // Anfang des Textes (nicht der Kästen – Absender und Vorschau haben Innenabstand)
              const T = (r, sel) => { const g = ad.createRange(); g.selectNodeContents(r.querySelector(sel)); return g.getBoundingClientRect(); };
              const sn = T(single, ".sender").left;
              const sub = L(star, ".subject"), icons = L(star, ".thread-card-icon-info");
              out[density] = { subject: Math.round(T(single, ".subject").left - sn), preview: Math.round(T(single, ".mc-preview").left - sn),
                               twisty: Math.round(L(conv, ".thread-card-subject-container").left - L(conv, "button.twisty").right),
                               icons: icons.width > 0 ? Math.round(icons.left - sub.right) : null };
            }
          } finally {
            Services.prefs.clearUserPref("mail.uidensity"); list.markMessagesFlagged([hdr], false); await wait(1000);
          }
          // gruppiert nach Sortierung: Karten unter einem Gruppenkopf (thread-children)
          // verlieren sonst Thunderbirds Einzug des Absenders – Betreff/Vorschau 3 px rechts davon
          const v = a3.gViewWrapper; v.sort(Ci.nsMsgViewSortType.byDate, Ci.nsMsgViewSortOrder.descending);
          v.showGroupedBySort = true; await wait(1200); cmd("cmd_expandAllThreads"); await wait(1200);
          try {
            const g = await until(() => cards().find(r => !props(r).includes("dummy") && props(r).includes("thread-children")
                                                      && r.querySelector(".mc-preview")?.textContent), 8000);
            if (!g) out.gruppiert = { fehlt: true };
            else {
              const T = sel => { const rg = ad.createRange(); rg.selectNodeContents(g.querySelector(sel)); return rg.getBoundingClientRect().left; };
              const sn = T(".sender");
              out.gruppiert = { subject: +(T(".subject") - sn).toFixed(2), preview: +(T(".mc-preview") - sn).toFixed(2) };
            }
          } finally { v.showGroupedBySort = false; v.showThreaded = true; await wait(800); cmd("cmd_collapseAllThreads"); await wait(800); }
          return out;""")
        grp = res.get("gruppiert", {})
        dens = [v for k, v in res.items() if k != "gruppiert"]
        ok = (len(dens) == 3 and all("fehlt" not in v and abs(v["subject"]) <= 1 and abs(v["preview"]) <= 1 and v["twisty"] >= 2
                                     and v["icons"] is not None and v["icons"] >= 2 for v in dens)
              and "fehlt" not in grp and abs(grp.get("subject", 9)) <= 0.5 and abs(grp.get("preview", 9)) <= 0.5)
        return ok, f"{res}"
    check("Mailliste: Betreff der Karte bündig mit Absender und Vorschau (auch gruppiert), Abstand zu Thread-Knopf und Symbolen", card_alignment, results)

    def thread_sender():
        # zugeklappt: Name und Bild der neuesten Mail (Carla), aufgeklappt die Wurzel (Ben)
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards(); a3.gViewWrapper.showThreaded = true; await wait(800);
          const info = r => r && { sender: r.querySelector(".sender").textContent, avatar: r.querySelector(".mc-avatar").textContent,
                                   email: r.querySelector(".mc-avatar").dataset.email, img: !!r.querySelector(".mc-avatar img") };
          cmd("cmd_collapseAllThreads"); await wait(800);
          const closed = await until(() => cards().find(r => r.classList.contains("children") && r.classList.contains("collapsed") && subjectOf(r).includes("Halo Faden")
                                                           && r.querySelector(".mc-avatar")?.dataset.email), 6000);
          const out = { closed: info(closed) };
          cmd("cmd_expandAllThreads"); await wait(800);
          const open = await until(() => cards().find(r => r.classList.contains("children") && !r.classList.contains("collapsed") && subjectOf(r).includes("Halo Faden")), 6000);
          out.open = info(open);
          cmd("cmd_collapseAllThreads"); await wait(500);
          return out;""")
        c, o = res.get("closed") or {}, res.get("open") or {}
        ok = (c.get("sender") == "Carla Ölmann" and c.get("email") == "carla@example.invalid" and (c.get("img") or c.get("avatar") == "CÖ")
              and o.get("sender") == "Ben Muster" and o.get("email") == "ben@example.invalid" and (o.get("img") or o.get("avatar") == "BM"))
        return ok, f"{res}"
    check("Mailliste: zugeklappte Konversation zeigt Name und Bild der neuesten Mail", thread_sender, results)

    def thread_button():
        # Thread-Knopf ohne Stern und Akzentrahmen, Abstand zum Betreff; Ungelesen-Punkt
        # bei zugeklappter Konversation mit ungelesener Antwort
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards(); a3.gViewWrapper.showThreaded = true; await wait(600); cmd("cmd_collapseAllThreads"); await wait(800);
          const row = () => cards().find(r => r.classList.contains("children") && r.classList.contains("collapsed") && subjectOf(r).includes("Halo Faden"));
          const out = { gaps: {} };
          for (const density of [1, 0]) {
            Services.prefs.setIntPref("mail.uidensity", density); await wait(1200);
            const r = await until(row, 5000); const t = r.querySelector("button.twisty");
            out.gaps[density] = Math.round(r.querySelector(".subject").getBoundingClientRect().left - t.getBoundingClientRect().right);
          }
          Services.prefs.clearUserPref("mail.uidensity"); await wait(1000);
          const r = row(), t = r.querySelector("button.twisty"), dot = r.querySelector(".read-status");
          Object.assign(out, { props: r.dataset.properties, before: cs(t, "::before").content, border: cs(t).borderTopColor,
                               dot: cs(dot).display, dotColor: cs(dot).backgroundColor, accent });
          // ausgewählt mit Fokus: durchscheinende Kapsel auf der Akzentfarbe
          const i = [...Array(a3.gDBView.rowCount).keys()].find(k => a3.gDBView.getMsgHdrAt(k)?.messageId == "halo-ml-1@example.invalid");
          a3.threadTree.selectedIndex = i; a3.threadTree.focus(); await wait(800);
          const sel = await until(() => cards().find(x => x.classList.contains("selected") && subjectOf(x).includes("Halo Faden")), 4000);
          out.selected = sel ? cs(sel.querySelector("button.twisty")).backgroundColor : null;
          a3.threadTree.selectedIndex = -1; await wait(300);
          return out;""")
        ok = (res["before"] == "none" and rgba_alpha(res["border"]) == 0 and res["dot"] != "none" and same_color(res["dotColor"], res["accent"])
              and all(g >= 2 for g in res["gaps"].values()) and res["selected"] and rgba_alpha(res["selected"]) < 1)
        return ok, f"{res}"
    check("Mailliste: Thread-Knopf ohne Stern und Akzentrahmen, Ungelesen-Punkt an zugeklappter Konversation", thread_button, results)

    def date_weight():
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards();
          const r = await until(() => cards().find(x => props(x).includes("unread") && !props(x).includes("dummy")), 5000);
          return r ? { date: cs(r.querySelector(".date")).fontWeight, sender: cs(r.querySelector(".sender")).fontWeight } : {};""")
        return res.get("date") == "400" and res.get("sender") == "600", f"ungelesene Karte {res}"
    check("Mailliste: Datum ungelesener Karten normal, Absender halbfett", date_weight, results)

    def sent_avatar():
        # Gesendet: Name und Bild des Empfängers; im Mailkopf bleibt der Absender
        res = m.js(MAILLIST_JS + r"""
          await showFolder(sent); await asCards();
          const r = await until(() => cards().find(x => x.querySelector(".mc-avatar")?.dataset.email), 6000);
          if (!r) return {};
          const av = r.querySelector(".mc-avatar");
          const out = { sender: r.querySelector(".sender").textContent, avatar: av.textContent, email: av.dataset.email, img: !!av.querySelector("img") };
          a3.threadTree.selectedIndex = 0; await wait(1500);
          const md = a3.messageBrowser.contentWindow.document;
          const hav = await until(() => md.querySelector("#fromRecipient0 .mc-hdr-avatar")?.dataset.email && md.querySelector("#fromRecipient0 .mc-hdr-avatar"), 6000);
          out.header = hav ? { email: hav.dataset.email, text: hav.textContent } : null;
          a3.threadTree.selectedIndex = -1; await wait(300);
          return out;""")
        h = res.get("header") or {}
        ok = (res.get("sender") == "Anna Beispiel" and res.get("email") == "anna@example.invalid" and (res.get("img") or res.get("avatar") == "AB")
              and h.get("email") == "halo@example.invalid")
        return ok, f"{res}"
    check("Mailliste: Gesendet zeigt Bild des Empfängers, Mailkopf weiter den Absender", sent_avatar, results)

    def table_font():
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards();
          const card = await until(() => cards().find(x => !props(x).includes("dummy")), 5000);
          const out = { card: cs(card.querySelector(".sender")).fontSize };
          await asTable();
          const row = await until(() => tableRows()[0], 5000);
          out.row = cs(row.querySelector("td")).fontSize; out.head = cs(ad.querySelector("#threadTree thead th")).fontSize;
          await asCards(); return out;""")
        return res["card"] == res["row"] == res["head"] == "13px", f"Karte/Tabelle/Spaltenkopf {res}"
    check("Mailliste: Tabelle in 13 px wie Karten und Spaltenkopf", table_font, results)

    def table_unread():
        # Ungelesen als Punkt in Akzentfarbe (kein Grün), kein Stern vor neuen Mails;
        # Zusammenfassung mehrerer Mails ebenso
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asTable(); a3.threadTree.selectedIndex = -1; await wait(500);
          if (!tableRows().some(r => props(r).includes("new"))) {
            // neue Mail, solange der Ordner angezeigt wird (sonst setzt Thunderbird „neu“ zurück)
            list.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage(raw({ id: "halo-ml-new-" + Date.now(), from: "Ida Viel <ida@example.invalid>", subject: "Halo Neu", date: ago(0, 7) }));
            await wait(1200);
          }
          const unread = await until(() => tableRows().find(r => props(r).includes("unread") && !r.classList.contains("selected")), 5000);
          const fresh = tableRows().find(r => props(r).includes("new") && !["replied", "forwarded", "redirected"].some(p => props(r).includes(p)));
          const img = unread?.querySelector(".tree-button-unread > img");
          const out = { fill: img && cs(img).fill, accent, newStar: fresh ? cs(fresh.querySelector(".subject-line img")).visibility : "keine neue Mail" };
          await asCards();
          // Zusammenfassung: eine ungelesene und eine gelesene Mail auswählen
          const v = a3.gDBView, ids = ["halo-ml-5@example.invalid", "halo-ml-6@example.invalid"];
          a3.threadTree.selectedIndices = [...Array(v.rowCount).keys()].filter(k => ids.includes(v.getMsgHdrAt(k)?.messageId)); await wait(1500);
          const md = a3.multiMessageBrowser?.contentDocument;
          const li = await until(() => md?.querySelector("#messageList > li.unread"), 5000);
          out.summary = li ? md.defaultView.getComputedStyle(li, "::before").fill : null;
          a3.threadTree.selectedIndex = -1; await wait(300);
          return out;""")
        ok = same_color(res["fill"], res["accent"]) and res["newStar"] == "hidden" and same_color(res["summary"], res["accent"])
        return ok, f"{res}"
    check("Mailliste: Tabelle und Zusammenfassung mit Ungelesen-Punkt in Akzentfarbe, ohne Stern", table_unread, results)

    def tag_contrast():
        # Schlagwortfarben als Schrift (Tabelle, Schnellfilter-Knöpfe) mit Kontrast ≥ 4,5:1
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asTable(); a3.threadTree.selectedIndex = -1; await wait(600);
          const treeBg = rgba(cs(ad.getElementById("threadTree")).backgroundColor);
          const out = { rows: {}, buttons: {} };
          for (const r of tableRows().filter(x => subjectOf(x).includes("Halo Schlagwort")))
            out.rows[subjectOf(r)] = contrast(over(rgba(cs(r).color), treeBg), over(rgba(cs(r).backgroundColor), treeBg));
          await asCards();
          if (ad.getElementById("quick-filter-bar")?.hidden !== false) { cmd("cmd_toggleQuickFilterBar"); await wait(900); }
          ad.getElementById("qfb-tags").click(); await wait(1200);
          const bar = ad.getElementById("quick-filter-bar"), barBg = over(rgba(cs(bar).backgroundColor), treeBg);
          for (const b of ad.querySelectorAll('#quick-filter-bar button.qfb-tag-button:not([aria-pressed="true"])'))
            if (b.getClientRects().length) out.buttons[b.textContent.trim()] = contrast(rgba(cs(b).color), barBg);
          cmd("cmd_resetQuickFilterBar"); cmd("cmd_toggleQuickFilterBar"); await wait(600);
          return out;""")
        values = list(res["rows"].values()) + list(res["buttons"].values())
        ok = len(res["rows"]) == 2 and len(res["buttons"]) >= 2 and all(v >= 4.5 for v in values)
        return ok, f"Kontrast {res}"
    check("Mailliste: Schlagwortfarben in Tabelle und Schnellfilter lesbar (Kontrast ≥ 4,5:1)", tag_contrast, results)

    def quick_filter():
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards();
          if (ad.getElementById("quick-filter-bar")?.hidden !== false) { cmd("cmd_toggleQuickFilterBar"); await wait(900); }
          const bar = ad.getElementById("quick-filter-bar");
          const card = cards().find(x => !props(x).includes("dummy"))?.querySelector(".card-container");
          const left = el => el ? Math.round(el.getBoundingClientRect().left) : null;
          const out = { bg: cs(bar).backgroundColor, tree: cs(ad.getElementById("threadTree")).backgroundColor, line: parseFloat(cs(bar).borderBottomWidth),
                        card: left(card), pin: left(ad.getElementById("qfb-sticky")) };
          ad.getElementById("qfb-tags").click(); await wait(1200);
          out.mode = left(ad.getElementById("qfb-tag-filter-mode"));
          cmd("cmd_resetQuickFilterBar"); cmd("cmd_toggleQuickFilterBar"); await wait(600);
          return out;""")
        ok = (res["bg"] == res["tree"] and res["line"] <= 1 and res["card"] is not None
              and abs(res["pin"] - res["card"]) <= 4 and abs(res["mode"] - res["card"]) <= 4)
        return ok, f"{res}"
    check("Mailliste: Schnellfilter-Leiste auf der Listenfläche, bündig mit den Karten", quick_filter, results)

    def layout_lines():
        res = m.js(MAILLIST_JS + r"""
          await showFolder(); await asCards();
          const before = Services.prefs.getIntPref("mail.pane_config.dynamic", 2);
          const line = () => { const p = ad.getElementById("messagePane"); return { width: parseFloat(cs(p).borderTopWidth), style: cs(p).borderTopStyle,
            left: Math.round(p.getBoundingClientRect().left), folders: Math.round(ad.getElementById("folderPane").getBoundingClientRect().left) }; };
          const out = {};
          cmd("cmd_viewClassicMailLayout"); await wait(1200); out.classic = line();
          cmd("cmd_viewWideMailLayout"); await wait(1200); out.wide = line();
          cmd("cmd_viewVerticalMailLayout"); await wait(1200); out.vertical = line();
          Services.prefs.setIntPref("mail.pane_config.dynamic", before); await wait(800);
          return out;""")
        c, w_, v = res["classic"], res["wide"], res["vertical"]
        ok = (c["width"] > 0 and c["style"] == "solid" and w_["width"] > 0 and w_["style"] == "solid"
              and w_["left"] <= w_["folders"] + 1 and v["width"] == 0)
        return ok, f"{res}"
    check("Mailliste: Layout „klassisch“ und „breit“ mit Linie über der Leseansicht, „vertikal“ ohne", layout_lines, results)

    def account_central():
        res = m.js(MAILLIST_JS + r"""
          a3.displayFolder(root.URI);
          const doc = await until(() => { const x = ad.getElementById("accountCentralBrowser")?.contentDocument; return x?.getElementById("accountCentral") && x; }, 8000);
          if (!doc) return {};
          const vis = e => e.getClientRects().length && e.getBoundingClientRect().height > 0;
          const parts = () => [doc.body, ...[...doc.querySelectorAll(".account-central-header, .account-central-section")].filter(vis)];
          const bgs = () => [...new Set(parts().map(e => doc.defaultView.getComputedStyle(e).backgroundColor))];
          await until(() => bgs().length == 1, 4000);
          const btn = [...doc.querySelectorAll(".btn-hub")].find(vis);
          const out = { backgrounds: bgs(), radius: btn ? doc.defaultView.getComputedStyle(btn).borderTopLeftRadius : null };
          await showFolder(); return out;""")
        ok = len(res.get("backgrounds", [])) == 1 and res.get("radius") == "6px"
        return ok, f"{res}"
    check("Mailliste: Konto-Startseite in einer ruhigen Fläche, Kacheln als Knöpfe", account_central, results)

    def account_hub_fields():
        # Account Hub: die Dialogfeld-Regel (28 px, Haarlinie, 7 px) gilt hier
        # nicht – Felder behalten ihre Höhe, die Beschriftung sitzt in der
        # Rahmenkerbe statt frei darüber (Gegenprobe 28 px: „Dialoge: Eingabefelder …“)
        res = m.js(r"""
          await toMail();
          const hub = () => [...d.querySelectorAll("account-hub-container")].map(c => c.shadowRoot?.querySelector("dialog")).find(x => x?.open);
          w.openAccountHub();
          const dl = await until(hub, 8000);
          if (!dl) return { open: false };
          const root = dl.getRootNode();
          const field = id => until(() => { const i = root.getElementById(id); return i?.getClientRects().length && i; }, 6000);
          const out = { open: true, cls: dl.className };
          for (const id of ["realName", "email"]) {
            const i = await field(id); if (!i) { out[id] = null; continue; }
            const lab = root.querySelector(`label[for="${id}"]`);
            out[id] = { h: Math.round(i.getBoundingClientRect().height), top: i.getBoundingClientRect().top,
                        labBottom: lab ? lab.getBoundingClientRect().bottom : null, pad: w.getComputedStyle(i).paddingTop };
          }
          dl.close(); await wait(500);
          out.closed = !hub();
          return out;""")
        rn, em = res.get("realName"), res.get("email")
        ok = (res.get("open") and res.get("closed") and rn and em
              and rn["h"] >= 36 and em["h"] >= 36 and rn["labBottom"] is not None
              and rn["labBottom"] >= rn["top"] - 2)
        return ok, f"{res}"
    check("Account Hub: Felder in eigener Höhe (≥ 36 px), Beschriftung „Full name“ in der Rahmenkerbe statt darüber", account_hub_fields, results)

    # aufräumen: Testmails endgültig löschen (sonst fänden spätere Prüfungen wie
    # die Suche sie mit), Gesendet-Merkmal wieder entfernen
    m.js(MAILLIST_JS + r"""
      a3.threadTree.selectedIndex = -1; await asCards();
      for (const f of [list, sent]) { const hs = [...f.messages]; if (hs.length) f.deleteMessages(hs, null, true, false, null, false); }
      sent.clearFlag(Ci.nsMsgFolderFlags.SentMail); await wait(800); return 1;""")


# Leseansicht und Mailkopf: erfundene Mails (example.invalid) im Ordner „Kopf“
READING_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
  const root = MailServices.accounts.localFoldersServer.rootFolder;
  const pad = n => String(n).padStart(2, "0");
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const rfc = dt => { const o = -dt.getTimezoneOffset();
    return `${DAYS[dt.getDay()]}, ${pad(dt.getDate())} ${MONTHS[dt.getMonth()]} ${dt.getFullYear()} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())} ${o >= 0 ? "+" : "-"}${pad(Math.floor(Math.abs(o) / 60))}${pad(Math.abs(o) % 60)}`; };
  const ics = (days, h) => { const t = new Date(); t.setDate(t.getDate() + days); t.setHours(h, 0, 0, 0); return t.toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z"); };
  const raw = o => unescape(encodeURIComponent([`From: ${o.from || "Anna Beispiel <anna@example.invalid>"}`, `To: ${o.to || "Halo Test <halo@example.invalid>"}`,
    ...(o.cc ? [`Cc: ${o.cc}`] : []), `Subject: ${o.subject}`, `Date: ${rfc(o.date || new Date(Date.now() - 2 * 86400000))}`, `Message-ID: <${o.id}@example.invalid>`,
    "MIME-Version: 1.0", `Content-Type: ${o.type || "text/plain; charset=UTF-8"}`, "", o.body || "Erfundene Testnachricht.", ""].join("\r\n")));
  if (!root.containsChildNamed("Kopf")) { root.createSubfolder("Kopf", null); await wait(800); }
  const f = root.getChildNamed("Kopf");
  if (!f.getTotalMessages(false)) {
    const many = ["Halo Test", "Anna Beispiel", "Ben Muster", "Carla Ölmann", "Emil Kurz", "Frieda Lang", "Gustav Weit", "Jana Breit", "Karl Lang", "Lena Mehr", "Mia Viel", "Nora Weit"]
      .map(n => `${n} <${n.split(" ")[0].toLowerCase()}@example.invalid>`).join(", ");
    const b = "----=_halo_kopf", c = "----=_halo_einladung";
    const vcal = ["BEGIN:VCALENDAR", "PRODID:-//Halo//Test//DE", "VERSION:2.0", "METHOD:REQUEST", "BEGIN:VEVENT", "UID:halo-kopf-einladung@example.invalid",
      `DTSTAMP:${ics(0, 8)}`, `DTSTART:${ics(3, 10)}`, `DTEND:${ics(3, 11)}`, "SUMMARY:Halo Workshop", "LOCATION:Raum 2.01",
      "ORGANIZER;CN=Anna Beispiel:mailto:anna@example.invalid",
      "ATTENDEE;CN=Halo Test;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:halo@example.invalid",
      "ATTENDEE;CN=Anna Beispiel;ROLE=CHAIR;PARTSTAT=ACCEPTED:mailto:anna@example.invalid", "SEQUENCE:0", "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    const att = name => `--${b}\r\nContent-Type: text/plain; name="${name}"\r\nContent-Disposition: attachment; filename="${name}"\r\nContent-Transfer-Encoding: base64\r\n\r\n${btoa("Erfundene Testdatei " + name)}\r\n`;
    const lf = f.QueryInterface(Ci.nsIMsgLocalMailFolder);
    for (const o of [
      { id: "halo-kopf-lang", from: "Dr. Maximilian Alexander von Langenname-Überlänge <max@example.invalid>",
        subject: "Halo Lang: eine sehr lange Betreffzeile, die garantiert nicht in eine Zeile passt, weil sie wirklich außergewöhnlich viele Wörter enthält – und noch mehr", body: "Kurzer Inhalt." },
      { id: "halo-kopf-viele", from: "Dana Zöllner <dana@example.invalid>", to: many, cc: "Hannah Mehr <hannah@example.invalid>, Ida Viel <ida@example.invalid>", subject: "Halo Viele Empfänger" },
      { id: "halo-kopf-anhang", subject: "Halo Anhänge", type: `multipart/mixed; boundary="${b}"`,
        body: `--${b}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nDrei Anhänge.\r\n${att("Ausflug-01.txt")}${att("Ausflug-02.txt")}${att("Notizen.txt")}--${b}--` },
      { id: "halo-kopf-einladung", subject: "Einladung: Halo Workshop", type: `multipart/alternative; boundary="${c}"`,
        body: `--${c}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nErfundene Einladung.\r\n--${c}\r\nContent-Type: text/calendar; charset=UTF-8; method=REQUEST\r\n\r\n${vcal}\r\n--${c}--` },
      { id: "halo-kopf-jetzt", subject: "Halo Jetzt", date: new Date() },
      { id: "halo-kopf-kontakt", from: "Paula Panel <paula@example.invalid>", subject: "Halo Kontakt" },
    ]) lf.addMessage(raw(o));
    await wait(1000);
  }
  const a3 = await toMail();
  const md = () => a3.messageBrowser.contentDocument;
  const cs = (el, p) => el.ownerDocument.defaultView.getComputedStyle(el, p);
  const vis = el => !!el && el.getClientRects().length > 0 && el.getBoundingClientRect().width > 0;
  const showMail = async subj => {
    if (a3.gFolder?.URI != f.URI) { a3.displayFolder(f.URI); await until(() => a3.gFolder?.URI == f.URI && a3.gDBView, 6000); await wait(800); }
    const v = a3.gDBView; let i = -1;
    for (let k = 0; k < v.rowCount; k++) if ((v.getMsgHdrAt(k).mime2DecodedSubject || "").includes(subj)) i = k;
    a3.threadTree.selectedIndex = i;
    await until(() => (md().getElementById("expandedsubjectBox")?.textContent || "").includes(subj) && md().getElementById("messagepane")?.contentDocument?.body?.textContent, 6000);
    await wait(900); return md(); };
  // schmaler Mailbereich (unter 768 px stellt Thunderbird den Kopf auf Spalten um): Today-Pane auf
  const tpCmd = d.getElementById("calendar_toggle_todaypane_command");
  const narrow = async () => { if (md().documentElement.clientWidth >= 768 && !w.TodayPane.isVisible) { tpCmd.doCommand(); w.__haloTpOpened = true; await wait(1500); } return md().documentElement.clientWidth; };
  const restore = async () => { if (w.__haloTpOpened && w.TodayPane.isVisible) { tpCmd.doCommand(); await wait(800); } w.__haloTpOpened = false; };
  const rgb = c => (c.match(/-?[\d.]+/g) || []).map(Number).map((v, i) => (c.startsWith("color(") && i < 3 ? v * 255 : v));
  const lum = ([r, g, b]) => { const t = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * t(r) + 0.7152 * t(g) + 0.0722 * t(b); };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
  const over = (fg, bg) => { const al = fg[3] ?? 1; return fg.slice(0, 3).map((v, i) => v * al + bg[i] * (1 - al)); };"""


def reading_checks(m, results):
    """Leseansicht und Mailkopf: langer Absender, Einladung, Anhänge, Suchleiste, Kontakt-Panel, Mail im Tab, Datum, Linie, „Mehr“, Kommas."""

    def long_sender():
        # schmaler Mailbereich: Name endet mit „…“ vor Ordner und Uhrzeit, Kopf nicht breiter als der Mailbereich
        res = m.js(READING_JS + r"""
          let doc = await showMail("Halo Lang"); const width = await narrow(); doc = md(); await wait(500);
          const header = doc.getElementById("messageHeader"), meta = doc.getElementById("mcHdrMeta"), subj = doc.getElementById("expandedsubjectBox");
          const name = [...doc.querySelectorAll("#fromRecipient0 :is(.recipient-single-line, .recipient-multi-line-name)")].find(vis);
          // das kürzende Element: der Name selbst (Block) oder sein Listenelement (einzeiliger Name)
          const box = name && (cs(name).display == "inline" ? name.closest("li") : name);
          const out = { width, scroll: header.scrollWidth, client: header.clientWidth, name: name?.textContent,
                        nameRight: Math.round(box?.getBoundingClientRect().right), metaLeft: Math.round(meta?.getBoundingClientRect().left),
                        subjRight: Math.round(subj.getBoundingClientRect().right), headerRight: Math.round(header.getBoundingClientRect().right),
                        ellipsis: box && cs(box).textOverflow, cut: box && box.scrollWidth > box.clientWidth };
          await restore(); return out;""")
        ok = (res["width"] < 768 and res["scroll"] <= res["client"] + 1 and res["nameRight"] <= res["metaLeft"] + 1
              and res["subjRight"] <= res["headerRight"] and res["ellipsis"] == "ellipsis" and res["cut"])
        return ok, f"{res}"
    check("Mailkopf: langer Absender im schmalen Mailbereich endet mit „…“ vor Ordner und Uhrzeit, Betreff ganz", long_sender, results)

    def invitation():
        # Einladung: graue Kapsel statt blauer/lila Fläche mit Schatten, Text einzeilig und lesbar; Details in voller Breite
        res = m.js(READING_JS + r"""
          await showMail("Halo Workshop"); await narrow(); const doc = md();
          const bar = await until(() => vis(doc.getElementById("imip-bar")) && doc.getElementById("imip-bar"), 6000);
          if (!bar) { await restore(); return { bar: false }; }
          await wait(500);
          const s = cs(bar), t = bar.querySelector(".msgNotificationBarText");
          const lh = parseFloat(cs(t).lineHeight) || parseFloat(cs(t).fontSize) * 1.2;
          const win = rgb(cs(doc.getElementById("messageHeader")).backgroundColor);
          const btn = doc.getElementById("imipAcceptButton");
          const body = doc.getElementById("messagepane").contentDocument;
          const border = await until(() => body.querySelector(".invitation-border"), 6000);
          const out = { bar: true, bg: s.backgroundColor, radius: parseFloat(s.borderTopLeftRadius), shadow: s.boxShadow,
                        text: t.textContent.trim(), textLines: Math.round(t.getBoundingClientRect().height / lh * 10) / 10,
                        // Text über die ganze Zeile (nicht als schmale Spalte neben den Knöpfen), Knöpfe darunter
                        fullRow: t.getBoundingClientRect().right >= bar.getBoundingClientRect().right - parseFloat(s.paddingRight) - 2,
                        below: doc.getElementById("imip-view-toolbox").getBoundingClientRect().top >= t.getBoundingClientRect().bottom - 1,
                        contrast: contrast(rgb(cs(t).color), over(rgb(s.backgroundColor), win)),
                        btnRadius: parseFloat(cs(btn).borderTopLeftRadius), btnBorder: cs(btn.querySelector(".toolbarbutton-menubutton-button") || btn).borderTopColor,
                        bodyScroll: body.documentElement.scrollWidth, inner: body.defaultView.innerWidth,
                        cardBorder: border && parseFloat(cs(border).borderTopWidth), cardRight: border && Math.round(border.getBoundingClientRect().right) };
          await restore(); return out;""")
        ok = (res.get("bar") and res["bg"] not in ("rgb(192, 132, 252)", "rgb(221, 238, 254)") and res["radius"] >= 10
              and res["shadow"] == "none" and res["fullRow"] and res["below"] and res["contrast"] >= 4.5 and res["btnRadius"] >= 10
              and rgba_alpha(res["btnBorder"]) == 0 and res["bodyScroll"] <= res["inner"] + 1
              and res["cardBorder"] is not None and res["cardBorder"] <= 1 and res["cardRight"] <= res["inner"])
        return ok, f"{res}"
    check("Einladung: Leiste als graue Kapsel (Text über die ganze Zeile, lesbar, Knöpfe darunter), Details als Karte in der Breite des Lesebereichs", invitation, results)

    def attachments():
        res = m.js(READING_JS + r"""
          const doc = await showMail("Halo Anhänge");
          doc.defaultView.toggleAttachmentList?.(true, true); await wait(900);
          const list = doc.getElementById("attachmentList");
          // Hauptfenster vorn, sonst bekommt die Liste unter Linux (xvfb) keinen Fokus und bleibt grau
          w.focus(); await until(() => Services.focus.activeWindow == w, 3000);
          list.selectedIndex = 0; list.focus(); await until(() => list.matches(":focus-within"), 2000); await wait(400);
          const item = list.querySelector(".attachmentItem[selected]");
          const focused = { bg: cs(item).backgroundColor, radius: parseFloat(cs(item).borderTopLeftRadius), outline: cs(item).outlineStyle };
          a3.threadTree.focus(); await wait(300);
          const out = { list: cs(list).backgroundColor, header: cs(doc.getElementById("messageHeader")).backgroundColor,
                        bar: cs(doc.getElementById("attachmentBar")).backgroundColor, focused, unfocused: cs(item).backgroundColor,
                        accent: (() => { const e = doc.createElement("div"); e.style.color = "AccentColor"; doc.documentElement.append(e); const c = cs(e).color; e.remove(); return c; })() };
          doc.defaultView.toggleAttachmentList?.(false); return out;""")
        f = res["focused"]
        ok = (same_color(res["list"], res["header"]) and same_color(res["bar"], res["header"]) and f["radius"] >= 6
              and f["outline"] == "none" and same_color(f["bg"], res["accent"]) and not same_color(res["unfocused"], res["accent"]))
        return ok, f"{res}"
    check("Anhänge: Liste auf der Fläche der Mail, markierte Datei abgerundet ohne Rahmen (unfokussiert grau)", attachments, results)

    def find_bar():
        res = m.js(READING_JS + r"""
          const doc = await showMail("Halo Jetzt"); await narrow();
          a3.commandController.doCommand("cmd_find"); await wait(900);
          const fb = doc.querySelector("findbar");
          if (!fb || fb.hidden) { await restore(); return { open: false }; }
          const right = fb.getBoundingClientRect().right;
          const outside = [...fb.querySelectorAll(".findbar-container > *")].filter(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().right > right + 1)
            .map(e => e.getAttribute("anonid") || e.className);
          const tb = fb.querySelector(".findbar-textbox");
          const out = { open: true, width: Math.round(right), outside, border: cs(tb).borderTopStyle, radius: parseFloat(cs(tb).borderTopLeftRadius) };
          fb.close(); await wait(900);
          // geschlossen: keine Lücke unter der Mail
          out.gap = Math.round(doc.getElementById("messagepanebox").getBoundingClientRect().bottom - doc.getElementById("messagepane").getBoundingClientRect().bottom);
          await restore(); return out;""")
        ok = res.get("open") and not res["outside"] and res["border"] == "none" and res["radius"] >= 6 and res["gap"] <= 1
        return ok, f"{res}"
    check("Suchleiste in der Mail: nichts abgeschnitten, Suchfeld ohne Rahmen, geschlossen ohne Lücke", find_bar, results)

    def contact_panel():
        # Panel „Kontakt bearbeiten“ (über das Menü zur Absenderadresse) mit der Fläche der Tooltips
        res = m.js(READING_JS + r"""
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          let card = book.childCards.find(c => c.primaryEmail == "paula@example.invalid");
          if (!card) { card = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
            card.displayName = "Paula Panel"; card.primaryEmail = "paula@example.invalid"; card = book.addCard(card); }
          const doc = await showMail("Halo Kontakt");
          const menu = doc.getElementById("emailAddressPopup"), from = doc.querySelector("#fromRecipient0");
          (from.querySelector(".recipient-single-line, .recipient-multi-line-name") || from).click();
          await until(() => menu.state == "open", 3000);
          const item = doc.getElementById("editContactItem"); const shown = !!item && !item.hidden;
          if (shown) item.doCommand();
          menu.hidePopup();
          const panel = await until(() => { const p = doc.getElementById("editContactPanel"); return p?.state == "open" && p; }, 4000);
          const out = { shown, open: !!panel };
          if (panel) { await wait(300); const s = cs(panel), r = cs(doc.documentElement);
            Object.assign(out, { bg: s.getPropertyValue("--panel-background-color").trim(), want: r.getPropertyValue("--mt-tooltip-bg").trim(),
                                 border: s.getPropertyValue("--panel-border-color").trim(), wantBorder: r.getPropertyValue("--mt-tooltip-border").trim() });
            panel.hidePopup(); await wait(300); }
          book.deleteCards([card]); return out;""")
        ok = res.get("open") and res["bg"] == res["want"] and res["border"] == res["wantBorder"] and "262d3b" not in res["bg"].lower()
        return ok, f"{res}"
    check("Mailkopf: Panel „Kontakt bearbeiten“ mit neutraler Fläche wie die Tooltips", contact_panel, results)

    def message_tab():
        # Mail im eigenen Tab: kein Listenkopf, kein Grau der Ordnerliste; zurück im Mail-Tab wieder da
        res = m.js(READING_JS + r"""
          await showMail("Halo Jetzt"); await wait(500);
          const hdr = a3.gDBView.hdrForFirstSelectedMessage;
          tm.openTab("mailMessageTab", { messageURI: hdr.folder.getUriForMsg(hdr), background: false });
          await until(() => d.documentElement.getAttribute("mc-tab") == "mailMessageTab", 6000); await wait(1500);
          const row = d.getElementById("unifiedToolbarContainer"), status = d.getElementById("status-bar"), lh = d.getElementById("mcListHeader");
          const v = (el, n) => w.getComputedStyle(el).getPropertyValue(n).trim();
          const tab = { mode: d.documentElement.getAttribute("mc-tab"), header: lh && w.getComputedStyle(lh).display,
                        row: v(row, "--mc-sidebar-right"), status: v(status, "--mc-sidebar-right"), line: v(row, "--mc-list-right") };
          tm.closeTab(tm.currentTabInfo); await toMail(); await wait(1200);
          const mail = { mode: d.documentElement.getAttribute("mc-tab"), header: lh && w.getComputedStyle(lh).display, row: v(row, "--mc-sidebar-right") };
          return { tab, mail };""")
        t, ml = res["tab"], res["mail"]
        ok = (t["mode"] == "mailMessageTab" and t["header"] == "none" and t["row"] == "0px" and t["status"] == "0px" and t["line"] == "-10px"
              and ml["mode"] == "mail3PaneTab" and ml["header"] != "none" and float(ml["row"].replace("px", "") or 0) > 0)
        return ok, f"{res}"
    check("Mail im eigenen Tab: ohne Listenkopf und Seitenleisten-Grau, im Mail-Tab wieder vorhanden", message_tab, results)

    def list_date():
        # Uhrzeit in Liste und Kopf im selben Format (Regionaleinstellungen des Systems)
        res = m.js(READING_JS + r"""
          const doc = await showMail("Halo Jetzt");
          const hdr = a3.gDBView.hdrForFirstSelectedMessage;
          const row = await until(() => [...a3.document.querySelectorAll('#threadTree tr[is="thread-card"]')].find(r => (r.querySelector(".subject")?.textContent || "").includes("Halo Jetzt") && r.querySelector(".date")?.textContent), 6000);
          const norm = s => (s || "").replace(/\s+/g, " ").trim();
          // ältere Mail (vor zwei Tagen): ganzes Datum im Muster des Systems
          const oldHdr = [...f.messages].find(h => h.messageId == "halo-kopf-anhang@example.invalid");
          const oldRow = [...a3.document.querySelectorAll('#threadTree tr[is="thread-card"]')].find(r => (r.querySelector(".subject")?.textContent || "").includes("Halo Anhänge"));
          return { list: norm(row?.querySelector(".date")?.textContent), header: norm(doc.querySelector("#mcHdrMeta #dateLabel")?.textContent),
                   want: norm(new Services.intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date(hdr.date / 1000))),
                   old: norm(oldRow?.querySelector(".date")?.textContent), oldWant: oldHdr && norm(new Services.intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(oldHdr.date / 1000))) };""")
        ok = bool(res["list"]) and res["list"] == res["want"] and res["list"] in res["header"] and bool(res["old"]) and res["old"] == res["oldWant"]
        return ok, f"{res}"
    check("Mailliste und Mailkopf: Uhrzeit und Datum im Format der Regionaleinstellungen", list_date, results)

    def header_line():
        res = m.js(READING_JS + r"""
          const doc = await showMail("Halo Jetzt");
          const top = doc.getElementById("mail-notification-top"), header = doc.getElementById("messageHeader");
          return { top: parseFloat(cs(top).borderBottomWidth), header: parseFloat(cs(header).borderBottomWidth),
                   gap: Math.round((doc.getElementById("messagepane").getBoundingClientRect().top - header.getBoundingClientRect().bottom) * 10) / 10 };""")
        ok = res["top"] == 0 and res["header"] > 0 and res["gap"] <= 0.5
        return ok, f"{res}"
    check("Mailkopf: eine Linie zum Mailtext (keine zweite darunter)", header_line, results)

    def recipients():
        # viele Empfänger: „Mehr“ als graue Kapsel in 11 px; Kommas in Cc wie in An
        res = m.js(READING_JS + r"""
          const doc = await showMail("Halo Viele Empfänger");
          const btn = [...doc.querySelectorAll("#expandedtoBox .show-more-recipients")].find(vis);
          const accent = (() => { const e = doc.createElement("div"); e.style.color = "AccentColor"; doc.documentElement.append(e); const c = cs(e).color; e.remove(); return c; })();
          const comma = id => { const li = doc.querySelector(`#${id} li.header-recipient`); return li && cs(li, "::after").color; };
          return { more: !!btn, transform: btn && cs(btn).textTransform, size: btn && parseFloat(cs(btn).fontSize), bg: btn && cs(btn).backgroundColor, accent,
                   to: comma("expandedtoBox"), cc: comma("expandedccBox") };""")
        ok = (res["more"] and res["transform"] == "none" and res["size"] >= 11 and not same_color(res["bg"], res["accent"])
              and res["to"] and res["cc"] and same_color(res["to"], res["cc"]))
        return ok, f"{res}"
    check("Mailkopf: „Mehr“-Knopf als graue Kapsel in 11 px, Kommas in Cc wie in An", recipients, results)


# Verfassen-Fenster und seine Dialoge: Test-Identität (example.invalid, kein Server), Fenster öffnen/schließen,
# Editor-Dialoge (modal) erst nach dem Skript öffnen. Gewartet wird über den Zeitgeber des Moduls –
# solange ein modaler Dialog offen ist, ruhen die Zeitgeber der Fenster.
COMPOSE_CHECK_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  const { setTimeout: modTimeout } = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
  const pause = ms => new Promise(r => modTimeout(r, ms));
  const till = async (fn, ms = 8000) => { for (let t = 0; t < ms; t += 100) { const v = fn(); if (v) return v; await pause(100); } return fn(); };
  try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await pause(500); }
  const acc = MailServices.accounts.findAccountForServer(MailServices.accounts.localFoldersServer);
  if (!acc.identities.length) { const id = MailServices.accounts.createIdentity(); id.fullName = "Halo Test"; id.email = "halo@example.invalid"; acc.addIdentity(id); }
  const later = fn => w.setTimeout(() => { try { fn(); } catch (e) { console.error("Test:", e); } }, 0);
  const compose = async (o = {}) => {
    const params = Cc["@mozilla.org/messengercompose/composeparams;1"].createInstance(Ci.nsIMsgComposeParams);
    const fields = Cc["@mozilla.org/messengercompose/composefields;1"].createInstance(Ci.nsIMsgCompFields);
    fields.to = o.to ?? "Anna Beispiel <anna@example.invalid>"; fields.subject = o.subject ?? "Halo Entwurf";
    if (o.cc) fields.cc = o.cc;
    fields.body = o.body ?? "<p>Hallo Anna,</p><p>das ist ein Testentwurf.</p>";
    params.composeFields = fields; params.identity = acc.identities[0]; params.format = o.plain ? Ci.nsIMsgCompFormat.PlainText : Ci.nsIMsgCompFormat.HTML;
    const before = new Set(Services.wm.getEnumerator("msgcompose"));
    MailServices.compose.OpenComposeWindowWithParams(null, params);
    const cw = await till(() => [...Services.wm.getEnumerator("msgcompose")].find(x => !before.has(x) && x.document.readyState == "complete" && x.gMsgCompose), 12000);
    if (!cw) throw new Error("Verfassen-Fenster nicht offen");
    cw.resizeTo(o.width ?? 1000, 760); await pause(1800); return cw; };
  const closeCompose = async cw => { if (!cw || cw.closed) return; cw.gContentChanged = false; if (cw.gMsgCompose) cw.gMsgCompose.bodyModified = false;
    cw.close(); await till(() => cw.closed, 4000); await pause(300); };
  // mit Verfassen-Fenster: fn(cw, cd), danach das Fenster immer schließen
  const withCompose = async (o, fn) => { const cw = await compose(o); try { return await fn(cw, cw.document); } finally { await closeCompose(cw); } };
  const winUrl = (part, ms = 10000) => till(() => [...Services.wm.getEnumerator(null)].find(x => x.location.href.includes(part) && x.document.readyState == "complete"), ms);
  // Dialog über „Abbrechen“ schließen (die Rechtschreibprüfung gibt nur so ihr Verfassen-Fenster wieder frei)
  const shut = async x => { for (let i = 0; i < 3 && x && !x.closed; i++) {
    try { const dl = x.document.querySelector("dialog"); if (i == 0 && dl?.cancelDialog) dl.cancelDialog(); else x.close(); } catch {}
    await till(() => x.closed, 2000); } await pause(200); };
  // modalen Dialog über einen Befehl öffnen: fn(dw, dd), danach schließen
  const dialog = async (open, part, fn) => { later(open); const dw = await winUrl(part); if (!dw) throw new Error(part + " nicht offen");
    await pause(800); try { return await fn(dw, dw.document); } finally { await shut(dw); } };
  // Fenster nach vorn, damit :focus greift
  const front = async x => { x.focus(); await till(() => Services.focus.activeWindow == x, 3000); await pause(200); };
  const csOf = (el, pseudo) => el.ownerDocument.defaultView.getComputedStyle(el, pseudo);
  // berechnete Farbe eines Werts (AccentColor, var(--mt-…)) im Dokument
  const colorOf = (doc, value, prop = "color") => { const e = doc.createElementNS("http://www.w3.org/1999/xhtml", "div"); e.style[prop] = value;
    doc.documentElement.append(e); const c = csOf(e)[prop]; e.remove(); return c; };
  const vis = el => !!el && el.getClientRects().length > 0 && el.getBoundingClientRect().width > 0;
  const rgba = c => { const v = (String(c).match(/-?[\d.]+(?:e-?\d+)?/g) || []).map(Number); const k = String(c).startsWith("color(") ? 255 : 1;
    return [v[0] * k, v[1] * k, v[2] * k, v.length > 3 ? v[3] : 1]; };
  // Farbe über einem Grund gemischt, relative Leuchtdichte, senkrechte Mitte eines Elements
  const over = (fg, bg) => fg.slice(0, 3).map((x, i) => x * fg[3] + bg[i] * (1 - fg[3])).concat(1);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const mid = el => { if (!el) return null; const r = el.getBoundingClientRect(); return Math.round((r.top + r.height / 2) * 10) / 10; };
  const dark = w.matchMedia("(prefers-color-scheme: dark)").matches;
  const testFolder = async () => { const root = MailServices.accounts.localFoldersServer.rootFolder;
    if (!root.containsChildNamed("Lesen")) { root.createSubfolder("Lesen", null); await pause(800); } return root.getChildNamed("Lesen"); };"""


def compose_checks(m, results):
    """Verfassen-Fenster und Editor-Dialoge: Kästchen, Anhänge, Textfläche, Hinweisleiste, Felder, Kontakte, Rückfragen,
    Listen, Reiter, Anpassen, Trennlinie, Empfängerzeilen, schmale Symbolleiste."""

    def checkboxes():
        # angehakt mit Haken: data:-Bilder sperrt die CSP der Dialoge (default-src chrome:) – nur die blaue Fläche blieb
        res = m.js(COMPOSE_CHECK_JS + r"""
          const look = (dd, cb) => { const s = csOf(cb.querySelector(".checkbox-check"));
            return { img: s.backgroundImage, fill: s.fill, bg: s.backgroundColor, accent: colorOf(dd, "AccentColor"), accentText: colorOf(dd, "AccentColorText") }; };
          const out = {};
          out.replace = await withCompose({}, cw => dialog(() => cw.goDoCommand("cmd_findReplace"), "EdReplace", async (dw, dd) => {
            const blocked = []; dd.addEventListener("securitypolicyviolation", e => blocked.push(e.blockedURI));
            const cb = dd.getElementById("dialog.wrap"), was = cb.checked;
            cb.checked = false; await pause(100); cb.checked = true; await pause(400);
            const r = look(dd, cb); r.blocked = blocked; cb.checked = was; return r; }));
          const f = await testFolder(); tm.switchToTab(0); await pause(500); const a3 = tm.currentAbout3Pane; a3.displayFolder(f.URI); await pause(800);
          out.folder = await dialog(() => a3.commandController.doCommand("cmd_properties"), "folderProps", async (dw, dd) => {
            const cb = [...dd.querySelectorAll("checkbox")].find(vis), was = cb.checked;
            cb.checked = true; await pause(300); const r = look(dd, cb); cb.checked = was; return r; });
          return out;""")
        def good(r):
            return (r["img"].startswith('url("chrome://') and "data:" not in r["img"]
                    and same_color(r["fill"], r["accentText"]) and same_color(r["bg"], r["accent"]))
        ok = good(res["replace"]) and not res["replace"]["blocked"] and good(res["folder"])
        return ok, f"{res}"
    check("Dialoge: angehakte Kästchen mit Haken (chrome://-Grafik, die CSP sperrt data:) – Suchen/Ersetzen, Ordner-Eigenschaften", checkboxes, results)

    def attachments():
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async (cw, cd) => {
            const atts = [];
            for (const n of ["Halo Anhang eins.txt", "Halo Anhang zwei.txt"]) { const path = PathUtils.join(PathUtils.profileDir, n);
              if (!await IOUtils.exists(path)) await IOUtils.writeUTF8(path, "Erfundene Testdatei\n");
              const a = Cc["@mozilla.org/messengercompose/attachment;1"].createInstance(Ci.nsIMsgAttachment); a.url = PathUtils.toFileURI(path); a.name = n; a.size = 30; atts.push(a); }
            cw.AddAttachments(atts);
            if (!await till(() => cw.gAttachmentBucket?.itemCount >= 2, 5000)) return { attached: false };
            await pause(800); await front(cw);
            const area = cd.getElementById("attachmentArea"), bucket = cd.getElementById("attachmentBucket");
            bucket.selectedIndex = 0; bucket.focus(); await pause(300);
            const item = bucket.querySelector(".attachmentItem[selected]"), s = csOf(item);
            const focused = { focus: bucket.matches(":focus"), bg: s.backgroundColor, radius: parseFloat(s.borderTopLeftRadius), outline: s.outlineStyle, border: parseFloat(s.borderTopWidth) };
            cd.getElementById("msgSubject").focus(); await pause(300);
            return { attached: true, focused, unfocused: csOf(item).backgroundColor, accent: colorOf(cd, "AccentColor"),
                     summary: csOf(area.querySelector("summary")).backgroundColor, bucket: csOf(bucket).backgroundColor,
                     header: csOf(cd.getElementById("MsgHeadersToolbar")).backgroundColor, bucketBorder: parseFloat(csOf(bucket).borderTopWidth),
                     size: csOf(cd.getElementById("attachmentBucketSize")).backgroundColor }; });""")
        f = res.get("focused") or {}
        ok = (res.get("attached") and same_color(res["summary"], res["header"]) and same_color(res["bucket"], res["header"]) and res["bucketBorder"] == 0
              and f["focus"] and same_color(f["bg"], res["accent"]) and f["radius"] >= 6 and f["outline"] == "none" and f["border"] == 0
              and not same_color(res["unfocused"], res["accent"]) and rgba_alpha(res["size"]) == 0)
        return ok, f"{res}"
    check("Verfassen: Anhänge auf der Fläche des Fensters, markierte Datei abgerundet ohne Rahmen (unfokussiert grau), Größe ohne Plakette", attachments, results)

    def body():
        # Textfläche in der Fläche des Fensters (dunkel sonst bläulich #2a2a2e); eigene Hintergründe der Mail bleiben
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async (cw, cd) => {
            const ed = cw.GetCurrentEditorElement().contentDocument; const b = ed.body;
            const out = { dark, body: csOf(b).backgroundColor, header: csOf(cd.getElementById("MsgHeadersToolbar")).backgroundColor,
                          area: csOf(cd.getElementById("messageArea")).backgroundColor, box: csOf(cd.getElementById("composeContentBox")).backgroundColor };
            b.setAttribute("bgcolor", "#ffffcc"); await pause(200); out.own = csOf(b).backgroundColor; b.removeAttribute("bgcolor");
            return out; });""")
        ok = same_color(res["area"], res["header"]) and same_color(res["box"], res["header"]) and same_color(res["own"], "rgb(255, 255, 204)")
        # hell bleibt der Körper weiß (bzw. durchsichtig auf weißem Grund)
        ok = ok and (same_color(res["body"], res["header"]) if res["dark"]
                     else rgba_alpha(res["body"]) == 0 or same_color(res["body"], "rgb(255, 255, 255)"))
        return ok, f"{res}"
    check("Verfassen: Textfläche und Fugen in der Fläche des Fensters (dunkel kein zweites Grau), eigene Hintergrundfarbe bleibt", body, results)

    def reminder():
        # Hinweis „Anhang vergessen?“: „Später erinnern“ als Kapsel wie „Anhang hinzufügen“, Leiste ohne violettgrauen Rand
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({ body: "<p>Hallo Anna,</p><p>im Anhang findest du das Dokument (attached).</p>" }, async (cw, cd) => {
            await cw.gAttachmentNotifier.checkForAttachmentKeywords?.();
            const msg = await till(() => cd.querySelector('notification-message[value="attachmentReminder"]'), 6000);
            if (!msg) return { bar: false };
            await pause(800);
            const all = sel => [...msg.querySelectorAll(sel), ...(msg.shadowRoot?.querySelectorAll(sel) || [])].find(vis);
            const b = all("button.notification-button"), t = all("toolbarbutton.notification-button");
            if (!b || !t) return { bar: true, buttons: false };
            const rb = b.getBoundingClientRect(), rt = t.getBoundingClientRect(), st = csOf(t);
            const stack = msg.closest(".notificationbox-stack") || cd.querySelector("#compose-notification-bottom .notificationbox-stack");
            return { bar: true, buttons: true, heights: [rb.height, rt.height], mids: [rb.top + rb.height / 2, rt.top + rt.height / 2],
                     radius: parseFloat(st.borderTopLeftRadius), border: parseFloat(st.borderTopWidth),
                     innerBorder: parseFloat(csOf(t.querySelector(".toolbarbutton-menubutton-button")).borderTopWidth),
                     // die gelbe Fläche (Schatten-DOM, fest 4 px) wird vom runden Rand der Leiste zugeschnitten
                     host: parseFloat(csOf(msg).borderTopLeftRadius), clip: csOf(msg).overflowX,
                     container: parseFloat(csOf(msg.shadowRoot.querySelector(".container")).borderTopLeftRadius),
                     stack: stack && csOf(stack).backgroundColor, header: csOf(cd.getElementById("MsgHeadersToolbar")).backgroundColor }; });""")
        ok = (res.get("buttons") and abs(res["heights"][0] - res["heights"][1]) <= 1 and abs(res["mids"][0] - res["mids"][1]) <= 1
              and res["radius"] >= 14 and res["border"] == 0 and res["innerBorder"] == 0
              and res["host"] >= 10 and (res["container"] >= 10 or res["clip"] in ("clip", "hidden"))
              and res["stack"] and same_color(res["stack"], res["header"]))
        return ok, f"{res}"
    check("Verfassen: Hinweis „Anhang vergessen?“ – „Später erinnern“ als Kapsel gleich hoch wie „Anhang hinzufügen“, runde Leiste ohne Rand", reminder, results)

    def dialog_fields():
        # Felder in Dialogen 28 px wie die Auswahllisten daneben, Zahlenfelder bleiben breit genug
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async cw => {
            const out = {};
            out.table = await dialog(() => cw.goDoCommand("cmd_InsertTable"), "EdInsertTable", async (dw, dd) => {
              const rows = dd.getElementById("rowsInput"), wi = dd.getElementById("widthInput"), ml = dd.getElementById("widthPixelOrPercentMenulist");
              const was = wi.value; wi.value = "100"; await pause(100);
              const r = { rows: rows.getBoundingClientRect().height, width: wi.getBoundingClientRect().height, menulist: ml.getBoundingClientRect().height,
                          scroll: wi.scrollWidth, client: wi.clientWidth };
              wi.value = was; return r; });
            out.replace = await dialog(() => cw.goDoCommand("cmd_findReplace"), "EdReplace", async (dw, dd) => dd.getElementById("dialog.findInput").getBoundingClientRect().height);
            return out; });""")
        t = res["table"]
        ok = t["rows"] <= 29 and abs(t["width"] - t["menulist"]) <= 1 and t["scroll"] <= t["client"] and res["replace"] <= 29
        return ok, f"{res}"
    check("Dialoge: Eingabefelder 28 px hoch wie die Auswahllisten daneben, „100“ im Zahlenfeld ganz sichtbar", dialog_fields, results)

    def contacts():
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async (cw, cd) => {
            cw.toggleContactsSidebar();
            const d2 = await till(() => { const b = cd.getElementById("contactsBrowser"); const x = b?.contentDocument;
              return x?.readyState == "complete" && x.getElementById("abResultsTree") && x; }, 6000);
            if (!d2) return { open: false };
            await pause(1000);
            const tree = d2.getElementById("abResultsTree"), list = d2.getElementById("addressbookList"), label = d2.querySelector("label[control]");
            const head = cd.querySelector("#contactsSidebar > .sidebar-header");
            return { open: true, tree: csOf(tree).backgroundColor, root: csOf(d2.documentElement).backgroundColor,
                     listBorder: parseFloat(csOf(list).borderTopWidth), listRadius: parseFloat(csOf(list).borderTopLeftRadius),
                     labelMargin: label && parseFloat(csOf(label).marginInlineStart),
                     headLine: csOf(head).borderBottomColor, line: colorOf(cd, "var(--mt-pane-line)") }; });""")
        ok = (res.get("open") and (rgba_alpha(res["tree"]) == 0 or same_color(res["tree"], res["root"])) and not same_color(res["tree"], "rgb(0, 0, 0)")
              and res["listBorder"] == 0 and res["listRadius"] >= 12 and (res["labelMargin"] or 0) >= 6 and same_color(res["headLine"], res["line"]))
        return ok, f"{res}"
    check("Verfassen: Kontakte-Seitenleiste durchgehend im Seitenleisten-Grau, Adressbuch-Auswahl als Kapsel, Abstand zum Rand", contacts, results)

    def common_dialog():
        # Rückfragen (hier die des Verfassen-Fensters wie „Speichern?“) dunkel neutral wie die übrigen Dialoge,
        # ohne violettgrauen Farbstich; hell weiß. Sie gehört nicht zum Hauptfenster – Marionette lässt sie offen
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async cw => {
            let done = false;
            cw.setTimeout(() => Services.prompt.asyncConfirm(cw.browsingContext, Services.prompt.MODAL_TYPE_WINDOW, "Halo", "Test")
              .finally(() => { done = true; }), 0);
            const dw = await winUrl("commonDialog");
            if (!dw) return { open: false };
            await pause(600);
            const dl = dw.document.querySelector("dialog");
            const own = csOf(dl).backgroundColor, rootBg = csOf(dw.document.documentElement).backgroundColor;
            dl.cancelDialog(); await till(() => done && dw.closed, 4000);
            return { open: true, dark, dialog: own, root: rootBg, visible: rgba(own)[3] > 0 ? own : rootBg }; });""")
        c = res.get("visible", "")
        import re
        v = [float(x) for x in re.findall(r"-?[\d.]+", c)][:3]
        if res.get("dark"):
            ok = len(v) == 3 and max(abs(v[0] - v[1]), abs(v[1] - v[2]), abs(v[0] - v[2])) <= 3 and not same_color(c, "rgb(66, 65, 77)")
        elif sys.platform == "darwin":
            ok = len(v) == 3 and min(v) >= 250
        else:
            # hell bleibt Thunderbirds Fläche – unter Linux das helle Grau von GTK (246, 245, 244)
            ok = len(v) == 3 and min(v) >= 240 and max(v) - min(v) <= 3
        return bool(res.get("open")) and ok, f"{res}"
    check("Rückfragen: neutrale Fläche (dunkel ohne violettgrauen Farbstich, hell weiß)", common_dialog, results)

    def lists():
        # Listen in Dialogen ohne harten macOS-Rahmen, Auswahl abgerundet in Akzentfarbe (unfokussiert grau)
        res = m.js(COMPOSE_CHECK_JS + r"""
          const out = {};
          out.spell = await withCompose({ body: "<p>Ein Tset mit Fehlrn und noch mehr Fehlren.</p>" }, cw =>
            dialog(() => cw.goDoCommand("cmd_spelling"), "EdSpellCheck", async (dw, dd) => {
              await pause(600);
              const list = dd.getElementById("SuggestedList");
              if (!list.itemCount) list.appendItem("Probe");
              if (list.selectedIndex < 0) list.selectedIndex = 0;
              await front(dw); list.focus(); await pause(300);
              const item = list.selectedItem;
              const r = { appearance: csOf(list).appearance, radius: parseFloat(csOf(item).borderTopLeftRadius), focus: list.matches(":focus"),
                          focused: csOf(item).backgroundColor, accent: colorOf(dd, "AccentColor") };
              dd.getElementById("ReplaceWordInput").focus(); await pause(300); r.unfocused = csOf(item).backgroundColor;
              return r; }));
          // Filter-Editor: Zeilen mit Menülisten und Feldern behalten ihre Farben
          const f = await testFolder(); w.MsgFilters(null, f);
          const lw = await winUrl("FilterListDialog"); if (!lw) throw new Error("Filterliste nicht offen");
          await pause(1000);
          try {
            out.filter = await dialog(() => lw.onNewFilter(), "FilterEditor", async (dw, dd) => {
              // „Apply filter when:“ bündig und gleich groß wie „Filter name:“, Kästchen eingerückt
              const leg = dd.querySelector("#applyFiltersSettings > legend"), lab = dd.getElementById("filterName").previousElementSibling,
                    cb = dd.getElementById("runManual");
              return { terms: csOf(dd.getElementById("searchTermList")).appearance, actions: csOf(dd.getElementById("filterActionList")).appearance,
                       legend: [leg.getBoundingClientRect().left, parseFloat(csOf(leg).fontSize), parseInt(csOf(leg).fontWeight)],
                       label: [lab.getBoundingClientRect().left, parseFloat(csOf(lab).fontSize)], box: cb.getBoundingClientRect().left }; });
          } finally { await shut(lw); }
          return out;""")
        s, f = res["spell"], res["filter"]
        ok = (s["appearance"] == "none" and s["radius"] >= 6 and s["focus"] and same_color(s["focused"], s["accent"])
              and not same_color(s["unfocused"], s["accent"]) and f["terms"] == "none" and f["actions"] == "none"
              and abs(f["legend"][0] - f["label"][0]) <= 1 and abs(f["legend"][1] - f["label"][1]) < 0.5
              and 500 <= f["legend"][2] <= 650 and f["box"] >= f["legend"][0] + 8)
        return ok, f"{res}"
    check("Dialoge: Listen ohne harten Rahmen, Auswahl abgerundet in Akzentfarbe (Rechtschreibung), Filter-Editor ohne macOS-Rahmen, „Apply filter when:“ bündig und gleich groß", lists, results)

    def tabs():
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, cw => dialog(() => cw.goDoCommand("cmd_image"), "EdImageProps", async (dw, dd) => {
            const tabs = dd.querySelector("tabs"), t = tabs.querySelector("tab[selected]"), u = tabs.querySelector("tab:not([selected])");
            const s = csOf(t), after = csOf(t, "::after");
            return { bottom: parseFloat(s.borderBottomWidth), radius: parseFloat(s.borderTopLeftRadius), bg: s.backgroundColor,
                     control: colorOf(dd, "var(--mt-control)", "backgroundColor"), after: [after.display, after.content],
                     tabsLine: parseFloat(csOf(tabs).borderBottomWidth), other: csOf(u).backgroundColor }; }));""")
        ok = (res["bottom"] == 0 and res["radius"] >= 12 and same_color(res["bg"], res["control"])
              and (res["after"][0] == "none" or res["after"][1] == "none") and res["tabsLine"] == 0 and rgba_alpha(res["other"]) == 0)
        return ok, f"{res}"
    check("Dialoge: Reiter als Segment-Kapseln ohne Strich und Linie (Bild einfügen)", tabs, results)

    def customize():
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async (cw, cd) => {
            cw.CustomizeMailToolbar("compose-toolbox", "CustomizeComposeToolbar");
            // macOS als Sheet im Fenster, Linux/Windows als eigenes Fenster (toolbar.customization.usesheet)
            const frame = cd.getElementById("customizeToolbarSheetIFrame");
            const ready = x => x?.readyState == "complete" && x.getElementById("palette-box")?.querySelector("toolbarspring") && x;
            const d2 = await till(() => ready(frame?.contentDocument)
              || ready([...Services.wm.getEnumerator(null)].find(x => x.location.href.includes("customizeToolbar"))?.document), 8000);
            if (!d2) return { open: false };
            await pause(800);
            const box = d2.getElementById("palette-box"), spring = box.querySelector("toolbarspring"), s = csOf(box);
            const out = { open: true, border: parseFloat(s.borderTopWidth), radius: parseFloat(s.borderTopLeftRadius), bg: s.backgroundColor,
                          spring: [csOf(spring).borderTopStyle, parseFloat(csOf(spring).borderTopLeftRadius)] };
            try { d2.defaultView.onClose(); } catch {} await pause(800);
            return out; });""")
        ok = res.get("open") and res["border"] == 0 and res["radius"] >= 8 and rgba_alpha(res["bg"]) <= 0.15 and res["spring"][0] == "dashed" and res["spring"][1] >= 4
        return ok, f"{res}"
    check("Verfassen: Anpassen-Sheet mit ruhiger Palette ohne Rahmen, Platzhalter gestrichelt und gerundet", customize, results)

    def compose_panels():
        # Rand (und beim Anordnen-Panel die Fläche) neutral wie die Tooltips statt Thunderbirds bläulichem Panelgrau
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async (cw, cd) => {
            const val = (el, v) => { const x = csOf(el).getPropertyValue(v).trim(); return x ? colorOf(cd, x, "backgroundColor") : ""; };
            const out = { border: colorOf(cd, "var(--mt-tooltip-border)", "backgroundColor"), bg: colorOf(cd, "var(--mt-tooltip-bg)", "backgroundColor") };
            const look = p => p ? { border: val(p, "--panel-border-color"), bg: val(p, "--panel-background-color") } : null;
            for (const id of ["reorderAttachmentsPanel", "customizeToolbarSheetPopup"]) out[id] = look(cd.getElementById(id));
            // Adressvorschläge: die Empfängerfelder legen ein eigenes, namenloses Panel an (nicht #PopupAutoComplete) –
            // in das An-Feld tippen und das tatsächlich offene Panel messen, samt berechnetem Rand der Inhaltsfläche
            const inp = cd.querySelector(".address-row:not(.hidden) input.address-row-input, #toAddrInput");
            inp.focus(); inp.value = "an"; inp.controller.handleText();
            await till(() => inp.controller.matchCount > 0, 5000);
            if (inp.popup.state != "open") inp.openPopup();
            const ac = await till(() => [...cd.querySelectorAll('panel[type="autocomplete-richlistbox"]')].find(p => p.state == "open"), 4000);
            out.autocomplete = look(ac);
            if (ac) { out.autocomplete.id = ac.id; const c = ac.shadowRoot?.querySelector('[part~="content"]');
              out.autocomplete.content = c ? csOf(c).borderTopColor : null; ac.hidePopup(); }
            inp.value = ""; await pause(300);
            return out; });""")
        ids = ["reorderAttachmentsPanel", "autocomplete", "customizeToolbarSheetPopup"]
        # Thunderbirds Panelrand #5e7799 / #91939f und Panelfläche #262d3b (Deckkraft egal)
        rgb = lambda c: "rgb(" + ", ".join(__import__("re").findall(r"-?[\d.]+", c or "")[:3]) + ")"
        bluish = lambda c: any(same_color(rgb(c), t, 4) for t in ["rgb(94, 119, 153)", "rgb(145, 147, 159)", "rgb(38, 45, 59)"])
        ac = res.get("autocomplete") or {}
        # Adressvorschläge: auch die Fläche unter der halbtransparenten Haarlinie neutral (sonst färbt sie den Rand bläulich)
        ok = (ac.get("bg") and not bluish(ac["bg"]) and all(res.get(i) and same_color(res[i]["border"], res["border"]) and not bluish(res[i]["border"]) for i in ids)
              and (ac.get("content") is None or (same_color(ac["content"], res["border"]) and not bluish(ac["content"])))
              and same_color(res["reorderAttachmentsPanel"]["bg"], res["bg"]) and not bluish(res["reorderAttachmentsPanel"]["bg"]))
        return ok, f"{res}"
    check("Verfassen: Anhänge-anordnen-Panel neutral wie Tooltips, Adressvorschläge und Anpassen-Sheet mit Haarlinie statt bläulichem Rand", compose_panels, results)

    def format_toolbox():
        # Reintext: Thunderbird blendet nur die Formatleiste aus – die leere Box darf keine zweite Linie unter den Betreff legen;
        # Farbfelder: dezenter Rand statt Thunderbirds rgba(255, 255, 255, 0.7), Ring in Fensterfarbe trennt Text- und Hintergrundfeld
        res = m.js(COMPOSE_CHECK_JS + r"""
          const html = await withCompose({}, async (cw, cd) => {
            const box = cd.getElementById("FormatToolbox"), t = cd.getElementById("TextColorButton"), b = cd.getElementById("BackgroundColorButton");
            return { line: parseFloat(csOf(box).borderBottomWidth), style: csOf(box).borderBottomStyle,
                     shadow: csOf(t).boxShadow, window: colorOf(cd, "var(--mt-window)"), swatch: colorOf(cd, "var(--mt-swatch-border)"),
                     borders: [csOf(t).borderTopColor, csOf(b).borderTopColor] }; });
          const plain = await withCompose({ plain: true, body: "Hallo Anna,\n\ndas ist ein Testentwurf." }, async (cw, cd) => {
            const box = cd.getElementById("FormatToolbox");
            return { barHidden: cd.getElementById("FormatToolbar").hidden, line: parseFloat(csOf(box).borderBottomWidth), style: csOf(box).borderBottomStyle }; });
          return { html, plain };""")
        h, p = res["html"], res["plain"]
        ok = (h["line"] > 0 and h["style"] != "none" and p["barHidden"] and (p["line"] == 0 or p["style"] == "none")
              and h["window"] in h["shadow"] and all(same_color(c, h["swatch"]) and not same_color(c, "rgba(255, 255, 255, 0.7)") for c in h["borders"]))
        return ok, f"{res}"
    check("Verfassen: Formatleiste mit einer Haarlinie, im Reintext keine zweite Linie unter dem Betreff; Farbfelder mit dezentem Rand und Ring in Fensterfarbe", format_toolbox, results)

    def separator():
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, cw => dialog(() => cw.goDoCommand("cmd_link"), "EdLinkProps", async (dw, dd) => {
            const s = dd.getElementById("advancedSeparator");
            return { border: csOf(s).borderTopWidth, height: s.getBoundingClientRect().height, bg: csOf(s).backgroundColor,
                     line: colorOf(dd, "var(--mt-pane-line)", "backgroundColor") }; }));""")
        ok = res["border"] == "0px" and res["height"] <= 1 and same_color(res["bg"], res["line"])
        return ok, f"{res}"
    check("Dialoge: Trennlinie über OK/Abbrechen als Haarlinie (Link einfügen)", separator, results)

    # Empfängerzeilen: vier Empfänger in An (bricht bei 860 px um), einer in Cc, Bcc leer eingeblendet – ein Fenster für drei Prüfungen
    rcpt = {}

    def recipients():
        if not rcpt:
            rcpt.update(m.js(COMPOSE_CHECK_JS + r"""
              const to = "Anna Beispiel <anna@example.invalid>, Ben Muster <ben@example.invalid>, Carla Ölmann <carla@example.invalid>, "
                + "Dr. Maximilian Alexander von Langenname-Überlänge <maximilian.von.langenname@example.invalid>";
              return await withCompose({ to, cc: "Projektteam <team@example.invalid>", width: 860 }, async (cw, cd) => {
                const pills = () => [...cd.querySelectorAll("#toAddrContainer mail-address-pill")];
                const top = p => Math.round(p.getBoundingClientRect().top), left = p => Math.round(p.getBoundingClientRect().left * 10) / 10;
                const rows = () => new Set(pills().map(top)).size;
                for (const width of [760, 680]) { if (rows() >= 2) break; cw.resizeTo(width, 760); await pause(800); }
                cw.showAndFocusAddressRow("addressRowBcc"); await pause(500);
                const all = pills(), first = all[0], textLeft = el => el.getBoundingClientRect().left + parseFloat(csOf(el).paddingLeft);
                const bar = csOf(cd.getElementById("MsgHeadersToolbar")).backgroundColor, bcc = cd.querySelector("#bccAddrContainer .address-input");
                const out = { dark, rows: rows(), bar, pill: csOf(first).backgroundColor,
                  to: [mid(cd.getElementById("toAddrLabel")), mid(first)],
                  cc: [mid(cd.getElementById("ccAddrLabel")), mid(cd.querySelector("#ccAddrContainer mail-address-pill"))],
                  bcc: [mid(cd.getElementById("bccAddrLabel")), mid(bcc)],
                  first: left(first), wrapped: all.filter(p => top(p) > top(first) + 4).map(left),
                  bccText: textLeft(bcc), subjectText: textLeft(cd.getElementById("msgSubject")) };
                out.pillLum = lum(over(rgba(out.pill), rgba(bar))); out.barLum = lum(rgba(bar));
                // Zustände ohne Übergang messen (verdeckte Testfenster halten Übergänge an)
                const p = all[1]; p.style.transition = "none";
                p.setAttribute("selected", "selected"); await pause(150); out.selected = csOf(p).backgroundColor; p.removeAttribute("selected");
                p.classList.add("invalid-address"); await pause(150); out.invalid = csOf(p).backgroundColor; p.classList.remove("invalid-address");
                p.style.transition = ""; out.accent = colorOf(cd, "AccentColor");
                return out; });"""))
        return rcpt

    def labels():
        r = recipients()
        ok = all(a is not None and b is not None and abs(a - b) <= 1.5 for a, b in (r["to"], r["cc"], r["bcc"]))
        return ok, f"Mitte Beschriftung/Pille: An {r['to']}, Cc {r['cc']}, Bcc leer (Eingabefeld) {r['bcc']}"
    check("Verfassen: „An“, „Cc“ und „Bcc“ auf der Höhe der ersten Pille bzw. des leeren Eingabefelds", labels, results)

    def wrap():
        r = recipients()
        ok = (r["rows"] >= 2 and r["wrapped"] and all(abs(x - r["first"]) <= 0.5 for x in r["wrapped"])
              and abs(r["bccText"] - r["subjectText"]) <= 1)
        return ok, (f"{r['rows']} Zeilen, erste Pille links {r['first']}, umbrochene {r['wrapped']}; "
                    f"Text leeres Bcc {r['bccText']} gegen Betreff {r['subjectText']}")
    check("Verfassen: umbrochene Empfänger-Pillen beginnen bündig mit der ersten, leeres Feld bündig mit dem Betreff", wrap, results)

    def pill_color():
        r = recipients()
        # dunkel heller als die Fläche (vorher dunkler: „Löcher“), hell weiter Thunderbirds Grau (dunkler als die Fläche)
        lighter = r["pillLum"] > r["barLum"] if r["dark"] else r["pillLum"] < r["barLum"]
        ok = lighter and same_color(r["selected"], r["accent"]) and same_color(r["invalid"], "rgb(215, 0, 34)")
        return ok, (f"Pille {r['pill']} auf {r['bar']} (Leuchtdichte {r['pillLum']:.4f} gegen {r['barLum']:.4f}), "
                    f"ausgewählt {r['selected']} (Akzent {r['accent']}), ungültige Adresse {r['invalid']}")
    check("Verfassen: Empfänger-Pillen dunkel heller als die Fläche; Auswahl und Warnfarbe ungültiger Adressen bleiben", pill_color, results)

    def narrow_toolbar():
        # schmales Fenster: nur Symbole statt gekürzter Beschriftungen, Formatleiste innerhalb des Fensters; breit wieder mit Beschriftung
        res = m.js(COMPOSE_CHECK_JS + r"""
          return await withCompose({}, async (cw, cd) => {
            const bar = cd.getElementById("composeToolbar2"), fmt = cd.getElementById("FormatToolbar"), box = cd.getElementById("compose-toolbox");
            const state = () => { const texts = [...bar.querySelectorAll(":scope > toolbarbutton .toolbarbutton-text")].filter(vis);
              return { width: cw.innerWidth, icons: bar.hasAttribute("mc-icons-only"), labels: texts.length,
                       cut: texts.filter(t => t.scrollWidth > t.clientWidth + 1).map(t => t.value || t.textContent),
                       overflow: bar.scrollWidth - bar.clientWidth, fmt: [fmt.scrollWidth, fmt.clientWidth],
                       outside: [...fmt.children].filter(c => vis(c) && c.getBoundingClientRect().right > cw.innerWidth + 0.5).map(c => c.id || c.localName) }; };
            const size = async width => { cw.resizeTo(width, 700); await till(() => cw.innerWidth == width, 3000); await pause(900); return state(); };
            const out = { mode: box.getAttribute("mode") };
            out.narrow = await size(640); out.tiny = await size(560); out.wide = await size(1000);
            // Modus „nur Text“: Beschriftungen bleiben auch schmal (sonst leere Knöpfe)
            box.setAttribute("mode", "text"); out.text = await size(640);
            box.setAttribute("mode", out.mode || "full"); await pause(300);
            return out; });""")
        n, t, wd, tx = res["narrow"], res["tiny"], res["wide"], res["text"]
        fits = lambda s: not s["cut"] and s["overflow"] <= 1 and s["fmt"][0] <= s["fmt"][1] + 1 and not s["outside"]
        ok = (n["icons"] and n["labels"] == 0 and fits(n) and t["icons"] and fits(t)
              and not wd["icons"] and wd["labels"] >= 3 and fits(wd)
              and not tx["icons"] and tx["labels"] >= 3)
        return ok, f"{res}"
    check("Verfassen: schmales Fenster zeigt nur Symbole statt gekürzter Beschriftungen, Formatleiste bleibt im Fenster; breit wieder mit Beschriftung", narrow_toolbar, results)


DIALOG_READING_JS = READING_JS + r"""
  const { setTimeout: modT } = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
  const nap = ms => new Promise(r => modT(r, ms));
  const tillM = async (fn, ms = 8000) => { for (let t = 0; t < ms; t += 100) { const v = fn(); if (v) return v; await nap(100); } return fn(); };
  const winOf = (part, ms = 10000) => tillM(() => [...Services.wm.getEnumerator(null)].find(x => x.location.href.includes(part) && x.document.readyState == "complete"), ms);
  const colorIn = (doc, value, prop = "color") => { const e = doc.createElementNS("http://www.w3.org/1999/xhtml", "div"); e.style[prop] = value;
    (doc.body || doc.documentElement).append(e); const c = doc.defaultView.getComputedStyle(e)[prop]; e.remove(); return c; };"""


def dialog_checks(m, results):
    """Seltene Dialoge: Ordnerwahl der Suchordner, Filterprotokoll, „Ordner komprimieren?“, Filterliste/Suche/OpenPGP,
    Druckvorschau, Gespeicherte Dateien, „Öffnen von …“."""

    def folder_picker():
        # Suchordner → „Choose…“: Liste in der Inhaltsfläche mit Haarlinie (dunkel vorher tiefschwarz), Kästchen im macOS-Stil
        # mit chrome://-Haken (die CSP sperrt data:); im Suchordner-Dialog +/− mittig zur Bedingungszeile
        res = m.js(COMPOSE_CHECK_JS + r"""
          const f = await testFolder(); tm.switchToTab(0); await pause(500); const a3 = tm.currentAbout3Pane; a3.displayFolder(f.URI); await pause(800);
          return await dialog(() => a3.commandController.doCommand("cmd_newVirtualFolder"), "virtualFolderProperties", async (dw, dd) => {
            const row = dd.querySelector("#searchTermList > richlistitem");
            const btn = [...row.querySelectorAll(".small-button")].find(vis), ml = [...row.querySelectorAll("menulist")].find(vis);
            const out = { mids: [mid(btn), mid(ml)] };
            // die Ordnerwahl ist modal zum Dialog – über dessen Zeitgeber öffnen, sonst wartet dieses Skript, bis sie zu ist
            dw.setTimeout(() => dd.getElementById("folderListPicker").click(), 0);
            const lw = await winUrl("virtualFolderListEdit"); if (!lw) return { ...out, picker: false };
            try {
              await pause(1200); const ld = lw.document, t = ld.getElementById("folderPickerTree");
              const cb = await till(() => t.querySelector('input[type="checkbox"]:checked'), 4000);
              const s = csOf(t), c = cb && csOf(cb);
              return { ...out, picker: true, bg: s.backgroundColor, window: colorOf(ld, "var(--mt-window)", "backgroundColor"), radius: s.borderTopLeftRadius,
                       line: s.borderTopColor, paneLine: colorOf(ld, "var(--mt-pane-line)"), cb: c && [c.appearance, c.backgroundImage, c.backgroundColor], accent: colorOf(ld, "AccentColor") };
            } finally { await shut(lw); } }); """)
        ok = (res.get("picker") and same_color(res["bg"], res["window"]) and not same_color(res["bg"], "rgb(0, 0, 0)") and res["radius"] == "8px"
              and same_color(res["line"], res["paneLine"]) and res["cb"] and res["cb"][0] == "none" and res["cb"][1].startswith('url("chrome://')
              and same_color(res["cb"][2], res["accent"]) and None not in res["mids"] and abs(res["mids"][0] - res["mids"][1]) <= 1)
        return ok, f"{res}"
    check("Suchordner: Ordnerwahl in der Inhaltsfläche mit Haarlinie und 8 px, Kästchen im macOS-Stil mit Haken; +/− mittig zur Bedingungszeile", folder_picker, results)

    def filter_windows():
        # Filterliste, Filterprotokoll und Nachrichten suchen sind <window>: Listen und Felder trotzdem mit Haarlinie statt hartem Rahmen;
        # Protokoll dunkel ohne weiße Fläche (Inhaltsprozess, noscroll.css)
        res = m.js(COMPOSE_CHECK_JS + r"""
          const look = el => { const s = csOf(el), dd = el.ownerDocument;
            return { app: s.appearance, radius: s.borderTopLeftRadius, line: s.borderTopColor, paneLine: colorOf(dd, "var(--mt-pane-line)"), img: s.backgroundImage,
                     h: Math.round(el.getBoundingClientRect().height) }; };
          // Spaltenköpfe: ohne Thunderbirds Systemlinie (Schatten unten, Trenner links), Trenner als Haarlinie, erster Kopf ohne Trenner
          const head = (dd, sel) => [...dd.querySelectorAll(sel + " > treecols > treecol")].filter(vis).slice(0, 3).map(c => { const s = csOf(c);
            return { id: c.id, sh: s.boxShadow, bl: s.borderInlineStartWidth, blc: s.borderInlineStartColor }; });
          // Spaltenwahl-Knopf rechts: Trenner links wie die übrigen Köpfe, kein Strich unten (inset-Schatten des Knopfs)
          const pick = (dd, sel) => { const p = dd.querySelector(sel + " > treecols > treecolpicker"); if (!p) return null;
            const s = csOf(p), b = csOf(p.querySelector(".tree-columnpicker-button") ?? p);
            return { sh: s.boxShadow, bsh: b.boxShadow, blc: s.borderInlineStartColor, bb: s.borderBlockEndWidth }; };
          const headOf = (dd, sel) => ({ cols: head(dd, sel), pick: pick(dd, sel), sep: colorOf(dd, "var(--mt-separator)"), bb: csOf(dd.querySelector(sel + " > treecols")).borderBottomColor });
          const out = {};
          const f = await testFolder(); w.MsgFilters(null, f);
          const lw = await winUrl("FilterListDialog"); if (!lw) throw new Error("Filterliste nicht offen");
          try {
            await pause(1000); const ld = lw.document;
            out.list = look(ld.getElementById("filterList")); out.search = look(ld.getElementById("searchBox"));
            out.listHead = headOf(ld, "#filterList");
            later(() => ld.getElementById("filterLogButton").click());
            const vw = await winUrl("viewLog"); if (!vw) throw new Error("Filterprotokoll nicht offen");
            try {
              const lv = vw.document.getElementById("logView");
              await till(() => lv.currentURI?.spec?.endsWith("filterlog.html"), 6000); await pause(1200);
              out.log = look(lv);
              const snap = await lv.browsingContext.currentWindowGlobal.drawSnapshot(new DOMRect(20, 20, 4, 4), 1, "rgb(255,0,255)");
              const cv = vw.document.createElementNS("http://www.w3.org/1999/xhtml", "canvas"); cv.width = snap.width; cv.height = snap.height;
              const cx = cv.getContext("2d"); cx.drawImage(snap, 0, 0); out.pixel = [...cx.getImageData(1, 1, 1, 1).data];
            } finally { await shut(vw); }
          } finally { await shut(lw); }
          later(() => w.searchAllMessages());
          const sw = await winUrl("SearchDialog"); if (!sw) throw new Error("Suchfenster nicht offen");
          try { await pause(1000); const sd = sw.document;
            out.terms = look(sd.getElementById("searchTermList")); out.field = look([...sd.querySelectorAll("#searchTermList input:not([type=checkbox])")].find(vis));
            out.resHead = headOf(sd, "#threadTree");
          } finally { await shut(sw); }
          later(() => w.openKeyManager());
          const kw = await winUrl("KeyManager"); if (!kw) throw new Error("OpenPGP-Schlüssel nicht offen");
          try { await pause(1000); out.keys = look(kw.document.getElementById("pgpKeyList")); out.keyHead = headOf(kw.document, "#pgpKeyList"); } finally { await shut(kw); }
          out.dark = dark; return out;""")
        hair = lambda r, rad: r["radius"] == rad and same_color(r["line"], r["paneLine"])
        px = res.get("pixel") or [255, 255, 255, 255]
        log_ok = (sum(px[:3]) < 200) if res["dark"] else (min(px[:3]) >= 250)
        ok = (res["list"]["app"] == "none" and hair(res["list"], "8px") and hair(res["search"], "7px") and res["search"]["img"] != "none"
              and hair(res["log"], "8px") and log_ok and hair(res["terms"], "8px") and hair(res["field"], "7px") and res["field"]["h"] <= 30
              and hair(res["keys"], "8px"))
        def head_ok(h):
            cols = h["cols"]
            return (len(cols) >= 2 and same_color(h["bb"], h["sep"]) and all(c["sh"] == "none" for c in cols)
                    and cols[0]["bl"] == "0px" and all(same_color(c["blc"], h["sep"]) for c in cols[1:])
                    and (p := h["pick"]) is not None and p["sh"] == "none" and p["bsh"] == "none" and p["bb"] == "0px"
                    and same_color(p["blc"], cols[1]["blc"]))
        ok = ok and all(head_ok(res[k]) for k in ("listHead", "resHead", "keyHead"))
        return ok, f"{res}"
    check("Filterliste, Filterprotokoll, Suche, OpenPGP: Listen und Felder mit Haarlinie und Radius statt hartem Rahmen, Protokoll dunkel ohne weiße Fläche; Spaltenköpfe samt Spaltenwahl-Knopf mit Haarlinien statt Systemlinie", filter_windows, results)

    def compact_icon():
        # „Ordner komprimieren?“: Fragezeichen in der Akzentfarbe statt schwarz (dunkel unsichtbar); nie „Compact now“
        res = m.js(COMPOSE_CHECK_JS + r"""
          const bag = Cc["@mozilla.org/hash-property-bag;1"].createInstance(Ci.nsIWritablePropertyBag2); bag.setPropertyAsAString("compactSize", "120 MB");
          w.openDialog("chrome://messenger/content/compactFoldersDialog.xhtml", "", "chrome,dialog,centerscreen", bag);
          const cw = await winUrl("compactFoldersDialog"); if (!cw) throw new Error("Dialog nicht offen");
          try { await pause(800); const cd = cw.document, img = cd.querySelector("#contentWrapper > img"), s = csOf(img), r = img.getBoundingClientRect();
            // gezeichnet prüfen: fill wirkt nur mit -moz-context-properties (berechnet nicht abfragbar)
            const cv = cd.createElementNS("http://www.w3.org/1999/xhtml", "canvas"); cv.width = Math.ceil(r.width); cv.height = Math.ceil(r.height);
            const cx = cv.getContext("2d"); cx.drawWindow(cw, r.left, r.top, r.width, r.height, "rgb(128,128,128)");
            const acc = rgba(colorOf(cd, "AccentColor")), px = cx.getImageData(0, 0, cv.width, cv.height).data; let hits = 0;
            for (let i = 0; i < px.length; i += 4) if (Math.abs(px[i] - acc[0]) + Math.abs(px[i + 1] - acc[1]) + Math.abs(px[i + 2] - acc[2]) < 40) hits++;
            return { fill: s.fill, accent: colorOf(cd, "AccentColor"), accentPixels: hits };
          } finally { await shut(cw); }""")
        ok = same_color(res["fill"], res["accent"]) and not same_color(res["fill"], "rgb(0, 0, 0)") and res["accentPixels"] >= 50
        return ok, f"{res}"
    check("„Ordner komprimieren?“: Fragezeichen in der Akzentfarbe statt schwarz", compact_icon, results)

    def downloads():
        # Gespeicherte Dateien (about:downloads) bekommt das Design: Kapsel-Knopf, Fläche in Fensterfarbe (dunkel nicht Navy)
        res = m.js(COMPOSE_CHECK_JS + r"""
          tm.switchToTab(0); await pause(300); await w.openSavedFilesWnd(); await pause(2000);
          const t = tm.tabInfo.find(x => x.browser?.currentURI?.spec == "about:downloads"); if (!t) throw new Error("Tab fehlt");
          try { const dd = t.browser.contentDocument; await till(() => dd.getElementById("clearDownloads") && dd.defaultView.__mcTheme, 5000); await pause(400);
            const b = csOf(dd.getElementById("clearDownloads")), l = csOf(dd.getElementById("msgDownloadsRichListBox"));
            return { theme: !!dd.defaultView.__mcTheme, radius: b.borderTopLeftRadius, bg: b.backgroundColor, control: colorOf(dd, "var(--mt-control)", "backgroundColor"),
                     body: csOf(dd.body).backgroundColor, window: colorOf(dd, "var(--mt-window)", "backgroundColor"), list: [l.borderTopLeftRadius, l.borderTopColor],
                     paneLine: colorOf(dd, "var(--mt-pane-line)") };
          } finally { tm.closeTab(t); await pause(300); }""")
        ok = (res["theme"] and res["radius"] == "999px" and same_color(res["bg"], res["control"]) and same_color(res["body"], res["window"])
              and not same_color(res["body"], "rgb(26, 32, 44)") and res["list"][0] == "8px" and same_color(res["list"][1], res["paneLine"]))
        return ok, f"{res}"
    check("Gespeicherte Dateien: Design auch in about:downloads – Kapsel-Knopf, Fensterfarbe, Liste mit Haarlinie", downloads, results)

    def import_export():
        # Import und Export (about:import): Fläche in Fensterfarbe wie die übrigen Tabs, dunkel nicht Firefox-Blauschwarz #18181B
        # (der leichte Schleier des body bleibt, damit sich hell die weiße Karte abhebt)
        res = m.js(COMPOSE_CHECK_JS + r"""
          tm.switchToTab(0); await pause(300); const out = {};
          for (const [k, open] of [["imp", () => w.toImport()], ["exp", () => w.toExport()]]) {
            open(); await pause(2000);
            const t = tm.tabInfo.find(x => x.browser?.currentURI?.spec?.startsWith("about:import")); if (!t) throw new Error("Tab fehlt");
            try { const dd = t.browser.contentDocument; await till(() => dd.getElementById("stepNav") && dd.defaultView.__mcTheme, 5000); await pause(400);
              out[k] = { theme: !!dd.defaultView.__mcTheme, root: csOf(dd.documentElement).backgroundColor, body: csOf(dd.body).backgroundColor,
                         color: csOf(dd.documentElement).color, hash: dd.location.hash,
                         window: colorOf(dd, "var(--mt-window)", "backgroundColor"), text: colorOf(dd, "var(--mt-text)") };
            } finally { tm.closeTab(t); await pause(300); }
          }
          return out;""")
        def ok1(r):
            return (r["theme"] and same_color(r["root"], r["window"]) and not same_color(r["root"], "rgb(24, 24, 27)")
                    and same_color(r["color"], r["text"]))
        return ok1(res["imp"]) and ok1(res["exp"]), f"{res}"
    check("Import und Export: Fläche in Fensterfarbe wie die übrigen Tabs, dunkel kein Blauschwarz", import_export, results)

    def print_preview():
        # Druckvorschau einer Mail: Knopf „Print/Save“ in der Systemakzentfarbe statt Proton-Blau bzw. -Türkis, Panel neutral; nie drucken
        res = m.js(DIALOG_READING_JS + r"""
          await showMail("Halo Jetzt");
          w.setTimeout(() => a3.commandController.doCommand("cmd_print"), 0);
          const all = () => { const out = []; const walk = bc => { out.push(bc); bc.children.forEach(walk); }; walk(w.browsingContext); return out; };
          const pd = await tillM(() => all().map(bc => { try { return bc.window?.document; } catch { return null; } })
            .find(x => x && x.documentURI == "chrome://global/content/print.html" && x.getElementById("print-button")), 12000);
          if (!pd) return { open: false };
          try { await nap(1500); const pw = pd.defaultView, s = pw.getComputedStyle(pd.getElementById("print-button"));
            return { open: true, btn: s.backgroundColor, text: s.color, accent: colorIn(pd, "AccentColor"), accentText: colorIn(pd, "AccentColorText"),
                     root: pw.getComputedStyle(pd.documentElement).backgroundColor,
                     sheet: colorIn(pd, "var(--mt-sheet)", "backgroundColor"), window: colorIn(pd, "var(--mt-window)", "backgroundColor") };
          } finally { try { pd.getElementById("cancel-button")?.click(); } catch {} await nap(800);
            try { if (!pd.defaultView.closed) pd.defaultView.close(); } catch {} await nap(400); }""")
        ok = (res.get("open") and same_color(res["btn"], res["accent"]) and same_color(res["text"], res["accentText"])
              and (same_color(res["root"], res["sheet"]) or same_color(res["root"], res["window"])) and not same_color(res["root"], "rgb(28, 27, 34)"))
        return ok, f"{res}"
    check("Druckvorschau: Hauptknopf in der Systemakzentfarbe statt Proton-Blau/-Türkis, Panel neutral", print_preview, results)

    def open_with():
        # Anhang ohne gespeicherte Aktion → „Öffnen von …“: Knöpfe flach wie in den übrigen Dialogen (Cancel grau, OK in Akzentfarbe)
        # statt nativem eckigem Knopf neben flachem; nie OK – sonst würde die Datei geschrieben/geöffnet
        res = m.js(DIALOG_READING_JS + r"""
          const doc = await showMail("Halo Anhänge"); const mw = doc.defaultView;
          const a = await tillM(() => mw.currentAttachments?.find(x => x.name == "Notizen.txt"), 4000); if (!a) return { open: false, why: "Anhang fehlt" };
          const mi = Cc["@mozilla.org/mime;1"].getService(Ci.nsIMIMEService).getFromTypeAndExtension(a.contentType, "txt");
          if (Cc["@mozilla.org/uriloader/handler-service;1"].getService(Ci.nsIHandlerService).exists(mi) && !mi.alwaysAskBeforeHandling)
            return { open: false, why: "gespeicherte Aktion – der Dialog käme nicht" };
          w.setTimeout(() => a.open(mw.browsingContext), 0);
          const x = await winOf("unknownContentType"); if (!x) return { open: false, why: "Dialog nicht offen" };
          const dl = x.document.getElementById("unknownContentType");
          try { await nap(800); const sr = dl.shadowRoot, ok = sr.querySelector('[dlgtype="accept"]'), cancel = sr.querySelector('[dlgtype="cancel"]');
            const look = b => { const s = x.getComputedStyle(b); return [s.appearance, s.backgroundColor, s.borderTopLeftRadius, Math.round(b.getBoundingClientRect().height)]; };
            const out = { open: true, cancel: look(cancel), control: colorIn(x.document, "var(--mt-control)", "backgroundColor"), accent: colorIn(x.document, "AccentColor") };
            // OK ist anfangs gesperrt (Sicherheitsverzögerung) – zum Messen freigeben, nie anklicken
            ok.disabled = true; await nap(100); out.disabled = x.getComputedStyle(ok).opacity;
            ok.disabled = false; await nap(150); out.ok = look(ok);
            return out;
          } finally { try { dl.cancelDialog(); } catch {} await tillM(() => x.closed, 3000); if (!x.closed) x.close(); await nap(300); }""")
        if not res.get("open"):
            return False, f"{res}"
        c, o = res["cancel"], res["ok"]
        ok = (c[0] == "none" and o[0] == "none" and c[2] == "999px" and o[2] == "999px" and c[3] == o[3]
              and same_color(c[1], res["control"]) and same_color(o[1], res["accent"]) and float(res["disabled"]) < 1)
        return ok, f"{res}"
    check("„Öffnen von …“: Knöpfe als flache Kapseln wie in den Dialogen (Cancel grau, OK in Akzentfarbe) statt nativem Knopf", open_with, results)

    def rule_rows():
        # Bedingungszeilen (Suchordner-Dialog und Suchfenster): Auswahllisten nur in --mt-control ohne zweiten Verlauf (vorher doppelt
        # grau bzw. Fensterfarbe), gleich wie die Auswahl außerhalb der Liste; +/− mit Lücke statt aneinander; im Suchfenster der Teiler
        # als eine Haarlinie statt Doppellinie; Aktivitäten: „Clear List“ mit Luft zum Fensterrand, darüber eine Haarlinie
        res = m.js(COMPOSE_CHECK_JS + r"""
          const rows = dd => { const row = dd.querySelector("#searchTermList > richlistitem");
            const ml = [...row.querySelectorAll("menulist")].find(vis), btn = [...row.querySelectorAll(".small-button")].filter(vis);
            const other = [...dd.querySelectorAll("menulist")].find(x => vis(x) && !x.closest("richlistbox"));
            return { img: csOf(ml).backgroundImage, bg: csOf(ml).backgroundColor, other: other && csOf(other).backgroundColor,
                     control: colorOf(dd, "var(--mt-control)", "backgroundColor"),
                     gap: btn.length == 2 ? btn[1].getBoundingClientRect().left - btn[0].getBoundingClientRect().right : null }; };
          const f = await testFolder(); tm.switchToTab(0); await pause(500); const a3 = tm.currentAbout3Pane; a3.displayFolder(f.URI); await pause(800);
          const out = {};
          out.vf = await dialog(() => a3.commandController.doCommand("cmd_newVirtualFolder"), "virtualFolderProperties", async (dw, dd) => rows(dd));
          later(() => w.searchAllMessages());
          const sw = await winUrl("SearchDialog"); if (!sw) throw new Error("Suchfenster nicht offen");
          try { await pause(1000); const sd = sw.document, s = csOf(sd.getElementById("gray_horizontal_splitter"));
            out.search = rows(sd); out.split = { top: s.borderTopWidth, topColor: s.borderTopColor, bottom: s.borderBottomStyle, paneLine: colorOf(sd, "var(--mt-pane-line)") };
          } finally { await shut(sw); }
          later(() => w.openActivityMgr());
          const aw = await winUrl("activity.xhtml"); if (!aw) throw new Error("Aktivitäten nicht offen");
          try { await pause(800); const ad = aw.document, r = ad.getElementById("clearListButton").getBoundingClientRect(), v = csOf(ad.getElementById("activityView"));
            out.act = { left: r.left, bottom: aw.innerHeight - r.bottom, line: v.borderBottomColor, paneLine: colorOf(ad, "var(--mt-pane-line)") };
          } finally { await shut(aw); }
          return out;""")
        rows_ok = lambda r: (r["img"] == "none" and same_color(r["bg"], r["control"]) and r["other"] and same_color(r["bg"], r["other"])
                             and r["gap"] is not None and r["gap"] >= 3)
        sp, ac = res["split"], res["act"]
        ok = (rows_ok(res["vf"]) and rows_ok(res["search"]) and sp["bottom"] == "none" and float(sp["top"].rstrip("px")) <= 1
              and same_color(sp["topColor"], sp["paneLine"]) and ac["left"] >= 12 and ac["bottom"] >= 8 and same_color(ac["line"], ac["paneLine"]))
        return ok, f"{res}"
    check("Bedingungszeilen: Auswahllisten einfach grau wie die übrigen, +/− mit Lücke; Suche: Teiler eine Haarlinie; Aktivitäten: „Clear List“ mit Luft, Haarlinie", rule_rows, results)


FOLDER_JS = r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
  const csOf = (el, pseudo) => el.ownerDocument.defaultView.getComputedStyle(el, pseudo);
  // berechnete Farbe eines Werts (var(--mt-…)) im Dokument
  const colorOf = (doc, value, prop = "color") => { const e = doc.createElementNS("http://www.w3.org/1999/xhtml", "div"); e.style[prop] = value;
    doc.documentElement.append(e); const c = csOf(e)[prop]; e.remove(); return c; };
  const rgba = c => { const v = (String(c).match(/-?[\d.]+(?:e-?\d+)?/g) || []).map(Number); const k = String(c).startsWith("color(") ? 255 : 1;
    return [v[0] * k, v[1] * k, v[2] * k, v.length > 3 ? v[3] : 1]; };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
  // ausgeblendet (display oder visibility) bzw. gar nicht vorhanden
  const gone = el => !el || csOf(el).display == "none" || csOf(el).visibility == "hidden";"""


def folder_checks(m, results):
    """Ordnerliste, Toolbar und Suche: neue Mails, Platz für den Bereiche-Knopf, Abschnitte ohne Linien, globale Suche
    (Suchfeld, Ergebnis-Tab, Vorschläge), Toolbar anpassen, „Anpassen…“ der Bereiche-Leiste."""

    def new_messages():
        res = m.js(FOLDER_JS + r"""
          const a3 = await toMail(); const ad = a3.document; const tree = ad.getElementById("folderTree");
          const li = await until(() => [...tree.querySelectorAll("li:not([data-server-type], [data-mode], .unselectable)")]
            .find(x => x.querySelector(":scope > .container > .name")?.getBoundingClientRect().width));
          if (!li) return { folder: null };
          li.classList.add("new-messages"); await wait(150);
          const name = li.querySelector(":scope > .container > .name"), star = li.querySelector(":scope > .container > .new-icon");
          const out = { folder: name.textContent, color: csOf(name).color, text: colorOf(ad, "var(--mt-text)"), weight: csOf(name).fontWeight,
                        star: star ? csOf(star).visibility : "fehlt" };
          li.classList.remove("new-messages");
          // Kontozeile bleibt grauer Abschnittstitel
          const srv = tree.querySelector("li[data-server-type] > .container > .name");
          if (srv) { const sl = srv.closest("li"); const had = sl.classList.contains("new-messages"); sl.classList.add("new-messages"); await wait(100);
            out.server = csOf(srv).color; out.tertiary = colorOf(ad, "var(--mt-text-tertiary)"); if (!had) sl.classList.remove("new-messages"); }
          return out;""")
        ok = (res.get("folder") is not None and same_color(res["color"], res["text"]) and res["weight"] == "400" and res["star"] == "hidden"
              and ("server" not in res or same_color(res["server"], res["tertiary"])))
        return ok, f"{res}"
    check("Ordnerliste: Ordner mit neuen Mails ohne Funkelstern, Name in Textfarbe wie die übrigen", new_messages, results)

    def toggle_room():
        # Bereiche-Leiste aus: der Knopf unten links schwebt über der Ordnerliste – ganz nach unten gescrollt endet die
        # letzte Zeile darüber (auch ohne Statusleiste); Liste künstlich kurz, damit sie im leeren Testprofil scrollt
        res = m.js(FOLDER_JS + r"""
          const a3 = await toMail(); const ad = a3.document; const tree = ad.getElementById("folderTree");
          const wasHidden = w.gSpacesToolbar.isHidden;
          w.gSpacesToolbar.toggleToolbar(true); await wait(900);
          try {
            const btn = d.getElementById("mcSpacesToggle").getBoundingClientRect();
            const off = a3.browsingContext.embedderElement.getBoundingClientRect();
            const pane = ad.getElementById("folderPane").getBoundingClientRect();
            const pad = parseFloat(csOf(tree).paddingBottom);
            tree.style.maxHeight = "120px"; await wait(200);
            tree.scrollTop = tree.scrollHeight; await wait(200);
            const t = tree.getBoundingClientRect();
            const rows = [...tree.querySelectorAll("li > .container")].filter(c => c.getBoundingClientRect().height > 0);
            const last = rows.at(-1)?.getBoundingClientRect();
            return { pad, btnTop: Math.round(btn.top), btnW: Math.round(btn.width), btnLeft: Math.round(btn.left), paneBottom: Math.round(off.top + pane.bottom),
                     paneLeft: Math.round(off.left + pane.left), win: w.innerHeight, scrolls: tree.scrollHeight > tree.clientHeight,
                     lastGap: last ? Math.round(t.bottom - last.bottom) : null };
          } finally {
            tree.style.maxHeight = ""; tree.scrollTop = 0;
            if (!wasHidden) w.gSpacesToolbar.toggleToolbar(false);
            await wait(600);
          }""")
        ok = (res["btnW"] > 0 and res["btnLeft"] >= res["paneLeft"] and res["pad"] >= 46
              and res["paneBottom"] - res["pad"] <= res["btnTop"] - 4 and res["win"] - res["pad"] <= res["btnTop"]
              and res["scrolls"] and res["lastGap"] is not None and res["lastGap"] >= res["pad"] - 1)
        return ok, f"{res}"
    check("Ordnerliste: letzte Zeile lässt sich über den Bereiche-Knopf hinaus scrollen (Leiste ausgeblendet)", toggle_room, results)

    def mode_lines():
        res = m.js(FOLDER_JS + r"""
          const a3 = await toMail(); const ad = a3.document; const fp = a3.folderPane; const old = fp.activeModes;
          fp.activeModes = ["smart", "all", "unread", "recent"]; await wait(1200);
          const out = [...ad.querySelectorAll("#folderTree > li[data-mode] > .mode-container")].filter(c => csOf(c).display != "none")
            .map(c => [c.parentNode.dataset.mode, csOf(c).borderTopStyle, csOf(c).borderTopWidth]);
          fp.activeModes = old; await wait(800);
          return out;""")
        ok = len(res) >= 3 and all(s == "none" or wd == "0px" for _, s, wd in res)
        return ok, f"{res}"
    check("Ordnerliste: Abschnitte (Favoriten, Ungelesen, Zuletzt) einheitlich ohne Linie darüber", mode_lines, results)

    # globale Suche im eigenen Tab: ein Tab für zwei Prüfungen
    gloda = {}

    def gloda_tab():
        if not gloda:
            gloda.update(m.js(FOLDER_JS + r"""
              const { GlodaMsgSearcher } = ChromeUtils.importESModule("resource:///modules/gloda/GlodaMsgSearcher.sys.mjs");
              await toMail();
              const measure = () => { const p = d.getElementById("spacesPinnedButton").getBoundingClientRect();
                const s = d.querySelector('#unifiedToolbarContent > li[item-id="search-bar"]')?.getBoundingClientRect();
                return { pinned: Math.round(p.right), search: s?.width ? Math.round(s.left) : null }; };
              const fits = () => { const x = measure(); return x.search !== null && x.search >= x.pinned + 11 && x; };
              const tab = tm.openTab("glodaFacet", { searcher: new GlodaMsgSearcher(null, "halo") });
              const out = {};
              try {
                await wait(1500);
                out.first = await until(fits, 4000) || measure();
                // nach einem Bereich mit anderer Kante (Kalender) wieder zum Such-Tab
                await toCalendar(); tm.switchToTab(tab); await wait(1200);
                out.again = await until(fits, 4000) || measure();
                const gd = await until(() => { const x = tab.browser?.contentDocument; return x?.readyState == "complete" && x.getElementById("gloda-facet-view") && x; }, 6000);
                if (gd) {
                  const view = gd.getElementById("gloda-facet-view"), empty = gd.querySelector("span.empty"), img = gd.querySelector("img.empty");
                  out.view = { bg: csOf(view).backgroundColor, window: colorOf(gd, "var(--mt-window)", "backgroundColor"),
                    side: csOf(gd.querySelector(".facets-sidebar")).backgroundColor, sidebar: colorOf(gd, "var(--mt-sidebar)", "backgroundColor"),
                    empty: csOf(empty).color, secondary: colorOf(gd, "var(--mt-text-secondary)"), img: csOf(img).width };
                  out.view.contrast = contrast(rgba(out.view.empty), rgba(out.view.bg));
                  // Treffer mit denselben Klassen wie glodaFacet.js nachgebaut (Gloda indiziert im Testprofil
                  // nicht verlässlich rechtzeitig); Thunderbirds Regeln hängen nur an den Klassen
                  const mk = (tag, cls, text) => { const e = gd.createElementNS("http://www.w3.org/1999/xhtml", tag); e.className = cls;
                    if (text) e.textContent = text; return e; };
                  const box = mk("div", "halo-test"), m1 = mk("div", "message"), m2 = mk("div", "message");
                  const subj = mk("span", "message-subject", "Betreff"), tag = mk("span", "message-tag", "To Do"),
                        body = mk("div", "message-body", "Auszug"), bar = mk("span", "bar-link", "Anna Beispiel");
                  m1.append(subj, tag, body); box.append(m1, m2, bar); gd.getElementById("main-column").append(box);
                  out.results = { font: csOf(view).fontFamily, msg: csOf(m1).fontFamily, bodyFont: csOf(body).fontFamily,
                    subj: [csOf(subj).color, csOf(subj).fontSize, csOf(subj).fontWeight], text: colorOf(gd, "var(--mt-text)"),
                    body: [csOf(body).color, csOf(body).fontSize], line: csOf(m1).borderBottomColor, sep: colorOf(gd, "var(--mt-separator)"),
                    person: csOf(bar).color, tag: [csOf(tag).borderTopStyle, csOf(tag).borderTopLeftRadius] };
                  box.remove();
                }
                const rs = tab.panel?.querySelector(".remote-gloda-search");
                out.field = rs && { border: csOf(rs).borderTopStyle, radius: parseFloat(csOf(rs).borderTopLeftRadius), height: Math.round(rs.getBoundingClientRect().height),
                                    bg: csOf(rs).backgroundColor, control: colorOf(d, "var(--mt-control)", "backgroundColor") };
              } finally { tm.closeTab(tab); await wait(600); await toMail(); }
              return out;"""))
        return gloda

    def gloda_search_field():
        g = gloda_tab()
        ok = all(g.get(k, {}).get("search") is not None and g[k]["search"] >= g[k]["pinned"] + 11 for k in ("first", "again"))
        return ok, f"Suchfeld links / Seitenleisten-Knopf rechts: zuerst {g.get('first')}, nach dem Kalender {g.get('again')}"
    check("Globale Suche: Suchfeld oben rechts vom Seitenleisten-Knopf, auch nach dem Wechsel aus dem Kalender", gloda_search_field, results)

    def gloda_page():
        g = gloda_tab()
        v, f = g.get("view") or {}, g.get("field") or {}
        ok = (bool(v) and same_color(v["bg"], v["window"]) and same_color(v["side"], v["sidebar"]) and same_color(v["empty"], v["secondary"])
              and v["contrast"] >= 4.5 and v["img"].endswith("px") and float(v["img"][:-2]) <= 64
              and bool(f) and f["border"] == "none" and f["radius"] >= 14 and f["height"] >= 26 and same_color(f["bg"], f["control"]))
        return ok, f"Seite {v}; Suchfeld {f}"
    check("Globale Suche: Ergebnis-Tab in den Flächen der übrigen Ansichten, Leerhinweis grau (Kontrast ≥ 4,5:1), Suchfeld als Kapsel", gloda_page, results)

    def gloda_results():
        g = gloda_tab()
        r, v = g.get("results") or {}, g.get("view") or {}
        ok = (bool(r) and r["msg"] == r["font"] and r["bodyFont"] == r["font"] and "monospace" not in r["bodyFont"]
              and same_color(r["subj"][0], r["text"]) and r["subj"][1] == "13px" and r["subj"][2] == "600"
              and same_color(r["body"][0], v.get("secondary")) and r["body"][1] == "12px"
              and same_color(r["line"], r["sep"]) and same_color(r["person"], r["text"])
              and r["tag"] == ["none", "4px"])
        return ok, f"{r}"
    check("Globale Suche: Treffer in Systemschrift statt Monospace, Betreff und Personen in Textfarbe statt Linkblau, Linien als Haarlinie",
          gloda_results, results)

    def menu_accel():
        # Tastenkürzel in Menüs (z. B. „Markieren“): neutral grau statt blaugrau, im markierten Eintrag in Auswahl-Schrift.
        # Eigenes kleines Menü im Hauptfenster (Einträge geschlossener Menüs haben keine berechneten Stile)
        res = m.js(FOLDER_JS + r"""
          await toMail();
          const p = d.createXULElement("menupopup"), mi = d.createXULElement("menuitem"), off = d.createXULElement("menuitem");
          mi.setAttribute("label", "Als ungelesen"); mi.setAttribute("acceltext", "M");
          off.setAttribute("label", "Als gelesen"); off.setAttribute("acceltext", "M"); off.setAttribute("disabled", "true");
          p.append(mi, off); (d.getElementById("mainPopupSet") || d.documentElement).append(p);
          p.openPopupAtScreen(w.screenX + 300, w.screenY + 200, false);
          const out = {};
          try {
            out.state = await until(() => p.state == "open" && p.state, 4000) || p.state;
            const acc = mi.querySelector(".menu-accel"), acc2 = off.querySelector(".menu-accel");
            if (!acc) return out;
            Object.assign(out, { color: csOf(acc).color, secondary: colorOf(d, "var(--mt-text-secondary)"),
                                 disabled: [csOf(acc2).color, csOf(off).color] });
            mi.setAttribute("_moz-menuactive", "true"); await wait(100);
            out.active = [csOf(acc).color, csOf(mi).color, colorOf(d, "var(--mt-accent-text)")];
          } finally { p.hidePopup(); await wait(300); p.remove(); }
          return out;""")
        ok = (bool(res.get("color")) and same_color(res["color"], res["secondary"]) and same_color(res["disabled"][0], res["disabled"][1])
              and same_color(res["active"][0], res["active"][1]) and same_color(res["active"][0], res["active"][2]))
        return ok, f"{res}"
    check("Menüs: Tastenkürzel neutral grau, im markierten Eintrag in der Schriftfarbe der Auswahl", menu_accel, results)

    def folder_menu_icons():
        # Ordnermenü „Verschieben“ (Toolbar): Umriss-Symbole wie die Ordnerliste in Akzentfarbe, Papierkorb und Konto
        # mit eigenem Symbol; markiertes Konto in der Schrift der Auswahl, ohne dass sein Untermenü das erbt
        res = m.js(FOLDER_JS + r"""
          await toMail();
          const P = d.getElementById("toolbarMoveToPopup");
          const mask = v => { const e = d.createElementNS("http://www.w3.org/1999/xhtml", "div"); e.style.maskImage = v;
            d.documentElement.append(e); const r = csOf(e).maskImage; e.remove(); return r; };
          const icon = x => x.querySelector(":scope > .menu-icon");
          const info = x => { const s = csOf(icon(x)); return { label: x.getAttribute("label"), mask: s.maskImage, bg: s.backgroundColor, w: s.width }; };
          const out = { accent: colorOf(d, "var(--mt-accent)"), folder: mask("var(--mi-folder)"), serverMask: mask("var(--mi-server)"),
                        trashMask: mask("var(--mi-trash)") };
          P.openPopupAtScreen(w.screenX + 300, w.screenY + 200, false);
          try {
            out.state = await until(() => P.state == "open" && P.state, 4000) || P.state;
            const server = [...P.children].find(x => x.getAttribute("IsServer") == "true");
            const plain = [...P.children].find(x => x.classList.contains("folderMenuItem") && !x.hasAttribute("IsServer"));
            if (!server || !plain || !icon(server)) return { ...out, fehlt: [!!server, !!plain] };
            server.openMenu(true);
            out.sub_state = await until(() => server.menupopup?.state == "open" && "open", 4000) || server.menupopup?.state;
            const kids = [...server.menupopup.children].filter(x => x.classList.contains("folderMenuItem"));
            const trash = kids.find(x => x.getAttribute("SpecialFolder") == "Trash"), sub = kids.find(x => x.getAttribute("SpecialFolder") == "none");
            Object.assign(out, { plain: info(plain), trash: trash && info(trash), sub: sub && info(sub) });
            server.setAttribute("_moz-menuactive", "true"); await wait(100);
            out.server = info(server); out.server_color = csOf(server).color; out.trash_active = trash && csOf(icon(trash)).backgroundColor;
          } finally { P.hidePopup(); await wait(400); }
          // Ordner- und Mailansicht erlauben data:-Bilder (sonst fielen die Masken dort aus)
          const scope = ':has(> head > meta[http-equiv="Content-Security-Policy"][content*="data:"])';
          const a3 = tm.currentAbout3Pane;
          out.scope = [d, a3.document, a3.messageBrowser?.contentDocument].map(x => !!x && x.documentElement.matches(scope));
          return out;""")
        if not res or "fehlt" in res or "plain" not in res:
            return False, f"{res}"
        acc, trash, sub = res["accent"], res.get("trash") or {}, res.get("sub")
        flags = {
            "Ordner": res["plain"]["mask"] == res["folder"] and same_color(res["plain"]["bg"], acc) and res["plain"]["w"] == "16px",
            "Konto markiert": res["server"]["mask"] == res["serverMask"] and same_color(res["server"]["bg"], res["server_color"]),
            "Papierkorb": trash.get("mask") == res["trashMask"] and same_color(trash.get("bg"), acc) and same_color(res.get("trash_active"), acc),
            "Unterordner": not sub or (sub["mask"] == res["folder"] and same_color(sub["bg"], acc)),
            "CSP erlaubt data:": res["scope"] == [True, True, True]}
        detail = {k: v for k, v in res.items() if k not in ("folder", "serverMask", "trashMask")}
        for k in ("plain", "server", "trash", "sub"):
            if detail.get(k):
                detail[k] = {**detail[k], "mask": detail[k]["mask"][:40]}
        return all(flags.values()), f"{flags} {detail}"
    check("Ordnermenüs (Verschieben): Umriss-Symbole in Akzentfarbe wie die Ordnerliste statt Thunderbirds gefüllter Ordner",
          folder_menu_icons, results)

    def suggestions():
        res = m.js(FOLDER_JS + r"""
          const p = d.getElementById("PopupGlodaAutocomplete"); if (!p) return null; const s = csOf(p);
          return { font: s.fontSize, border: colorOf(d, s.getPropertyValue("--panel-border-color").trim() || "red"),
                   bg: colorOf(d, s.getPropertyValue("--panel-background-color").trim() || "red"), menu: colorOf(d, "var(--mt-menu-bg)"),
                   url: colorOf(d, s.getPropertyValue("--autocomplete-popup-url-color").trim() || "red"), secondary: colorOf(d, "var(--mt-text-secondary)") };""")
        ok = (res is not None and res["font"] == "13px" and rgba_alpha(res["border"]) == 0 and same_color(res["bg"], res["menu"])
              and same_color(res["url"], res["secondary"]))
        return ok, f"{res}"
    check("Suche: Vorschlagsliste wie die übrigen Menüs (13 px, ohne harten Rand, Adressen grau)", suggestions, results)

    def customize_toolbar():
        res = m.js(FOLDER_JS + r"""
          await toMail();
          d.querySelector("unified-toolbar").showCustomization();
          const out = { on: !!await until(() => d.documentElement.classList.contains("customizingUnifiedToolbar")) };
          try {
            await wait(800);
            const IDS = ["mcListHeader", "mcTodayToggle", "mcTodayTop", "mcTodayNew", "mcSpacesToggle"];
            const row = d.getElementById("unifiedToolbarContainer");
            out.shown = IDS.filter(id => !gone(d.getElementById(id)));
            out.hits = [[w.innerWidth - 50, 10], [30, w.innerHeight - 20], [400, 10]]
              .map(([x, y]) => d.elementFromPoint(x, y)?.closest?.('[id^="mc"]')?.id).filter(Boolean);
            out.row = [csOf(row).backgroundImage, csOf(row).backgroundColor, colorOf(d, "var(--mt-window)", "backgroundColor"), csOf(row, "::before").display];
          } finally {
            d.querySelector("unified-toolbar-customization").toggle(false);
            out.off = !!await until(() => !d.documentElement.classList.contains("customizingUnifiedToolbar"));
            await wait(600);
          }
          out.back = ["mcListHeader", "mcSpacesToggle"].filter(id => gone(d.getElementById(id)));
          return out;""")
        r = res.get("row") or ["?", "", "", ""]
        ok = (res["on"] and res["off"] and not res["shown"] and not res["hits"] and r[0] == "none" and same_color(r[1], r[2])
              and r[3] == "none" and not res["back"])
        return ok, f"{res}"
    check("Toolbar anpassen: Listenkopf, Today- und Bereiche-Knopf ausgeblendet, Zeile einfarbig; danach wieder da", customize_toolbar, results)

    def spaces_customize():
        res = m.js(FOLDER_JS + r"""
          await toMail();
          const item = id => d.getElementById(id);
          const sep = item("settingsContextOpenCustomizeItem")?.previousElementSibling;
          const out = { hidden: ["spacesToolbarContextCustomize", "settingsContextOpenCustomizeItem"].map(id => item(id)?.hidden ?? "fehlt"),
                        sep: sep?.localName == "menuseparator" ? sep.hidden : "fehlt" };
          const pop = async (menu, target) => { const r = target.getBoundingClientRect();
            target.dispatchEvent(new w.MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
              screenX: w.screenX + r.left + r.width / 2, screenY: w.screenY + r.top + r.height / 2 }));
            await wait(700); const state = menu.state;
            const visible = [...menu.children].filter(c => !c.hidden && c.localName == "menuitem").length;
            if (state != "closed") { menu.hidePopup(); await wait(400); } return { state, visible }; };
          // Rechtsklick auf die leere Leiste: kein (leeres) Menü
          out.bar = await pop(item("spacesToolbarContextMenu"), item("spacesToolbar"));
          out.customizing = w.gSpacesToolbar.isCustomizing;
          // Gegenprobe: das Menü am Einstellungen-Knopf geht weiter auf (Einstellungen, Konten, Add-ons)
          out.settings = await pop(item("settingsContextMenu"), item("settingsButton"));
          const before = w.gSpacesToolbar.isHidden;
          w.gSpacesToolbar.toggleToolbar(!before); await wait(300); out.toggled = w.gSpacesToolbar.isHidden != before;
          w.gSpacesToolbar.toggleToolbar(before); await wait(500); out.restored = w.gSpacesToolbar.isHidden == before;
          return out;""")
        ok = (res["hidden"] == [True, True] and res["sep"] is True and res["bar"]["state"] == "closed" and res["customizing"] is False
              and res["settings"]["state"] in ("open", "showing") and res["settings"]["visible"] == 3 and res["toggled"] and res["restored"])
        return ok, f"{res}"
    check("Bereiche-Leiste: „Anpassen…“ (öffnete nicht, sperrte das Ausblenden) entfernt, leere Leiste ohne leeres Menü", spaces_customize, results)


# Kontextmenü der Mailliste per Rechtsklick auf die ausgewählte Testmail (nach MESSAGE_JS) öffnen;
# dazu Farbhilfen (rgb()/color(srgb …) auf 0–255) und Kontrast nach WCAG
MENU_JS = MESSAGE_JS + r"""
  const ad = a3.document, P = ad.getElementById("mailContext");
  const cs = (el, pseudo) => a3.getComputedStyle(el, pseudo);
  const rgba = c => { const v = (String(c).match(/-?[\d.]+(?:e-?\d+)?/g) || []).map(Number); const k = String(c).startsWith("color(") ? 255 : 1;
    return [v[0] * k, v[1] * k, v[2] * k, v.length > 3 ? v[3] : 1]; };
  const over = (fg, bg) => fg.slice(0, 3).map((x, i) => x * fg[3] + bg[i] * (1 - fg[3])).concat(1);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
  const colorOf = value => { const e = ad.createElementNS("http://www.w3.org/1999/xhtml", "div"); e.style.color = value;
    ad.documentElement.append(e); const c = cs(e).color; e.remove(); return c; };
  const openContext = async () => {
    const row = ad.querySelector('#threadTree tr.selected, #threadTree tr[aria-selected="true"]');
    if (!row) return "keine Zeile";
    const r = row.getBoundingClientRect(), x = r.left + Math.min(r.width / 2, 40), y = r.top + r.height / 2;
    for (const [type, buttons] of [["mousedown", 2], ["contextmenu", 2], ["mouseup", 0]])
      row.dispatchEvent(new a3.MouseEvent(type, { bubbles: true, cancelable: true, composed: true, view: a3, button: 2, buttons,
        clientX: x, clientY: y, screenX: a3.mozInnerScreenX + x, screenY: a3.mozInnerScreenY + y }));
    return await until(() => P.state == "open" && "open", 4000) || P.state;
  };"""


def menu_checks(m, results):
    """Menüs: gleichmäßige Zeilen im Kontextmenü der Mailliste, lesbare Schlagwörter im Schlagwort-Menü."""

    def nav_rows():
        # Archivieren/Spam/Löschen baut halo.spaces aus Thunderbirds Symbolzeile zu Textzeilen um – sie waren 2 px niedriger
        res = m.js(MENU_JS + r"""
          const item = id => ad.getElementById(id);
          const NAV = ["navContext-archive", "navContext-markAsJunk", "navContext-delete"], REST = ["mailContext-editAsNew", "mailContext-moveMenu", "mailContext-tags", "mailContext-saveAs"];
          const out = { list: !!item("mailContext-navigation")?.classList.contains("mc-nav-list") };
          out.state = await openContext();
          try {
            // berechnete Abstände gibt es erst bei offenem Menü
            out.pad = Object.fromEntries([...NAV, ...REST].map(id => [id, item(id) ? cs(item(id)).paddingTop : "fehlt"]));
            const h = id => { const e = item(id); return e && e.getClientRects().length ? Math.round(e.getBoundingClientRect().height * 10) / 10 : null; };
            out.nav = NAV.map(h).filter(x => x); out.rest = REST.map(h).filter(x => x);
          } finally { P.hidePopup(); await wait(400); }
          return out;""")
        pads = set((res.get("pad") or {"-": ""}).values())
        hs = res.get("nav", []) + res.get("rest", [])
        # Fenster verdeckt (Höhe 0): nur das Padding werten
        heights_ok = (not any(hs)) or (len(res["nav"]) >= 2 and len(res["rest"]) >= 3 and max(hs) - min(hs) < 0.5)
        ok = res["list"] and len(pads) == 1 and pads.pop().endswith("px") and heights_ok
        return ok, f"{res}"
    check("Kontextmenü Mailliste: Archivieren/Spam/Löschen so hoch wie die übrigen Zeilen", nav_rows, results)

    def tag_menu():
        # Schlagwort-Menü: Thunderbird färbt die Namen in der Grundfarbe (Orange auf Hellgrau 1,6:1) – gemischt mit der Textfarbe lesbar
        res = m.js(MENU_JS + r"""
          const sub = ad.getElementById("mailContext-tagpopup"), menu = ad.getElementById("mailContext-tags");
          const text = colorOf("var(--mt-text)"), menuBg = rgba(colorOf("var(--mt-menu-bg)"));
          const dark = lum(rgba(text)) > 0.5;
          // gemessener Menügrund (durchscheinend) und die Menüfläche über Weiß bzw. Schwarz
          const bgs = dark ? [[36, 36, 38, 1], over(menuBg, [0, 0, 0])] : [[224, 224, 224, 1], over(menuBg, [255, 255, 255])];
          const out = { dark, state: await openContext(), tags: [] };
          try {
            menu.open = true;
            out.sub = await until(() => sub.state == "open" && "open", 4000) || sub.state;
            const tags = [...sub.querySelectorAll(':scope > menuitem[type="checkbox"]')].filter(x => x.style.color);
            for (const t of tags) {
              const tx = cs(t.querySelector(".menu-text")).color, icon = t.querySelector(".menu-icon");
              out.tags.push({ name: t.getAttribute("label"), inline: t.style.color, text: tx, icon: icon ? cs(icon).color : null,
                              contrast: Math.min(...bgs.map(b => contrast(rgba(tx), b))) });
            }
            if (tags[1]) { tags[1].setAttribute("_moz-menuactive", "true"); await wait(100);
              out.active = [cs(tags[1].querySelector(".menu-text")).color, colorOf("var(--mt-accent-text)")];
              tags[1].removeAttribute("_moz-menuactive"); }
          } finally { sub.hidePopup?.(); P.hidePopup(); await wait(400); }
          return out;""")
        tags = res.get("tags", [])
        ok = (len(tags) >= 5 and all(not same_color(t["text"], t["inline"]) and same_color(t["icon"], t["text"]) and t["contrast"] >= 4.5 for t in tags)
              and same_color(*res.get("active", ["", "?"])))
        return ok, f"{res}"
    check("Schlagwort-Menü: Namen in Schlagwortfarbe lesbar (Kontrast ≥ 4,5:1), markiert in der Schrift der Auswahl", tag_menu, results)


# Kalender: Woche mit heute (auf 8 Uhr gescrollt), Spalten, Popups öffnen/schließen, Inhaltsteil eines Panels
CAL_CHECK_JS = COMPOSE_CHECK_JS + r"""
  const { CalEvent } = ChromeUtils.importESModule("resource:///modules/CalEvent.sys.mjs");
  const toWeek = async (width = 1500) => { w.resizeTo(width, 900); await pause(900); await toCalendar(); w.switchToView("week");
    w.currentView().goToDay(cal.dtz.now()); await pause(1200); w.currentView().scrollToMinute(480); await pause(700); return w.currentView(); };
  const cols = () => [...d.querySelectorAll("#week-view .day-column-container")]
    .map(c => ({ h: c.querySelector(".day-column-heading"), hc: c.querySelector("calendar-header-container") })).filter(x => vis(x.h));
  const isOpen = p => till(() => p?.state == "open", 4000);
  const shutPop = async p => { if (p && p.state != "closed") { p.hidePopup(); await till(() => p.state == "closed", 2000); } };
  const partOf = p => p?.shadowRoot?.querySelector('[part~="content"]');
  const today = () => { const t = cal.dtz.now(); t.isDate = true; return t; };"""


def calendar_checks(m, results):
    """Kalender: Tagesköpfe der Woche (Höhe, schmales Fenster), Ganztags-Termine, Rasterlinien, Schnellfenster samt
    Datumsauswahl und Auswahlliste, Pfeil des „+“-Popovers, Termin-Dialog (Schrift, Minimonat, Uhrzeit-Raster), Drucken."""

    def week_heads():
        # Thunderbird versetzt die deckende Ganztags-Zeile um Text + Innenabstand + Rand des Kopfs (ohne min-height) –
        # mit min-height lag sie über den Unterlängen („Mondav“)
        res = m.js(CAL_CHECK_JS + r"""
          await toWeek();
          return cols().map(({ h, hc }) => { const a = h.getBoundingClientRect(), b = hc.getBoundingClientRect();
            const el = d.elementFromPoint(a.left + a.width / 2, a.bottom - 2);
            const sp = [...h.children].find(s => !s.hidden && s.getBoundingClientRect().width > 0);
            return { height: Math.round(a.height * 10) / 10, gap: Math.round((b.top - a.bottom) * 10) / 10, hit: !!el && h.contains(el),
                     text: sp?.textContent, cut: !sp || sp.scrollWidth > sp.clientWidth + 0.5 }; });""")
        # breites Fenster: Thunderbird wählt Lang- oder Kurzform so, dass sie passt – kein Kopf mit „…“ (früher „Wednesday Oct…“)
        ok = len(res) == 7 and all(c["gap"] >= -0.6 and c["hit"] and c["height"] >= 28 and not c["cut"] for c in res)
        return ok, f"{res}"
    check("Woche: Tagesköpfe ganz sichtbar (Ganztags-Zeile beginnt darunter, Unterlängen nicht abgeschnitten, passende Lang- oder Kurzform ohne „…“)", week_heads, results)

    def narrow_heads():
        # schmales Fenster: Kopf nicht breiter als seine Spalte (Thunderbirds Inline-Mindestbreite), Text endet mit „…“
        res = m.js(CAL_CHECK_JS + r"""
          await toWeek(1136);
          const heads = cols().map(({ h }) => { const spans = [...h.children].filter(s => !s.hidden && s.getBoundingClientRect().width > 0);
            const a = h.getBoundingClientRect(), r = spans[0]?.getBoundingClientRect();
            return { shown: spans.length, ellipsis: spans[0] ? csOf(spans[0]).textOverflow : null,
                     inside: !!r && r.right <= a.right + 0.5 && r.left >= a.left - 0.5, l: Math.round(a.left * 10) / 10, r: Math.round(a.right * 10) / 10 }; });
          const out = { width: w.outerWidth, heads };
          w.resizeTo(1500, 900); await pause(900); return out;""")
        h = res["heads"]
        ok = (len(h) == 7 and all(x["shown"] == 1 and x["ellipsis"] == "ellipsis" and x["inside"] for x in h)
              and all(h[i]["r"] <= h[i + 1]["l"] + 0.5 for i in range(len(h) - 1)))
        return ok, f"{res}"
    check("Woche im schmalen Fenster: Tagesköpfe in ihrer Spalte, gekürzt mit „…“, ohne Überlappung", narrow_heads, results)

    def allday_single_line():
        # ganztägige Termine in Woche/Tag einzeilig (Thunderbird bricht dort um – die Zeile wurde doppelt so hoch)
        res = m.js(CAL_CHECK_JS + r"""
          const c = testCalendar(); const e = new CalEvent(); e.title = "Halo Ganztags Konferenz mit sehr langem Titel in Wien"; e.calendar = c;
          const s = today(); const en = s.clone(); en.day += 2; e.startDate = s; e.endDate = en;
          const saved = await c.addItem(e);
          try {
            await toWeek();
            const labels = await till(() => { const l = [...d.querySelectorAll("#week-view .allday-events-list .event-name-label")]
              .filter(x => /Halo Ganztags Konferenz/.test(x.textContent) && vis(x)); return l.length && l; }, 6000) || [];
            await pause(300);
            return labels.map(l => ({ ws: csOf(l).whiteSpace, li: Math.round(l.closest("li").getBoundingClientRect().height * 10) / 10 }));
          } finally { try { await c.deleteItem(saved); } catch {} }""")
        ok = len(res) >= 1 and all(x["ws"] == "nowrap" and x["li"] <= 26 for x in res)
        return ok, f"{res}"
    check("Woche: ganztägige Termine einzeilig (höchstens 26 px hoch)", allday_single_line, results)

    def grid_lines():
        # keine 2-px-Linie der Zeitleiste und unter den Ganztags-Zeilen, keine doppelte Linie rechts der ausgewählten Spalte
        res = m.js(CAL_CHECK_JS + r"""
          const v = await toWeek(); v.selectedDay = today(); await pause(500);
          const sel = d.querySelector("#week-view .day-column-selected");
          const tb = d.querySelector("#week-view .multiday-timebar"), hc = d.querySelector("#week-view calendar-header-container");
          const hb = sel?.querySelector(".multiday-hour-box"), shc = sel?.querySelector("calendar-header-container");
          return { selected: !!sel, timebar: csOf(tb).borderRightWidth, header: parseFloat(csOf(hc).borderBottomWidth),
                   hourBox: hb ? csOf(hb).borderRightWidth : null, selHeader: shc ? csOf(shc).borderRightWidth : null };""")
        ok = res["selected"] and res["timebar"] == "0px" and res["header"] <= 1 and res["hourBox"] == "0px" and res["selHeader"] == "0px"
        return ok, f"{res}"
    check("Woche: Rasterlinien als Haarlinie (Zeitleiste, Ganztags-Zeile, ausgewählte Spalte ohne doppelte Linie)", grid_lines, results)

    def quick_panel_surfaces():
        # Schnellfenster in der deckenden Popover-Fläche ohne Rand (dunkel sonst navyblau); Datumsauswahl als ein
        # Popover ohne harte Ränder, Auswahl in Akzentfarbe; Auswahlliste ohne Kachel-Flächen je Zeile
        res = m.js(CAL_CHECK_JS + r"""
          await toWeek();
          const li = [...d.querySelectorAll('#unifiedToolbarContent li[item-id="new-event"]')].find(vis);
          li.querySelector("button").click();
          const qp = await till(() => { const q = d.getElementById("mcQuickPanel"); return q?.state == "open" && q; }, 4000);
          if (!qp) return { open: false, visibility: d.visibilityState };
          await pause(300);
          const out = { open: true, dark, token: colorOf(d, "var(--mt-popover-bg)", "backgroundColor") };
          try {
            const pc = csOf(partOf(qp)); out.panel = { bg: pc.backgroundColor, border: pc.borderTopColor, bw: pc.borderTopWidth };
            const f = qp.__mc; if (!vis(f.startDate)) { f.summary.click(); await pause(600); }
            const dp = d.getElementById("DateTimePickerPanel");
            d.notifyUserGestureActivation(); f.startDate.showPicker();
            if (await isOpen(dp)) {
              const fd = await till(() => dp.querySelector("iframe")?.contentDocument?.querySelector("button.month-year") && dp.querySelector("iframe").contentDocument, 4000);
              await pause(400);
              const pp = csOf(partOf(dp)), sel = fd?.querySelector(".days-view td.selection");
              out.picker = { bg: pp.backgroundColor, border: pp.borderTopColor, bw: pp.borderTopWidth, body: fd && csOf(fd.body).backgroundColor,
                month: fd && csOf(fd.querySelector("button.month-year")).borderTopColor, clear: fd && csOf(fd.getElementById("clear-button")).borderTopColor,
                sel: sel && csOf(sel).backgroundColor, accent: fd && colorOf(fd, "AccentColor", "backgroundColor") };
              await shutPop(dp);
            }
            d.notifyUserGestureActivation(); try { f.repeat.showPicker(); } catch {}
            const sd = await till(() => d.getElementById("ContentSelectDropdown")?.menupopup, 4000);
            // Diagnose, falls die Auswahlliste nicht messbar aufgeht
            out.selectInfo = { os: Services.appinfo.OS, dropdown: !!sd, repeatVisible: vis(f.repeat) };
            if (sd && await isOpen(sd)) {
              await pause(300);
              out.select = [...sd.children].filter(x => x.localName == "menuitem" && x.getAttribute("_moz-menuactive") != "true" && vis(x)).map(x => csOf(x).backgroundColor);
              await shutPop(sd);
            } else {
              // unter macOS bleibt die Liste nach showPicker() zu – dann ein echter Mausklick (unten), Schnellfenster bleibt offen
              out.selectInfo.state = sd?.state ?? null;
              const r = f.repeat.getBoundingClientRect(); out.click = [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
            }
          } finally { if (!out.click) await shutPop(qp); }
          return out;""")
        if res.get("click"):
            x, y = res["click"]
            m.pointer([{"type": "pointerMove", "x": x, "y": y, "origin": "viewport"}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}])
            res["select"] = m.js(CAL_CHECK_JS + r"""
              const qp = d.getElementById("mcQuickPanel"), sd = d.getElementById("ContentSelectDropdown")?.menupopup;
              try {
                if (!sd || !await isOpen(sd)) return null;
                await pause(300);
                const c = [...sd.children].filter(x => x.localName == "menuitem" && x.getAttribute("_moz-menuactive") != "true" && vis(x)).map(x => csOf(x).backgroundColor);
                await shutPop(sd); return c;
              } finally { await shutPop(qp); }""")
        if not res.get("open"):
            return res.get("visibility") == "hidden", f"Schnellfenster nicht offen {res}"
        p, k = res["panel"], res.get("picker") or {}
        no_border = lambda c, wd: wd == "0px" or rgba_alpha(c) == 0
        ok = (no_border(p["border"], p["bw"]) and same_color(p["bg"], res["token"])
              and same_color(res["token"], "rgb(44, 44, 46)" if res["dark"] else "rgb(251, 251, 252)")
              and bool(k) and no_border(k["border"], k["bw"]) and same_color(k["bg"], k["body"])
              and rgba_alpha(k["month"]) == 0 and rgba_alpha(k["clear"]) == 0 and (k["sel"] is None or same_color(k["sel"], k["accent"]))
              and bool(res.get("select")) and all(rgba_alpha(c) == 0 for c in res["select"]))
        return ok, f"{res}"
    check("Schnellfenster: deckende Fläche ohne Rand; Datumsauswahl ein Popover ohne harte Ränder; Auswahlliste ohne Kacheln", quick_panel_surfaces, results)

    def new_popup_arrow():
        # „+“ der Today-Pane: Pfeil des Popovers über der Mitte des Knopfs (früher 240 px daneben) – auch am Bildschirmrand
        res = m.js(CAL_CHECK_JS + r"""
          const sx = w.screenX, sy = w.screenY, sw = w.outerWidth, sh = w.outerHeight; const out = { visibility: d.visibilityState };
          await toMail();
          const measure = async () => { await pause(800);
            if (!w.TodayPane.isVisible) { d.getElementById("mcTodayToggle").click(); await pause(900); }
            const np = d.getElementById("mcNewPopup"), btn = d.getElementById("mcTodayNew");
            btn.click(); if (!await isOpen(np)) return { open: false };
            await pause(400);
            const box = np.querySelector(".mc-pop"), b = box.getBoundingClientRect(), a = btn.getBoundingClientRect();
            const arrow = b.left + parseFloat(csOf(box, "::before").left) + 7, mid = a.left + a.width / 2;
            const r = { open: true, diff: Math.round(arrow - mid), inL: Math.round(arrow - b.left), inR: Math.round(b.right - arrow), bg: csOf(box).backgroundColor,
                        overButton: arrow >= a.left + 4 && arrow <= a.right - 4,
                        // Diagnose in Bildschirmkoordinaten: Bildschirm, Fenster, Popover und Knopf
                        screen: [w.screen.availLeft, w.screen.availWidth], win: [w.screenX, w.outerWidth],
                        panel: (o => [Math.round(o.left), Math.round(o.width)])(np.getOuterScreenRect()), btnX: Math.round(w.mozInnerScreenX + a.left) };
            await shutPop(np); return r; };
          w.moveTo(0, 0); w.resizeTo(1500, 900); out.left = await measure();
          // rechter Fensterrand am Bildschirmrand (wie maximiert): Gecko schiebt das Popover nach links
          w.resizeTo(1300, 900); await pause(800); w.moveTo(w.screen.availLeft + w.screen.availWidth - w.outerWidth, w.screen.availTop);
          // das „+“ selbst 26 px vor dem Bildschirmrand wie im maximierten Fenster unter macOS (unter Linux/Windows
          // liegt es wegen Menü und Fensterknöpfen weiter innen, Gecko klappte das Popover dort nie um)
          await pause(800); const nb = d.getElementById("mcTodayNew");
          if (!w.TodayPane.isVisible) { d.getElementById("mcTodayToggle").click(); await pause(900); }
          const shift = w.screen.availLeft + w.screen.availWidth - 26 - (w.mozInnerScreenX + nb.getBoundingClientRect().right);
          if (Math.abs(shift) > 2) { w.moveTo(w.screenX + Math.round(shift), w.screen.availTop); await pause(800); }
          out.edge = await measure();
          w.moveTo(sx, sy); w.resizeTo(sw, sh); await pause(800);
          out.token = colorOf(d, "var(--mt-popover-bg)", "backgroundColor");
          return out;""")
        shots = [res["left"], res["edge"]]
        if any(not s["open"] for s in shots) and res["visibility"] == "hidden":
            return True, f"Testfenster verdeckt – übersprungen {res}"
        # am Bildschirmrand bleibt der Pfeil vor der runden Ecke – dann zumindest über dem Knopf
        ok = all(s["open"] and s["inL"] >= 20 and s["inR"] >= 20 and same_color(s["bg"], res["token"]) for s in shots) \
            and abs(res["left"]["diff"]) <= 3 and (abs(res["edge"]["diff"]) <= 3 or res["edge"]["overButton"])
        return ok, f"{res}"
    check("Today-Pane: Pfeil des „+“-Popovers über der Mitte des Knopfs (auch am Bildschirmrand)", new_popup_arrow, results)

    def event_dialog():
        # Termin-Dialog: Schrift 13 px (Beschriftungen, Felder, Beschreibung in der Systemschrift), Abstand Beschriftung–Feld;
        # Minimonat im Datumsfeld ohne Heute-Kästchen und fette Lavendel-Wochen; Uhrzeit-Raster ohne Gitter, 13 px, Akzent
        res = m.js(CAL_CHECK_JS + r"""
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          const c = testCalendar(); const e = new CalEvent(); e.title = "Halo Dialogtermin"; e.calendar = c;
          const s = cal.dtz.now(); s.minute = 0; s.second = 0; const en = s.clone(); en.hour += 1; e.startDate = s; e.endDate = en;
          e.setProperty("DESCRIPTION", "Erfundene Beschreibung zum Test."); const saved = await c.addItem(e);
          const out = {};
          let dw = null;
          try {
            await toCalendar(); w.modifyEventWithDialog(saved, true);
            dw = await winUrl("calendar-event-dialog"); if (!dw) return { dialog: false };
            const iw = await till(() => { const f = dw.document.getElementById("calendar-item-panel-iframe")?.contentWindow;
              return f?.document.readyState == "complete" && f.document.getElementById("event-grid") && f; }, 8000);
            const id = iw.document, ed = id.getElementById("item-description");
            const body = await till(() => { const b = ed.contentDocument?.body; return b && /Erfundene/.test(b.textContent) && b; }, 6000);
            await pause(1800);
            // Zeilen mit Beschriftung (XUL-label mit value) und sichtbarem Feld
            const rows = [...id.querySelectorAll("#event-grid > tr")].filter(tr => vis(tr.querySelector(":scope > th label")) && vis(tr.querySelector(":scope > td")?.firstElementChild));
            out.rows = rows.map(tr => { const lab = tr.querySelector(":scope > th label"), fld = tr.querySelector(":scope > td").firstElementChild;
              return { text: lab.getAttribute("value") || lab.textContent.trim(), font: csOf(lab).fontSize, gap: Math.round(fld.getBoundingClientRect().left - lab.getBoundingClientRect().right) }; });
            out.title = csOf(id.getElementById("item-title")).fontSize;
            out.desc = body ? { font: csOf(body).fontSize, family: csOf(body).fontFamily } : null;
            const grid = id.getElementById("event-grid");
            out.overflow = { grid: [grid.scrollWidth, grid.clientWidth], doc: [id.documentElement.scrollWidth, id.documentElement.clientWidth] };
            // Datumsfeld: Minimonat
            const dml = id.querySelector("#event-starttime datepicker menulist");
            dml.open = true;
            if (await isOpen(dml.menupopup)) {
              await pause(500);
              const mm = dml.menupopup.querySelector("calendar-minimonth"), td = mm.querySelector("td.minimonth-day[today]"), wk = [...mm.querySelectorAll(".minimonth-week")].find(vis);
              out.mini = { bg: csOf(mm).backgroundColor, today: td ? csOf(td).borderTopColor : null, week: wk ? [csOf(wk).fontWeight, csOf(wk).color] : null };
              await shutPop(dml.menupopup);
            }
            // Uhrzeitfeld: Raster
            // unter Linux (xvfb, ohne Fenstermanager) schließt sich das Popup gleich wieder – das Raster ist mit
            // popupshowing aber aufgebaut und gestaltet, gemessen wird dann am geschlossenen Popup
            const tml = id.querySelector("#event-starttime timepicker menulist");
            tml.open = true;
            if (await isOpen(tml.menupopup) || tml.menupopup.querySelector(".time-picker-hour-box-class[selected]")) {
              await pause(500);
              const g = tml.menupopup.querySelector("timepicker-grids"), hb = g.querySelector(".time-picker-hour-box-class"), sh = g.querySelector(".time-picker-hour-box-class[selected]");
              out.time = { border: [csOf(hb).borderLeftColor, csOf(hb).borderLeftWidth], radius: csOf(hb).borderTopLeftRadius,
                           font: csOf(g.querySelector(".time-picker-grids")).fontSize, sel: sh ? csOf(sh).backgroundColor : null, accent: colorOf(id, "AccentColor", "backgroundColor") };
              await shutPop(tml.menupopup);
            }
          } finally {
            if (dw && !dw.closed) { dw.close(); await till(() => dw.closed, 4000); }
            try { await c.deleteItem(saved); } catch {}
          }
          return out;""")
        if res.get("dialog") is False:
            return False, "Termin-Dialog nicht offen"
        rows, mini, tp = res.get("rows") or [], res.get("mini") or {}, res.get("time") or {}
        desc = res.get("desc") or {}
        ok = (len(rows) >= 4 and all(r["font"] == "13px" and r["gap"] >= 8 for r in rows) and res["title"] == "13px"
              and desc.get("font") == "13px" and ("system-ui" in desc.get("family", "") or "-apple-system" in desc.get("family", ""))
              and res["overflow"]["doc"][0] <= res["overflow"]["doc"][1] + 1
              and bool(mini) and rgba_alpha(mini["bg"]) == 0 and (mini["today"] is None or rgba_alpha(mini["today"]) == 0)
              and mini["week"] and mini["week"][0] == "400" and not same_color(mini["week"][1], "rgb(155, 158, 194)")
              and bool(tp) and (rgba_alpha(tp["border"][0]) == 0 or tp["border"][1] == "0px") and tp["radius"] == "6px" and tp["font"] == "13px"
              and tp["sel"] and not same_color(tp["sel"], "rgb(0, 100, 225)") and same_color(tp["sel"], tp["accent"]))
        return ok, f"{res}"
    check("Termin-Dialog: Schrift 13 px auch in der Beschreibung, Abstand Beschriftung–Feld; Minimonat und Uhrzeit-Raster ruhig mit Akzent", event_dialog, results)

    def event_dialog_lines():
        # Termin-Dialog: Trennlinien im Raster als Haarlinie (Thunderbird: 1 px Feldrahmenfarbe); Statuszeile mit Abstand
        # zwischen Beschriftung und Wert („Time as: Busy“ statt „Time as:Busy“); Beschreibung dunkel lesbar (früher schwarz auf #1E1E1E)
        res = m.js(CAL_CHECK_JS + r"""
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          const c = testCalendar(); const e = new CalEvent(); e.title = "Halo Linientermin"; e.calendar = c;
          const s = cal.dtz.now(); s.minute = 0; s.second = 0; const en = s.clone(); en.hour += 1; e.startDate = s; e.endDate = en;
          e.setProperty("DESCRIPTION", "Erfundene Beschreibung zum Kontrast."); e.setProperty("TRANSP", "OPAQUE"); e.setCategories(["Business"]); const saved = await c.addItem(e);
          const out = { dark };
          let dw = null;
          try {
            await toCalendar(); w.modifyEventWithDialog(saved, true);
            dw = await winUrl("calendar-event-dialog"); if (!dw) return { dialog: false };
            const iw = await till(() => { const f = dw.document.getElementById("calendar-item-panel-iframe")?.contentWindow;
              return f?.document.readyState == "complete" && f.document.getElementById("event-grid") && f; }, 8000);
            const id = iw.document, ed = id.getElementById("item-description");
            const body = await till(() => { const b = ed.contentDocument?.body; return b && /Erfundene/.test(b.textContent) && b; }, 6000);
            await pause(1800);
            out.seps = [...id.querySelectorAll("#event-grid tr.separator td")].filter(vis).map(td => [csOf(td).borderBottomColor, csOf(td).borderBottomWidth]);
            // Statuszeile „Time as: Busy“ (nur bei gesetzter Verfügbarkeit sichtbar)
            const fb = await till(() => { const p = dw.document.getElementById("status-freebusy"); return vis(p) && p; }, 3000);
            const labs = fb ? [...fb.querySelectorAll(":scope > label")].filter(l => !l.hidden && vis(l)) : [];
            out.status = labs.length >= 2 ? Math.round((labs[1].getBoundingClientRect().left - labs[0].getBoundingClientRect().right) * 10) / 10 : null;
            out.statusText = labs.map(l => l.value || l.textContent).join("|");
            out.shadows = [...new Set([...dw.document.querySelectorAll("#status-bar :is(label, description)")].map(l => csOf(l).textShadow))];
            // Kategorien: Farbpunkte im Menü mit feinem Ring, Farbchip der gewählten Kategorie im Feld mit Haarlinie
            const cats = id.getElementById("item-categories"), cp = id.getElementById("item-categories-popup") || cats?.menupopup;
            const mt = cp && [...cp.querySelectorAll(":scope > menuitem .menu-text")][0];
            out.catDot = mt ? csOf(mt).backgroundImage.slice(0, 20) : null;
            const chip = cats?.shadowRoot?.querySelector('[part~="color"]');
            out.catChip = chip ? csOf(chip).boxShadow : null;
            let bg = null;
            for (let el = ed; el && el.nodeType == 1; el = el.parentElement) { const b = csOf(el).backgroundColor; if (!/rgba\(.*, 0\)$/.test(b) && b != "transparent") { bg = b; break; } }
            out.desc = body ? { color: csOf(body).color, body: csOf(body).backgroundColor, field: bg } : null;
          } finally {
            if (dw && !dw.closed) { dw.close(); await till(() => dw.closed, 4000); }
            try { await c.deleteItem(saved); } catch {}
          }
          return out;""")
        if res.get("dialog") is False:
            return False, "Termin-Dialog nicht offen"
        seps, desc = res.get("seps") or [], res.get("desc") or {}
        ok_desc = bool(desc) and (rgba_alpha(desc["body"]) == 0 or not res["dark"]) and (
            contrast(desc["color"], desc["field"]) >= 4.5 if res["dark"] else luminance(desc["color"]) < 0.2)
        ok = (len(seps) >= 2 and all(rgba_alpha(c) <= 0.12 and float(wd[:-2]) <= 1 for c, wd in seps)
              and res.get("status") is not None and res["status"] >= 3 and ok_desc
              and res.get("shadows") == ["none"] and (res.get("catDot") or "").startswith("radial-gradient")
              and res.get("catChip") not in (None, "none"))
        return ok, f"{res}"
    check("Termin-Dialog: Trennlinien als Haarlinie, „Time as: Busy“ mit Abstand ohne Prägeschatten, Beschreibung lesbar (dunkel ≥ 4,5:1), Kategorie-Farbpunkte mit Ring", event_dialog_lines, results)

    def reminder_dialog():
        # Erinnerungen anpassen: Liste ohne native Rahmenzeichnung, mit Haarlinie; Trenner neben den Überschriften fein
        res = m.js(CAL_CHECK_JS + r"""
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          const c = testCalendar(); const e = new CalEvent(); e.title = "Halo Erinnerungstermin"; e.calendar = c;
          const s = cal.dtz.now(); s.minute = 0; s.second = 0; s.day += 1; const en = s.clone(); en.hour += 1; e.startDate = s; e.endDate = en;
          const saved = await c.addItem(e);
          const out = { dark };
          let dw = null, rw = null;
          try {
            await toCalendar(); w.modifyEventWithDialog(saved, true);
            dw = await winUrl("calendar-event-dialog.xhtml"); if (!dw) return { dialog: false };
            const iw = await till(() => { const f = dw.document.getElementById("calendar-item-panel-iframe")?.contentWindow;
              return f?.document.readyState == "complete" && f.document.getElementById("item-alarm") && f; }, 8000);
            await pause(800);
            const ml = iw.document.getElementById("item-alarm"); ml.value = "custom"; later(() => iw.updateReminder());
            rw = await winUrl("calendar-event-dialog-reminder"); if (!rw) return { reminder: false };
            await pause(1200);
            const rd = rw.document, lb = rd.getElementById("reminder-listbox");
            out.list = { appearance: csOf(lb).appearance, border: csOf(lb).borderTopColor, bw: csOf(lb).borderTopWidth };
            out.seps = [...rd.querySelectorAll("separator.groove")].filter(vis).map(x => [csOf(x).borderTopColor, csOf(x).borderTopWidth]);
          } finally {
            if (rw && !rw.closed) { rw.close(); await till(() => rw.closed, 4000); }
            if (dw && !dw.closed) { dw.close(); await till(() => dw.closed, 4000); }
            try { await c.deleteItem(saved); } catch {}
          }
          return out;""")
        if res.get("dialog") is False or res.get("reminder") is False:
            return False, f"Dialog nicht offen {res}"
        lst, seps = res.get("list") or {}, res.get("seps") or []
        ok = (lst.get("appearance") == "none" and rgba_alpha(lst["border"]) <= 0.12 and float(lst["bw"][:-2]) <= 1
              and len(seps) >= 2 and all(float(wd[:-2]) <= 1 and not same_color(c, "rgba(128, 128, 128, 0.6)") and rgba_alpha(c) <= 0.12 for c, wd in seps))
        return ok, f"{res}"
    check("Erinnerungen anpassen: Liste und Trenner als Haarlinie ohne native Rahmen", reminder_dialog, results)

    def recurrence_preview():
        # Wiederholung: Monate der Vorschau mit Haarlinie und 10 px Radius statt 1 px Zinkgrau (dunkel #71717A), ohne Fläche
        res = m.js(CAL_CHECK_JS + r"""
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          const out = { dark };
          let dw = null, rw = null;
          try {
            await toCalendar(); w.createEventWithDialog(testCalendar(), null, null, "Halo Wiederholungsvorschau");
            dw = await winUrl("calendar-event-dialog.xhtml"); if (!dw) return { dialog: false };
            const iw = await till(() => { const f = dw.document.getElementById("calendar-item-panel-iframe")?.contentWindow;
              return f?.document.readyState == "complete" && f.document.getElementById("item-repeat") && f; }, 8000);
            await pause(800);
            const ml = iw.document.getElementById("item-repeat"); ml.value = "custom"; later(() => iw.editRepeat ? iw.editRepeat() : iw.updateRepeat());
            rw = await winUrl("calendar-event-dialog-recurrence"); if (!rw) return { recurrence: false };
            await pause(1500);
            const rd = rw.document, mid = el => { const r = el.getBoundingClientRect(); return r.top + r.height / 2; };
            const lab = [...rd.querySelectorAll("label.recurrence-pattern-hbox-label")].find(vis), pl = rd.getElementById("period-list");
            const dd = rd.getElementById("daily-days");
            out.align = lab && pl ? Math.round((mid(lab) - mid(pl)) * 10) / 10 : null;
            out.heights = [pl && Math.round(pl.getBoundingClientRect().height * 10) / 10, dd && vis(dd) ? Math.round(dd.getBoundingClientRect().height * 10) / 10 : null];
            out.months = [...rw.document.querySelectorAll("#recurrencePreview calendar-minimonth")].filter(vis).map(mm => { const st = csOf(mm);
              return { bg: st.backgroundColor, bw: st.borderTopWidth, border: st.borderTopColor, radius: st.borderTopLeftRadius,
                       busy: [...mm.querySelectorAll("td[busy]")].length }; });
          } finally {
            if (rw && !rw.closed) { rw.close(); await till(() => rw.closed, 4000); }
            if (dw && !dw.closed) { dw.close(); await till(() => dw.closed, 4000); }
          }
          return out;""")
        if res.get("dialog") is False or res.get("recurrence") is False:
            return False, f"Dialog nicht offen {res}"
        ms = res.get("months") or []
        ok = (len(ms) >= 1 and all(rgba_alpha(x["bg"]) == 0 and float(x["bw"][:-2]) <= 1 and rgba_alpha(x["border"]) <= 0.12
                                   and not same_color(x["border"], "rgb(113, 113, 122)") and float(x["radius"][:-2]) >= 10 for x in ms)
              and any(x["busy"] for x in ms))
        al, hs = res.get("align"), res.get("heights") or [None, None]
        ok = ok and al is not None and abs(al) <= 1 and None not in hs and abs(hs[0] - 28) <= 1 and abs(hs[1] - 28) <= 1
        return ok, f"{res}"
    check("Wiederholung: Vorschau-Monate mit Haarlinie und 10 px Radius, ohne Fläche, Belegt-Punkte bleiben; „Repeat“ mittig zur Liste, Zahlenfeld 28 px", recurrence_preview, results)

    def agenda_days():
        # Today-Pane: Tagesspalte (ca. 38 px) eines Tags mit nur einem Eintrag ragte bis auf 2–6 px an den nächsten Tag
        res = m.js(CAL_CHECK_JS + r"""
          const c = testCalendar(); const added = [];
          try {
            for (const [dd, title] of [[5, "Halo Agenda Einzeltag"], [6, "Halo Agenda Folgetag"]]) {
              const e = new CalEvent(); e.title = title; e.calendar = c; const s = today(); s.day += dd; const en = s.clone(); en.day += 1;
              e.startDate = s; e.endDate = en; added.push(await c.addItem(e)); }
            await toMail(); if (!w.TodayPane?.isVisible) d.getElementById("calendar_toggle_todaypane_command").doCommand();
            await pause(2000);
            const lis = [...d.querySelectorAll("#agenda > li.agenda-listitem")].filter(vis);
            const out = { pairs: [], single: 0 };
            lis.forEach((li, i) => { const h = li.querySelector(":scope > .agenda-date-header"); if (!h || h.hidden) return;
              const next = lis.slice(i + 1).find(x => { const nh = x.querySelector(":scope > .agenda-date-header"); return nh && !nh.hidden; });
              if (!next) return;
              const single = lis[i + 1] == next; if (single) out.single++;
              out.pairs.push([h.dataset.mcDay, single, Math.round(next.querySelector(":scope > .agenda-date-header").getBoundingClientRect().top - h.getBoundingClientRect().bottom)]); });
            return out;
          } finally { for (const it of added) try { await c.deleteItem(it); } catch {} }""")
        ps = res.get("pairs") or []
        ok = res.get("single", 0) >= 1 and len(ps) >= 2 and all(gap >= 12 for _, _, gap in ps)
        return ok, f"{res}"
    check("Today-Pane: Tage mit nur einem Eintrag ragen nicht in den nächsten Tag", agenda_days, results)

    def occurrence_prompt():
        # Rückfrage wiederholter Termin: Titelkasten ohne harten Rahmen, Kapselknöpfe ohne alte Kalendersymbole
        res = m.js(CAL_CHECK_JS + r"""
          const { CalRecurrenceInfo } = ChromeUtils.importESModule("resource:///modules/CalRecurrenceInfo.sys.mjs");
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          const c = testCalendar(); const e = new CalEvent(); e.title = "Halo Serientermin"; e.calendar = c;
          const s = cal.dtz.now(); s.minute = 0; s.second = 0; s.day -= 7; const en = s.clone(); en.hour += 1; e.startDate = s; e.endDate = en;
          e.recurrenceInfo = new CalRecurrenceInfo(e); e.recurrenceInfo.appendRecurrenceItem(cal.createRecurrenceRule("RRULE:FREQ=WEEKLY;COUNT=10"));
          const saved = await c.addItem(e);
          const out = {};
          let pw = null;
          try {
            await toCalendar(); w.switchToView("week"); await pause(800);
            const occ = saved.recurrenceInfo.getNextOccurrence(cal.dtz.now()) || saved;
            later(() => w.calendarViewController.deleteOccurrences([occ], false, false));
            pw = await winUrl("calendar-occurrence-prompt"); if (!pw) return { prompt: false };
            await pause(1000);
            const pd = pw.document, h = pd.getElementById("occurrence-prompt-header");
            out.header = { bw: csOf(h).borderTopWidth, radius: csOf(h).borderTopLeftRadius };
            out.buttons = [...pd.querySelectorAll(".occurrence-accept-buttons")].filter(vis).map(b => { const ic = b.querySelector(".button-icon");
              // Textbereich: das Label (.button-text) ist so breit wie sein Text
              const lab = b.querySelector(".button-text"), t = lab ? lab.getBoundingClientRect() : { width: 0, left: 0, right: 0 }, br = b.getBoundingClientRect();
              return { img: csOf(b).listStyleImage, icon: !!ic && vis(ic), tw: Math.round(t.width), bw: Math.round(br.width),
                       padL: Math.round((t.left - br.left) * 10) / 10, padR: Math.round((br.right - t.right) * 10) / 10 }; });
          } finally {
            if (pw && !pw.closed) { pw.close(); await till(() => pw.closed, 4000); await pause(500); }
            try { await c.deleteItem(saved); } catch {}
          }
          return out;""")
        if res.get("prompt") is False:
            return False, "Rückfrage nicht offen"
        b = res.get("buttons") or []
        ok = res["header"]["bw"] == "0px" and len(b) >= 2 and all(x["img"] == "none" and not x["icon"] for x in b)
        ok = ok and all(0 < x["tw"] < x["bw"] - 20 and abs(x["padL"] - x["padR"]) <= 2 for x in b)
        return ok, f"{res}"
    check("Rückfrage wiederholter Termin: Titelkasten ohne harten Rahmen, Knöpfe ohne alte Kalendersymbole, Text mittig", occurrence_prompt, results)

    def quick_segment():
        # Schnellfenster: gewähltes Segment („Termin“/„Aufgabe“) heller als die Spur – dunkel früher dunkler (#1E1E1E)
        res = m.js(CAL_CHECK_JS + r"""
          await toWeek();
          const li = [...d.querySelectorAll('#unifiedToolbarContent li[item-id="new-event"]')].find(vis);
          li.querySelector("button").click();
          const qp = await till(() => { const q = d.getElementById("mcQuickPanel"); return q?.state == "open" && q; }, 4000);
          if (!qp) return { open: false, visibility: d.visibilityState };
          await pause(300);
          try {
            const sel = qp.querySelector(".mc-qc-seg > button[selected]");
            return { open: true, dark, sel: sel ? csOf(sel).backgroundColor : null, track: csOf(qp.querySelector(".mc-qc-seg")).backgroundColor };
          } finally { await shutPop(qp); }""")
        if not res.get("open"):
            return res.get("visibility") == "hidden", f"Schnellfenster nicht offen {res}"
        sel = res.get("sel")
        ok = bool(sel) and (luminance(sel) > 0.08 and rgba_alpha(sel) == 1 if res["dark"] else same_color(sel, "rgb(255, 255, 255)"))
        return ok, f"{res}"
    check("Schnellfenster: gewähltes Segment heller als die Spur (auch dunkel)", quick_segment, results)

    def quick_allday_calrow():
        # Schnellfenster: „All Day“ als macOS-Kästchen (früher grau gefülltes Systemkästchen ohne Rand, wirkte deaktiviert);
        # Kalendername 8 px hinter dem Farbpunkt statt ca. 21 px (Innenabstand der Auswahl)
        res = m.js(CAL_CHECK_JS + r"""
          await toWeek();
          const li = [...d.querySelectorAll('#unifiedToolbarContent li[item-id="new-event"]')].find(vis);
          li.querySelector("button").click();
          const qp = await till(() => { const q = d.getElementById("mcQuickPanel"); return q?.state == "open" && q; }, 4000);
          if (!qp) return { open: false, visibility: d.visibilityState };
          await pause(300);
          const out = { open: true, dark, checkBg: colorOf(d, "var(--mt-check-bg)", "backgroundColor"), accent: colorOf(d, "var(--mt-accent)", "backgroundColor") };
          try {
            const f = qp.__mc; if (!vis(f.allDay)) { f.summary.click(); await pause(600); }
            const cb = f.allDay, st = csOf(cb);
            out.cb = { app: st.appearance, bw: st.borderTopWidth, bg: st.backgroundColor, w: Math.round(cb.getBoundingClientRect().width) };
            const was = cb.checked; cb.click(); await pause(250);
            out.cbOn = { checked: cb.checked, bg: csOf(cb).backgroundColor, img: csOf(cb).backgroundImage.slice(0, 20) };
            if (cb.checked != was) { cb.click(); await pause(150); }
            const sel = f.calendar, card = sel.closest(".mc-qc-calcard");
            out.calGap = Math.round((sel.getBoundingClientRect().left + parseFloat(csOf(sel).paddingInlineStart)
              - (card.getBoundingClientRect().left + parseFloat(csOf(card).paddingInlineStart) + 12)) * 10) / 10;
            return out;
          } finally { await shutPop(qp); }""")
        if not res.get("open"):
            return res.get("visibility") == "hidden", f"Schnellfenster nicht offen {res}"
        cb, on = res.get("cb") or {}, res.get("cbOn") or {}
        ok = (cb.get("app") == "none" and float(cb["bw"][:-2]) >= 0.5 and same_color(cb["bg"], res["checkBg"])
              and on.get("checked") and same_color(on["bg"], res["accent"]) and on["img"].startswith("url(")
              and res.get("calGap") is not None and res["calGap"] <= 10)
        return ok, f"{res}"
    check("Schnellfenster: „Ganztägig“ als macOS-Kästchen, Kalendername dicht am Farbpunkt", quick_allday_calrow, results)

    def quick_time_fits():
        # Schnellfenster aufgeklappt: Datum, Uhrzeit (samt Uhrsymbol) und Auswahllisten bleiben auf der grauen Karte
        # (früher feste 96-px-Labelspalte – das Uhrsymbol ragte über die Kartenkante); Labels ungekürzt, Felder bündig
        res = m.js(CAL_CHECK_JS + r"""
          await toWeek();
          const li = [...d.querySelectorAll('#unifiedToolbarContent li[item-id="new-event"]')].find(vis);
          li.querySelector("button").click();
          const qp = await till(() => { const q = d.getElementById("mcQuickPanel"); return q?.state == "open" && q; }, 4000);
          if (!qp) return { open: false, visibility: d.visibilityState };
          await pause(300);
          try {
            const f = qp.__mc; if (!qp.querySelector(".mc-qc[data-expanded]")) { f.summary.click(); await pause(600); }
            const card = qp.querySelector(".mc-qc-time"), cr = card.getBoundingClientRect();
            const fields = [...card.querySelectorAll('input[type="date"], input[type="time"], select')].filter(vis).map(e => {
              const r = e.getBoundingClientRect();
              return { t: e.type || e.localName, over: Math.round((r.right - (cr.right - 4)) * 10) / 10,
                       clip: e.type == "time" ? e.scrollWidth - e.clientWidth : 0, left: Math.round(r.left) };
            });
            const labels = [...card.querySelectorAll(".mc-qc-row > label")].filter(vis).map(l => ({ t: l.textContent, clip: l.scrollWidth - l.clientWidth }));
            const ctrlLefts = [...new Set([...card.querySelectorAll(".mc-qc-row")].filter(vis).map(r => Math.round(r.querySelector(".mc-qc-ctrl").getBoundingClientRect().left)))];
            return { open: true, fields, labels, ctrlLefts, card: Math.round(cr.width) };
          } finally { await shutPop(qp); }""")
        if not res.get("open"):
            return res.get("visibility") == "hidden", f"Schnellfenster nicht offen {res}"
        fields, labels = res.get("fields") or [], res.get("labels") or []
        ok = (sum(1 for x in fields if x["t"] == "time") >= 2 and all(x["over"] <= 0 for x in fields)
              and all(x["clip"] <= 1 for x in fields) and len(labels) >= 5 and all(x["clip"] <= 0 for x in labels)
              and len(res.get("ctrlLefts") or []) == 1)
        return ok, f"{res}"
    check("Schnellfenster: Uhrzeit samt Uhrsymbol innerhalb der Karte, Labels ungekürzt, Felder bündig", quick_time_fits, results)

    def enable_badge():
        # Kalenderliste: Plakette „Aktivieren“ als graue Kapsel statt schieferblauer Fläche mit weißer Großschrift
        res = m.js(CAL_CHECK_JS + r"""
          const c = testCalendar(); c.setProperty("disabled", true);
          try {
            await toCalendar();
            const b = await till(() => [...d.querySelectorAll("#calendar-list button.calendar-enable-button")].find(vis), 4000);
            if (!b) return { badge: false };
            // Haken im Farbkästchen des deaktivierten, eingeblendeten Kalenders: Textfarbe statt weiß
            const li = b.closest("li"), shown = li?.querySelector("input.calendar-displayed")?.checked;
            const sw = li?.querySelector(".calendar-color");
            return { bg: csOf(b).backgroundColor, color: csOf(b).color, tt: csOf(b).textTransform, weight: csOf(b).fontWeight, radius: csOf(b).borderTopLeftRadius,
                     dark: w.matchMedia("(prefers-color-scheme: dark)").matches, disabled: li?.hasAttribute("calendar-disabled"), shown,
                     tick: sw ? w.getComputedStyle(sw, "::after").backgroundColor : null };
          } finally { c.setProperty("disabled", false); await pause(500); }""")
        if res.get("badge") is False:
            return False, "Plakette nicht sichtbar"
        ok = (not same_color(res["bg"], "rgb(107, 128, 164)") and not same_color(res["color"], "rgb(255, 255, 255)")
              and res["tt"] == "none" and int(res["weight"]) <= 600)
        if res.get("shown"):
            ok = ok and res.get("disabled") and same_color(res["tick"], "rgb(161, 161, 166)" if res["dark"] else "rgb(110, 110, 115)")
        else:
            ok = False
        return ok, f"{res}"
    check("Kalenderliste: Plakette „Aktivieren“ als graue Kapsel ohne Großschrift; Haken des deaktivierten Kalenders grau statt weiß", enable_badge, results)

    def print_minimonths():
        # Drucken: „Von“/„Bis“-Minikalender passen ins Formular, Pfeile sichtbar, Knöpfe ohne helle Fläche (dunkel)
        res = m.js(CAL_CHECK_JS + r"""
          w.resizeTo(1500, 900); await pause(600); await toCalendar(); w.switchToView("week"); await pause(800);
          later(() => w.goDoCommand("cmd_print"));
          const frame = await till(() => [...d.querySelectorAll(".dialogFrame, browser")].find(f => { try { return f.contentDocument?.querySelector("form#calendar-print #from-minimonth .months-forward-button"); } catch { return false; } }), 12000);
          if (!frame) return { print: false };
          const pd = frame.contentDocument; await pause(1500);
          const form = pd.querySelector("form#calendar-print"), fr = form.getBoundingClientRect();
          const out = { print: true, dark, months: ["from-minimonth", "to-minimonth"].map(idm => { const mm = pd.getElementById(idm), r = mm.getBoundingClientRect();
            const fwd = mm.querySelector(".months-forward-button"), nav = mm.querySelector(".minimonth-nav-btn:not(.today-button, .years-back-button, .years-forward-button)");
            return { right: Math.round(r.right * 10) / 10, formRight: Math.round(fr.right * 10) / 10, fwd: Math.round(fwd.getBoundingClientRect().width),
                     mask: csOf(fwd, "::before").maskImage.slice(0, 12), navBg: nav ? csOf(nav).backgroundColor : null,
                     heads: [...mm.querySelectorAll(".minimonth-month-name, .minimonth-year-name")].map(i => csOf(i).appearance) }; }) };
          const cancel = pd.querySelector('#next-button-container button[is="cancel-button"]');
          if (cancel) cancel.click();
          await pause(800);
          try { if (frame.isConnected && frame.contentDocument?.querySelector("form#calendar-print")) frame.contentWindow.close(); } catch {}
          await pause(500);
          return out;""")
        if not res.get("print"):
            return False, f"keine Druckvorschau {res}"
        def dim(c):
            import re
            v = [float(x) for x in re.findall(r"-?[\d.]+", c or "")][:3]
            lum = sum(k * ((x / 255) / 12.92 if x / 255 <= 0.03928 else ((x / 255 + 0.055) / 1.055) ** 2.4) for k, x in zip((0.2126, 0.7152, 0.0722), v)) if len(v) == 3 else 1
            return rgba_alpha(c) < 0.2 or lum < 0.3
        ok = all(mm["right"] <= mm["formRight"] + 0.5 and mm["fwd"] > 0 and mm["mask"].startswith("url(")
                 and (not res["dark"] or (mm["navBg"] and dim(mm["navBg"])))
                 and len(mm["heads"]) == 2 and all(x == "none" for x in mm["heads"]) for mm in res["months"])
        return ok, f"{res}"
    check("Drucken: Minikalender „Von“/„Bis“ im Formular, Pfeile sichtbar, Knöpfe ohne helle Fläche, Monat/Jahr ohne Feldfläche", print_minimonths, results)


def rgba_alpha(c):
    """Deckkraft aus rgb()/rgba()/color(srgb …) – 1, wenn keine angegeben ist."""
    import re
    v = re.findall(r"-?[\d.]+(?:e-?\d+)?", c or "")
    return float(v[3]) if len(v) > 3 else 1.0


def luminance(c):
    """Relative Luminanz (WCAG) aus rgb()/rgba()/color(srgb …)."""
    import re
    v = [float(x) for x in re.findall(r"-?[\d.]+(?:e-?\d+)?", c or "")][:3]
    if len(v) < 3:
        return 0.0
    k = 1 if (c or "").startswith("color(") else 255
    lin = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return sum(f * lin(x / k) for f, x in zip((0.2126, 0.7152, 0.0722), v))


def contrast(a, b):
    """Kontrastverhältnis (WCAG) zweier Farben."""
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def same_color(a, b, tol=2):
    """Gleiche Farbe (rgb() und color(srgb …) gleichwertig), Abweichung höchstens tol je Kanal."""
    import re
    def norm(c):
        v = [float(x) for x in re.findall(r"-?[\d.]+(?:e-?\d+)?", c or "")]
        k = 255 if (c or "").startswith("color(") else 1
        return [x * k for x in v[:3]] + [v[3] if len(v) > 3 else 1.0]
    x, y = norm(a), norm(b)
    return len(x) == 4 and len(y) == 4 and all(abs(p - q) <= (0.02 if i == 3 else tol) for i, (p, q) in enumerate(zip(x, y)))


def run_checks(m, version, profile, results):
    # Vorbereitung: Fenstergröße, Testkalender, Fenster ohne Dialoge
    m.js("""
      for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
      w.moveTo(0, 0); w.resizeTo(1500, 900); await wait(500);
      // Marionette sperrt Add-on-Updates – für die Prüfung „Updates beim Start“ erlauben. Die Update-Liste
      // (updates.json auf GitHub) bleibt im Testprofil aber unerreichbar: ein veröffentlichtes Update
      // ersetzte sonst mitten im Lauf Design und Logik des geprüften Pakets
      Services.obs.addObserver({ observe(ch) { ch.QueryInterface(Ci.nsIHttpChannel);
        if (/\\/updates\\.json(\\?|$)/.test(ch.URI.spec)) ch.cancel(Cr.NS_ERROR_ABORT); } }, "http-on-modify-request");
      Services.prefs.setBoolPref("extensions.update.enabled", true);
      // Aktionen beim Überfahren sind standardmäßig aus – für die Prüfungen einschalten
      Services.prefs.setBoolPref("extensions.mailcards.hoverActions", true);
      if (!testCalendar()) { const c = cal.manager.createCalendar("storage", Services.io.newURI("moz-storage-calendar://")); c.name = "Halo Test"; c.setProperty("color", "#FF9500"); cal.manager.registerCalendar(c); }
      return 1;""")

    def addon():
        v = m.js("""const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
                    const a = await AddonManager.getAddonByID("%s"); return [a?.version, a?.isActive];""" % ADDON_ID)
        return v == [version, True], f"{v}"
    check("Erweiterung aktiv und richtige Version", addon, results)

    def folder_start_width():
        # Neues Profil, Mail-Tab zuerst offen: Ordnerliste 206 px wie in Apple Mail (und wie nach
        # Doppelklick auf den Trenner) statt Thunderbirds 198 px, sodass „Local Folders“ in den
        # Favoriten neben einer Ungelesen-Zahl nicht gekürzt wird. Muss vor „Ordnerleiste: Ziehen
        # und Doppelklick“ laufen, das die gespeicherte Breite ändert
        res = m.js("""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Inbox")) { root.createSubfolder("Inbox", null); }
          const inbox = root.getChildNamed("Inbox");
          const a3 = await toMail(); await wait(1000); const ad = a3.document;
          const row = await until(() => [...ad.querySelectorAll('#folderTree > li[data-mode="smart"] li[is="folder-tree-row"]')]
            .find(li => li.uri == inbox.URI && li.querySelector(":scope > .container .name")?.clientWidth), 8000);
          const name = row?.querySelector(":scope > .container .name");
          // Ungelesen-Zahl wie im Alltag (einstellig) nur für die Messung anzeigen
          if (row) row.unreadCount = 6; await wait(300);
          const out = { width: Math.round(ad.getElementById("folderPane").getBoundingClientRect().width),
                        pref: Services.prefs.getIntPref("extensions.mailcards.sidebarWidth", 0), text: name?.textContent,
                        count: row?.querySelector(":scope > .container .unread-count")?.textContent,
                        client: name?.clientWidth, scroll: name?.scrollWidth };
          if (row) row.unreadCount = inbox.getNumUnread(false);
          return out;""")
        # die 206 px sind auf die Systemschrift von macOS abgestimmt (dort passt „Local Folders“ genau) – mit
        # anderen Schriften (Linux: 2 px breiter) wird nur die Breite geprüft
        fits = res["scroll"] <= res["client"] or sys.platform != "darwin"
        ok = (res["width"] == 206 and res["pref"] in (0, 206) and res["text"] == "Local Folders"
              and res["count"] == "6" and res["client"] and fits)
        return ok, f"{res}"
    check("Ordnerliste: im neuen Profil 206 px breit, „Local Folders“ nicht gekürzt", folder_start_width, results)

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
        detail = " · ".join(f"{r['width']}px: Linie {'✓' if r['line'] else '✗'}, Knöpfe {'✓' if r['buttonsRightOfList'] else '✗'}, Suche {r['search']}" for r in res)
        return ok, detail
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
          await until(() => p.state == "closed", 3000);
          return { opened: true, afterIme, created: (await items("Halo Testtermin")).length, closed: p.state, visibility: d.visibilityState };""")
        # verdeckt pausiert macOS die Schließ-Animation – dann bleibt es bei „hiding“
        closed = res["closed"] == "closed" or (res["closed"] == "hiding" and res["visibility"] == "hidden")
        ok = res["afterIme"] == 0 and res["created"] == 1 and closed
        return ok, f"nach IME-Enter {res['afterIme']}, nach Enter {res['created']} Termin, Fenster {res['closed']} ({res['visibility']})"
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
          // nur Tag und Dauer („morgen für 2h“): nicht ganztägig, 2 Stunden lang
          li.querySelector("button").click(); await wait(900);
          const t2 = p.querySelector(".mc-qc-title");
          p.querySelector(".mc-qc-calsel").value = testCalendar().id; p.querySelector(".mc-qc-calsel").dispatchEvent(new w.Event("change"));
          t2.value = "Halo NL Dauer morgen für 2h"; t2.dispatchEvent(new w.Event("input", { bubbles: true })); await wait(300);
          p.querySelector(".mc-qc-primary").click(); await wait(1200);
          const it2 = (await items("Halo NL Dauer"))[0];
          const dur = it2 ? { allDay: it2.startDate.isDate, minutes: (cal.dtz.dateTimeToJsDate(it2.endDate) - cal.dtz.dateTimeToJsDate(it2.startDate)) / 60000,
                              tomorrow: cal.dtz.dateTimeToJsDate(it2.startDate).getDate() == tm2.getDate() } : null;
          return { tomorrow: s.getDate() == tm2.getDate(), start: s.getHours() * 60 + s.getMinutes(), minutes: (e - s) / 60000, dur };''')
        ok = (bool(res) and res["tomorrow"] and res["start"] == 750 and res["minutes"] == 90
              and bool(res["dur"]) and res["dur"]["allDay"] is False and res["dur"]["minutes"] == 120 and res["dur"]["tomorrow"])
        return ok, f"{res}"
    check("Schnellfenster: natürliche Eingabe („morgen 12:30 für 90 min“, „morgen für 2h“ nicht ganztägig)", natural, results)

    def natural_rules():
        # parseNatural direkt über das Experiment-Modul, „jetzt“ = Di 20.10.2026 15:00
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
          const parse = Cu.evalInSandbox("parseNatural", g);
          const p = n => String(n).padStart(2, "0");
          const f = x => x ? `${p(x.getDate())}.${p(x.getMonth() + 1)}.${x.getFullYear()} ${p(x.getHours())}:${p(x.getMinutes())}` : "-";
          const out = {};
          for (const t of ["Lunch für 2h um 12 Uhr", "Workshop für 1.5h morgen um 10 Uhr", "Meeting 14:00 für 2h", "Arzt Freitag morgen 8 Uhr",
                           "Arzt morgen 8 Uhr", "Termin 1.3.25", "Call 11-1pm", "Call 2-4pm", "Party 22-2 Uhr", "Arbeit 9-5",
                           "Schicht 18-7 Uhr", "Standup 11-12am", "Gottesdienst Karfreitag morgen 10 Uhr", "Party 11-1am", "Party 10-2am",
                           "Meeting morgen für 2h"]) {
            const r = parse(t, new Date(2026, 9, 20, 15, 0));
            out[t] = `${r.title} | ${f(r.start)} – ${f(r.end)}` + (!r.end && !r.allDay ? ` | ohne Uhrzeit, ${r.duration} min` : "");
          }
          return out;''' % ADDON_ID)
        expected = {
            "Lunch für 2h um 12 Uhr": "Lunch | 20.10.2026 12:00 – 20.10.2026 14:00",
            "Workshop für 1.5h morgen um 10 Uhr": "Workshop | 21.10.2026 10:00 – 21.10.2026 11:30",
            "Meeting 14:00 für 2h": "Meeting | 20.10.2026 14:00 – 20.10.2026 16:00",
            "Arzt Freitag morgen 8 Uhr": "Arzt | 23.10.2026 08:00 – 23.10.2026 09:00",
            "Arzt morgen 8 Uhr": "Arzt | 21.10.2026 08:00 – 21.10.2026 09:00",
            "Termin 1.3.25": "Termin | 01.03.2025 00:00 – -",
            "Call 11-1pm": "Call | 20.10.2026 11:00 – 20.10.2026 13:00",
            "Call 2-4pm": "Call | 20.10.2026 14:00 – 20.10.2026 16:00",
            "Party 22-2 Uhr": "Party | 20.10.2026 22:00 – 21.10.2026 02:00",
            "Arbeit 9-5": "Arbeit | 20.10.2026 09:00 – 20.10.2026 17:00",
            "Schicht 18-7 Uhr": "Schicht | 20.10.2026 18:00 – 21.10.2026 07:00",
            "Standup 11-12am": "Standup | 20.10.2026 11:00 – 20.10.2026 12:00",
            "Gottesdienst Karfreitag morgen 10 Uhr": "Gottesdienst Karfreitag | 21.10.2026 10:00 – 21.10.2026 11:00",
            "Party 11-1am": "Party | 20.10.2026 23:00 – 21.10.2026 01:00",
            "Party 10-2am": "Party | 20.10.2026 22:00 – 21.10.2026 02:00",
            "Meeting morgen für 2h": "Meeting | 21.10.2026 00:00 – - | ohne Uhrzeit, 120 min",
        }
        bad = [f"„{k}“ → {res.get(k)}" for k, v in expected.items() if res.get(k) != v]
        return not bad, "; ".join(bad) or f"{len(expected)} Eingaben richtig (Dauer, Dauer ohne Uhrzeit, „Freitag morgen“, „Karfreitag morgen“, Jahr „25“, am/pm, „12am“, „11-1am“, über Mitternacht)"
    check("Schnellfenster: Dauer, Wochentag mit „morgen“, zweistelliges Jahr, Zeiträume", natural_rules, results)

    def quick_late_allday():
        # Doppelklick auf einen Tag um 23:15: der Termin bleibt an diesem Tag
        # (Uhrzeit im Experiment-Modul kurz auf 23:15 gestellt)
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
          await toCalendar();
          let out;
          Cu.evalInSandbox("globalThis.__mcRealDate = Date; Date = class extends __mcRealDate { constructor(...a) { if (a.length) super(...a); else super(2026, 9, 20, 23, 15); } };", g);
          try {
            Cu.evalInSandbox("enhancer", g).openQuickCreate(w, "event", null, { start: new Date(2026, 9, 21), allDay: true });
            const p = d.getElementById("mcQuickPanel"); const f = p.__mc;
            out = { start: f.startDate.value, time: f.startTime.value, end: f.endDate.value, allDay: f.allDay.checked };
            p.hidePopup();
            // „+“ der Today-Pane mit heute als Tag: 0:00 am Folgetag statt 23:00 heute (Beginn in der Vergangenheit)
            const tp = w.TodayPane; const origStart = tp.start;
            tp.start = { year: 2026, month: 9, day: 20 };
            try {
              Cu.evalInSandbox("enhancer", g).openQuickCreate(w, "event", d.getElementById("todaypane-new-event-button"));
              out.todayPane = { start: f.startDate.value, time: f.startTime.value };
            } finally {
              tp.start = origStart;
            }
          } finally {
            Cu.evalInSandbox("Date = globalThis.__mcRealDate; delete globalThis.__mcRealDate;", g);
          }
          d.getElementById("mcQuickPanel").hidePopup(); await wait(400);
          return out;''' % ADDON_ID)
        ok = res == {"start": "2026-10-21", "time": "23:00", "end": "2026-10-21", "allDay": True,
                     "todayPane": {"start": "2026-10-21", "time": "00:00"}}
        return ok, f"{res}"
    check("Schnellfenster: ganztägig um 23 Uhr bleibt am angeklickten Tag, „+“ der Today-Pane um 23 Uhr beginnt morgen 0 Uhr", quick_late_allday, results)

    def quick_checks():
        # ganztägig mit Ende vor dem Beginn → ein Tag; Aufgabe mit Erinnerung bekommt eine Fälligkeit
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const enh = Cu.evalInSandbox("enhancer", ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global);
          await toCalendar();
          const open = mode => {
            enh.openQuickCreate(w, mode);
            const p = d.getElementById("mcQuickPanel"); const f = p.__mc;
            f.calendar.value = testCalendar().id; f.calendar.dispatchEvent(new w.Event("change"));
            return [p, f];
          };
          const set = (input, v) => { if (typeof v == "boolean") input.checked = v; else input.value = v; input.dispatchEvent(new w.Event("change")); };
          const find = async t => { for (let i = 0; i < 40; i++) { const x = (await items(t))[0]; if (x) return x; await wait(100); } return null; };
          let [p, f] = open("event");
          f.title.value = "Halo Ganztag rückwärts"; f.title.dispatchEvent(new w.Event("input", { bubbles: true }));
          set(f.allDay, true); set(f.startDate, "2026-11-12"); set(f.endDate, "2026-11-10");
          f.add.click();
          const ev = await find("Halo Ganztag rückwärts");
          await until(() => p.state == "closed", 3000);
          [p, f] = open("task");
          f.title.value = "Halo Aufgabe Erinnerung"; f.title.dispatchEvent(new w.Event("input", { bubbles: true }));
          const before = f.hasDue.checked;
          set(f.alert, "PT15M"); const due = f.hasDue.checked;
          set(f.hasDue, false); const cleared = f.alert.value;
          set(f.alert, "PT15M");
          f.add.click();
          const td = await find("Halo Aufgabe Erinnerung");
          await until(() => p.state == "closed", 3000);
          const out = { ev: ev ? [ev.startDate.icalString, ev.endDate.icalString] : null,
                        task: { before, due, cleared, hasDue: !!td?.dueDate, alarms: td ? td.getAlarms().length : null } };
          for (const it of [ev, td].filter(Boolean)) await testCalendar().deleteItem(it);
          return out;''' % ADDON_ID)
        ok = (res["ev"] == ["20261112", "20261113"] and res["task"] == {"before": False, "due": True, "cleared": "", "hasDue": True, "alarms": 1})
        return ok, f"{res}"
    check("Schnellfenster: ganztägiges Ende vor Beginn, Erinnerung bei Aufgabe", quick_checks, results)

    def emoji():
        res = m.js("""
          const { CalEvent } = ChromeUtils.importESModule("resource:///modules/CalEvent.sys.mjs");
          const e = new CalEvent(); e.title = "Geburtstag Testperson";
          const s = cal.dtz.now(); s.hour = 9; s.minute = 0; const en = s.clone(); en.hour = 10;
          e.startDate = s; e.endDate = en; await testCalendar().addItem(e);
          await toCalendar(); w.switchToView("week");
          const label = await until(() => [...d.querySelectorAll("#view-box .event-name-label")].find(l => /Geburtstag Testperson/.test(l.textContent) && l.hasAttribute("data-mc-emoji")));
          const builtin = label?.getAttribute("data-mc-emoji") || null;
          // eigenes Stichwort aus den Einstellungen wirkt sofort und hat Vorrang
          Services.prefs.setStringPref("extensions.mailcards.emojiCustom", "Testperson = ⚽");
          await until(() => label?.getAttribute("data-mc-emoji") == "⚽", 3000);
          const custom = label?.getAttribute("data-mc-emoji") || null;
          Services.prefs.clearUserPref("extensions.mailcards.emojiCustom");
          await until(() => label?.getAttribute("data-mc-emoji") == "🎂", 3000);
          return [builtin, custom, label?.getAttribute("data-mc-emoji") || null];""")
        return res == ["🎂", "⚽", "🎂"], f"eingebaut {res[0]}, eigenes Stichwort {res[1]}, wieder {res[2]}"
    check("Emoji vor Termintitel", emoji, results)

    def emoji_rules():
        # emojiFor direkt über das Experiment-Modul: „Ordination“ nicht in
        # „Koordination“, „Steuer“ nicht in „Steuerung“
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const f = Cu.evalInSandbox("emojiFor", ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global);
          const out = {};
          for (const t of ["Ordination Dr. Muster", "Ordinationszeiten", "Koordination Projekt X", "Koordinationsmeeting",
                           "Einkommensteuer", "Steuererklärung", "Steuerungsgruppe", "Steuerkreissitzung", "Steuergruppe", "Steuerunterlagen"]) out[t] = f(t);
          return out;''' % ADDON_ID)
        expected = {"Ordination Dr. Muster": "🩺", "Ordinationszeiten": "🩺", "Koordination Projekt X": "", "Koordinationsmeeting": "👥",
                    "Einkommensteuer": "💰", "Steuererklärung": "💰", "Steuerungsgruppe": "", "Steuerkreissitzung": "",
                    "Steuergruppe": "", "Steuerunterlagen": "💰"}
        bad = [f"„{k}“ → {res.get(k)!r}" for k, v in expected.items() if res.get(k) != v]
        return not bad, "; ".join(bad) or f"{len(expected)} Titel richtig"
    check("Emoji: „Koordination“ ohne Arzt, „Steuerung“, „Steuerkreis“, „Steuergruppe“ ohne Geld", emoji_rules, results)

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
          // Tag ohne Termine – frühere Prüfungen legen heute/morgen welche an, ein
          // Treffer öffnet den Termin statt des Schnellfensters (je nach Wochentag)
          const col = [...d.querySelectorAll("#week-view calendar-event-column")].filter(c => c.getBoundingClientRect().width && ![...c.querySelectorAll("calendar-event-box")].some(b => !b.hidden && b.occurrence))[1];
          const lbl = [...d.querySelectorAll("#week-view .multiday-timebar-time")].find(l => /^\\s*(14[:.]00|0?2:00\\s*PM)\\s*$/i.test(l.textContent));
          lbl.scrollIntoView({ block: "center" }); await wait(500);
          // Aufgehen und Zugehen mitzählen – unter xvfb ohne Fenstermanager klappt
          // das Fenster teils sofort wieder zu
          const qp = d.getElementById("mcQuickPanel"); const t0 = Date.now(); w.__mcQp = { shown: 0, hiddenAfter: null };
          qp?.addEventListener("popupshown", () => { w.__mcQp.shown++; w.__mcQp.t = Date.now(); }, { once: true });
          qp?.addEventListener("popuphidden", () => { w.__mcQp.hiddenAfter = Date.now() - (w.__mcQp.t || t0); }, { once: true });
          const r = col.getBoundingClientRect(); return [Math.round(r.left + r.width / 2), Math.round(lbl.getBoundingClientRect().top + 8)];''')
        time.sleep(1.2)
        m.pointer([{"type": "pointerMove", "x": x, "y": y, "origin": "viewport"}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0},
                   {"type": "pause", "duration": 80}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}])
        res = m.js('''const p = await until(() => { const q = d.getElementById("mcQuickPanel"); return q?.state == "open" && q; }) || d.getElementById("mcQuickPanel");
          const r = { state: p?.state, line: p?.querySelector(".mc-qc-line1").textContent, shown: w.__mcQp?.shown || 0, hiddenAfter: w.__mcQp?.hiddenAfter ?? null,
            dialogs: [...Services.wm.getEnumerator(null)].filter(x => /calendar-event-dialog/.test(x.location.href)).length };
          p?.hidePopup();
          // falls doch ein Fenster aufging: schließen, sonst fehlt den folgenden Prüfungen der Fokus
          for (const x of [...Services.wm.getEnumerator(null)]) if (!x.location.href.includes("messenger.xhtml")) x.close();
          return r;''')
        # „showing“ = geht gerade auf (in einem verdeckten Fenster bleibt die Animation dort stehen)
        # aufgegangen = jetzt offen oder zumindest einmal gezeigt (xvfb schließt es teils sofort)
        opened = res["state"] in ("open", "showing") or res["shown"] > 0
        ok = opened and res["dialogs"] == 0 and ("14:" in res["line"] or "02:00 PM" in res["line"] or "2:00 PM" in res["line"])
        return ok, f"Fenster {res['state']} (gezeigt {res['shown']}×, zu nach {res['hiddenAfter']} ms), {res['line']}, große Dialoge {res['dialogs']}"
    check("Doppelklick im Kalender öffnet das Schnellfenster", double_click, results)

    def hover_actions():
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Inbox")) { root.createSubfolder("Inbox", null); await wait(800); }
          const inbox = root.getChildNamed("Inbox"); const lf = inbox.QueryInterface(Ci.nsIMsgLocalMailFolder);
          for (const n of [1, 2]) lf.addMessage(`From - Sat Oct 17 10:00:00 2026\\r\\nFrom: Test ${n} <t${n}@example.invalid>\\r\\nSubject: Halo Karte ${n}\\r\\nDate: Sat, 17 Oct 2026 10:0${n}:00 +0200\\r\\nMessage-ID: <halo-card-${n}@example.invalid>\\r\\n\\r\\nTest\\r\\n`);
          const a3 = await toMail(); a3.displayFolder(inbox.URI);
          await until(() => a3.document.querySelectorAll('#threadTree tr[is="thread-card"] .mc-act-flag').length >= 2, 15000);
          const rows = a3.document.querySelectorAll('#threadTree tr[is="thread-card"]');
          if (!rows[0]?.querySelector(".mc-act-flag")) {
            return { diag: true, visibility: a3.document.visibilityState, topVisibility: d.visibilityState, rows: rows.length, avatars: a3.document.querySelectorAll('#threadTree tr[is="thread-card"] .mc-avatar').length,
                     patched: !!a3.document.__mcPatched,
                     protoOurs: String(a3.customElements.get("thread-card")?.prototype.fillRow).includes("decorate"),
                     rowOwn: rows[0] ? Object.prototype.hasOwnProperty.call(rows[0], "fillRow") : null,
                     rowIsCard: rows[0] instanceof a3.customElements.get("thread-card"),
                     container: !!rows[0]?.querySelector(".card-container"),
                     sameDoc: rows[0]?.ownerDocument == a3.document, tableRows: a3.document.querySelectorAll('#threadTree tr[is="thread-row"]').length,
                     pref: Services.prefs.getBoolPref("extensions.mailcards.hoverActions", false), msgs: inbox.getTotalMessages(false),
                     folder: a3.gFolder?.URI == inbox.URI, view: Services.prefs.getIntPref("mail.threadpane.listview", -1) };
          }
          const buttons = rows[0]?.querySelectorAll(".mc-action") || [];
          rows[0].querySelector(".mc-act-flag").click(); await wait(500);
          const flagged = a3.gDBView.getMsgHdrAt(0).isFlagged; const selected = a3.gDBView.selection.count;
          // Löschen per Knopf landet in Thunderbirds Rückgängig-Liste (früher ohne msgWindow: nicht)
          const txn = w.messenger.transactionManager; const undo0 = txn.numberOfUndoItems;
          rows[0].querySelector(".mc-act-delete").click(); await wait(1200);
          const trash = root.getFolderWithFlags(Ci.nsMsgFolderFlags.Trash);
          const out = { buttons: buttons.length, flagged, selected, inbox: inbox.getTotalMessages(false), trash: trash?.getTotalMessages(false),
                        undoItems: txn.numberOfUndoItems - undo0 };
          if (out.undoItems > 0) { w.messenger.undo(w.msgWindow); out.undone = await until(() => inbox.getTotalMessages(false) == 2 && 2, 6000); }
          // Archivieren per Knopf ebenso rückgängig (ohne Identität: Lokale Ordner/Archives)
          if (out.undone) {
            const btn = await until(() => a3.document.querySelector('#threadTree tr[is="thread-card"] .mc-act-archive'), 6000);
            const undoA = txn.numberOfUndoItems;
            btn?.click();
            out.archived = await until(() => inbox.getTotalMessages(false) == 1 && 1, 8000);
            out.archiveUndo = txn.numberOfUndoItems - undoA;
            if (out.archiveUndo > 0) { w.messenger.undo(w.msgWindow); out.unarchived = await until(() => inbox.getTotalMessages(false) == 2 && 2, 6000); }
          }
          return out;''')
        if res.get("diag"):
            return False, f"keine Knöpfe auf der Karte – Diagnose {res}"
        ok = (res["buttons"] == 3 and res["flagged"] and res["selected"] == 0 and res["inbox"] == 1 and res["trash"] == 1
              and res["undoItems"] == 1 and res.get("undone") == 2
              and res.get("archived") == 1 and res.get("archiveUndo") == 1 and res.get("unarchived") == 2)
        return ok, f"{res}"
    check("Mailkarte: Aktionen beim Überfahren (Markieren, Löschen, Archivieren, Rückgängig)", hover_actions, results)

    def selected_actions():
        res = m.js('''
          const a3 = await toMail(); a3.threadTree.selectedIndex = 0; a3.threadTree.focus();
          await until(() => a3.document.querySelector('#threadTree tr[is="thread-card"][aria-selected="true"] .mc-action, #threadTree tr[is="thread-card"].selected .mc-action'));
          const row = a3.document.querySelector('#threadTree tr[is="thread-card"].selected, #threadTree tr[is="thread-card"][aria-selected="true"]');
          const b = row?.querySelector(".mc-action"); const box = row?.querySelector(".mc-actions");
          if (!b) return { found: false };
          // rgb(255, 255, 255) und color(srgb 1 1 1) auf dieselbe Skala 0–255
          const rgb = c => { const v = (c.match(/[\\d.]+/g) || []).slice(0, 3).map(Number); return c.startsWith("color(") ? v.map(x => x * 255) : v; };
          const cs = a3.getComputedStyle; const fg = rgb(cs(b).color), bg = rgb(cs(box).backgroundColor);
          const diff = Math.max(...fg.map((v, i) => Math.abs(v - bg[i])));
          return { found: true, icon: cs(b).color, pill: cs(box).backgroundColor, diff };''')
        return res.get("found") and res["diff"] >= 60, f"{res}"
    check("Ausgewählte Karte: Aktions-Symbole sichtbar", selected_actions, results)

    def list_date_future():
        # Datum in der Mailliste: heute nur die Uhrzeit, in der Zukunft (falsche Uhr,
        # Spam „oben halten“) das ganze Datum statt nur der Uhrzeit; „jetzt“ = Di 20.10.2026 15:00
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
          const f = Cu.evalInSandbox("appleListDate", g); const now = new Date(2026, 9, 20, 15, 0);
          return { today: f(new Date(2026, 9, 20, 10, 15).getTime(), now), tomorrow: f(new Date(2026, 9, 21, 10, 15).getTime(), now),
                   nextYear: f(new Date(2027, 2, 1, 10, 15).getTime(), now), older: f(new Date(2026, 9, 17, 10, 15).getTime(), now) };''' % ADDON_ID)
        ok = ("2026" not in res["today"] and "2026" in res["tomorrow"] and "21" in res["tomorrow"]
              and "2027" in res["nextYear"] and "2026" in res["older"])
        return ok, f"{res}"
    check("Mailliste: Datum in der Zukunft zeigt das ganze Datum", list_date_future, results)

    def smart_folder_names():
        # Favoriten: nur das Postfach je Konto unter „Alle Eingänge“ heißt wie das Konto –
        # Unterordner darunter und Ordner unter den Kontozeilen behalten ihren Namen
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Inbox")) { root.createSubfolder("Inbox", null); await wait(800); }
          const inbox = root.getChildNamed("Inbox");
          if (!inbox.containsChildNamed("Rechnungen")) { inbox.createSubfolder("Rechnungen", null); await wait(800); }
          if (!root.containsChildNamed("Projekte")) { root.createSubfolder("Projekte", null); await wait(800); }
          const sub = inbox.getChildNamed("Rechnungen"), own = root.getChildNamed("Projekte");
          const a3 = await toMail(); const ad = a3.document;
          const smart = () => [...ad.querySelectorAll(\'#folderTree > li[data-mode="smart"] li[is="folder-tree-row"]\')];
          const nameOf = li => li?.querySelector(":scope > .container .name")?.textContent;
          const find = (f, underServer) => smart().find(li => li.uri == f.URI &&
            !!li.parentElement?.closest("li")?.hasAttribute("data-server-type") == underServer);
          await until(() => find(sub, false) && find(own, true), 8000);
          // erst prüfen, wenn die Dekoration nach dem Einfügen der Zeilen gelaufen ist
          // (sie läuft im nächsten Bild) – sonst stünden hier Thunderbirds eigene
          // Namen, und die Prüfung bestünde auch ohne Korrektur
          const frames = await Promise.race([new Promise(r => a3.requestAnimationFrame(() => a3.requestAnimationFrame(() => r(true)))), wait(5000).then(() => false)]);
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const L = Cu.evalInSandbox("appleLabels", ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global)();
          const top = ad.querySelector('#folderTree > li[data-mode="smart"] > ul > li[is="folder-tree-row"][data-folder-type="inbox"]');
          return { modes: a3.folderPane?.activeModes, frames, visibility: d.visibilityState, inbox: nameOf(find(inbox, false)), account: root.server.prettyName,
                   sub: nameOf(find(sub, false)), underAccount: nameOf(find(own, true)), top: nameOf(top), allInboxes: L.native ? null : L.allInboxes };''' % ADDON_ID)
        if not res.get("modes") or "smart" not in res["modes"]:
            return False, f"Favoriten nicht eingeschaltet {res}"
        if not res["frames"]:
            return True, f"Testfenster verdeckt (kein Bild gezeichnet) – übersprungen {res}"
        ok = (res["sub"] == "Rechnungen" and res["underAccount"] == "Projekte" and res["inbox"] == res["account"]
              and (res["allInboxes"] is None or res["top"] == res["allInboxes"]))
        return ok, f"{res}"
    check("Favoriten: Unterordner behalten ihren eigenen Namen statt des Kontonamens", smart_folder_names, results)

    def account_dot_rename():
        # Farbpunkt vor dem Kontonamen: neue und umbenannte Konten bekommen ihn
        # sofort (früher nur die Konten vom Start). Feed-Konto ohne Abos – kein
        # Netzzugriff –, wird danach wieder entfernt
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const color = Cu.evalInSandbox("accountColor", ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global);
          const a3 = await toMail(); const ad = a3.document;
          const srv = MailServices.accounts.createIncomingServer("nobody", "halo-feeds.invalid", "rss");
          srv.prettyName = "Halo Feeds"; srv.doBiff = false;
          const acc = MailServices.accounts.createAccount(); acc.incomingServer = srv;
          const row = () => ad.querySelector(`#folderTree > li[data-mode="all"] li[is="folder-tree-row"][data-server-type][data-server-key="${srv.key}"]`);
          const dot = () => row()?.style.getPropertyValue("--mc-acc") || "";
          const out = { row: false };
          try {
            out.row = !!(await until(() => row(), 8000));
            out.added = await until(() => dot(), 6000);
            out.addedWant = color("Halo Feeds");
            srv.prettyName = "Halo Feeds Neu";
            out.renamedWant = color("Halo Feeds Neu");
            out.renamed = await until(() => dot() == out.renamedWant && dot(), 6000) || dot();
            out.name = row()?.querySelector(":scope > .container .name")?.textContent;
          } finally {
            MailServices.accounts.removeAccount(acc, true); await wait(800);
          }
          return out;''' % ADDON_ID)
        ok = res["row"] and res["added"] == res["addedWant"] and res["renamed"] == res["renamedWant"]
        return ok, f"{res}"
    check("Ordnerliste: neue und umbenannte Konten bekommen ihren Farbpunkt sofort", account_dot_rename, results)

    def card_sender_date():
        # Absender nur als Adresse → Name aus der Domain; Datum vor gestern ganz;
        # kompakte Dichte: Abstand oben und unten gleich (früher unten ~10 px mehr)
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Karten")) { root.createSubfolder("Karten", null); await wait(800); }
          const f = root.getChildNamed("Karten");
          f.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage("From - Mon Jan 05 10:00:00 2026\\r\\nFrom: \\"rueckgabe@amazon.de\\" <rueckgabe@amazon.de>\\r\\nSubject: Ihre Ruecksendung\\r\\nDate: Mon, 05 Jan 2026 10:00:00 +0100\\r\\nMessage-ID: <halo-amazon@example.invalid>\\r\\n\\r\\nIhre Ruecksendung ist eingegangen.\\r\\n");
          const a3 = await toMail(); a3.displayFolder(f.URI);
          const out = {};
          for (const density of [1, 0]) {
            Services.prefs.setIntPref("mail.uidensity", density); await wait(1200);
            const row = await until(() => a3.document.querySelector(\'#threadTree tr[is="thread-card"] .mc-preview\')?.textContent && a3.document.querySelector(\'#threadTree tr[is="thread-card"]\'), 8000);
            if (!row) return { diag: true, density, rows: a3.gDBView?.rowCount, folder: a3.gFolder?.URI,
              cards: [...a3.document.querySelectorAll('#threadTree tr')].map(r => [r.getAttribute("is"), r.querySelector(".mc-preview")?.textContent ?? null]),
              preview: Services.prefs.getIntPref("extensions.mailcards.previewLines", -1), view: Services.prefs.getIntPref("mail.threadpane.listview", -1) };
            const r = sel => row.querySelector(sel).getBoundingClientRect();
            const c = r(".card-container"), sn = r(".sender"), pv = r(".mc-preview"), av = r(".mc-avatar"), dot = r(".read-status");
            out[density] = { sender: row.querySelector(".sender").textContent, date: row.querySelector(".date").textContent,
                             top: Math.round(sn.top - c.top), bottom: Math.round(c.bottom - pv.bottom),
                             dot: Math.round((dot.top + dot.height / 2) - (av.top + av.height / 2)) };
          }
          Services.prefs.clearUserPref("mail.uidensity"); await wait(800);
          // im Mailkopf derselbe Name
          a3.threadTree.selectedIndex = 0;
          const md = a3.messageBrowser.contentWindow.document;
          await until(() => md.querySelector("#fromRecipient0 .recipient-single-line")?.textContent == "Amazon", 5000);
          const header = md.querySelector("#fromRecipient0 .recipient-single-line")?.textContent;
          return { cards: out, header };''')
        if res.get("diag"):
            return False, f"keine Karte mit Vorschau – Diagnose {res}"
        ok = res["header"] == "Amazon" and all(v["sender"] == "Amazon" and "2026" in v["date"] and 0 <= v["bottom"] - v["top"] <= 3 and abs(v["dot"]) <= 2 for v in res["cards"].values())
        return ok, f"{res}"
    check("Mailkarte und Mailkopf: Absendername aus der Domain, ganzes Datum, Abstände oben/unten gleich", card_sender_date, results)

    maillist_checks(m, results)

    def reading():
        res = m.js(MESSAGE_JS + '''
          const am = a3.messageBrowser.contentWindow; const md = am.document;
          const box = await until(() => md.querySelector("#fromRecipient0 .recipient-avatar.mc-hdr-avatar"));
          const body = md.getElementById("messagepane")?.contentDocument;
          const pre = await until(() => body?.querySelector(".moz-text-plain pre, .moz-text-flowed, div.moz-text-plain"));
          const font = pre ? body.defaultView.getComputedStyle(pre).fontFamily : "";
          const title = a3.document.getElementById("threadPaneFolderName")?.textContent || "";
          const head = [...a3.document.querySelectorAll("#threadPaneHeaderBar *")].map(e => e.textContent).join(" ");
          const vis = e => !!e && e.getBoundingClientRect().height > 0;
          const banner = md.getElementById("mcListBanner");
          return { avatar: box?.textContent.trim(), size: box ? Math.round(box.getBoundingClientRect().width) : 0, font, title, undefinedInHeader: /undefined|null/.test(head),
                   listIdRow: vis(md.getElementById("expandedlist-id")), banner: vis(banner), unsub: !!banner?.querySelector(".mc-lb-unsub"),
                   folder: md.querySelector("#mcHdrMeta .mc-hdr-folder")?.textContent, date: md.querySelector("#mcHdrMeta #dateLabel")?.textContent };''')
        ok = (res["avatar"] == "AB" and res["size"] >= 36 and "monospace" not in res["font"].lower() and not res["undefinedInHeader"]
              and not res["listIdRow"] and res["banner"] and res["unsub"] and "Lesen" in (res["folder"] or "") and res["date"])
        return ok, f"{res}"
    check("Leseansicht wie Apple: Absenderbild, Ordner, Verteiler-Hinweis statt List-ID", reading, results)

    def header_avatar_refresh():
        # Adressbuch-Änderung (Stern im Mailkopf, CardDAV): Thunderbird setzt sein
        # Bild neu (ein Buchstabe) – danach steht wieder das eigene Absenderbild
        res = m.js(MESSAGE_JS + '''
          const am = a3.messageBrowser.contentWindow; const md = am.document;
          const box = await until(() => md.querySelector("#fromRecipient0 .recipient-avatar.mc-hdr-avatar"));
          const foreign = () => !!box?.querySelector(":scope > span, :scope > img[data-l10n-id]");
          const before = box?.textContent.trim();
          md.getElementById("fromRecipient0").updateRecipient();
          const replaced = foreign();
          await until(() => !foreign(), 3000); await wait(200);
          return { before, replaced, after: box?.textContent.trim(), foreign: foreign() };''')
        ok = res["before"] == "AB" and res["replaced"] and not res["foreign"] and res["after"] == "AB"
        return ok, f"{res}"
    check("Mailkopf: Absenderbild bleibt nach einer Adressbuch-Änderung (nicht Thunderbirds Buchstabe)", header_avatar_refresh, results)

    def unsubscribe():
        res = m.js(MESSAGE_JS + '''
          const am = a3.messageBrowser.contentWindow; const md = am.document;
          const btn = await until(() => md.querySelector("#mcListBanner .mc-lb-unsub"));
          // nicht wirklich den Browser öffnen: Aufruf abfangen
          const orig = am.openLinkExternally; let opened = null;
          am.openLinkExternally = url => { opened = String(url); };
          btn?.click(); await wait(300);
          am.openLinkExternally = orig;
          const log = await IOUtils.readUTF8(PathUtils.join(PathUtils.profileDir, "mail-cards-debug.log")).catch(() => "");
          return { button: !!btn, opened, error: /unsubscribe error/.test(log) };''')
        return res["button"] and res["opened"] == "https://example.invalid/abmelden?id=1" and not res["error"], f"{res}"
    check("Verteiler-Hinweis: Abmelden öffnet den Link", unsubscribe, results)

    def header_long_name():
        # eigene Adresse bei mehreren Identitäten: Thunderbird schreibt „Name <Adresse>“
        # in den Kopf – nur der Name; lange Namen enden mit „…“ vor Ordner und
        # Uhrzeit statt darunter zu laufen (neues Profil auf dem Mac mini)
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          const acc = MailServices.accounts.findAccountForServer(MailServices.accounts.localFoldersServer);
          const ids = [["Halo Ich", "ich@example.invalid"], ["Halo Arbeit", "arbeit@example.invalid"]].map(([n, e]) => {
            const id = MailServices.accounts.createIdentity(); id.fullName = n; id.email = e; acc.addIdentity(id); return id; });
          const name = "Postfach mit einem sehr langen Namen ich@example.invalid";
          if (!root.containsChildNamed(name)) { root.createSubfolder(name, null); await wait(800); }
          const f = root.getChildNamed(name);
          const lf = f.QueryInterface(Ci.nsIMsgLocalMailFolder);
          lf.addMessage("From - Sat Oct 17 10:00:00 2026\r\nFrom: Halo Ich <ich@example.invalid>\r\nSubject: Eigene Mail\r\nDate: Sat, 17 Oct 2026 11:43:00 +0200\r\nMessage-ID: <halo-own@example.invalid>\r\n\r\nTest\r\n");
          lf.addMessage("From - Sat Oct 17 10:00:00 2026\r\nFrom: Maximiliane Sophie von und zu Langnamenhausen-Beispiel <lang@example.invalid>\r\nSubject: Langer Name\r\nDate: Sat, 17 Oct 2026 11:44:00 +0200\r\nMessage-ID: <halo-long@example.invalid>\r\n\r\nTest\r\n");
          await wait(800);
          const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
          const md = () => a3.messageBrowser.contentWindow.document;
          const out = {};
          for (const i of [0, 1]) {
            const key = a3.gDBView.getMsgHdrAt(i).subject == "Eigene Mail" ? "own" : "long";
            a3.threadTree.selectedIndex = i; await wait(2000);
            const d = md(); const li = d.querySelector("#fromRecipient0"); const meta = d.getElementById("mcHdrMeta");
            const nameEl = [li?.querySelector(".recipient-multi-line-name"), li?.querySelector(".recipient-single-line")].find(e => e?.getBoundingClientRect().width);
            out[key] = { text: nameEl?.textContent, nameRight: Math.round(li?.getBoundingClientRect().right), metaLeft: Math.round(meta?.getBoundingClientRect().left),
                         cut: !!nameEl && nameEl.scrollWidth > nameEl.clientWidth, header: Math.round(d.getElementById("messageHeader").getBoundingClientRect().right),
                         row: Math.round(d.getElementById("headerSenderToolbarContainer").getBoundingClientRect().right) };
          }
          // Testidentitäten wieder weg (die zuerst angelegte ist Standard und geht zuletzt)
          for (const id of ids.reverse()) { try { acc.removeIdentity(id); } catch {} }
          return out;""")
        own, long = res["own"], res["long"]
        ok = (own["text"] == "Halo Ich" and long["nameRight"] <= long["metaLeft"] and long["cut"]
              and long["row"] <= long["header"])
        return ok, f"{res}"
    check("Mailkopf: eigene Adresse nur mit Namen, lange Namen mit „…“ vor Ordner und Uhrzeit", header_long_name, results)

    def one_click_unsubscribe():
        # List-Unsubscribe-Post (RFC 8058, z. B. Google): nachfragen, dann POST
        # statt Browser – der Link ergäbe dort nur eine leere Seite. Testadresse
        # ist gesperrt (example.invalid), daher greift danach der Browser als Rückfall.
        m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("EinKlick")) { root.createSubfolder("EinKlick", null); await wait(800); }
          const f = root.getChildNamed("EinKlick");
          f.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage("From - Sat Oct 17 10:00:00 2026\r\nFrom: Google <noreply-accounts@example.invalid>\r\nSubject: Kontodaten geteilt\r\nDate: Sat, 17 Oct 2026 09:41:00 +0200\r\nMessage-ID: <halo-oneclick@example.invalid>\r\nList-Unsubscribe: <https://example.invalid/ein-klick?id=7>\r\nList-Unsubscribe-Post: List-Unsubscribe=One-Click\r\nList-Id: <abc@example.invalid>\r\n\r\nTest\r\n");
          await wait(800);
          const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
          a3.threadTree.selectedIndex = 0; await wait(2000);
          const am = a3.messageBrowser.contentWindow;
          await until(() => am.document.querySelector("#mcListBanner .mc-lb-unsub"));
          am.__mcOrigOpen ??= am.openLinkExternally; am.__mcOpened = null;
          am.openLinkExternally = url => { am.__mcOpened = String(url); };
          return 1;""")
        am = "const a3 = await toMail(); const am = a3.messageBrowser.contentWindow;"
        click = am + 'am.document.querySelector("#mcListBanner .mc-lb-unsub")?.click(); return 1;'
        opened = am + "await until(() => am.__mcOpened, 3000); return am.__mcOpened;"

        # der Dialog kommt asynchron – Marionette meldet ihn als Alert
        def alert(cmd):
            for _ in range(20):
                try:
                    return m.cmd(cmd, {}) or True
                except RuntimeError:
                    time.sleep(0.25)
            return None
        m.js(click)
        text = (alert("WebDriver:GetAlertText") or {}).get("value", "")
        alert("WebDriver:DismissAlert")
        after_cancel = m.js(opened)
        m.js(click)
        accepted = alert("WebDriver:AcceptAlert")
        after_accept = m.js(opened)
        m.js(am + "if (am.__mcOrigOpen) am.openLinkExternally = am.__mcOrigOpen; return 1;")
        res = {"prompt": text, "afterCancel": after_cancel, "accepted": bool(accepted), "opened": after_accept}
        ok = "no longer" in text and after_cancel is None and accepted and after_accept == "https://example.invalid/ein-klick?id=7"
        return ok, f"{res}"
    check("Verteiler-Hinweis: Ein-Klick-Abmeldung fragt nach und sendet statt Browser", one_click_unsubscribe, results)

    def unsubscribe_identity():
        # nur Abmelde-Mail (mailto, z. B. LISTSERV): Absender ist die Identität,
        # an die die Mail ging, nicht die erste/Standard-Identität. Das
        # Verfassen-Fenster wird nur geöffnet und ungesendet wieder geschlossen;
        # die zweite Test-Identität wird danach wieder entfernt (die erste wie
        # in COMPOSE_JS bleibt – die letzte lässt Thunderbird nicht entfernen).
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const acc = MailServices.accounts.findAccountForServer(MailServices.accounts.localFoldersServer);
          const ensure = (name, email) => { if (acc.identities.some(i => i.email == email)) return null; const id = MailServices.accounts.createIdentity(); id.fullName = name; id.email = email; acc.addIdentity(id); return id; };
          if (!acc.identities.length) ensure("Halo Test", "halo@example.invalid");
          const added = ensure("Halo Arbeit", "arbeit@example.invalid");
          const first = acc.identities[0]?.email;
          let cw = null; let from = null; let to = ""; let button = false;
          try {
            const root = MailServices.accounts.localFoldersServer.rootFolder;
            if (!root.containsChildNamed("Liste")) { root.createSubfolder("Liste", null); await wait(800); }
            const f = root.getChildNamed("Liste");
            if (!f.getTotalMessages(false)) {
              f.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage("From - Sat Oct 17 10:00:00 2026\r\nFrom: Halo Liste <liste@example.invalid>\r\nTo: Halo Arbeit <arbeit@example.invalid>\r\nSubject: Rundbrief\r\nDate: Sat, 17 Oct 2026 09:41:00 +0200\r\nMessage-ID: <halo-listserv@example.invalid>\r\nList-Id: <rundbrief.example.invalid>\r\nList-Unsubscribe: <mailto:listserv@example.invalid?body=SIGNOFF%20RUNDBRIEF>\r\n\r\nTest\r\n");
              await wait(800);
            }
            const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
            a3.threadTree.selectedIndex = 0; await wait(1500);
            const am = a3.messageBrowser.contentWindow;
            // about:message bleibt beim Mailwechsel geladen: erst klicken, wenn der Hinweis
            // zur Rundbrief-Mail gehört, nicht noch der der vorigen Ein-Klick-Mail ist
            const btn = await until(() => { const b = am.document.querySelector("#mcListBanner .mc-lb-unsub");
              return (am.gMessage?.messageId == "halo-listserv@example.invalid" && b?.title.startsWith("listserv@example.invalid") && b) || null; }, 10000);
            button = !!btn;
            const before = new Set(Services.wm.getEnumerator("msgcompose"));
            btn?.click();
            cw = await until(() => [...Services.wm.getEnumerator("msgcompose")].find(x => !before.has(x)), 8000);
            from = await until(() => cw?.gCurrentIdentity?.email, 8000);
            to = cw?.gMsgCompose?.compFields?.to || [...(cw?.document.querySelectorAll("mail-address-pill") || [])].map(p => p.emailAddress).join(",");
          } finally {
            cw?.close(); await wait(500);
            try { if (added) acc.removeIdentity(added); } catch {}
          }
          return { button, compose: !!cw, first, from, to };""")
        ok = (res["button"] and res["compose"] and res["first"] != "arbeit@example.invalid"
              and res["from"] == "arbeit@example.invalid" and "listserv@example.invalid" in (res["to"] or ""))
        return ok, f"{res}"
    check("Verteiler-Hinweis: Abmelde-Mail geht von der Identität, an die die Mail ging", unsubscribe_identity, results)

    def html_font():
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Schrift")) { root.createSubfolder("Schrift", null); await wait(800); }
          const f = root.getChildNamed("Schrift"); const lf = f.QueryInterface(Ci.nsIMsgLocalMailFolder);
          const mail = (n, body) => `From: Halo <h@example.invalid>\r\nSubject: Schrift ${n}\r\nDate: Sat, 17 Oct 2026 10:0${n}:00 +0200\r\nMessage-ID: <halo-font-${n}@example.invalid>\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n${body}\r\n\r\n`;
          if (!f.getTotalMessages(false)) {
            lf.addMessage(mail(1, "<html><body><p id='t'>Ohne eigene Schrift</p><img src='https://example.invalid/bild.png' width='1' height='1'></body></html>"));
            lf.addMessage(mail(2, "<html><body style='font-family: Georgia, serif'><p id='t'>Mit eigener Schrift</p></body></html>"));
            lf.addMessage(mail(3, "<html><body><p id='t'>Bild</p><img id='bild' src='https://example.invalid/logo.png' alt='Icono 1' width='48' height='40'><img id='pixel' src='https://example.invalid/p.gif' alt='' width='1' height='1'></body></html>"));
            await wait(800);
          }
          const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
          const out = {};
          for (let i = 0; i < a3.gDBView.rowCount; i++) {
            if (!/Schrift [12]$/.test(a3.gDBView.getMsgHdrAt(i).subject)) continue;
            a3.threadTree.selectedIndex = i; await wait(1500);
            const md = a3.messageBrowser.contentDocument;
            const body = await until(() => md.getElementById("messagepane")?.contentDocument?.getElementById("t"));
            const subj = a3.gDBView.getMsgHdrAt(i).subject;
            out[subj] = body ? body.ownerDocument.defaultView.getComputedStyle(body).fontFamily : null;
            out.pill = md.getElementById("header-view-toolbox")?.getBoundingClientRect().width || 0;
            out.dates = [...md.querySelectorAll("#dateLabel, #dateLabelSubject")].filter(e => e.getBoundingClientRect().width).length;
          }
          return out;""")
        own, plain = res.get("Schrift 2") or "", res.get("Schrift 1") or ""
        ok = "apple-system" in plain and own.startswith("Georgia") and not res["pill"] and res["dates"] == 1
        return ok, f"{res}"
    check("Mails in Systemschrift, eigene Schrift bleibt, keine Kapsel im Kopf", html_font, results)

    def remote_bar():
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const f = MailServices.accounts.localFoldersServer.rootFolder.getChildNamed("Schrift");
          const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
          for (let i = 0; i < a3.gDBView.rowCount; i++) if (a3.gDBView.getMsgHdrAt(i).subject == "Schrift 1") a3.threadTree.selectedIndex = i;
          const md = a3.messageBrowser.contentDocument; const mw = md.defaultView;
          const n = await until(() => md.querySelector('#mail-notification-top notification-message[value="remoteContent"]'));
          await until(() => n?.shadowRoot?.querySelector("style.mc-layout"), 3000); await wait(600);
          const text = n?.shadowRoot?.querySelector(".text-container")?.getBoundingClientRect();
          const btn = n?.querySelector("button")?.getBoundingClientRect();
          return { bar: !!n, styled: !!n?.shadowRoot?.querySelector("style.mc-layout"), paneWidth: Math.round(md.documentElement.clientWidth),
                   sameRow: !!(text && btn && btn.top < text.bottom && btn.left >= text.right - 1), bg: n && mw.getComputedStyle(n).backgroundColor };""")
        yellow = res.get("bg", "").startswith("rgb(255, 2")
        return res.get("bar") and res.get("styled") and res.get("sameRow") and yellow, f"{res}"
    check("Hinweis über der Mail: Knopf neben dem Text, Farbe unverändert", remote_bar, results)

    def blocked_image():
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const f = MailServices.accounts.localFoldersServer.rootFolder.getChildNamed("Schrift");
          const a3 = await toMail(); a3.displayFolder(f.URI); await wait(800);
          for (let i = 0; i < a3.gDBView.rowCount; i++) if (a3.gDBView.getMsgHdrAt(i).subject == "Schrift 3") a3.threadTree.selectedIndex = i;
          const md = a3.messageBrowser.contentDocument;
          const img = await until(() => md.getElementById("messagepane")?.contentDocument?.getElementById("bild"));
          await wait(800);
          const px = img.ownerDocument.getElementById("pixel");
          const cs = img.ownerDocument.defaultView.getComputedStyle(img), r = img.getBoundingClientRect(), pr = px.getBoundingClientRect();
          return { placeholder: cs.backgroundImage.includes("svg"), textHidden: cs.color == "rgba(0, 0, 0, 0)" || parseFloat(cs.fontSize) == 0, size: [Math.round(r.width), Math.round(r.height)], pixel: [Math.round(pr.width), Math.round(pr.height)] };""")
        ok = res["placeholder"] and res["textHidden"] and res["size"] == [48, 40] and max(res["pixel"]) <= 1
        return ok, f"{res}"
    check("Blockierte Bilder: Platzhalter statt Ersatztext, Zählpixel unsichtbar", blocked_image, results)

    reading_checks(m, results)
    compose_checks(m, results)
    folder_checks(m, results)
    dialog_checks(m, results)
    menu_checks(m, results)
    calendar_checks(m, results)

    def min_widths():
        res = m.js('''
          const out = {};
          const probe = async (name, open, getEl) => {
            await open(); w.resizeTo(1500, 900); await wait(1500);
            w.resizeTo(600, 900); await wait(1500);
            const el = getEl(); const r = el?.getBoundingClientRect();
            out[name] = { window: w.outerWidth, pane: r ? Math.round(r.width) : null, min: el ? parseFloat(el.ownerDocument.defaultView.getComputedStyle(el).minWidth) : null };
          };
          await probe("mail", () => toMail(), () => tm.currentAbout3Pane.document.getElementById("messagePane"));
          await probe("calendar", () => toCalendar(), () => d.getElementById("calendarDisplayBox"));
          await probe("settings", async () => { w.openPreferencesTab(); await wait(2000); }, () => tm.currentTabInfo.browser.contentDocument.getElementById("preferencesContainer"));
          // Chat: früher sperrte der ausgeblendete Kalender die Breite (Fenster ließ sich nicht verkleinern)
          await probe("chat", async () => { tm.openTab("chat", {}); await wait(1500); }, () => d.getElementById("conversationsBox"));
          out.chat.inside = d.documentElement.getBoundingClientRect().width <= w.innerWidth + 1;
          w.resizeTo(1500, 900); await wait(800); await toMail();
          return out;''')
        # Adressbuch (Bearbeiten): schmales Fenster und weit gezogener Teiler –
        # die Details bleiben mindestens so breit wie vorgegeben und im Fenster
        res["addressbook"] = m.js(ADDRESS_EDIT_JS + '''
          w.resizeTo(600, 900); await wait(1500);
          ad.body.style.setProperty("--sharedSplitter-width", "2000px"); await wait(800);
          const el = ad.getElementById("detailsPane"), r = el.getBoundingClientRect();
          const out = { window: w.outerWidth, pane: Math.round(r.width), min: parseFloat(ab.getComputedStyle(el).minWidth),
            inside: r.right <= ab.innerWidth + 1 };
          ad.body.style.removeProperty("--sharedSplitter-width");
          ab.detailsPane.isDirty = false; ad.getElementById("cancelEditButton").click(); await wait(300);
          tm.closeTab(tm.currentTabInfo); w.resizeTo(1500, 900); await wait(800); await toMail();
          return out;''')
        ok = res["chat"]["window"] < 1400 and res["chat"]["inside"] and res["addressbook"]["inside"] and res["addressbook"]["min"] >= 560 and all(v["pane"] is not None and v["pane"] >= v["min"] - 1 and v["window"] > 600 for v in res.values())
        return ok, f"{res}"
    check("Mindestbreiten: Fenster wird nicht schmaler als die Bereiche", min_widths, results)

    def ab_min_width_unselected():
        # Adressbuch ohne Auswahl: das Fenster lässt sich wieder schmaler ziehen
        # (früher sperrte der ausgeblendete Kalender die Breite auf die aktuelle);
        # nach Wahl eines Kontakts bleiben die Details mindestens so breit wie vorgegeben
        res = m.js(r"""
          w.resizeTo(1500, 900); await wait(800);
          tm.openTab("addressBookTab", {});
          const tab = tm.currentTabInfo;
          const ab = await until(() => { const c = tab.browser?.contentWindow; return c?.document?.getElementById("cards")?.view?.rowCount && c; }, 8000);
          const ad = ab.document, list = ad.getElementById("cards"), dp = ad.getElementById("detailsPane");
          const out = {};
          try {
            await wait(800);
            list.selectedIndices = []; await wait(800);
            out.hidden = dp.hidden || !dp.getClientRects().length;
            w.resizeTo(1500, 900); await wait(1000);
            w.resizeTo(1250, 900); await wait(1200);
            out.narrow = w.outerWidth;
            list.selectedIndex = 0; await wait(1000);
            w.resizeTo(600, 900); await wait(1500);
            const r = dp.getBoundingClientRect();
            out.pane = Math.round(r.width); out.min = parseFloat(ab.getComputedStyle(dp).minWidth);
            out.inside = r.right <= ab.innerWidth + 1; out.window = w.outerWidth;
          } finally {
            tm.closeTab(tab); w.resizeTo(1500, 900); await wait(800);
          }
          return out;""")
        ok = (res["hidden"] and res["narrow"] < 1450 and res["pane"] >= res["min"] - 1 and res["min"] >= 560
              and res["inside"] and res["window"] > 600)
        return ok, f"{res}"
    check("Adressbuch ohne Auswahl: Fenster lässt sich verkleinern, Details danach mindestens so breit wie vorgegeben", ab_min_width_unselected, results)

    def chat_toolbar():
        # Chat ohne Konto: leerer Zustand ruhig (Info-Symbol in Tertiärgrau, Text 13 px grau,
        # Knopf voll deckend und ohne Dauer-Fokusring); Statuskapsel mit 13-px-Text und flachem
        # Punkt; deaktivierte Knöpfe ohne Hover; Knöpfe und Suche überlappen nie
        res = m.js(r"""
          const cs = el => w.getComputedStyle(el);
          const colorOf = (value, prop = "color") => { const e = d.createElementNS("http://www.w3.org/1999/xhtml", "div"); e.style[prop] = value;
            d.documentElement.append(e); const c = cs(e)[prop]; e.remove(); return c; };
          const { IMServices } = ChromeUtils.importESModule("resource:///modules/IMServices.sys.mjs");
          const gus = IMServices.core.globalUserStatus;
          const q = s => d.querySelector(s);
          const search = () => q('#unifiedToolbarContent > li[item-id="search-bar"]').getBoundingClientRect();
          const out = {};
          try {
            w.resizeTo(1500, 900); await wait(800);
            tm.openTab("chat", {}); await wait(1500);
            // leerer Zustand: Gruppe voll deckend, Erklärtext 13 px grau, Knopf in Akzentfarbe, eigenes Info-Symbol in Tertiärgrau
            const box = d.getElementById("noConvBox"), btn = d.getElementById("openIMAccountWizardButton");
            let dim = []; for (let e = btn; e && !e.classList?.contains("im-placeholder-screen"); e = e.parentElement) { if (parseFloat(cs(e).opacity) < 1) dim.push(e.id || e.className); }
            const desc = d.getElementById("noAccountDesc");
            out.empty = { inner: cs(d.getElementById("noAccountInnerBox")).opacity, dim, descSize: cs(desc).fontSize,
              descOk: cs(desc).color == colorOf("var(--mt-text-secondary)"), btnOk: cs(btn).backgroundColor == colorOf("var(--mt-accent)", "backgroundColor"),
              icon: cs(box).backgroundImage.includes("mailcards/icons/info.svg"), stroke: cs(box).stroke == colorOf("var(--mt-text-tertiary)") };
            // Standardknopf: nach dem Öffnen fokussiert, aber ohne Ring; per Tastatur mit Ring
            out.focus = { active: d.activeElement === btn, fv: btn.matches(":focus-visible"), outline: cs(btn).outlineStyle };
            // (Fenster nach vorn, sonst greift :focus-visible nicht)
            w.focus(); await until(() => Services.focus.activeWindow == w, 3000); await wait(200);
            btn.blur(); btn.focus({ focusVisible: true }); await wait(100);
            out.focus.kbFv = btn.matches(":focus-visible");
            out.focus.kbOutline = cs(btn).outlineStyle; out.focus.kbWidth = parseFloat(cs(btn).outlineWidth);
            btn.blur();
            // Statuskapsel: Text 13 px wie „Add Contact“, ohne Konto gedimmt wie die übrigen Knöpfe; flacher Punkt
            const lbl = d.getElementById("statusMessageLabel"), type = d.getElementById("statusTypeIcon"), ic = q("#statusTypeIcon > .toolbarbutton-icon");
            const addText = q("#button-add-buddy .toolbarbutton-text"), addIcon = q("#button-add-buddy .toolbarbutton-icon");
            const ir = ic.getBoundingClientRect(), sr = q("#chat-status-selector").getBoundingClientRect();
            out.status = { size: cs(lbl).fontSize, addSize: cs(addText).fontSize, disabled: type.hasAttribute("disabled"),
              lblOp: cs(lbl).opacity, addTextOp: cs(addText).opacity, dotOp: cs(ic).opacity, addIconOp: cs(addIcon).opacity,
              img: cs(ic).listStyleImage, w: ir.width, h: ir.height, mid: Math.abs((ir.top + ir.bottom) / 2 - (sr.top + sr.bottom) / 2),
              online: cs(ic).backgroundColor == colorOf("var(--mt-status-online)", "backgroundColor") };
            // Innenabstand der Kapsel links (bis zum Punkt) und rechts (hinter dem Textende) gleich
            // und wie bei „Add Contact“ (Symbol links, Text rechts)
            const textRight = el => { const r = d.createRange(); r.selectNodeContents(el); const rr = r.getBoundingClientRect();
              return rr.width > 0 ? rr.right : el.getBoundingClientRect().right - parseFloat(cs(el).paddingRight); };
            const ar = q("#button-add-buddy").getBoundingClientRect(), air = addIcon.getBoundingClientRect();
            Object.assign(out.status, { padL: ir.left - sr.left, padR: sr.right - textRight(lbl),
              addL: air.left - ar.left, addR: ar.right - textRight(addText), text: lbl.value || lbl.textContent });
            const st = type.getAttribute("status"); type.setAttribute("status", "away"); await wait(100);
            out.status.away = cs(ic).backgroundColor == colorOf("var(--mt-status-away)", "backgroundColor");
            type.setAttribute("status", st);
            // deaktivierte Knöpfe (ohne Konto) werden beim Überfahren nicht dunkler
            out.hover = {};
            for (const id of ["button-join-chat", "button-add-buddy"]) {
              const b = d.getElementById(id), base = cs(b).backgroundColor;
              InspectorUtils.addPseudoClassLock(b, ":hover");
              out.hover[id] = { disabled: b.hasAttribute("disabled"), same: cs(b).backgroundColor == base };
              InspectorUtils.clearPseudoClassLocks(b);
            }
            // Knöpfe an der Kante der Mailliste, solange Platz ist
            out.edge1500 = Math.round(d.getElementById("chat-view-toolbox").getBoundingClientRect().left);
            // langer Statustext endet mit „…“; Knöpfe und Suche überlappen bei keiner Fensterbreite
            gus.setStatus(Ci.imIStatusInfo.STATUS_AWAY, "I am currently away from the computer and will be back later. ".repeat(2));
            await wait(1500);
            out.long = { vb: Math.round(q("#chat-status-selector > vbox").getBoundingClientRect().width), to: cs(lbl).textOverflow, ox: cs(lbl).overflowX };
            out.widths = {};
            for (const W of [1500, 1280, 1150, 1000, 900]) {
              w.resizeTo(W, 900); await wait(1200);
              const tb = d.getElementById("chat-view-toolbox").getBoundingClientRect(), s = search(), lp = d.getElementById("listPaneBox").getBoundingClientRect();
              out.widths[W] = { win: w.outerWidth, tbl: Math.round(tb.left), tbr: Math.round(tb.right), sl: Math.round(s.left), lpr: Math.round(lp.right), inner: w.innerWidth };
            }
          } finally {
            gus.setStatus(Ci.imIStatusInfo.STATUS_AVAILABLE, "");
            w.resizeTo(1500, 900); await wait(800); await toMail();
          }
          return out;""")
        e, f, st, wd = res["empty"], res["focus"], res["status"], res["widths"]
        empty_ok = (e["inner"] == "1" and not e["dim"] and e["descSize"] == "13px" and e["descOk"] and e["btnOk"]
                    and e["icon"] and e["stroke"])
        focus_ok = f["active"] and not f["fv"] and f["outline"] == "none" and f["kbOutline"] != "none" and f["kbWidth"] >= 2
        status_ok = (st["size"] == "13px" == st["addSize"] and st["img"] == "none" and abs(st["w"] - 10) <= 0.5
                     and abs(st["h"] - 10) <= 0.5 and st["mid"] <= 1 and st["online"] and st["away"]
                     and abs(st["padL"] - st["padR"]) <= 3 and abs(st["padL"] - st["addL"]) <= 3
                     and (not st["disabled"] or (st["lblOp"] == st["addTextOp"] and st["dotOp"] == st["addIconOp"])))
        hover_ok = all(v["same"] for v in res["hover"].values() if v["disabled"])
        long_ok = res["long"]["vb"] <= 161 and res["long"]["to"] == "ellipsis" and res["long"]["ox"] == "hidden"
        widths_ok = all(v["tbr"] + 4 <= v["sl"] and v["tbl"] >= v["lpr"] and v["tbr"] <= v["inner"] for v in wd.values())
        # mit langem Statustext rücken die Knöpfe nur nach links, wenn die Suche schon auf ihre Mindestbreite
        # gekürzt ist (12 px Abstand) – mit breiteren Systemschriften (Linux) schon bei 1500 px
        edge_ok = (abs(wd["1500"]["tbl"] - res["edge1500"]) <= 1
                   or (wd["1500"]["tbl"] < res["edge1500"] and wd["1500"]["sl"] - wd["1500"]["tbr"] <= 13))
        ok = empty_ok and focus_ok and status_ok and hover_ok and long_ok and widths_ok and edge_ok
        return ok, f"{res}"
    check("Chat: leerer Zustand ruhig ohne Dauer-Fokusring, Statuskapsel 13 px mit flachem Punkt und beidseitig gleichem Innenabstand wie „Add Contact“, kein Hover auf deaktivierten Knöpfen, langer Statustext mit „…“, Knöpfe und Suche überlappen bei keiner Fensterbreite", chat_toolbar, results)

    def side_line():
        # Trennlinie der Seitenleiste läuft in der Toolbar-Zeile ohne Versatz und
        # ohne Farbsprung weiter: --mc-side-right ist die Außenkante samt der
        # 1-px-Linie der Seitenleiste, die Linie oben liegt auf dem letzten Pixel davor
        res = m.js(r"""
          const out = {};
          const pixels = async r => { const cv = d.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
            cv.width = Math.round(r.width); cv.height = Math.round(r.height); const ctx = cv.getContext("2d");
            try { const bm = await w.browsingContext.currentWindowGlobal.drawSnapshot(new w.DOMRect(r.left, r.top, r.width, r.height), 1, "white"); ctx.drawImage(bm, 0, 0); }
            catch { ctx.drawWindow(w, r.left, r.top, r.width, r.height, "white"); }
            const data = ctx.getImageData(0, 0, cv.width, cv.height).data;
            return (x, y) => { const i = (Math.round(y) * cv.width + Math.round(x)) * 4; return [data[i], data[i + 1], data[i + 2]]; }; };
          try {
            w.resizeTo(1500, 900); await wait(800);
            for (const [mode, id] of [["chat", "listPaneBox"], ["calendar", "calSidebar"]]) {
              tm.openTab(mode, {}); await wait(1500);
              const rowEl = d.getElementById("unifiedToolbarContainer"), row = rowEl.getBoundingClientRect();
              const side = parseFloat(w.getComputedStyle(rowEl).getPropertyValue("--mc-side-right"));
              const paneEl = d.getElementById(id), pane = paneEl.getBoundingClientRect();
              const bg = w.getComputedStyle(rowEl).backgroundImage;
              // je ein Bildpunkt links von, auf und rechts von der Linie, über und unter der Toolbar-Kante
              const px = await pixels(new w.DOMRect(Math.round(pane.right) - 3, row.bottom - 4, 5, 8));
              const col = x => ({ up: px(x, 1), down: px(x, 6) });
              out[mode] = { off: row.left + side - pane.right, border: w.getComputedStyle(paneEl).borderInlineEndWidth,
                layers: (bg.match(/linear-gradient/g) || []).length, cols: [col(1), col(2), col(3)] };
            }
          } finally {
            await toMail();
          }
          return out;""")
        def same(a, b):
            return all(abs(x - y) <= 6 for x, y in zip(a, b))
        ok = all(v["border"] == "1px" and abs(v["off"]) <= 0.5 and v["layers"] == 2
                 and all(same(c["up"], c["down"]) for c in v["cols"]) for v in res.values())
        return ok, f"{res}"
    check("Bereiche: Trennlinie der Seitenleiste läuft in der Toolbar-Zeile ohne Versatz und Farbsprung weiter (Chat, Kalender)", side_line, results)

    def today_closed():
        # Today-Pane aus: keine graue Fläche oben rechts neben dem Knopf
        res = m.js('''
          await toMail(); await wait(800);
          const row = d.getElementById("unifiedToolbarContainer"); const top = d.getElementById("mcTodayTop");
          const cmd = d.getElementById("calendar_toggle_todaypane_command");
          const was = w.TodayPane?.isVisible;
          // erst offen (Fläche da), dann zu (Fläche weg), dann wie vorher
          if (!was) { cmd.doCommand(); await wait(800); }
          const out = { open: !row.hasAttribute("data-mc-tp-none") && Math.round(top.getBoundingClientRect().width) > 0 };
          cmd.doCommand(); await wait(800);
          out.none = row.hasAttribute("data-mc-tp-none"); out.width = Math.round(top.getBoundingClientRect().width);
          if (was) { cmd.doCommand(); await wait(800); }
          return out;''')
        return res["open"] and res["none"] and res["width"] == 0, f"{res}"
    check("Today-Pane aus: keine Fläche rechts neben dem Knopf", today_closed, results)

    def statusbar():
        # kein Today-Pane-Knopf mehr unten rechts (das Symbol oben übernimmt
        # weiter dessen Tageszahl); Leiste flach, Grau der Seitenleiste läuft
        # durch, Text beginnt rechts der Ordnerliste
        res = m.js('''
          await toMail(); await wait(800);
          const sb = d.getElementById("status-bar"), cs = getComputedStyle(sb);
          const a3 = tm.currentAbout3Pane, fp = a3.document.getElementById("folderPane").getBoundingClientRect();
          const sidebarRight = tm.currentTabInfo.chromeBrowser.getBoundingClientRect().left + fp.right;
          const panel = d.getElementById("calendar-show-todaypane-panel");
          const text = d.getElementById("statusTextBox").getBoundingClientRect();
          return { panel: panel ? getComputedStyle(panel).display : "fehlt",
                   day: d.querySelector("#mcTodayToggle .mc-today-day")?.textContent,
                   height: Math.round(sb.getBoundingClientRect().height), font: cs.fontSize,
                   textLeft: Math.round(text.left), sidebarRight: Math.round(sidebarRight),
                   bg: cs.backgroundImage.includes("gradient") };''')
        ok = (res["panel"] in ("none", "fehlt") and res["day"] and res["height"] <= 24 and res["font"] == "11px"
              and res["bg"] and res["textLeft"] >= res["sidebarRight"])
        return ok, f"{res}"
    check("Statusleiste: ohne Today-Pane-Knopf, flach, Seitenleiste läuft durch", statusbar, results)

    def today_plus_event():
        # „+“ ganz rechts → „New Event“: Schnellfenster ganz auf dem Bildschirm
        # (früher mittig unter dem „+“ geöffnet und von Thunderbird am Rand auf
        # 224 statt 380 px zusammengedrückt)
        res = m.js('''
          await toMail(); const sx = w.screenX, sy = w.screenY, sw = w.outerWidth, sh = w.outerHeight;
          const right = w.screen.availLeft + w.screen.availWidth;
          w.moveTo(right - 1300, w.screen.availTop); w.resizeTo(1300, 900); await wait(1200);
          if (!w.TodayPane.isVisible) { d.getElementById("mcTodayToggle").click(); await wait(800); }
          const out = { visibility: d.visibilityState, screenRight: right };
          for (const id of ["mcNewEvent", "mcNewTask"]) {
            d.getElementById("mcTodayNew").click(); await until(() => d.getElementById("mcNewPopup").state == "open", 3000);
            d.getElementById(id).click();
            const qp = d.getElementById("mcQuickPanel"); await until(() => qp.state == "open", 3000); await wait(400);
            const r = qp.getOuterScreenRect();
            out[id] = { state: qp.state, mode: qp.querySelector(".mc-qc-seg > button[selected]")?.dataset.mode, width: Math.round(r.width), right: Math.round(r.left + r.width) };
            qp.hidePopup(); await until(() => qp.state == "closed", 2000);
          }
          w.moveTo(sx, sy); w.resizeTo(sw, sh); await wait(800);
          return out;''')
        panels = [res["mcNewEvent"], res["mcNewTask"]]
        if any(p["state"] != "open" for p in panels) and res["visibility"] == "hidden":
            return True, f"Testfenster verdeckt – übersprungen {res}"
        modes = res["mcNewEvent"]["mode"] == "event" and res["mcNewTask"]["mode"] == "task"
        return modes and all(p["width"] >= 370 and p["right"] <= res["screenRight"] for p in panels), f"{res}"
    check("Today-Pane: „+“ → Neuer Termin / Neue Aufgabe ganz auf dem Bildschirm", today_plus_event, results)

    def today_animation():
        res = m.js('''
          await toMail(); await wait(1500);
          const panel = d.getElementById("today-pane-panel"); const btn = d.getElementById("mcTodayToggle");
          const record = async () => { const ws = [], ts = []; const t0 = performance.now(); while (performance.now() - t0 < 600) { ws.push(Math.round(panel.getBoundingClientRect().width)); ts.push(performance.now()); await new Promise(r => w.requestAnimationFrame(r)); } return { ws, ts }; };
          const out = { start: Math.round(panel.getBoundingClientRect().width), animating: !!panel.__mcAnimating, tpVisible: w.TodayPane?.isVisible, tab: d.documentElement.getAttribute("mc-tab"), popups: [...d.querySelectorAll("panel, menupopup")].filter(p => p.state == "open").map(p => p.id) };
          if (!out.start) return { skipped: true };
          const errs = []; const onErr = e => errs.push(String(e.message || e.error).slice(0, 200)); w.addEventListener("error", onErr);
          const cons = []; const listener = { observe: m => { if (m instanceof Ci.nsIScriptError && /implementation\\.js/.test(m.sourceName)) cons.push(m.errorMessage.slice(0, 200) + " @" + m.lineNumber); } };
          Services.console.registerListener(listener);
          out.errs = errs; out.cons = cons; out.visibility = d.visibilityState;
          // Bildtakt ohne Animation als Maßstab (60 oder 120 Hz)
          const idle = []; const tIdle = performance.now(); let tPrev = tIdle;
          while (performance.now() - tIdle < 300 || idle.length < 2) { await new Promise(r => w.requestAnimationFrame(r)); const t = performance.now(); idle.push(t - tPrev); tPrev = t; if (idle.length > 60) break; }
          out.idleFrameMs = Math.round(idle.sort((a, b) => a - b)[idle.length >> 1]);
          for (const phase of ["aus", "ein"]) {
            btn.click(); const { ws, ts } = await record(); await wait(300);
            // nur Bilder, in denen sich die Breite ändert (die Animation selbst)
            const moving = ws.map((v, i) => i > 0 && v != ws[i - 1]);
            const dts = ts.slice(1).map((t, i) => t - ts[i]).filter((_, i) => moving[i + 1]);
            const jumps = ws.slice(1).map((v, i) => Math.abs(v - ws[i]));
            out[phase] = { steps: moving.filter(Boolean).length + 1, maxJump: Math.max(...jumps), maxFrameMs: Math.round(Math.max(...dts)), medianFrameMs: Math.round(dts.sort((a, b) => a - b)[dts.length >> 1] || 0) };
          }
          out.end = Math.round(panel.getBoundingClientRect().width);
          w.removeEventListener("error", onErr); Services.console.unregisterListener(listener);
          return out;''')
        if res.get("skipped"):
            return True, "Today-Pane zu – übersprungen"
        if res.get("visibility") == "hidden" and all(res[p]["steps"] <= 1 for p in ("aus", "ein")):
            # macOS pausiert Bildschritte in verdeckten Fenstern – kein Fehler der Animation
            return True, "Testfenster verdeckt – übersprungen"
        # flüssig: viele Zwischenschritte, kein Sprung über die halbe Breite und
        # Bilder im normalen Takt – früher ordnete jedes Bild den ganzen
        # Mailbereich neu an (20–35 ms statt 8 ms bei 120 Hz); Maßstab höchstens
        # 60 Hz, falls das Fenster beim Messen des Leerlaufs verdeckt war
        ok = all(res[p]["steps"] >= 6 and res[p]["maxJump"] < res["start"] / 2 and
                 res[p]["medianFrameMs"] <= min(res["idleFrameMs"], 17) * 1.5 + 2 for p in ("aus", "ein")) and res["end"] == res["start"]
        return ok, f"{res}"
    check("Today-Pane: Ein-/Ausblenden flüssig (kein Sprung)", today_animation, results)


    def address_book():
        # Person und Firma (example.invalid) im persönlichen Adressbuch
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          const add = props => { const c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
            for (const [k, v] of Object.entries(props)) c.setProperty(k, v);
            c.displayName = props.DisplayName; c.primaryEmail = props.PrimaryEmail; return book.addCard(c); };
          // einzeln anlegen – Anna gibt es evtl. schon (ADDRESS_EDIT_JS)
          const has = name => book.childCards.some(c => c.displayName == name);
          if (!has("Anna Beispiel")) add({ FirstName: "Anna", LastName: "Beispiel", DisplayName: "Anna Beispiel", PrimaryEmail: "anna@example.invalid", Company: "Beispiel GmbH", JobTitle: "Leitung", WorkPhone: "+43 1 234" });
          if (!has("Muster AG")) add({ DisplayName: "Muster AG", Company: "Muster AG", PrimaryEmail: "info@example.invalid", WorkPhone: "+43 1 999" });
          tm.openTab("addressBookTab", {}); await wait(2500);
          const ab = tm.currentTabInfo.browser.contentWindow; const ad = ab.document;
          const list = ad.getElementById("cards");
          const out = {};
          for (const name of ["Anna Beispiel", "Muster AG"]) {
            const i = [...Array(list.view.rowCount).keys()].find(k => list.view.getCardFromRow(k)?.displayName == name);
            list.selectedIndex = i; await wait(1200);
            const row = await until(() => [...ad.querySelectorAll("#cards tr")].find(r => r.querySelector(".name")?.textContent == name));
            const av = row?.querySelector("contact-avatar");
            const photo = ad.getElementById("viewContactPhoto");
            out[name] = { company: !!av?.classList.contains("mc-company"), letters: av?.shadowRoot?.querySelector("span")?.textContent,
              radius: av ? ab.getComputedStyle(av).borderRadius : null,
              photo: (photo.getAttribute("src") || "").slice(0, 60),
              books: [...ad.querySelectorAll("#mcDetailBooks .mc-book")].map(e => e.textContent),
              types: [...ad.querySelectorAll("#viewContact .entry-type")].filter(e => e.textContent).map(e => [e.textContent, ab.getComputedStyle(e).textTransform]) };
          }
          // Teiler anfassen ohne Bewegung: Kontaktliste bleibt gleich breit (kein Sprung)
          const shared = ad.getElementById("sharedSplitter"); const cards = ad.getElementById("cardsPane");
          const before = Math.round(cards.getBoundingClientRect().width);
          shared._updateSize?.(before); await wait(200);
          out.splitter = [before, Math.round(cards.getBoundingClientRect().width)];
          tm.closeTab(tm.currentTabInfo);
          return out;""")
        a, f = res.get("Anna Beispiel", {}), res.get("Muster AG", {})
        ok = (a.get("letters") == "AB" and not a.get("company") and a.get("photo", "").startswith("data:image/svg")
              and f.get("company") and "company-avatar.svg" in f.get("photo", "")
              and a.get("radius") == "50%" and a.get("books") and all(t[1] == "none" for t in a.get("types", []))
              and len(a.get("types", [])) >= 2 and abs(res["splitter"][0] - res["splitter"][1]) <= 1)
        return ok, f"{res}"
    check("Adressbuch: Firmen-Avatar, Initialen im Detail, Konto-Etiketten, Bezeichnungen, Teiler ohne Sprung", address_book, results)

    def contact_edit():
        # Kontakt bearbeiten wie Apple Kontakte: eine Schrift, Überschriften über den Feldern,
        # volle Breite; zuerst nur Vor-/Nachname, E-Mail, Telefon, Adressen und Ausgefülltes
        res = m.js(ADDRESS_EDIT_JS + r"""
          // unter Last kommen die „Mehr“-Knöpfe erst nach den festen Wartezeiten dazu
          await until(() => ad.querySelector("#addr-book-edit-n .mc-more-button") && ad.querySelector("vcard-edit + .mc-more-button"), 6000);
          const font = ab.getComputedStyle(ad.documentElement).getPropertyValue("--mt-font").trim().split(",")[0];
          const ve = ad.querySelector("#editContactForm vcard-edit");
          const scroll = ve.parentElement;
          const ctrls = [...ad.querySelectorAll("#editContactForm :is(input:not([type=checkbox]), select, legend:not(.screen-reader-only), label:not(.screen-reader-only), .add-property-button:not(.only-icon))")]
            .filter(e => e.getClientRects().length);
          const fonts = [...new Set(ctrls.map(e => ab.getComputedStyle(e).fontFamily.split(",")[0]))];
          const sizes = [...new Set(ctrls.filter(e => !e.matches("label, legend")).map(e => ab.getComputedStyle(e).fontSize))];
          const tel = ad.getElementById("addr-book-edit-tel");
          const lg = tel.querySelector(":scope > legend").getBoundingClientRect(), inp = tel.querySelector("input[type=tel]").getBoundingClientRect();
          const out = { font, fonts, sizes, width: Math.round(ve.getBoundingClientRect().width),
            avail: Math.round(scroll.clientWidth - parseFloat(ab.getComputedStyle(scroll).paddingLeft) - parseFloat(ab.getComputedStyle(scroll).paddingRight)),
            legendAbove: lg.bottom <= inp.top && Math.abs(lg.left - tel.querySelector("select").getBoundingClientRect().left) <= 2 };
          const shown = () => [...ad.querySelectorAll("#addr-book-edit-n :is(input, .mc-more-button)")].filter(e => e.getClientRects().length).map(e => e.id || "mehr");
          const groups = () => [...ve.querySelectorAll(":scope > fieldset")].filter(e => e.getClientRects().length)
            .sort((x, y) => x.getBoundingClientRect().top - y.getBoundingClientRect().top).map(e => e.id.replace("addr-book-edit-", ""));
          const fn = ad.getElementById("vcard-n-firstname").getBoundingClientRect(), ln = ad.getElementById("vcard-n-lastname").getBoundingClientRect();
          out.names = { closed: shown(), sideBySide: Math.abs(fn.top - ln.top) <= 1 && Math.abs(fn.width - ln.width) <= 1 };
          out.groups = { closed: groups() };
          ad.querySelector("#addr-book-edit-n .mc-more-button").click();
          ad.querySelector("vcard-edit + .mc-more-button").click(); await wait(300);
          out.names.open = shown(); out.groups.open = groups();
          out.buttons = [...ad.querySelectorAll(".mc-more-button")].map(b => [b.textContent, b.getAttribute("aria-expanded")]);
          // Bild wie Apple Kontakte: Initialen, mittig über dem Namen; folgt dem Namen beim Tippen
          const photo = ad.querySelector("#photoInput .contact-photo"), pr = photo.getBoundingClientRect();
          const hr = ad.getElementById("editContactHeadingName").getBoundingClientRect();
          const letters = () => decodeURIComponent(photo.getAttribute("src") || "").match(/<text[^>]*>([^<]*)</)?.[1];
          out.photo = { letters: letters(), size: Math.round(pr.width), above: pr.bottom <= hr.top,
            centered: Math.abs((pr.left + pr.right) / 2 - (hr.left + hr.right) / 2) <= 2 };
          const first = ad.getElementById("vcard-n-firstname");
          first.value = "Berta"; first.dispatchEvent(new ab.InputEvent("input", { bubbles: true }));
          out.photo.typed = await until(() => letters() == "BB" && "BB") || letters();
          ab.detailsPane.isDirty = false; // Testeingabe verwerfen, ohne Rückfrage
          ad.getElementById("cancelEditButton").click(); await wait(500);
          const vp = ad.getElementById("viewContactPhoto");
          out.viewLetters = decodeURIComponent(vp.getAttribute("src") || "").match(/<text[^>]*>([^<]*)</)?.[1];
          out.viewSize = Math.round(vp.getBoundingClientRect().width);
          tm.closeTab(tm.currentTabInfo);
          return out;""")
        ok = (res["fonts"] == [res["font"]] and res["sizes"] == ["13px"]
              and res["width"] >= min(res["avail"], 1040) - 2 and res["legendAbove"]
              and res["names"]["closed"] == ["vcard-n-firstname", "vcard-n-lastname", "mehr"] and res["names"]["sideBySide"]
              and {"vcard-n-prefix", "vcard-n-middlename", "vcard-n-suffix", "vCardNickName", "vCardDisplayName"} <= set(res["names"]["open"])
              and res["groups"]["closed"][:4] == ["n", "email", "tel", "address"] and "org" in res["groups"]["closed"]
              and "url" not in res["groups"]["closed"] and "url" in res["groups"]["open"]
              and all(b[1] == "true" for b in res["buttons"]) and len(res["buttons"]) == 2
              and res["photo"]["letters"] == "AB" and res["photo"]["above"] and res["photo"]["centered"]
              and res["photo"]["typed"] == "BB" and res["viewLetters"] == "AB" and res["viewSize"] > res["photo"]["size"] >= 100)
        return ok, f"{res}"
    check("Adressbuch: Kontakt bearbeiten in Systemschrift, Überschriften über den Feldern, Wichtiges zuerst, Weiteres auf Wunsch, Initialen mittig über dem Namen", contact_edit, results)

    ab_views_res = {}

    def ab_views():
        # Kontakt-, Listen-, Auswahl-, Tabellen- und Leeransicht einmal messen
        if not ab_views_res:
            ab_views_res.update(m.js(r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  const { VCardUtils } = ChromeUtils.importESModule("resource:///modules/VCardUtils.sys.mjs");
  const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
  const mk = props => { const c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
    for (const [k, v] of Object.entries(props)) if (!["DisplayName", "PrimaryEmail"].includes(k)) c.setProperty(k, v);
    c.displayName = props.DisplayName; c.primaryEmail = props.PrimaryEmail; return c; };
  const has = name => book.childCards.some(c => c.displayName == name);
  // was hier angelegt wird, am Ende wieder entfernen (spätere Prüfungen zählen Kontakte)
  const made = [];
  if (!has("Anna Beispiel")) book.addCard(mk({ FirstName: "Anna", LastName: "Beispiel", DisplayName: "Anna Beispiel", PrimaryEmail: "anna@example.invalid", Company: "Beispiel GmbH", JobTitle: "Leitung", WorkPhone: "+43 1 234" }));
  if (!has("Ben Muster")) made.push(book.addCard(mk({ FirstName: "Ben", LastName: "Muster", DisplayName: "Ben Muster", PrimaryEmail: "ben@example.invalid" })));
  if (!has("Jonas Ärmel")) made.push(book.addCard(VCardUtils.vCardToAbCard("BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Jonas Ärmel\r\nN:Ärmel;Jonas;;;\r\nEMAIL;PREF=1:jonas@example.invalid\r\nTEL;TYPE=work:+43 1 777\r\nNOTE:Erfundener Testkontakt\r\nEND:VCARD\r\n")));
  if (!book.childNodes.some(l => l.dirName == "Halo Liste")) {
    const l = Cc["@mozilla.org/addressbook/directoryproperty;1"].createInstance(Ci.nsIAbDirectory);
    l.isMailList = true; l.dirName = "Halo Liste"; l.listNickName = "haloliste";
    const ml = book.addMailList(l);
    for (const c of book.childCards) if (["Anna Beispiel", "Ben Muster", "Jonas Ärmel"].includes(c.displayName)) ml.addCard(c);
  }
  if (!MailServices.ab.directories.some(b => b.dirName == "Halo Leer")) MailServices.ab.newAddressBook("Halo Leer", "", Ci.nsIAbManager.JS_DIRECTORY_TYPE);
  tm.openTab("addressBookTab", {});
  const ab = await until(() => tm.currentTabInfo.browser?.contentWindow?.cardsPane && tm.currentTabInfo.browser.contentWindow, 8000);
  await wait(1500);
  const abTab = tm.currentTabInfo;
  const ad = ab.document, cs = e => ab.getComputedStyle(e);
  const R = e => e.getBoundingClientRect(), mid = e => { const r = R(e); return (r.left + r.right) / 2; };
  const list = ad.getElementById("cards");
  const rows = () => [...Array(list.view.rowCount).keys()];
  const pick = async name => { list.selectedIndex = rows().find(k => list.view.getCardFromRow(k)?.displayName == name); await wait(900); };
  // Hilfselement für die berechnete Akzentfarbe
  const probe = ad.createElement("span"); probe.style.color = "AccentColor"; ad.body.append(probe);
  const accent = cs(probe).color; probe.remove();
  const out = { accent };
  try {
    // Kontakt: Kopf mittig, Links in Akzentfarbe, eine Kante in den Karten
    await pick("Jonas Ärmel");
    const body = ad.getElementById("detailsBody"), photo = ad.getElementById("viewContactPhoto");
    const em = ad.querySelector("#emailAddresses");
    const firstVal = em.querySelector(".entry-value"), link = em.querySelector("a");
    const telType = ad.querySelector("#phoneNumbers .entry-type"), note = ad.querySelector("#notes > div");
    out.contact = { photoMid: Math.round(mid(photo) - mid(body)), photoW: Math.round(R(photo).width),
      link: link && [cs(link).textDecorationLine, cs(link).color],
      edges: [em.querySelector("h2"), firstVal, telType, note].map(e => e ? Math.round(R(e).left) : null),
      // Notiz so groß wie die übrigen Werte
      noteFont: note && [cs(note).fontSize, cs(firstVal).fontSize] };
    // Darstellungsmenü „…“: drei Abschnitte mit genau einer Trennlinie dazwischen
    const sc = ad.getElementById("sortContext");
    const shownP = new Promise(r => sc.addEventListener("popupshown", r, { once: true }));
    sc.openPopup(list, "after_start"); await Promise.race([shownP, wait(3000)]); await wait(300);
    out.sortMenu = [...sc.children].filter(e => !e.hidden && cs(e).display != "none")
      .map(e => e.localName == "menuseparator" ? "|" : e.localName == "menucaption" ? "#" + e.getAttribute("label") : (e.getAttribute("value") || e.id || "item"));
    const hiddenP = new Promise(r => sc.addEventListener("popuphidden", r, { once: true }));
    sc.hidePopup(); await Promise.race([hiddenP, wait(2000)]);
    // neuer Kontakt ohne Namen: Personen-Silhouette statt Initialen aus „New Contact“,
    // nach Eingabe von Vor- und Nachname deren Initialen
    {
      ab.detailsPane.editNewContact(); await wait(800);
      const ph = ad.querySelector("#photoInput .contact-photo");
      const srcOf = () => decodeURIComponent(ph?.getAttribute("src") || "");
      const before = srcOf();
      const typeIn = (id, v) => { const f = ad.getElementById(id); f.value = v; f.dispatchEvent(new ab.InputEvent("input", { bubbles: true })); };
      typeIn("vcard-n-firstname", "Test"); typeIn("vcard-n-lastname", "Person"); await wait(500);
      const after = srcOf();
      out.newContact = { before: before.slice(-40), person: before.endsWith("person-avatar.svg"),
        initials: after.startsWith("data:") && after.includes(">TP<"), heading: ad.getElementById("editContactHeadingName")?.textContent };
      ab.detailsPane.isDirty = false;
      ad.getElementById("cancelEditButton").click(); await wait(600);
    }
    // Kontakt bearbeiten: Papierkorb im Knopf „Delete“ mit Abstand zum Text,
    // links und rechts etwa gleich viel Rand in der Kapsel
    {
      await pick("Jonas Ärmel");
      ad.getElementById("editButton").click(); await wait(1200);
      const del = ad.getElementById("detailsDeleteButton");
      const tn = []; { const tw = ad.createTreeWalker(del, ab.NodeFilter.SHOW_TEXT); while (tw.nextNode()) if (tw.currentNode.textContent.trim()) tn.push(tw.currentNode); }
      const rg = ad.createRange(); if (tn.length) { rg.setStart(tn[0], 0); rg.setEnd(tn[tn.length - 1], tn[tn.length - 1].length); }
      const tr = tn.length ? rg.getBoundingClientRect() : null, br = R(del);
      const bx = parseFloat(cs(del).backgroundPositionX), ps = parseFloat(cs(del).paddingInlineStart);
      out.del = { visible: del.getClientRects().length > 0, bx, ps, gap: ps - (bx + 16),
        left: bx, right: tr ? Math.round(br.right - tr.right) : null, textGap: tr ? Math.round(tr.left - br.left - bx - 16) : null };
      ab.detailsPane.isDirty = false;
      ad.getElementById("cancelEditButton").click(); await wait(600);
    }
    // breiter Detailbereich (> 64em): Kopf bleibt auf der Achse
    const dp = ad.getElementById("detailsPane");
    out.wide = { pane: Math.round(R(dp).width) };
    // Tabellenansicht: kleines Foto, erste Karte ohne Scrollen sichtbar, Kopf auf der Achse
    ab.cardsPane.toggleLayout(true); await wait(1500); await pick("Jonas Ärmel"); await wait(600);
    // Darstellungsmenü in der Tabelle: ohne Sortierung kein leerer Titel „Sort“
    {
      w.focus(); abTab.browser.focus(); await wait(200);
      const shown = new Promise(r => sc.addEventListener("popupshown", r, { once: true }));
      sc.openPopup(list, "after_start"); await Promise.race([shown, wait(3000)]); await wait(300);
      out.sortMenuState = sc.state;
      out.sortMenuTable = [...sc.children].filter(e => !e.hidden && e.getClientRects().length > 0)
        .map(e => e.localName == "menuseparator" ? "|" : e.localName == "menucaption" ? "#" + e.getAttribute("mc-section") : (e.getAttribute("value") || e.id || "item"));
      const hid = new Promise(r => sc.addEventListener("popuphidden", r, { once: true }));
      sc.hidePopup(); await Promise.race([hid, wait(2000)]);
    }
    const lh2 = d.querySelector("#mcListHeader .mc-lh-more"), search = d.querySelector("#unifiedToolbarContent global-search-bar, #unifiedToolbarContent search-bar, #unifiedToolbarContent .search-bar");
    out.table = { photoW: Math.round(R(photo).width), photoMid: Math.round(mid(photo) - mid(body)),
      emTop: Math.round(R(em).top), paneBottom: Math.round(R(dp).bottom), dpW: Math.round(R(dp).width),
      more: lh2 && [Math.round(lh2.getBoundingClientRect().left), Math.round(lh2.getBoundingClientRect().right)],
      search: search && [search.localName, Math.round(search.getBoundingClientRect().left), Math.round(search.getBoundingClientRect().width)],
      line: w.getComputedStyle(d.getElementById("unifiedToolbarContainer"), "::before").content,
      firstBtn: [...d.querySelectorAll("#unifiedToolbarContent > li:not([item-id=spacer])")].filter(e => e.getClientRects().length && e.getBoundingClientRect().width).map(e => [e.getAttribute("item-id"), Math.round(e.getBoundingClientRect().left)]).slice(0, 6) };
    ab.cardsPane.toggleLayout(false); await wait(1500);
    out.cardsView = { photoW: Math.round(R(photo).width),
      more: lh2 && [Math.round(lh2.getBoundingClientRect().left), Math.round(lh2.getBoundingClientRect().right)],
      search: search && [Math.round(search.getBoundingClientRect().left), Math.round(search.getBoundingClientRect().width)],
      line: w.getComputedStyle(d.getElementById("unifiedToolbarContainer"), "::before").content };
    // Liste: Kontaktkopf weg, Listenkopf mittig mit Verlaufs-Kreis
    const lrow = [...ad.querySelectorAll("#books li.listRow")].find(li => li.textContent.includes("Halo Liste"));
    ab.booksList.selectedIndex = ab.booksList.rows.indexOf(lrow); await wait(1200);
    const lc = lrow.querySelector(".listRow-container") || lrow.firstElementChild;
    // Auswahl unfokussiert grau, fokussiert wie die Ordnerliste akzentgetönt
    list.focus(); await wait(300);
    const bgBlur = cs(lc).backgroundColor;
    const tint = ad.createElement("span"); ad.body.append(tint);
    tint.style.backgroundColor = "var(--mt-selected-unfocused)"; const unfocused = cs(tint).backgroundColor;
    tint.style.backgroundColor = "color-mix(in srgb, var(--mt-accent) 22%, transparent)"; const focused = cs(tint).backgroundColor;
    tint.remove();
    // Hauptfenster und Tab nach vorn, sonst gilt :focus-within nicht
    w.focus(); abTab.browser.focus(); ad.getElementById("books").focus(); await wait(300);
    const licon = lrow.querySelector(".listRow-icon");
    out.listSel = { bgBlur, bgFocus: cs(lc).backgroundColor, unfocused, focused, fw: ad.getElementById("books").matches(":focus-within"),
      icon: [cs(licon).backgroundColor, cs(licon).maskImage.startsWith('url("data:'), Math.round(R(licon).width)] };
    const brow = ad.querySelector("#books .bookRow > .bookRow-container");
    out.listRow = { border: cs(lc).borderTopWidth, radius: cs(lc).borderTopLeftRadius, font: cs(lc).fontSize,
      h: Math.round(R(lc).height), bookH: Math.round(R(brow).height), bg: cs(lc).backgroundColor,
      // eingerückt unter seinem Buch
      indent: Math.round(R(lrow.querySelector(".listRow-icon")).left - R(lrow.parentElement.closest("li").querySelector(".bookRow-icon")).left) };
    // Abstand Symbol → Name gleich bei Verteilerliste und Buch
    {
      const brow2 = lrow.parentElement.closest("li");
      out.nameGap = { list: Math.round(R(lrow.querySelector(".listRow-name")).left - R(lrow.querySelector(".listRow-icon")).right),
        book: Math.round(R(brow2.querySelector(".bookRow-name")).left - R(brow2.querySelector(".bookRow-icon")).right) };
    }
    // Auswahlfarbe einer gewählten Buchzeile zum Vergleich
    ab.booksList.selectedIndex = 0; await wait(1200);
    await pick("Halo Liste");
    // Zeile der Verteilerliste: Symbol weiß und klein auf dem Verlauf
    const lav = list.getRowAtIndex?.(list.selectedIndex)?.querySelector("contact-avatar.is-mail-list");
    const limg = lav?.shadowRoot?.querySelector("img");
    out.listAvatar = lav && { bg: cs(lav).backgroundImage.includes("linear-gradient"), color: cs(lav).color,
      w: Math.round(R(lav).width), img: limg ? Math.round(R(limg).width) : null };
    const ch = ad.querySelector("#viewContact .contact-header"), lh = ad.querySelector("#viewContact .list-header");
    const lname = ad.getElementById("viewListName"), av = lh.querySelector(".recipient-avatar");
    out.list = { headerDisplay: cs(ch).display, photoRects: photo.getClientRects().length, hidden: ch.hidden,
      listMid: Math.round(mid(lname) - mid(body)), font: [cs(lname).fontSize, cs(lname).fontWeight],
      avatar: [Math.round(R(av).width), cs(av).backgroundImage.slice(0, 15), Math.round(mid(av) - mid(body))] };
    // Mehrfachauswahl
    ad.getElementById("cards").focus();
    list.selectedIndices = rows().filter(k => ["Anna Beispiel", "Ben Muster", "Jonas Ärmel"].includes(list.view.getCardFromRow(k)?.displayName)); await wait(1200);
    const cnt = ad.getElementById("viewSelectionCount"), sel = ad.getElementById("selectedCards");
    const avs = [...sel.querySelectorAll("contact-avatar")];
    out.multi = { headerDisplay: cs(ch).display, photoRects: photo.getClientRects().length,
      countMid: Math.round(mid(cnt) - mid(sel)), font: cs(cnt).fontSize, n: avs.length,
      avatars: avs.map(a => [cs(a).backgroundImage.includes("linear-gradient"), cs(a).color, cs(a).fontSize]) };
    // leeres Buch
    const erow = [...ad.querySelectorAll("#books li")].find(li => li.textContent.includes("Halo Leer"));
    ab.booksList.selectedIndex = ab.booksList.rows.indexOf(erow); await wait(1500);
    const slot = list.shadowRoot?.querySelector('slot[name="placeholders"]') || ad.querySelector('#cards > slot[name="placeholders"]');
    const btn = ad.getElementById("placeholderCreateContact"), empty = ad.getElementById("placeholderEmptyBook");
    out.empty = { opacity: slot && cs(slot).opacity, btn: [btn.getClientRects().length, cs(btn).fontSize, cs(btn).color],
      emptyColor: cs(empty).color, tert: cs(ad.documentElement).getPropertyValue("--mt-text-tertiary").trim() };
    // leeres Buch: Details ausgeblendet, rechts derselbe Grund wie die Kontaktliste
    {
      const dpR = R(ad.getElementById("cardsPane"));
      let el = ad.elementFromPoint(Math.round((dpR.right + ab.innerWidth) / 2), Math.round(ab.innerHeight / 2)), bg = null;
      for (; el; el = el.parentElement) { const c = cs(el).backgroundColor; if (c != "transparent" && !/rgba\(.*, 0\)$/.test(c)) { bg = [el.id || el.localName, c]; break; } }
      if (!bg) bg = ["root", cs(ad.documentElement).backgroundColor];
      out.emptyBg = { detailsHidden: ad.getElementById("detailsPane").hidden || cs(ad.getElementById("detailsPane")).display == "none",
        root: cs(ad.documentElement).backgroundColor, cards: cs(ad.getElementById("cardsPane")).backgroundColor, right: bg };
    }
    ab.booksList.selectedIndex = 0; await wait(1200);
  } finally {
    tm.closeTab(abTab);
    const ml = book.childNodes.find(l => l.dirName == "Halo Liste"); if (ml) book.deleteDirectory(ml);
    if (made.length) book.deleteCards(made);
    const eb = MailServices.ab.directories.find(b => b.dirName == "Halo Leer"); if (eb) MailServices.ab.deleteAddressBook(eb.URI);
    await wait(500);
  }
  return out;"""))
        return ab_views_res

    def ab_heads():
        # Verteilerliste und Mehrfachauswahl: kein leerer Kontaktkreis, Kopf mittig
        # und groß (Liste im Verlauf der Initialen-Kreise); Mitglieder-Kreise wie
        # in der Liste; Kontaktkopf auch im breiten Detailbereich (Tabelle) mittig
        res = ab_views()
        li, mu, ta = res["list"], res["multi"], res["table"]
        ok = (li["headerDisplay"] == "none" and li["photoRects"] == 0 and abs(li["listMid"]) <= 2
              and li["font"] == ["28px", "700"] and li["avatar"][0] == 120 and li["avatar"][1] == "linear-gradient" and abs(li["avatar"][2]) <= 2
              and mu["headerDisplay"] == "none" and mu["photoRects"] == 0 and abs(mu["countMid"]) <= 2 and mu["font"] == "28px"
              and mu["n"] >= 3 and all(a == [True, "rgb(255, 255, 255)", "15px"] for a in mu["avatars"])
              and abs(res["contact"]["photoMid"]) <= 2 and abs(ta["photoMid"]) <= 2 and ta["dpW"] > 840)
        return ok, f"{res}"
    check("Adressbuch: Verteilerliste und Mehrfachauswahl ohne leeren Kreis, Kopf mittig; Mitglieder-Kreise im Verlauf; Kontaktkopf auch breit mittig", ab_heads, results)

    def ab_details_cards():
        # Detailkarten: Links in der Akzentfarbe ohne Unterstrich, Überschrift,
        # Bezeichnungen, Werte ohne Bezeichnung und Notiz an einer Kante;
        # Verteilerliste in der Bücherliste wie die Buchzeilen; leeres Buch mit
        # kräftigem „New Contact“ statt halb durchsichtigem Hinweis
        res = ab_views()
        c, lr, e = res["contact"], res["listRow"], res["empty"]
        edges = c["edges"]
        ok = (c["link"] == ["none", res["accent"]] and None not in edges and max(edges) - min(edges) <= 1
              and lr["border"] == "0px" and lr["radius"] == "8px" and lr["font"] == "13px" and abs(lr["h"] - lr["bookH"]) <= 1 and lr["indent"] >= 16
              and e["opacity"] == "1" and e["btn"] == [1, "13px", res["accent"]])
        return ok, f"{res}"
    check("Adressbuch: Links in Akzentfarbe, Karteninhalt an einer Kante, Verteilerliste in der Bücherliste wie Buchzeilen, leeres Buch mit kräftigem Knopf", ab_details_cards, results)

    def ab_footer_gaps():
        # Bearbeiten: Papierkorb im Knopf „Delete“ mit Abstand zum Text (statt
        # fast daran klebend), Rand links/rechts ähnlich; Bücherliste: Name der
        # Verteilerliste so weit hinter dem Symbol wie bei den Büchern (eingerückt);
        # leeres Buch: rechts kein dunklerer, blaustichiger Seitengrund
        res = ab_views()
        dl, ng, eb, lr = res.get("del") or {}, res.get("nameGap") or {}, res.get("emptyBg") or {}, res.get("listRow") or {}
        ok = (dl.get("visible") and dl["gap"] >= 4 and dl["bx"] >= 10 and dl["textGap"] is not None and dl["textGap"] >= 4
              and abs(dl["left"] - dl["right"]) <= 6
              and ng and abs(ng["list"] - ng["book"]) <= 1 and 4 <= ng["book"] <= 8 and lr.get("indent", 0) > 0
              and eb.get("detailsHidden") and same_color(eb["root"], eb["cards"]) and same_color(eb["right"][1], eb["cards"]))
        return ok, f"del={dl} nameGap={ng} emptyBg={eb}"
    check("Adressbuch: Papierkorb im Knopf „Delete“ mit Abstand zum Text; Verteilerliste in der Bücherliste mit gleichem Namensabstand wie Bücher; leeres Buch rechts im Grund der Kontaktliste", ab_footer_gaps, results)

    def ab_table():
        # Tabellenansicht: kleines Foto, erste Karte ohne Scrollen sichtbar;
        # „…“ des Listenkopfs nicht über dem Suchfeld, Knöpfe rechts davon,
        # Suche so breit wie in der Kartenansicht, ohne Trennlinie ohne Spalte
        res = ab_views()
        ta, cv = res["table"], res["cardsView"]
        btns = [b[1] for b in ta["firstBtn"]]
        ok = (ta["photoW"] <= 100 and ta["emTop"] < ta["paneBottom"] and cv["photoW"] == 260
              and ta["more"] and ta["search"] and ta["more"][1] <= ta["search"][1] and btns and min(btns) >= ta["more"][1]
              and ta["search"][2] >= cv["search"][1] - 2 and ta["line"] == "none" and cv["line"] != "none")
        return ok, f"{res}"
    check("Adressbuch-Tabelle: kleines Foto mit sichtbaren Karten; „…“ nicht über der Suche, Knöpfe an ihrem Platz", ab_table, results)

    def ab_list_menu():
        # Notiz in 14 px wie die übrigen Werte; Verteilerliste in der Kontaktliste
        # mit weißem, kleinem Symbol auf dem Verlauf statt frei stehendem Umriss;
        # Darstellungsmenü: „Show Names As“ | „Sort“ | „View“ – je genau eine
        # Trennlinie, innerhalb von „View“ keine
        res = ab_views()
        c, la, sm = res["contact"], res.get("listAvatar"), res.get("sortMenu") or []
        view = sm.index("#View") if "#View" in sm else -1
        ok = (c.get("noteFont") == ["14px", "14px"]
              and bool(la) and la["bg"] and la["color"] == "rgb(255, 255, 255)" and la["img"] is not None and la["img"] <= 24
              and sm.count("|") == 2 and view > 0 and sm[view - 1] == "|" and "|" not in sm[view:]
              and "mcHideDuplicates" in sm[view:] and "sortContextTableLayout" in sm[view:] and "addrbook" in sm[view:])
        return ok, f"note={c.get('noteFont')} listAvatar={la} sortMenu={sm}"
    check("Adressbuch: Notiz so groß wie die Werte; Verteilerliste in der Liste im Verlaufskreis; Darstellungsmenü mit je einer Trennlinie zwischen den Abschnitten", ab_list_menu, results)

    def ab_list_select_new():
        # Verteilerliste in der Bücherliste: Auswahl unfokussiert grau, fokussiert
        # akzentgetönt wie die Ordnerliste, Symbol in der Akzentfarbe; Tabellen-
        # ansicht ohne leeren Titel „Sort“ und ohne doppelte Linie; neuer
        # Kontakt ohne Namen mit Silhouette statt „NC“, danach mit Initialen
        res = ab_views()
        ls, st, nc = res.get("listSel") or {}, res.get("sortMenuTable") or [], res.get("newContact") or {}
        # keine Linie am Rand oder doppelt; jeder Titel nach dem ersten mit Linie davor und Eintrag danach
        seps_ok = (bool(st) and st[0] != "|" and st[-1] != "|" and "#sort" not in st
                   and all(not (x == "|" and y == "|") for x, y in zip(st, st[1:]))
                   and all(i + 1 < len(st) and st[i + 1] != "|" and not st[i + 1].startswith("#") and (i == 0 or st[i - 1] == "|")
                           for i, x in enumerate(st) if x.startswith("#")))
        ok = (bool(ls) and same_color(ls["bgBlur"], ls["unfocused"]) and same_color(ls["bgFocus"], ls["focused"])
              and not same_color(ls["bgFocus"], ls["bgBlur"])
              and same_color(ls["icon"][0], res["accent"]) and ls["icon"][1] and ls["icon"][2] == 18
              and seps_ok and "sortContextTableLayout" in st
              and nc.get("person") is True and nc.get("initials") is True)
        return ok, f"listSel={ls} sortMenuTable={st} state={res.get('sortMenuState')} newContact={nc}"
    check("Adressbuch: Verteilerliste in der Bücherliste fokussiert akzentgetönt mit Akzentsymbol; Tabellen-Darstellungsmenü ohne leeres „Sort“; neuer Kontakt mit Silhouette statt „NC“", ab_list_select_new, results)

    def ab_search_dialog():
        # Adressen suchen: Bedingungen und Ergebnisse als Flächen mit Haarlinie
        # und 8 px Radius (dunkel keine schwarze Liste), Teiler als eine Linie
        res = m.js(COMPOSE_CHECK_JS + r"""
          later(() => w.MsgSearchAddresses());
          const sw = await winUrl("abSearchDialog"); if (!sw) throw new Error("Adressen suchen nicht offen");
          await pause(1000);
          try {
            const sd = sw.document, t = sd.getElementById("abResultsTree"), l = sd.getElementById("searchTermList"), sp = sd.getElementById("gray_horizontal_splitter");
            return { tree: [csOf(t).backgroundColor, csOf(t).borderTopLeftRadius, csOf(t).borderTopColor],
                     terms: [csOf(l).backgroundColor, csOf(l).borderTopLeftRadius, csOf(l).borderTopColor],
                     split: [csOf(sp).borderTopWidth, csOf(sp).borderBottomWidth],
                     win: colorOf(sd, "var(--mt-window)", "backgroundColor"), line: colorOf(sd, "var(--mt-pane-line)", "borderTopColor") };
          } finally { await shut(sw); }""")
        ok = (all(same_color(x[0], res["win"]) and x[1] == "8px" and same_color(x[2], res["line"]) for x in (res["tree"], res["terms"]))
              and res["tree"][0] != "rgb(0, 0, 0)" and res["split"][1] == "0px" and res["split"][0] in ("1px", "0.5px"))
        return ok, f"{res}"
    check("Adressen suchen: Bedingungen und Ergebnisse als Flächen mit Haarlinie, keine schwarze Liste, Teiler als eine Linie", ab_search_dialog, results)

    def ab_edit_dialogs():
        # Bearbeiten gleich nach dem Öffnen: das Layout (Weitere Felder) greift
        # auch, wenn vcard-edit erst nach dem ersten Aufruf definiert wird;
        # Kontaktbild-Dialog zeigt Hinweis und Symbol (Dateifeld durchsichtig,
        # Fläche als Karte); Unterdialoge im Tab auf neutraler Fläche (dunkel
        # nicht Thunderbirds Blaugrau)
        res = m.js(r"""
  const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
  const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
  if (!book.childCards.some(c => c.displayName == "Anna Beispiel")) {
    const c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
    c.setProperty("FirstName", "Anna"); c.setProperty("LastName", "Beispiel");
    c.displayName = "Anna Beispiel"; c.primaryEmail = "anna@example.invalid"; book.addCard(c);
  }
  const out = { race: [] };
  // Wettlauf: Tab neu öffnen und ohne Wartezeit bearbeiten – das Layout greift trotzdem
  for (let n = 0; n < 3; n++) {
    tm.openTab("addressBookTab", {});
    const tab = tm.currentTabInfo;
    const ab = await until(() => { const c = tab.browser?.contentWindow; return c?.document?.getElementById("cards")?.view?.rowCount && c; }, 8000);
    const ad = ab.document, list = ad.getElementById("cards");
    list.selectedIndex = [...Array(list.view.rowCount).keys()].find(k => list.view.getCardFromRow(k)?.displayName == "Anna Beispiel");
    await until(() => !ad.getElementById("editButton").hidden && ad.getElementById("editButton").getClientRects().length, 4000);
    ad.getElementById("editButton").click();
    await until(() => ad.querySelector("#addr-book-edit-n .mc-more-button"), 4000);
    const url = ad.getElementById("addr-book-edit-url");
    out.race.push({ more: !!ad.querySelector("#addr-book-edit-n .mc-more-button"), url: url ? url.getClientRects().length : null,
      layout: ab.customElements.get("vcard-edit")?.prototype.__mcLayout === true });
    if (n == 2) {
      // Kontaktbild-Dialog: Hinweis sichtbar, Feld durchsichtig, Fläche als Karte
      ad.getElementById("photoButton").click();
      const dlg = await until(() => ad.getElementById("photoDialog")?.open && ad.getElementById("photoDialog"), 4000);
      const fi = ad.getElementById("dialogFileInput"), dt = ad.getElementById("photoDropTarget");
      const lab = ad.querySelector('label[for="dialogFileInput"]');
      out.photo = { open: !!dlg, bg: ab.getComputedStyle(fi).backgroundColor, border: ab.getComputedStyle(fi).borderTopWidth,
        radius: ab.getComputedStyle(dt).borderTopLeftRadius, label: lab?.getClientRects().length,
        // Hinweis unter dem Symbol (nicht darüber), Knopfleiste ohne eigene Fläche
        below: Math.round(lab.getBoundingClientRect().top + parseFloat(ab.getComputedStyle(lab).paddingTop) - dt.getBoundingClientRect().top),
        menu: ab.getComputedStyle(ad.querySelector("#photoDialog .dialog-menu-container")).backgroundColor,
        dlgBg: ab.getComputedStyle(ad.getElementById("photoDialog")).backgroundColor,
        sheet: ab.getComputedStyle(ad.documentElement).getPropertyValue("--mt-sheet").trim() };
      ad.getElementById("photoDialog").close(); await wait(300);
    }
    ab.detailsPane.isDirty = false;
    ad.getElementById("cancelEditButton").click(); await wait(400);
    if (n == 2) {
      // Unterdialog „Neue Verteilerliste“: neutrale Fläche
      w.setTimeout(() => ab.createList(), 0);
      const fr = await until(() => [...ad.querySelectorAll(".dialogFrame")].find(f => f.contentDocument?.readyState == "complete" && f.contentDocument.location.href != "about:blank"), 6000);
      await wait(800);
      const box = ad.querySelector(".dialogBox"), sd = fr.contentDocument, sw = fr.contentWindow;
      const dlg = sd.querySelector("dialog");
      out.sub = { box: ab.getComputedStyle(box).backgroundColor, root: sw.getComputedStyle(sd.documentElement).backgroundColor,
        dialog: dlg && sw.getComputedStyle(dlg).backgroundColor, subAttr: sd.documentElement.hasAttribute("subdialog"),
        sheet: sw.getComputedStyle(sd.documentElement).getPropertyValue("--mt-sheet").trim() };
      (sd.querySelector("dialog")?.getButton?.("cancel") || null)?.click();
      await wait(600);
    }
    tm.closeTab(tab); await wait(300);
  }
  return out;""")
        import re
        ph, sub = res.get("photo", {}), res.get("sub", {})
        def neutral(c):
            v = [int(x) for x in re.findall(r"\d+", c or "")[:3]]
            return len(v) == 3 and max(v) - min(v) <= 4
        ok = (len(res["race"]) == 3 and all(r == {"more": True, "url": 0, "layout": True} for r in res["race"])
              and ph.get("open") and ph.get("bg") in ("rgba(0, 0, 0, 0)", "transparent") and ph.get("border") == "0px"
              and ph.get("radius") == "12px" and ph.get("label", 0) > 0 and ph.get("below", 0) >= 90
              and ph.get("menu") in ("rgba(0, 0, 0, 0)", "transparent") and neutral(ph.get("dlgBg"))
              and sub.get("subAttr") and all(neutral(sub.get(k)) for k in ("box", "root", "dialog"))
              and sub.get("box") != "rgb(26, 32, 44)" and sub.get("box") == sub.get("dialog"))
        return ok, f"{res}"
    check("Adressbuch: Bearbeiten-Layout auch sofort nach dem Öffnen; Kontaktbild-Dialog mit Hinweis; Unterdialoge auf neutraler Fläche", ab_edit_dialogs, results)

    OPEN_BOOKS_JS = r"""
          tm.openTab("addressBookTab", {});
          const cw = await until(() => { const c = tm.currentTabInfo?.browser?.contentWindow; return c?.document?.getElementById("mcBooksHeader") && c; }, 8000);
          const abTab = tm.currentTabInfo;"""

    def ab_background_header():
        # Adressbuch im Hintergrund: Änderungen an Kontakten (gesammelte Adressen,
        # CardDAV) überschreiben nicht die Kopfzeile über der Mailliste
        res = m.js(MESSAGE_JS + OPEN_BOOKS_JS + r"""
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          const title = () => d.querySelector("#mcListHeader .mc-lh-title")?.textContent;
          await wait(800);
          const abTitle = title();
          await toMail();
          const before = title(); const seen = new Set([before]);
          const iv = w.setInterval(() => seen.add(title()), 20);
          let c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
          c.displayName = "Hinter Grund"; c.primaryEmail = "hinter.grund@example.invalid";
          try {
            c = book.addCard(c); await wait(1500);
            c.setProperty("PopularityIndex", 3); book.modifyCard(c); await wait(1500);
          } finally {
            book.deleteCards([c]); await wait(1500);
            w.clearInterval(iv);
            tm.closeTab(abTab); await toMail();
          }
          return { tab: !!cw, abTitle, before, seen: [...seen] };""")
        ok = res["tab"] and res["before"] and res["abTitle"] != res["before"] and res["seen"] == [res["before"]]
        return ok, f"{res}"
    check("Adressbuch im Hintergrund: Kopfzeile der Mailliste bleibt, wenn sich Kontakte ändern", ab_background_header, results)

    def ab_avatar_recycle():
        # Kontaktzeilen werden beim Scrollen wiederverwendet: lädt das Foto des
        # neuen Kontakts nicht, erscheinen seine Initialen (nicht die des vorigen)
        res = m.js(OPEN_BOOKS_JS + r"""
          const ad = cw.document;
          const el = ad.createElement("contact-avatar"); ad.body.append(el);
          const img = el.shadowRoot.querySelector("img"), letters = el.shadowRoot.querySelector("span");
          const svg = "data:image/svg+xml," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8' fill='red'/></svg>");
          el.setData({ card: { displayName: "Anna Alt", primaryEmail: "anna.alt@example.invalid", photoURL: svg, emailAddresses: [] } });
          const loaded = await until(() => img.complete && img.naturalWidth > 0, 3000);
          el.setData({ card: { displayName: "Ben Neu", primaryEmail: "ben.neu@example.invalid", photoURL: "data:image/png;base64,AAAA", emailAddresses: [] } });
          await until(() => img.hidden, 3000); await wait(200);
          const out = { loaded, hidden: img.hidden, letters: letters.textContent };
          el.remove(); tm.closeTab(abTab); await toMail();
          return out;""")
        return res["loaded"] and res["hidden"] and res["letters"] == "BN", f"{res}"
    check("Adressbuch: wiederverwendete Kontaktzeile zeigt bei defektem Foto die eigenen Initialen", ab_avatar_recycle, results)

    def ab_dedupe_selection():
        # Dubletten, die per Sync dazukommen, werden beim nächsten Sortieren
        # zusammengeführt: die Auswahl bleibt beim gewählten Kontakt statt auf den
        # Nachbarn zu rutschen; fällt die gewählte Dublette weg, ist der verbliebene Eintrag gewählt
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          const add = props => { const c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
            for (const [k, v] of Object.entries(props)) c.setProperty(k, v);
            c.displayName = props.DisplayName; c.primaryEmail = props.PrimaryEmail; return book.addCard(c); };
          const cards = [add({ DisplayName: "Dora Doppel", PrimaryEmail: "dora@example.invalid" }),
                         add({ DisplayName: "Ella Eins", PrimaryEmail: "ella@example.invalid" }),
                         add({ DisplayName: "Zeno Ziel", PrimaryEmail: "zeno@example.invalid" })];
          """ + OPEN_BOOKS_JS + r"""
          const out = { tab: !!cw };
          try {
            const list = cw.document.getElementById("cards");
            const rows = () => [...Array(list.view.rowCount).keys()];
            const sel = () => rows().filter(i => list.view.selection.isSelected(i)).map(i => list.view.getCardFromRow(i)?.UID);
            const pick = test => { list.selectedIndex = rows().find(i => test(list.view.getCardFromRow(i))); };
            // eine Änderung an einem anderen Kontakt sortiert neu (und führt zusammen)
            const touch = async n => { cards[2].setProperty("PopularityIndex", n); book.modifyCard(cards[2]); await wait(800); };
            await until(() => list.view?.rowCount >= 3); await wait(500);
            pick(c => c?.UID == cards[1].UID); await wait(500);
            cards.push(add({ DisplayName: "Dora Doppel", PrimaryEmail: "dora@example.invalid" })); await wait(600);
            const n = list.view.rowCount;
            await touch(2);
            out.neighbor = { merged: list.view.rowCount == n - 1, sel: sel(), want: cards[1].UID };
            pick(c => c?.displayName == "Dora Doppel"); await wait(500);
            cards.push(add({ DisplayName: "Dora Doppel", PrimaryEmail: "dora@example.invalid", Company: "Doppel AG", JobTitle: "Leitung", WorkPhone: "+43 1 555" })); await wait(600);
            await touch(3);
            out.dropped = { merged: list.view.rowCount == n - 1, sel: sel(), want: cards[4].UID, shown: cw.detailsPane?.currentCard?.UID };
          } finally {
            book.deleteCards(cards); await wait(300);
            tm.closeTab(abTab); await toMail();
          }
          return out;""")
        nb, dr = res.get("neighbor", {}), res.get("dropped", {})
        ok = (res["tab"] and nb.get("merged") and nb.get("sel") == [nb.get("want")]
              and dr.get("merged") and dr.get("sel") == [dr.get("want")] and dr.get("shown") == dr.get("want"))
        return ok, f"{res}"
    check("Adressbuch: Zusammenführen von Dubletten lässt die Auswahl beim gewählten Kontakt, Details zeigen den verbliebenen Eintrag", ab_dedupe_selection, results)

    def donate():
        # „Say Thanks“ im Info-Fenster öffnet die Spendenseite (Aufruf abgefangen, kein echter Browser)
        res = m.js('''
          await toMail();
          const orig = w.openLinkExternally; let opened = null;
          w.openLinkExternally = url => { opened = String(url); };
          d.getElementById("mcHaloSpaces").doCommand();
          const hw = await until(() => [...Services.wm.getEnumerator(null)].find(x => x.location?.href.startsWith("resource://mailcards/about/halo.html") && x.document.getElementById("version")?.textContent));
          await wait(500);
          hw?.document.getElementById("donate")?.click(); await wait(300);
          // keine Mailadresse unten – dafür gibt es „Send Feedback“
          const address = /@/.test(hw?.document.body.textContent || "");
          const last = hw?.document.querySelector("main")?.lastElementChild?.getBoundingClientRect();
          const room = last ? Math.round(hw.innerHeight - last.bottom) : null;
          // Kopf: Logo oben mittig, darunter Name, darunter kleinere Version
          const box = sel => hw?.document.querySelector(sel)?.getBoundingClientRect();
          const icon = box(".icon"), h1 = box("h1"), ver = box("#version");
          const mid = r => r ? Math.round(r.left + r.width / 2 - hw.innerWidth / 2) : null;
          const size = sel => parseFloat(hw?.getComputedStyle(hw.document.querySelector(sel)).fontSize);
          const head = icon && h1 && ver ? { offsets: [mid(icon), mid(h1), mid(ver)],
            stacked: icon.bottom <= h1.top && h1.bottom <= ver.top + 1, sizes: [size("h1"), size("#version")] } : null;
          // nicht scrollbar (früher 3 px zu niedrig); Status in deckender Farbe, sonst malt Gecko das Emoji blass
          const overflow = hw ? hw.document.documentElement.scrollHeight - hw.innerHeight : null;
          const status = hw ? hw.getComputedStyle(hw.document.getElementById("emoji-status")).color : null;
          w.openLinkExternally = orig; hw?.close();
          return { window: !!hw, opened, address, room, head, overflow, status };''')
        url = res.get("opened") or ""
        ok = url.startswith("https://buymeacoffee.com/diversion?") and "utm_content=about-window" in url
        head = res.get("head") or {}
        centered = head and all(o is not None and abs(o) <= 2 for o in head["offsets"]) and head["stacked"] and head["sizes"][1] < 12
        # Einstellungsseite (eingebettet, nicht per Marionette erreichbar): Sekundärfarbe ohne Alpha in der Datei
        import re
        opts = open(os.path.join(ROOT, "extension", "options", "options.css")).read()
        opaque = not re.search(r"--text-secondary:\s*rgba", opts) and (res.get("status") or "").startswith("rgb(")
        return (ok and centered and not res["address"] and res["room"] is not None and 16 <= res["room"] <= 22
                and res.get("overflow") is not None and res["overflow"] <= 0 and opaque), f"{res}"
    check("Info-Fenster: Logo, Name und Version mittig untereinander; „Say Thanks“ öffnet die Spendenseite, keine Mailadresse unten; "
          "nicht scrollbar, unten 18 px; Emojis in Status und Hinweisen in voller Farbe", donate, results)

    def addons_manager():
        # Add-ons-Verwaltung (Thunderbird 140+, Bausteine im Schatten-DOM): Seitenleiste 34 px/13 px, Seite und Kopf in
        # --mt-window (dunkel kein #18181B), Suchfeld als Kapsel ohne Rahmen, Werkzeug und „…“ gleich (24 × 24, ohne
        # Fläche), Schalter mit weißem Knopf, Menüs wie halo (12 px, 22-px-Zeilen, Akzent), Detailansicht mit
        # Haarlinien ohne Doppellinie, eingebettete Einstellungen ohne eigene Fläche
        res = m.js(r'''
          w.resizeTo(1500, 900);
          const ID = "mail-cards@sebastian.local";
          w.openAddonsMgr("addons://list/extension");
          const ad = await until(() => { const x = tm.currentTabInfo.browser?.contentDocument; return x?.querySelector(`addon-card[addon-id="${ID}"] .extension-options-button`) && x; }, 8000);
          await wait(800);
          const aw = ad.defaultView; const cs = (e, p) => aw.getComputedStyle(e, p); const R = e => e.getBoundingClientRect();
          const probe = (prop, v) => { const p = ad.createElement("div"); p.style[prop] = v; ad.body.append(p); const c = cs(p)[prop]; p.remove(); return c; };
          const bg = v => probe("backgroundColor", v), fg = v => probe("color", v);
          const out = {};
          const btns = [...ad.querySelectorAll("categories-box moz-page-nav-button")].map(b => b.shadowRoot?.querySelector("a[href], button")).filter(b => b && R(b).height);
          out.nav = btns.map(b => [Math.round(R(b).height), cs(b).fontSize, Math.round(R(b.querySelector(".page-nav-icon") || b).width)]);
          const sel = btns.find(b => b.matches("[selected]"));
          out.navSel = !!sel && cs(sel).backgroundColor == bg("var(--mt-selected-unfocused)");
          const win = bg("var(--mt-window)");
          out.page = [ad.documentElement, ad.querySelector(".sticky-container"), ad.querySelector(".main-search"), ad.querySelector(".main-heading")].map(e => !!e && cs(e).backgroundColor == win);
          const inp = ad.querySelector("search-addons moz-input-search")?.shadowRoot?.querySelector("#input");
          out.search = inp ? [cs(inp).borderTopColor, parseFloat(cs(inp).borderTopLeftRadius), cs(inp).backgroundColor == bg("var(--mt-control)"), Math.round(R(inp).height)] : null;
          const knobs = c => [c.querySelector(".extension-options-button"), c.querySelector(".more-options-button")?.shadowRoot?.querySelector('[part="button"]')]
            .map(b => b ? [Math.round(R(b).width * 2) / 2, Math.round(R(b).height * 2) / 2, cs(b).backgroundColor, cs(b).borderTopLeftRadius] : null);
          const card = ad.querySelector(`addon-card[addon-id="${ID}"]`);
          out.knobs = [knobs(card)];
          const tb = card.querySelector("moz-toggle")?.shadowRoot?.querySelector('button[aria-pressed="true"]');
          out.toggleDot = tb ? cs(tb, "::before").backgroundColor : null;
          out.menus = [];
          for (const [btnSel, listSel] of [[`addon-card[addon-id="${ID}"] .more-options-button`, `addon-card[addon-id="${ID}"] addon-options > panel-list`],
                                           ["addon-page-header .page-options-menu .more-options-button", "addon-page-options > panel-list"]]) {
            ad.querySelector(btnSel).click();
            const pl = await until(() => { const p = ad.querySelector(listSel); return p?.open && R(p).height && p; }, 4000);
            await wait(300);
            if (!pl) { out.menus.push(null); continue; }
            const ib = [...pl.querySelectorAll("panel-item")].find(i => !i.disabled && !i.hidden && R(i).height)?.shadowRoot.querySelector("button");
            InspectorUtils.addPseudoClassLock(ib, ":hover"); const hover = cs(ib).backgroundColor; InspectorUtils.removePseudoClassLock(ib, ":hover");
            const hr = [...pl.querySelectorAll("hr")].find(h => R(h).width);
            const back = cs(pl).backgroundColor.match(/[\d.]+/g).map(Number);
            out.menus.push({ radius: cs(pl).borderTopLeftRadius, border: cs(pl).borderTopWidth, bg: cs(pl).backgroundColor == bg("var(--mt-tooltip-bg)"),
              blue: Math.abs(back[0] - back[2]) > 6, itemRadius: cs(ib).borderTopLeftRadius, itemH: Math.round(R(ib).height),
              hover: hover == bg("var(--mt-accent)"), hr: hr ? cs(hr).borderTopColor == fg("var(--mt-separator)") : null });
            pl.hide(); await wait(300);
          }
          w.openAddonsMgr("addons://detail/" + encodeURIComponent(ID));
          const tg = await until(() => { const t = ad.querySelector("addon-details .tab-group"); return t && R(t).height && t; }, 6000); await wait(800);
          const row = [...ad.querySelectorAll('addon-details section[name="details"] > .addon-detail-row')].find(e => R(e).height > 0);
          out.detail = tg && row ? { tgBottom: cs(tg).borderBottomWidth, gap: Math.round(R(row).top - R(tg).bottom), rowLine: cs(row).borderTopColor == fg("var(--mt-separator)"),
            tgTop: cs(tg).borderTopColor == fg("var(--mt-separator)") } : null;
          out.knobs.push(knobs(ad.querySelector("addon-card")));
          w.openAddonsMgr("addons://detail/" + encodeURIComponent(ID) + "/preferences");
          const br = await until(() => { const b = ad.querySelector("addon-card .addon-inline-options"); return b && R(b).height > 100 && b; }, 8000);
          await wait(1500);
          out.inline = br ? cs(br).backgroundColor : null;
          if (br) {
            // Schnappschuss mit Magenta als Grund: ist die Seite durchsichtig, bleibt der Rand magenta
            const snap = await br.browsingContext.currentWindowGlobal.drawSnapshot(new DOMRect(2, 2, 4, 4), 1, "rgb(255,0,255)");
            const cv = ad.createElement("canvas"); cv.width = snap.width; cv.height = snap.height; const cx = cv.getContext("2d"); cx.drawImage(snap, 0, 0);
            out.inlinePixel = [...cx.getImageData(1, 1, 1, 1).data];
          }
          tm.closeTab(tm.currentTabInfo); await wait(300);
          return out;''')
        nav_ok = len(res["nav"]) >= 4 and all(32 <= h <= 36 and f == "13px" and i == 18 for h, f, i in res["nav"]) and res["navSel"]
        s = res.get("search") or [None, 0, False, 0]
        search_ok = rgba_alpha(s[0]) == 0 and s[1] >= 14 and s[2] and 26 <= s[3] <= 30
        knobs_ok = all(k and all(b and b[0] == 24 and b[1] == 24 and b[2] == "rgba(0, 0, 0, 0)" and b[3] == "50%" for b in k) for k in res["knobs"])
        menus_ok = len(res["menus"]) == 2 and all(mn and mn["radius"] == "12px" and mn["border"] == "0px" and mn["bg"] and not mn["blue"]
                                                   and mn["itemRadius"] == "6px" and mn["itemH"] >= 22 and mn["hover"] and mn["hr"] is not False for mn in res["menus"])
        dt = res.get("detail") or {}
        detail_ok = dt.get("tgBottom") == "0px" and dt.get("gap") is not None and abs(dt["gap"]) <= 1 and dt.get("rowLine") and dt.get("tgTop")
        inline_ok = res.get("inline") == "rgba(0, 0, 0, 0)" and res.get("inlinePixel") == [255, 0, 255, 255]
        ok = nav_ok and all(res["page"]) and search_ok and knobs_ok and res.get("toggleDot") == "rgb(255, 255, 255)" and menus_ok and detail_ok and inline_ok
        return ok, f"{res}"
    check("Add-ons: Seitenleiste 34 px/13 px, Seite und Kopf in Fensterfarbe, Suchfeld als Kapsel, Symbolknöpfe gleich, Schalter weiß, "
          "Menüs wie macOS, Detailansicht mit Haarlinien ohne Doppellinie, Einstellungen ohne eigene Fläche", addons_manager, results)

    def tasks_view():
        # Leeranzeige, iCloud-Platzhalter ausgeblendet, Hinweis neben dem Plus, Kapsel-Knöpfe
        res = m.js(r'''
          w.resizeTo(1500, 900);
          const c = testCalendar();
          tm.openTab("tasks", {}); await wait(2000);
          const tree = d.getElementById("calendar-task-tree"); const empty = d.getElementById("mcTasksEmpty");
          const field = d.getElementById("view-task-edit-field");
          const shown = () => empty && !empty.hidden;
          const out = { emptyAtStart: shown() };
          // Platzhalter, wie iCloud ihn anlegt – darf nicht erscheinen
          const ph = new CalTodo(); ph.title = "Wo sind meine Erinnerungen?"; ph.calendar = c;
          ph.setProperty("DESCRIPTION", "Weitere Infos: https://support.apple.com/HT210220"); const phSaved = await c.addItem(ph);
          await wait(1200);
          out.placeholderRows = tree.mTreeView.rowCount; out.emptyWithPlaceholder = shown();
          const todo = new CalTodo(); todo.title = "Halo Testaufgabe"; todo.calendar = c; const todoSaved = await c.addItem(todo);
          await until(() => tree.mTreeView.rowCount > 0); await wait(300);
          out.rows = tree.mTreeView.rowCount; out.emptyWithTask = shown();
          tree.mTreeView.selection?.select(0); await wait(600);
          const btn = d.getElementById("task-actions-priority"); const cs = w.getComputedStyle(btn);
          out.button = [cs.borderRadius, cs.height];
          // schreibgeschützter Kalender als Standard: Hinweis in der Toolbar-Zeile neben dem Plus
          let ro = cal.manager.getCalendars().find(x => x.name == "Halo Nur Lesen");
          if (!ro) { ro = cal.manager.createCalendar("storage", Services.io.newURI("moz-storage-calendar://")); ro.name = "Halo Nur Lesen"; cal.manager.registerCalendar(ro); ro.readOnly = true; }
          const comp = cal.view.getCompositeCalendar(w); const before = comp.defaultCalendar;
          comp.defaultCalendar = ro; await wait(800);
          const plus = [...d.querySelectorAll("#unifiedToolbarContent > li:not([hidden])")].find(li => li.getBoundingClientRect().width > 30 && !["search-bar", "spacer"].includes(li.getAttribute("item-id")));
          const pr = plus?.getBoundingClientRect(), fr = field.getBoundingClientRect();
          out.hint = { readOnly: field.readOnly, dy: pr ? Math.round((fr.top + fr.height / 2) - (pr.top + pr.height / 2)) : null, dx: pr ? Math.round(fr.left - pr.right) : null };
          comp.defaultCalendar = before; await wait(500);
          for (const it of [phSaved, todoSaved]) { try { await c.deleteItem(it); } catch {} }
          return out;''')
        h = res.get("hint", {})
        ok = (res["emptyAtStart"] and res["placeholderRows"] == 0 and res["emptyWithPlaceholder"] and res["rows"] == 1 and not res["emptyWithTask"]
              and res["button"][0] == "999px" and h.get("readOnly") and h.get("dy") is not None and abs(h["dy"]) <= 3 and 0 <= h["dx"] <= 20)
        return ok, f"{res}"
    check("Aufgaben: Leeranzeige, iCloud-Platzhalter ausgeblendet, Hinweis neben dem Plus, Kapseln", tasks_view, results)

    def tasks_details():
        # Aufgaben: Beschreibung im Detailbereich in Systemschrift 13 px ohne Body-Rand, dunkel hell lesbar (früher schwarz
        # auf #1E1E1E); Spaltenköpfe ohne zweiten Strich aus tree.css; Menüteil von „Erledigt“ als schmaler Pfeil;
        # überfällige Aufgaben rot (--mt-red), Auswahl mit Fokus ohne eckiges Fokusrechteck
        res = m.js(CAL_CHECK_JS + r'''
          w.resizeTo(1500, 900);
          const c = testCalendar();
          tm.openTab("tasks", {}); await pause(1500);
          const { CalTodo } = ChromeUtils.importESModule("resource:///modules/CalTodo.sys.mjs");
          const tree = d.getElementById("calendar-task-tree");
          const todo = new CalTodo(); todo.title = "Halo Detailaufgabe"; todo.calendar = c; todo.priority = 1;
          const due = cal.dtz.now(); due.day -= 2; todo.dueDate = due;
          todo.setProperty("DESCRIPTION", "Halo Notiz"); const saved = await c.addItem(todo);
          const out = { dark };
          // Bildpunkte aus dem Fenster (Bäume malen Zeilen als Pseudo-Elemente – nur so prüfbar)
          const pixels = async r => { const cv = d.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
            cv.width = Math.round(r.width); cv.height = Math.round(r.height); const ctx = cv.getContext("2d");
            try { const bm = await w.browsingContext.currentWindowGlobal.drawSnapshot(new w.DOMRect(r.left, r.top, r.width, r.height), 1, "white"); ctx.drawImage(bm, 0, 0); }
            catch { ctx.drawWindow(w, r.left, r.top, r.width, r.height, "white"); }
            const data = ctx.getImageData(0, 0, cv.width, cv.height).data;
            return (x, y) => { const i = (Math.round(y) * cv.width + Math.round(x)) * 4; return [data[i], data[i + 1], data[i + 2]]; }; };
          try {
            const row = await till(() => { for (let i = 0; i < tree.mTreeView.rowCount; i++) if (tree.mTreeView.getItemAtIndex?.(i)?.title == "Halo Detailaufgabe" || tree.getTaskAtRow?.(i)?.title == "Halo Detailaufgabe") return i + 1; return 0; }, 6000) - 1;
            out.row = row;
            if (row < 0) return out;
            tree.focus(); tree.mTreeView.selection.select(row); await pause(900);
            const frame = d.getElementById("calendar-task-details-description");
            const b = await till(() => { const x = frame.contentDocument?.body; return x && /Halo Notiz/.test(x.textContent) && x; }, 4000);
            if (b) { const cs = frame.contentWindow.getComputedStyle(b); out.desc = { font: cs.fontSize, margin: cs.marginTop, family: cs.fontFamily, color: cs.color }; }
            // Spaltenköpfe
            out.heads = [...d.querySelectorAll("#calendar-task-tree > treecols > treecol")].filter(vis).map(t => csOf(t).boxShadow);
            const pick = d.querySelector("#calendar-task-tree .tree-columnpicker-button");
            out.picker = pick ? csOf(pick).boxShadow : null;
            out.headLine = [csOf(d.querySelector("#calendar-task-tree > treecols")).borderBottomColor, csOf(d.documentElement).getPropertyValue("--mt-pane-line").trim()];
            out.red = csOf(d.documentElement).getPropertyValue("--mt-red").trim();
            // „Erledigt“: Menüteil schmal, Pfeil als Maske
            const cap = d.getElementById("task-actions-markcompleted");
            const dm = cap?.querySelector(".toolbarbutton-menubutton-dropmarker");
            if (dm && vis(dm)) { const a = cap.getBoundingClientRect(), r = dm.getBoundingClientRect();
              out.marker = { w: Math.round(r.width * 10) / 10, mask: csOf(dm).maskImage.slice(0, 12), gap: Math.round((a.right - r.right) * 10) / 10,
                            dy: Math.round(((r.top + r.bottom) - (a.top + a.bottom)) / 2 * 10) / 10 }; }
            // ausgewählt mit Fokus: Zeilenrand links wie die Zeilenfläche daneben (kein Fokusrechteck)
            const tc = tree.querySelector("treechildren"), tr = tc.getBoundingClientRect(), rh = tree.rowHeight || 40;
            const top = tr.top + (row - tree.getFirstVisibleRow()) * rh;
            w.focus(); await till(() => Services.focus.activeWindow == w, 3000); tree.focus(); await pause(400);
            out.focused = Services.focus.activeWindow == w && (d.activeElement == tree || tree.contains(d.activeElement));
            out.rule = /treechildren::-moz-tree-row\(current, focus\)\s*\{\s*outline: none !important/.test(await (await fetch(`resource://mailcards/theme.css`)).text());
            const px1 = await pixels({ left: tr.left, top, width: 12, height: rh });
            out.edge = [px1(0, rh / 2), px1(4, rh / 2), px1(6, 0), px1(6, 3)];
            // ohne Auswahl: Text der überfälligen Zeile rot
            tree.mTreeView.selection.clearSelection(); await pause(600);
            const px2 = await pixels({ left: tr.left, top, width: Math.min(tr.width, 700), height: rh });
            let redPx = 0; for (let x = 0; x < Math.min(tr.width, 700); x++) for (let y = 4; y < rh - 4; y++) { const [r, g, bb] = px2(x, y); if (r > 200 && g < 120 && bb < 120) redPx++; }
            out.redPx = redPx;
          } finally { try { await c.deleteItem(saved); } catch {} }
          return out;''')
        if res.get("row", -1) < 0:
            return False, f"Aufgabe nicht in der Liste {res}"
        desc, mk = res.get("desc") or {}, res.get("marker") or {}
        fam = desc.get("family", "")
        ok_desc = (desc.get("font") == "13px" and desc.get("margin") == "0px" and ("-apple-system" in fam or "system-ui" in fam)
                   and same_color(desc.get("color", ""), "rgb(245, 245, 247)" if res["dark"] else "rgb(29, 29, 31)"))
        ok_head = (len(res["heads"]) >= 3 and all(s == "none" for s in res["heads"]) and res.get("picker") in (None, "none")
                   and same_color(res["headLine"][0], res["headLine"][1]))
        ok_marker = bool(mk) and mk["w"] <= 12 and mk["mask"].startswith("url(") and 8 <= mk["gap"] <= 16 and abs(mk["dy"]) <= 1.5
        e = res.get("edge") or []
        diff = lambda a, b: max(abs(x - y) for x, y in zip(a, b))
        # Rand nur mit fokussiertem Fenster sichtbar (parallele Läufe nehmen den Fokus) – sonst nur die Regel prüfen
        ok_focus = res.get("rule") and (not res.get("focused") or (len(e) == 4 and diff(e[0], e[1]) <= 12 and diff(e[2], e[3]) <= 12))
        ok_red = res.get("red", "").upper() == ("#FF6961" if res["dark"] else "#FF3B30") and res.get("redPx", 0) >= 10
        ok = ok_desc and ok_head and ok_marker and ok_focus and ok_red
        return ok, f"desc={ok_desc} kopf={ok_head} pfeil={ok_marker} fokus={ok_focus} rot={ok_red} {res}"
    check("Aufgaben: Beschreibung 13 px ohne Rand und dunkel lesbar, Spaltenköpfe ohne zweiten Strich, „Erledigt“ mit schmalem Pfeil, überfällig rot, kein Fokusrechteck", tasks_details, results)

    def tasks_list_states():
        # erledigte Aufgaben aufrecht (Thunderbird: kursiv) mit Kreis in der Systemakzentfarbe statt fest #007AFF;
        # ohne Auswahl kein Teiler über der Statusleiste (früher zwei Haarlinien); Leeranzeige bei Suche ohne Treffer
        # „No Results“ statt „No Tasks“; Kalenderliste im niedrigen Fenster ≥ 3 Zeilen, Monatskalender weicht
        res = m.js(CAL_CHECK_JS + r"""
          w.resizeTo(1500, 900);
          const c = testCalendar();
          tm.openTab("tasks", {}); await pause(1500);
          const { CalTodo } = ChromeUtils.importESModule("resource:///modules/CalTodo.sys.mjs");
          const tree = d.getElementById("calendar-task-tree");
          const out = {};
          const theme = await (await fetch("resource://mailcards/theme.css")).text();
          const ruleOf = sel => { const i = theme.indexOf(sel + " {"); return i < 0 ? "" : theme.slice(i, theme.indexOf("}", i)); };
          out.italic = /font-style: normal !important/.test(ruleOf(".calendar-task-tree treechildren::-moz-tree-cell-text(completed)"));
          const doneRule = ruleOf(".calendar-task-tree > treechildren::-moz-tree-image(calendar-task-tree-col-completed, completed)");
          out.doneRule = !/007AFF/i.test(doneRule) && doneRule.includes("resource://mailcards/icons/task-done.svg") && /fill: var\(--mt-accent\)/.test(doneRule);
          out.svg = /context-fill/.test(await (await fetch("resource://mailcards/icons/task-done.svg")).text());
          const pixels = async r => { const cv = d.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
            cv.width = Math.round(r.width); cv.height = Math.round(r.height); const ctx = cv.getContext("2d");
            try { const bm = await w.browsingContext.currentWindowGlobal.drawSnapshot(new w.DOMRect(r.left, r.top, r.width, r.height), 1, "white"); ctx.drawImage(bm, 0, 0); }
            catch { ctx.drawWindow(w, r.left, r.top, r.width, r.height, "white"); }
            const data = ctx.getImageData(0, 0, cv.width, cv.height).data;
            return (x, y) => { const i = (Math.round(y) * cv.width + Math.round(x)) * 4; return [data[i], data[i + 1], data[i + 2]]; }; };
          const todo = new CalTodo(); todo.title = "Halo Erledigt"; todo.calendar = c;
          const saved = await c.addItem(todo);
          const done = saved.clone(); done.isCompleted = true; const savedDone = await c.modifyItem(done, saved);
          const prevAccent = Services.prefs.getStringPref("ui.accentcolor", "");
          const comp = cal.view.getCompositeCalendar(w), prevDefault = comp.defaultCalendar;
          try {
            // Filter „Alle“, damit die erledigte Aufgabe in der Liste steht
            d.getElementById("opt_all_filter")?.click(); await pause(800);
            const row = await till(() => { for (let i = 0; i < tree.mTreeView.rowCount; i++) if (tree.getTaskAtRow?.(i)?.title == "Halo Erledigt") return i + 1; return 0; }, 6000) - 1;
            out.row = row;
            if (row >= 0) {
              // andere Akzentfarbe (Rosa) – der Kreis muss ihr folgen
              Services.prefs.setStringPref("ui.accentcolor", "#FF2D55"); await pause(800);
              out.accent = colorOf(d, "AccentColor");
              tree.mTreeView.selection.clearSelection(); tree.ensureRowIsVisible(row); await pause(500);
              const col = tree.columns.getNamedColumn("calendar-task-tree-col-completed");
              const tc = tree.querySelector("treechildren").getBoundingClientRect();
              const cr = tree.getCoordsForCellItem(row, col, "image");
              out.cell = [Math.round(cr.x), Math.round(cr.y), Math.round(cr.width), Math.round(cr.height)];
              const px = await pixels({ left: tc.left, top: tc.top + (row - tree.getFirstVisibleRow()) * (tree.rowHeight || 40), width: 120, height: tree.rowHeight || 40 });
              // kräftigstes Pixel im Kästchenbereich (weißer Haken ausgenommen)
              let best = null, sat = -1;
              for (let x = 0; x < 120; x++) for (let y = 0; y < (tree.rowHeight || 40); y++) { const p = px(x, y); const s = Math.max(...p) - Math.min(...p); if (s > sat) { sat = s; best = p; } }
              out.circle = best;
            }
            // ohne Auswahl kein Teiler, mit Auswahl Teiler und Details sichtbar
            tree.mTreeView.selection.clearSelection(); await pause(500);
            const sp = d.getElementById("calendar-task-view-splitter"), det = d.getElementById("calendar-task-details-container");
            out.splitNone = csOf(sp).display;
            if (row >= 0) { tree.mTreeView.selection.select(row); await pause(600); }
            out.splitSel = [csOf(sp).display, vis(det)];
            // Suche ohne Treffer
            const f = d.getElementById("task-text-filter-field"), box = d.getElementById("mcTasksEmpty");
            f.value = "xyzxyz"; f.dispatchEvent(new w.Event("input", { bubbles: true })); f.dispatchEvent(new w.Event("command"));
            await till(() => tree.mTreeView.rowCount == 0, 4000); await pause(400);
            out.search = [tree.mTreeView.rowCount, !box.hidden, box.querySelector(".mc-te-title")?.textContent, box.querySelector(".mc-te-text")?.textContent];
            f.value = ""; f.dispatchEvent(new w.Event("input", { bubbles: true })); f.dispatchEvent(new w.Event("command"));
            await till(() => tree.mTreeView.rowCount > 0, 4000); await pause(400);
            out.cleared = [tree.mTreeView.rowCount, box.hidden, box.querySelector(".mc-te-title")?.textContent];
            // Filter „Überfällig“ ohne Treffer: kein Versprechen „Tasks you add appear here.“ (dort erscheinen sie nicht);
            // Filter „Offen“ ohne Treffer (nur die erledigte Aufgabe): wieder der Normaltext
            // beschreibbarer Standardkalender, sonst gilt „No Task List Selected“ vorrangig
            comp.defaultCalendar = c; w.taskEdit?.callOnBlurForAllTaskFields(); await pause(300);
            d.getElementById("opt_overdue_filter")?.click();
            await till(() => tree.mTreeView.rowCount == 0, 4000); await pause(500);
            out.overdue = [tree.mTreeView.rowCount, !box.hidden, box.querySelector(".mc-te-title")?.textContent, box.querySelector(".mc-te-text")?.textContent];
            d.getElementById("opt_open_filter")?.click();
            await till(() => tree.mTreeView.rowCount == 0 && tree.getAttribute("filterValue") == "open", 4000); await pause(500);
            out.open = [tree.mTreeView.rowCount, !box.hidden, box.querySelector(".mc-te-text")?.textContent];
            d.getElementById("opt_all_filter")?.click(); await till(() => tree.mTreeView.rowCount > 0, 4000); await pause(300);
            // niedriges Fenster: Kalenderliste mindestens drei Zeilen, Monatskalender ausgeblendet oder ganz darunter
            w.resizeTo(1136, 700); await pause(1000);
            const list = d.getElementById("calendar-list"), mm = d.getElementById("minimonth-pane");
            const lr = list.getBoundingClientRect(), mr = mm.getBoundingClientRect();
            out.low = { h: list.clientHeight, mm: csOf(mm).display, mmTop: Math.round(mr.top), mmBottom: Math.round(mr.bottom), listBottom: Math.round(lr.bottom), win: w.innerHeight };
            w.resizeTo(1500, 900); await pause(1000);
            out.high = { mm: csOf(mm).display, vis: vis(mm), h: list.clientHeight };
          } finally {
            if (prevAccent) Services.prefs.setStringPref("ui.accentcolor", prevAccent); else Services.prefs.clearUserPref("ui.accentcolor");
            d.getElementById("opt_throughcurrent_filter")?.click();
            if (prevDefault) { comp.defaultCalendar = prevDefault; w.taskEdit?.callOnBlurForAllTaskFields(); }
            w.resizeTo(1500, 900);
            try { await c.deleteItem(savedDone); } catch {}
          }
          return out;""")
        if res.get("row", -1) < 0:
            return False, f"erledigte Aufgabe nicht in der Liste {res}"
        ci = res.get("circle") or [0, 0, 0]
        ok_static = res.get("italic") and res.get("doneRule") and res.get("svg")
        # Rosa (#FF2D55) dominiert: Rot deutlich vor Blau und Grün
        ok_circle = ci[0] > 180 and ci[0] - ci[2] > 60 and ci[0] - ci[1] > 100
        ok_split = res.get("splitNone") == "none" and res["splitSel"][0] != "none" and res["splitSel"][1]
        se, cl = res.get("search") or [], res.get("cleared") or []
        ok_search = len(se) == 4 and se[0] == 0 and se[1] and se[2] == "No Results" and se[3] == "No tasks match your search." and cl[0] > 0 and cl[1]
        ov, op = res.get("overdue") or [], res.get("open") or []
        ok_filter = (len(ov) == 4 and ov[0] == 0 and ov[1] and ov[2] == "No Tasks" and ov[3] == "No tasks in this view."
                     and len(op) == 3 and op[0] == 0 and op[1] and op[2] == "Tasks you add appear here.")
        lo, hi = res.get("low") or {}, res.get("high") or {}
        ok_low = lo.get("h", 0) >= 90 and (lo.get("mm") == "none" or lo["mmTop"] >= lo["listBottom"]) and hi.get("mm") != "none" and hi.get("vis")
        ok = bool(ok_static and ok_circle and ok_split and ok_search and ok_filter and ok_low)
        return ok, f"statisch={ok_static} kreis={ok_circle} teiler={ok_split} suche={ok_search} filter={ok_filter} niedrig={ok_low} {res}"
    check("Aufgaben: erledigt aufrecht mit Kreis in Akzentfarbe, ohne Auswahl kein Teiler, „No Results“ bei Suche, Leeranzeige je Filter, Kalenderliste im niedrigen Fenster", tasks_list_states, results)

    def tasks_hint():
        # Eingabehinweis bleibt grau, auch wenn Thunderbird ihn ohne focus/blur neu setzt (Wechsel des Standardkalenders);
        # Hinweis „schreibgeschützter Kalender“ im schmalen Fenster endet vor dem Suchfeld (früher über Lupe und „Search“)
        res = m.js(CAL_CHECK_JS + r'''
          w.resizeTo(1500, 900);
          tm.openTab("tasks", {}); await pause(1500);
          const field = d.getElementById("view-task-edit-field"), tree = d.getElementById("calendar-task-tree");
          let ro = cal.manager.getCalendars().find(x => x.name == "Halo Nur Lesen");
          if (!ro) { ro = cal.manager.createCalendar("storage", Services.io.newURI("moz-storage-calendar://")); ro.name = "Halo Nur Lesen"; cal.manager.registerCalendar(ro); ro.readOnly = true; }
          const comp = cal.view.getCompositeCalendar(w); const before = comp.defaultCalendar;
          const out = {};
          try {
            tree.focus(); field.removeAttribute("mc-hint");
            comp.defaultCalendar = ro; await pause(500);
            comp.defaultCalendar = testCalendar(); await pause(600);
            out.hint = { shows: field.showsInstructions, attr: field.hasAttribute("mc-hint"), color: csOf(field).color,
                         tertiary: colorOf(d, "var(--mt-text-tertiary)"), focused: d.activeElement == field };
            w.resizeTo(1136, 760); await pause(900);
            comp.defaultCalendar = ro; await pause(900);
            const sb = d.querySelector('#unifiedToolbarContent > li[item-id="search-bar"]:not([hidden])')?.getBoundingClientRect();
            const fr = field.getBoundingClientRect();
            out.narrow = { readOnly: field.readOnly, right: Math.round(fr.right), search: sb?.width ? Math.round(sb.left) : null, width: Math.round(fr.width) };
          } finally { comp.defaultCalendar = before; w.resizeTo(1500, 900); await pause(800); }
          return out;''')
        h, n = res.get("hint", {}), res.get("narrow", {})
        ok_hint = h.get("shows") and h.get("attr") and same_color(h.get("color", ""), h.get("tertiary", "x"))
        ok_narrow = n.get("readOnly") and n.get("search") is not None and n["right"] <= n["search"] - 8 and n["width"] > 40
        return bool(ok_hint and ok_narrow), f"{res}"
    check("Aufgaben: Eingabehinweis grau auch nach Kalenderwechsel, Hinweis „schreibgeschützt“ im schmalen Fenster vor dem Suchfeld", tasks_hint, results)

    def task_dialog():
        # Aufgaben-Dialog (calendar-task-dialog-inner) im selben Stil wie der Termin-Dialog: Felder grau ohne Rahmen, 32 px,
        # Fläche --mt-window; Haken aus chrome:// (CSP sperrt data:); Zeitkopplung als Kettensymbol aus chrome:// ohne
        # alte untere Klammer „↵“; Trennlinien als Haarlinie – Klammer und Kette auch im Termin-Dialog
        res = m.js(CAL_CHECK_JS + r'''
          const others = () => [...Services.wm.getEnumerator(null)].filter(x => !x.closed && !x.location.href.includes("messenger.xhtml"));
          for (const x of others()) x.close();
          await till(() => !others().length, 4000);
          const out = { dark };
          // nur ein neu geöffnetes Fenster (ein eben geschlossenes kann noch in der Liste stehen)
          const inner = async (open, ready) => {
            const before = new Set(Services.wm.getEnumerator(null));
            open();
            const dw = await till(() => [...Services.wm.getEnumerator(null)].find(x => !before.has(x) && !x.closed && x.location.href.includes("calendar-event-dialog.xhtml") && x.document.readyState == "complete"), 10000);
            if (!dw) return null;
            const iw = await till(() => { const f = dw.document.getElementById("calendar-item-panel-iframe")?.contentWindow;
              return f?.document.readyState == "complete" && f.document.getElementById(ready) && f; }, 8000);
            await pause(1200); return [dw, iw ? dw.document.getElementById("calendar-item-panel-iframe").contentDocument : null];
          };
          const link = id => { const kb = id.getElementById("keepduration-button"), lb = id.getElementById("link-image-bottom");
            const st = kb ? csOf(kb, "::before") : null;
            const kr = kb?.getBoundingClientRect(), sr = id.getElementById("event-grid-startdate-row")?.getBoundingClientRect();
            return { bottom: lb ? csOf(lb).display : null, bg: st ? st.backgroundImage.slice(0, 45) : null, mask: st?.maskImage, w: st?.width,
                     mid: kr && sr ? Math.round(((kr.top + kr.bottom) / 2 - sr.bottom) * 10) / 10 : null }; };
          // Beschreibung ganz im Fenster (früher im Aufgaben-Fenster unten abgeschnitten); Zahlenfeld ohne Pfeile
          const fits = id => { const e = id.getElementById("item-description"); const r = e?.getBoundingClientRect();
            return r ? [Math.round(r.bottom), Math.round(id.body.getBoundingClientRect().bottom), Math.round(r.height)] : null; };
          let dw = null;
          try {
            await toCalendar();
            let r = await inner(() => w.createTodoWithDialog(testCalendar(), null, "Halo Aufgabendialog"), "todo-has-duedate");
            if (!r || !r[1]) return { dialog: false };
            [dw] = r; const id = r[1];
            out.id = id.documentElement.id;
            const t = id.getElementById("item-title"), pc = id.getElementById("percent-complete-textbox"), cat = id.getElementById("item-categories");
            // Thunderbird setzt den Fokus ins Titelfeld – fokussiert ist es gewollt weiß (unter macOS ist das Testfenster meist nicht vorn)
            if (t.matches(":focus")) { t.blur(); await pause(200); }
            out.title = { border: csOf(t).borderTopStyle, h: csOf(t).height, bg: csOf(t).backgroundColor, cat: cat ? csOf(cat).backgroundColor : null };
            out.percent = pc ? { h: Math.round(pc.getBoundingClientRect().height), border: csOf(pc).borderTopStyle } : null;
            out.bg = [csOf(id.documentElement).backgroundColor, colorOf(id, "var(--mt-window)", "backgroundColor")];
            const cb = id.getElementById("todo-has-duedate"); cb.checked = true; await pause(300);
            const ck = cb.querySelector(".checkbox-check");
            out.check = ck ? [csOf(ck).backgroundImage.slice(0, 20), csOf(ck).backgroundColor] : null;
            out.taskLink = link(id); out.taskDesc = fits(id); out.spin = pc ? csOf(pc).appearance : null;
            out.seps = [...id.querySelectorAll("tr.separator > td")].filter(vis).map(td => [csOf(td).borderBottomColor, csOf(td).borderBottomWidth]);
            dw.close(); await till(() => dw.closed, 4000);
            r = await inner(() => w.createEventWithDialog(testCalendar(), null, null, "Halo Termindialog Kette"), "event-all-day");
            if (r && r[1]) { [dw] = r; const ed = r[1]; const ad = ed.getElementById("event-all-day"); ad.checked = true; await pause(300);
              const ac = ad.querySelector(".checkbox-check"); out.eventCheck = ac ? csOf(ac).backgroundImage.slice(0, 20) : null; ad.checked = false;
              out.eventLink = link(ed); out.eventDesc = fits(ed); }
          } finally { if (dw && !dw.closed) { dw.close(); await till(() => dw.closed, 4000); } }
          return out;''')
        if res.get("dialog") is False:
            return False, "Aufgaben-Dialog nicht offen"
        t, p, bg = res.get("title") or {}, res.get("percent") or {}, res.get("bg") or ["", "x"]
        lk = lambda x: (bool(x) and x["bottom"] == "none" and (x["bg"] or "").startswith('url("chrome://global/skin/icons/link.svg') and x["mask"] == "none"
                        and x["w"] == "16px" and x["mid"] is not None and abs(x["mid"]) <= 2)
        fit = lambda x: bool(x) and x[0] <= x[1] - 4 and x[2] >= 40
        seps = res.get("seps") or []
        ok = (res.get("id") == "calendar-task-dialog-inner" and t.get("border") == "none" and t.get("h") == "32px" and same_color(t.get("bg", ""), t.get("cat") or "x")
              and p.get("h") == 32 and p.get("border") == "none" and same_color(bg[0], bg[1])
              and res.get("check") and res["check"][0].startswith('url("chrome://') and rgba_alpha(res["check"][1]) > 0
              and (res.get("eventCheck") or "").startswith('url("chrome://')
              and lk(res.get("taskLink")) and lk(res.get("eventLink")) and fit(res.get("taskDesc")) and fit(res.get("eventDesc"))
              and res.get("spin") == "textfield"
              and len(seps) >= 2 and all(rgba_alpha(c) <= 0.12 and float(wd[:-2]) <= 1 for c, wd in seps))
        return ok, f"{res}"
    check("Aufgaben-Dialog: Felder und Fläche wie im Termin-Dialog, Haken sichtbar, Kettensymbol ohne alte Klammer (auch Termin-Dialog), Trennlinien als Haarlinie", task_dialog, results)

    def month_spans():
        # mehrtägige ganztägige Termine als durchgehender Balken; Titel läuft über alle Stücke weiter (früher nach
        # einer Spalte „Konferenz in Wi…“); Kalendersymbol ohne Emoji
        res = m.js(r'''
          w.resizeTo(1500, 900);
          const c = testCalendar();
          const mk = async (title, dd, days) => { const e = new CalEvent(); e.title = title; e.calendar = c;
            const s = cal.createDateTime(); s.resetTo(2026, 9, dd, 0, 0, 0, cal.dtz.floating); s.isDate = true; const en = s.clone(); en.day += days;
            e.startDate = s; e.endDate = en; return await c.addItem(e); };
          const made = [await mk("Halo Mehrtagig Konferenz in Wien", 23, 4), await mk("Qwrtz Abgabe", 27, 1)];
          await toCalendar(); w.switchToView("month"); w.currentView().goToDay(cal.createDateTime("20261015")); await wait(1500);
          const all = [...d.querySelectorAll("calendar-month-day-box-item")];
          const parts = all.filter(e => e.occurrence?.title == "Halo Mehrtagig Konferenz in Wien").map(e => { const b = e.getBoundingClientRect();
            const lab = e.querySelector(".event-name-label"), cs = w.getComputedStyle(lab);
            return { l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top), jl: e.hasAttribute("data-mc-join-l"), jr: e.hasAttribute("data-mc-join-r"),
                     ll: Math.round(lab.getBoundingClientRect().left * 10) / 10, vis: cs.visibility, indent: parseFloat(cs.textIndent), ov: cs.textOverflow }; });
          const plain = all.find(e => e.occurrence?.title == "Qwrtz Abgabe")?.querySelector(".event-name-label");
          const icon = plain ? w.getComputedStyle(plain, "::before").maskImage : null;
          for (const e of made) { try { await c.deleteItem(e); } catch {} }
          return { parts, icon: (icon || "").slice(0, 20), emoji: plain?.getAttribute("data-mc-emoji") };''')
        p = res["parts"]
        # Fr–Mo über einen Wochenwechsel: je Zeile zusammenhängend, an den Zeilenenden
        # gerundet – wo die Zeile umbricht, hängt vom Wochenbeginn ab (Mo bzw. So unter en-US)
        rows = [sorted((q for q in p if q["t"] == t), key=lambda q: q["l"]) for t in sorted({q["t"] for q in p})]
        joined = len(p) == 4 and len(rows) == 2 and all(
            not r[0]["jl"] and not r[-1]["jr"]
            and all(abs(r[i + 1]["l"] - r[i]["r"]) <= 2 and r[i]["jr"] and r[i + 1]["jl"] for i in range(len(r) - 1))
            for r in rows)
        # Folgestücke: Titel sichtbar, um den Abstand zum ersten Stück eingerückt; Stücke mit Fortsetzung schneiden ohne „…“
        flow = joined and all(
            all(q["vis"] == "visible" and abs(q["indent"] + (q["ll"] - r[0]["ll"])) <= 1 for q in r[1:])
            and all(q["ov"] == "clip" for q in r[:-1])
            for r in rows)
        return joined and flow and res["icon"].startswith("url(") and not res["emoji"], f"{res}"
    check("Kalender: mehrtägige Termine als Balken, Titel läuft über alle Stücke weiter, Kalendersymbol ohne Emoji", month_spans, results)

    def month_more():
        # volle Tage zeigen „+N weitere“ – danach bleibt die Ansicht ruhig (früher setzte
        # update() den Text in jedem Bild neu und lief so endlos, Dauerlast auf der CPU)
        res = m.js(r'''
          w.resizeTo(1500, 900);
          const c = testCalendar(); const made = [];
          for (let i = 0; i < 9; i++) { const e = new CalEvent(); e.title = "Halo Voll " + i; e.calendar = c;
            const s = cal.createDateTime(); s.resetTo(2026, 9, 14, 8 + i, 0, 0, cal.dtz.defaultTimezone); const en = s.clone(); en.hour += 1;
            e.startDate = s; e.endDate = en; made.push(await c.addItem(e)); }
          await toCalendar(); w.switchToView("month"); w.currentView().goToDay(cal.createDateTime("20261014"));
          const more = await until(() => d.querySelector("#month-view .mc-more"));
          let changes = null;
          if (more) {
            await wait(600); changes = 0;
            const mo = new w.MutationObserver(rs => { changes += rs.filter(r => (r.target.closest ? r.target : r.target.parentElement)?.closest(".mc-more")).length; });
            mo.observe(d.getElementById("month-view"), { childList: true, subtree: true, characterData: true });
            await wait(1500); mo.disconnect();
          }
          const text = more?.textContent;
          // der volle Tag rollt nicht selbst (ab Thunderbird 159 liegt die Liste in
          // einem eigenen Rollbereich, den macOS sonst ans Mausrad bindet)
          const day = d.querySelector("#month-view calendar-month-day-box[mc-has-more]");
          const scroll = day && w.getComputedStyle(day.querySelector(".calendar-month-day-box-scroll") || day.querySelector(".calendar-month-day-box-list")).overflowY;
          for (const e of made) { try { await c.deleteItem(e); } catch {} }
          return { text, changes, scroll, visibility: d.visibilityState };''')
        if res["text"] is None and res["visibility"] == "hidden":
            return True, f"Testfenster verdeckt – übersprungen {res}"
        return (bool(res["text"]) and res["text"].startswith("+") and res["changes"] == 0
                and res["scroll"] == "hidden"), f"{res}"
    check("Kalender: „+N weitere“ in der Monatsansicht ohne Endlosschleife, volle Tage rollen nicht", month_more, results)

    def mail_search():
        # Suchfeld oben: alle Postfächer, Datum („12.10“), Trefferzahl, gelbe Markierung, zurück beim Leeren
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Suchtest")) { root.createSubfolder("Suchtest", null); await wait(800); }
          const f = root.getChildNamed("Suchtest"); const lf = f.QueryInterface(Ci.nsIMsgLocalMailFolder);
          const mail = (n, date, subject, body) => `From: Shop <shop@example.invalid>\r\nTo: Halo <h@example.invalid>\r\nSubject: ${subject}\r\nDate: ${date}\r\nMessage-ID: <halo-search-${n}@example.invalid>\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n${body}\r\n`;
          if (!f.getTotalMessages(false)) {
            lf.addMessage(mail(1, "Thu, 15 Oct 2026 16:30:00 +0200", "Versendet: Paket", "Lieferung am 12.10 erfolgt, danke."));
            lf.addMessage(mail(2, "Mon, 12 Oct 2026 09:00:00 +0200", "Rechnung Oktober", "Ihre Rechnung."));
            lf.addMessage(mail(3, "Tue, 13 Oct 2026 09:00:00 +0200", "Ganz anderes Thema", "Nichts zu sehen."));
            await wait(1000);
          }
          const a3 = await toMail(); a3.displayFolder(f.URI); await wait(1000);
          const bar = d.querySelector("#unifiedToolbarContent global-search-bar");
          const fire = (type, text) => bar.dispatchEvent(new CustomEvent(type, { detail: text, cancelable: true }));
          const header = () => d.querySelector("#mcListHeader .mc-lh-count")?.textContent;
          const subjects = () => { const v = a3.gDBView; const r = []; for (let i = 0; i < (v?.rowCount || 0); i++) r.push(v.getMsgHdrAt(i).subject); return r.sort(); };
          const out = {};
          fire("search", "12.10"); await until(() => a3.gDBView?.rowCount >= 2, 6000); await wait(500);
          out.date = subjects(); out.count = header();
          fire("search", "rechnung"); await until(() => a3.gDBView?.rowCount == 1, 6000); await wait(800);
          out.text = subjects();
          out.marks = [...a3.document.querySelectorAll('#threadTree tr[is="thread-card"] mark.mc-hit')].map(e => e.textContent);
          out.visible = (() => { const row = a3.folderPane?.getRowForFolder?.(a3.gFolder.URI); return row ? Math.round(row.getBoundingClientRect().height) : 0; })();
          fire("autocomplete", ""); await wait(1500);
          out.back = a3.gFolder?.name; out.marksAfter = a3.document.querySelectorAll("mark.mc-hit").length;
          return out;""")
        ok = (res["date"] == ["Rechnung Oktober", "Versendet: Paket"] and "2" in (res["count"] or "")
              and res["text"] == ["Rechnung Oktober"] and res["visible"] == 0 and res["back"] == "Suchtest" and not res["marksAfter"])
        # Markierung braucht gezeichnete Karten (verdecktes Testfenster: übersprungen)
        visible = m.js("return d.visibilityState;") == "visible"
        if visible:
            ok = ok and any(t.lower() == "rechnung" for t in res["marks"])
        return ok, f"{res}"
    check("Suche: alle Postfächer, Datum, Trefferzahl, Markierung, zurück zum Ordner", mail_search, results)

    def search_placeholder():
        # Suchfeld oben: Platzhalter je Bereich steht im eigenen <span slot="placeholder">
        # (das placeholder-Attribut wäre unsichtbar) und in der Sprache der Oberfläche;
        # Überschrift über der Adressbuchliste und Today-Pane-Titel ebenso übersetzt
        res = m.js(r'''
          const before = new Set(tm.tabInfo);
          const bar = d.querySelector("#unifiedToolbarContent global-search-bar");
          const ph = () => bar?.querySelector('[slot="placeholder"]');
          const text = () => ph()?.textContent;
          const out = { locale: Services.locale.appLocaleAsBCP47, attr: null };
          const step = async (key, open, expectChange = true) => {
            const prev = text(); await open();
            out[key] = await until(() => (!expectChange || text() != prev) && text(), 4000) || text();
          };
          await toMail(); await wait(300); out.mail = text();
          out.slotted = !!ph()?.assignedSlot; out.l10n = !!ph()?.hasAttribute("data-l10n-id");
          // zu langer Platzhalter endet mit „…“ im Feld statt darüber hinaus
          const box = bar?.shadowRoot?.querySelector("div")?.getBoundingClientRect();
          out.ellipsis = ph() && [w.getComputedStyle(ph()).textOverflow, Math.round(ph().getBoundingClientRect().width) <= Math.round(box?.width || 0)];
          await step("calendar", () => toCalendar());
          await step("tasks", async () => { tm.openTab("tasks", {}); await wait(1500); });
          await step("addressbook", async () => { tm.openTab("addressBookTab", {}); await wait(1500); });
          // Dokument bei jedem Versuch neu lesen: unter Last ist nach 1,5 s noch das leere Startdokument geladen
          out.books = (await until(() => tm.currentTabInfo.browser?.contentDocument?.getElementById("mcBooksHeader"), 8000))?.textContent;
          await step("settings", async () => { w.openPreferencesTab(); await wait(1500); });
          out.attr = bar?.getAttribute("placeholder");
          out.today = [d.getElementById("mcTodayTitle")?.textContent, d.getElementById("today-pane-header")?.dataset.mcTitle];
          for (const t of [...tm.tabInfo]) { if (!before.has(t)) tm.closeTab(t); }
          await toMail(); await wait(300); out.back = text();
          return out;''')
        expect = {
            "de": ["Alle Postfächer durchsuchen", "Suchen", "Aufgaben durchsuchen", "Kontakte durchsuchen",
                   "Einstellungen durchsuchen", "Adressbücher", "Heute-Leiste"],
            "en": ["Search All Mailboxes", "Search", "Search Tasks", "Search Contacts", "Find in Settings",
                   "Address Books", "Today Pane"],
        }.get(res["locale"].split("-")[0])
        got = [res["mail"], res["calendar"], res["tasks"], res["addressbook"], res["settings"], res["books"]]
        ok = (res["slotted"] and not res["l10n"] and not res["attr"] and res["back"] == res["mail"]
              and res["ellipsis"] == ["ellipsis", True])
        if expect:
            ok = ok and got == expect[:6] and all(t in (None, expect[6]) for t in res["today"]) and expect[6] in res["today"]
        else:  # andere Sprache: Thunderbirds eigener Platzhalter, nur Überschrift prüfen
            ok = bool(res["books"])
        return ok, f"{res}"
    check("Suche: Platzhalter je Bereich sichtbar und übersetzt, Überschrift „Adressbücher“, Today-Pane-Titel", search_placeholder, results)

    def settings_style():
        # Einstellungen: Inhalt mittig (max. 800 px), Kästchen/Optionsfelder im macOS-Stil,
        # Zahlenfeld ohne Systempfeile, Ansichtskacheln ohne Optionsfeld, Kontoeinstellungen als Karten
        res = m.js(r'''
          w.resizeTo(1500, 950); w.openPreferencesTab("paneAppearance"); await wait(2500);
          const cw = tm.currentTabInfo.browser.contentWindow; const cd = cw.document; const cs = e => cw.getComputedStyle(e);
          const deck = cd.querySelector(".paneDeckContainer").getBoundingClientRect();
          const box = cd.getElementById("preferencesContainer").getBoundingClientRect();
          const checked = [...cd.querySelectorAll("#paneDeck checkbox[checked]")].find(c => c.getBoundingClientRect().width)?.querySelector(".checkbox-check");
          const radio = cd.querySelector("#paneDeck radio:not(.appearance-options radio) .radio-check");
          const tileCheck = cd.querySelector("#appearanceStyleCards .radio-check");
          // verschachtelte Unterüberschriften („Card view options“, „Display width“) wie der Kartentitel 13 px
          const legends = [...new Set([...cd.querySelectorAll("#paneDeck legend")].map(l => cs(l).fontSize))];
          cw.gotoPref("paneChat"); await wait(1200);
          const num = cd.querySelector("#paneDeck input[type=number]");
          const out = { width: Math.round(deck.width), offset: Math.round((deck.left - box.left) - (box.right - deck.right)),
            checkbox: checked ? [cs(checked).appearance, cs(checked).borderTopLeftRadius] : null,
            radio: radio ? [cs(radio).appearance, cs(radio).borderTopLeftRadius] : null,
            tileCheck: tileCheck ? cs(tileCheck).display : null, number: num ? cs(num).appearance : null, legends };
          // Zahlenfeld ohne macOS-Feldrahmen: dieselbe Haarlinie und Fläche wie die Textfelder
          const txt = [...cd.querySelectorAll("#paneDeck input[type=text]")][0];
          out.numberLook = num && txt ? [cs(num).borderTopColor == cs(txt).borderTopColor,
            cs(num).backgroundColor == cs(cd.getElementById("preferencesContainer")).backgroundColor] : null;
          tm.closeTab(tm.currentTabInfo);
          w.MsgAccountManager(null);
          // je nach Konto die Liste (Ausgangsserver) oder ein Eingabefeld (Kontoseite)
          const el = await until(() => tm.currentTabInfo.browser?.contentDocument?.getElementById("contentFrame")?.contentDocument
            ?.querySelector("#containerBox richlistbox, #containerBox input:is([type=text], :not([type]))"), 8000);
          out.accountList = el ? [el.localName, el.ownerDocument.defaultView.getComputedStyle(el).borderTopLeftRadius] : null;
          tm.closeTab(tm.currentTabInfo);
          return out;''')
        ok = (res["width"] <= 800 and abs(res["offset"]) <= 4 and res["checkbox"] == ["none", "4px"] and res["legends"] == ["13px"]
              and res["radio"] and res["radio"][0] == "none" and res["tileCheck"] == "none" and res["number"] == "none" and res["numberLook"] == [True, True]
              and res["accountList"] in (["richlistbox", "12px"], ["input", "7px"]))
        return ok, f"{res}"
    check("Einstellungen: Inhalt mittig, Kästchen und Optionsfelder wie macOS, Kacheln, Kontoeinstellungen", settings_style, results)

    def settings_cards():
        # Einstellungen: Grundschrift 13 px, Seitenleiste bündig, Listen mit Haarlinie, sicheres DNS als Karte,
        # Export für Mobilgeräte ohne Marineblau, leere Abstandhalter weg, Unterdialoge (Offline, Bäume)
        res = m.js(r'''
          w.resizeTo(1500, 950); w.openPreferencesTab("paneGeneral"); await wait(2500);
          const cw = tm.currentTabInfo.browser.contentWindow; const cd = cw.document;
          const cs = e => e.ownerDocument.defaultView.getComputedStyle(e);
          const vis = sel => [...cd.querySelectorAll(sel)].find(e => e.getBoundingClientRect().width);
          const win = cs(cd.getElementById("preferencesContainer")).backgroundColor;
          const line = cs(cd.querySelector("#paneDeck input[type=text]")).borderTopColor;
          const left = el => { const r = cd.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().left; };
          const out = {};
          const lab = vis("#paneDeck checkbox .checkbox-label"); const desc = vis("#paneDeck description");
          const fontLab = cd.getElementById("defaultFont")?.parentNode.querySelector("label");
          out.font = [lab && cs(lab).fontSize, fontLab && cs(fontLab).fontSize, desc && cs(desc).fontSize];
          const cn = cd.querySelector("#category-general .category-name"), fl = cd.querySelector("#accountButton .sidebar-footer-label");
          out.side = [Math.abs(left(cn) - left(fl)) <= 1, cs(cn).fontSize, cs(fl).fontSize];
          out.lists = ["tagList", "handlersView"].map(id => { const e = cd.getElementById(id);
            return [cs(e).borderTopLeftRadius, parseFloat(cs(e).borderTopWidth) <= 1, cs(e).borderTopColor == line]; });
          out.handlers = [cs(cd.querySelector("#handlersTable thead > tr")).backgroundColor == win, cs(cd.getElementById("handlersView")).overflowY];
          // Offline-Einstellungen: Optionen untereinander, jede einzeilig
          const ob = cd.getElementById("offlineSettingsButton"); ob.scrollIntoView({ block: "center" }); ob.click();
          let fr = await until(() => [...cd.querySelectorAll(".dialogFrame")].find(f => f.contentDocument?.readyState == "complete" && f.contentDocument.location.href.includes("offline")), 8000);
          if (fr) { await wait(800); const dd = fr.contentDocument;
            const rs = [...dd.querySelectorAll("#whengoingOnlinestate radio")].map(r => r.getBoundingClientRect());
            // einzeilig: höchstens 30 px (umbrochen wären es über 40; unter Linux mit GTK-Optionsfeld 26)
            out.offline = [rs.length > 1 && rs.every((r, i) => !i || (r.top >= rs[i - 1].bottom - 1 && Math.abs(r.left - rs[0].left) < 1)),
              Math.max(...[...dd.querySelectorAll("#whengoingOnlinestate radio, #whengoingOfflinestate radio")].map(r => r.getBoundingClientRect().height))];
            cw.gSubDialog._topDialog?.close(); await wait(600); }
          cw.gotoPref("panePrivacy"); await wait(1500);
          const arrow = cd.getElementById("dohDefaultArrow"); const icon = arrow?.querySelector(".button-icon");
          // -moz-context-properties steht nicht im berechneten Stil – stroke ist ohne die Regel „none“
          out.doh = arrow ? [cs(icon).stroke == cs(arrow).color, cs(arrow).backgroundColor,
            Math.round(arrow.getBoundingClientRect().width) <= 28] : null;
          const box = cd.getElementById("dohBox"), opt = cd.getElementById("dohOptionDefault");
          out.dohBox = [cs(box).borderTopLeftRadius, cs(box).backgroundColor != "rgba(0, 0, 0, 0)",
            cs(opt).borderTopLeftRadius, parseFloat(cs(opt).borderTopWidth) <= 1, cs(opt).borderTopColor == line];
          out.pwSep = cs(cd.getElementById("privacyPasswordsCategory").nextElementSibling).display;
          // Sicheres DNS: Statuskasten ohne Netzwerkstatus verborgen, mit Statustext sichtbar (Gegenprobe)
          const dss = cd.getElementById("dohStatusSection"), dst = cd.getElementById("dohStatus");
          const dssH = () => Math.round(dss.getBoundingClientRect().height);
          out.dohStatus = [dst.textContent, cs(dss).display, dssH()];
          const oldStatus = dst.textContent; dst.textContent = "Status: Off"; await wait(200);
          out.dohStatus.push(dssH()); dst.textContent = oldStatus; await wait(100);
          // Unterüberschriften (auch verschachtelte legend) nicht größer als der Kartentitel
          out.legendsPrivacy = [...new Set([...cd.querySelectorAll("#paneDeck legend")].map(l => cs(l).fontSize))];
          // OCSP einzeilig (eine Zeile ca. 23 px, zwei ca. 46 px), Knöpfe weiterhin rechts in der Karte
          const ocsp = cd.querySelector("#enableOCSP .checkbox-label"), ocspCard = cd.getElementById("enableOCSP").closest("fieldset");
          out.ocsp = [Math.round(ocsp.getBoundingClientRect().height),
            ["manageCertificatesButton", "viewSecurityDevicesButton"].map(id => { const r = cd.getElementById(id).getBoundingClientRect();
              return r.width > 0 && r.right <= ocspCard.getBoundingClientRect().right && r.left > ocsp.getBoundingClientRect().right; })];
          // Cookie-Ausnahmen: Baum mit Haarlinie und 8 px
          const cb = cd.getElementById("cookieExceptions"); cb.scrollIntoView({ block: "center" }); cb.click();
          fr = await until(() => [...cd.querySelectorAll(".dialogFrame")].find(f => f.contentDocument?.readyState == "complete" && f.contentDocument.querySelector("tree")), 8000);
          if (fr) { await wait(800); const dd = fr.contentDocument; const t = dd.querySelector("tree");
            const probe = dd.createElementNS("http://www.w3.org/1999/xhtml", "div"); probe.style.color = "var(--mt-pane-line)"; dd.documentElement.append(probe);
            out.tree = [cs(t).borderTopLeftRadius, parseFloat(cs(t).borderTopWidth) <= 1, cs(t).borderTopColor == cs(probe).color];
            probe.remove(); cw.gSubDialog._topDialog?.close(); await wait(600); }
          cw.gotoPref("paneCalendar"); await wait(1500);
          const fs = vis("#paneDeck fieldset"); const dp = cd.getElementById("datePrefsBox");
          out.cal = [fs.firstElementChild.localName, cs(fs.firstElementChild).display, Math.round(dp.getBoundingClientRect().top - dp.closest("fieldset").getBoundingClientRect().top)];
          cw.gotoPref("paneQrExport"); await wait(1500);
          const qr = cd.getElementById("qrExportIntroForm"); const rgb = cs(qr).backgroundColor.match(/[\d.]+/g).map(Number);
          out.qr = [cs(qr).borderTopStyle, cs(qr).borderTopLeftRadius, Math.abs(rgb[0] - rgb[2]) <= 3,
            cs(cd.querySelector(".qr-small")).fontSize, cs(cd.getElementById("qrExportSelectAll")).textTransform];
          tm.closeTab(tm.currentTabInfo);
          return out;''')
        ok = (res["font"] == ["13px", "13px", "12px"] and res["side"] == [True, "13px", "13px"]
              and res["lists"] == [["8px", True, True]] * 2 and res["handlers"] == [True, "auto"]
              and res.get("offline") and res["offline"][0] is True and res["offline"][1] <= 30
              and res["doh"] and res["doh"][0] and res["doh"][1] == "rgba(0, 0, 0, 0)" and res["doh"][2]
              and res["dohBox"] == ["12px", True, "10px", True, True] and res["pwSep"] == "none"
              and res["dohStatus"][1:3] == ["none", 0] and res["dohStatus"][3] > 0
              and res["legendsPrivacy"] == ["13px"] and res["ocsp"][0] <= 30 and res["ocsp"][1] == [True, True]
              and res.get("tree") == ["8px", True, True]
              and res["cal"][:2] == ["separator", "none"] and res["cal"][2] <= 20
              and res["qr"] == ["none", "12px", True, "11px", "none"])
        return ok, f"{res}"
    check("Einstellungen: Schrift 13 px, Seitenleiste bündig, Listen/DNS/Export als ruhige Karten, leerer DNS-Status verborgen, Unterüberschriften 13 px, OCSP einzeilig, Offline-Dialog untereinander", settings_cards, results)

    def settings_e2ee_cards():
        # Einstellungen: Karte nur mit „Advanced settings“ ohne Fläche (andere Karten behalten sie);
        # Ende-zu-Ende-Texte (html:p) wie Erklärtexte 12 px grau ohne Abstand oben, Linie als Haarlinie,
        # Link „Account settings“ behält seine Linkfarbe
        res = m.js(r"""
          w.resizeTo(1500, 950); w.openPreferencesTab("paneGeneral"); await wait(2500);
          const cw = tm.currentTabInfo.browser.contentWindow; const cd = cw.document;
          const cs = e => e.ownerDocument.defaultView.getComputedStyle(e);
          const out = {};
          const adv = cd.getElementById("configEditor").closest("fieldset");
          const other = [...cd.querySelectorAll("#paneDeck fieldset")].find(f => f != adv && f.querySelector(":scope > legend") && f.getBoundingClientRect().width);
          out.adv = [cs(adv).backgroundColor, cs(adv).paddingTop, cs(adv).marginBottom,
            other ? cs(other).backgroundColor != "rgba(0, 0, 0, 0)" : null];
          cw.gotoPref("panePrivacy"); await wait(1500);
          const p = cd.querySelector("#emailE2eeKeyServers > p"), hr = cd.querySelector("#emailE2eeKeyServers > hr");
          const ref = cd.querySelector("#emailE2eeGroupAutomatism description");
          const first = cd.querySelector("#emailE2eeGroupPreparation > p");
          const probe = cd.createElementNS("http://www.w3.org/1999/xhtml", "div");
          probe.style.borderTop = "1px solid var(--mt-pane-line)"; cd.getElementById("paneDeck").append(probe);
          out.p = p && ref ? [cs(p).fontSize, cs(p).color == cs(ref).color, cs(p).lineHeight] : null;
          out.hr = hr ? [parseFloat(cs(hr).borderTopWidth) <= 1, cs(hr).borderTopColor == cs(probe).borderTopColor,
            cs(hr).borderBottomStyle] : null;
          out.first = first ? [cs(first).marginTop, cs(first).fontSize] : null;
          const a = first?.querySelector("a");
          out.link = a ? cs(a).color != cs(first).color : "kein Link";
          probe.remove();
          tm.closeTab(tm.currentTabInfo);
          return out;""")
        ok = (res["adv"][0] in ("rgba(0, 0, 0, 0)", "transparent") and res["adv"][1] == "0px"
              and res["adv"][2] == "12px" and res["adv"][3] is True
              and res["p"] and res["p"][:2] == ["12px", True]
              and res["hr"] and res["hr"][:2] == [True, True] and res["hr"][2] == "none"
              and res["first"] == ["0px", "12px"] and res["link"] in (True, "kein Link"))
        return ok, f"{res}"
    check("Einstellungen: Karte „Advanced settings“ ohne leere Fläche; Ende-zu-Ende-Texte 12 px grau mit Haarlinie", settings_e2ee_cards, results)

    def settings_details():
        # Einstellungen: Arbeitstage mittig und mit Abstand, Chat-Vorschau mit Abstand/Rahmen und dunkel als
        # Variante „Dark“, Schlagwörter lesbar, „Verzeichnisse bearbeiten“ wie die übrigen Knöpfe (Bearbeiten im
        # Adressbuch bleibt groß), Update-Chronik mit Abstand, Port-Felder ohne Pfeile, schmales Fenster ohne Abschneiden,
        # Schriftgröße kompakt, Kryptographie-Module mit ungekürzten Namen und Abstand zwischen den Listen
        res = m.js(ADDRESS_EDIT_JS.replace('ad.getElementById("editButton").click(); await wait(1200);', '') + r"""
          const abEdit = ad.getElementById("editButton"); const out = { abEdit: [ab.getComputedStyle(abEdit).height, ab.getComputedStyle(abEdit).fontWeight] };
          tm.closeTab(tm.currentTabInfo);
          const dark = w.matchMedia("(prefers-color-scheme: dark)").matches;
          w.resizeTo(1500, 950); w.openPreferencesTab("paneGeneral"); await wait(2500);
          const cw = tm.currentTabInfo.browser.contentWindow; const cd = cw.document;
          const cs = e => e.ownerDocument.defaultView.getComputedStyle(e);
          // color-mix() liefert „color(srgb 0–1 …)“ statt rgb()
          const rgb = c => { const n = c.match(/[\d.]+/g).slice(0, 3).map(Number); return c.startsWith("color(") ? n.map(x => x * 255) : n; };
          const lum = c => { const [r, g, b] = c.map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
          const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
          const mid = r => (r.left + r.right) / 2;
          const bg = rgb(cs(cd.getElementById("tagList")).backgroundColor);
          out.tags = [...cd.querySelectorAll("#tagList > richlistitem:not([selected]) > label")].map(l => contrast(rgb(cs(l).color), bg));
          // Schriftgröße neben der Schriftart kompakt statt gleich breit
          const fsz = cd.getElementById("defaultFontSize");
          out.size = [Math.round(fsz.getBoundingClientRect().width), Math.round(cd.getElementById("defaultFont").getBoundingClientRect().width)];
          // Kryptographie-Module: linke Liste breit genug für die Namen, Dialog ohne Überbreite
          cw.gSubDialog.open("chrome://pippki/content/device_manager.xhtml");
          let fd = await until(() => [...cd.querySelectorAll(".dialogFrame")].find(f => f.contentDocument?.readyState == "complete" && f.contentDocument.getElementById("device_tree")), 8000);
          if (fd) { await wait(400); const dd = fd.contentDocument, de = dd.documentElement;
            const dt = dd.getElementById("device_tree"), it = dd.getElementById("info_tree");
            // Namen ungekürzt: Zellentext passt in die Spalte (ohne Ellipse)
            const names = [];
            for (let i = 0; i < dt.view.rowCount; i++) names.push(dt.view.getCellText(i, dt.columns[0]));
            const cv = dd.createElementNS("http://www.w3.org/1999/xhtml", "canvas").getContext("2d"); cv.font = `${cs(dt).fontSize} ${cs(dt).fontFamily}`;
            const colW = dt.columns[0].element.getBoundingClientRect().width;
            out.dev = [Math.round(dt.getBoundingClientRect().width), de.scrollWidth <= de.clientWidth,
              Math.round(it.getBoundingClientRect().left - dt.getBoundingClientRect().right),
              names.length > 0 && names.every((n, i) => cv.measureText(n).width + 16 * (dt.view.getLevel(i) + 1) + 24 <= colW)];
            cw.gSubDialog._topDialog?.close(); await wait(400); }
          // Update-Chronik: Hinweis „No updates installed yet“ nicht am Listenrand
          cw.gSubDialog.open("chrome://mozapps/content/update/history.xhtml");
          let fr = await until(() => [...cd.querySelectorAll(".dialogFrame")].find(f => f.contentDocument?.readyState == "complete" && f.contentDocument.getElementById("historyItems")), 8000);
          if (fr) { await wait(400); const hi = fr.contentDocument.getElementById("historyItems"), lb = hi.querySelector(":scope > label");
            out.history = lb ? [Math.round(lb.getBoundingClientRect().left - hi.getBoundingClientRect().left), Math.round(lb.getBoundingClientRect().top - hi.getBoundingClientRect().top)] : "kein Hinweis";
            cw.gSubDialog._topDialog?.close(); await wait(400); }
          // Verbindungs-Einstellungen: Port-Felder ohne Pfeile, Wert mittig
          cw.gSubDialog.open("chrome://messenger/content/preferences/connection.xhtml");
          fr = await until(() => [...cd.querySelectorAll(".dialogFrame")].find(f => f.contentDocument?.readyState == "complete" && f.contentDocument.getElementById("networkProxyHTTP_Port")), 8000);
          if (fr) { await wait(400); const pt = fr.contentDocument.getElementById("networkProxyHTTP_Port");
            out.port = [cs(pt).appearance, cs(pt).textAlign, cs(pt).borderTopLeftRadius];
            cw.gSubDialog._topDialog?.close(); await wait(400); }
          cw.gotoPref("paneCompose"); await wait(1500);
          const eb = cd.getElementById("editButton"), ar = cd.getElementById("attachment_reminder_button");
          out.edit = [Math.abs(eb.getBoundingClientRect().height - ar.getBoundingClientRect().height) <= 1, cs(eb).fontWeight];
          cw.gotoPref("paneChat"); await wait(1500);
          const pb = cd.getElementById("previewBox"); const pl = pb.parentNode.querySelector(":scope > label");
          out.preview = [Math.round(pb.getBoundingClientRect().left - pl.getBoundingClientRect().right), cs(pb).borderTopLeftRadius, parseFloat(cs(pb).borderTopWidth) <= 1];
          const body = await until(() => cd.querySelector("#previewBox browser")?.contentDocument?.body, 5000);
          out.chat = [Services.prefs.getCharPref("messenger.options.messagesStyle.variant"), dark,
            body ? Math.round(lum(rgb(body.ownerDocument.defaultView.getComputedStyle(body).backgroundColor)) * 100) / 100 : null];
          cw.gotoPref("paneCalendar"); await wait(1500);
          const days = [0, 1, 2, 3, 4, 5, 6].map(i => cd.getElementById("dayoff" + i)).filter(Boolean);
          days[1].scrollIntoView({ block: "center" }); await wait(300);
          const labs = days.map(b => b.querySelector(".checkbox-label").getBoundingClientRect());
          out.days = [days.length, Math.max(...days.map((b, i) => Math.abs(mid(b.querySelector(".checkbox-check").getBoundingClientRect()) - mid(labs[i])))),
            Math.min(...labs.slice(1).map((l, i) => l.left - labs[i].right))];
          // kleinste Fensterbreite: keine Seite breiter als der Inhaltsbereich
          w.resizeTo(800, 900); await wait(800);
          out.narrow = {};
          for (const p of ["paneGeneral", "paneAppearance", "paneCompose", "panePrivacy", "paneChat", "paneCalendar", "paneQrExport"]) {
            cw.gotoPref(p); await wait(700);
            const c = cd.getElementById("preferencesContainer");
            // abgeschnitten ist, was über die sichtbare Fläche (Innenabstand eingeschlossen) hinausragt
            const right = c.getBoundingClientRect().left + c.clientWidth;
            const over = [...cd.querySelectorAll(`#paneDeck [data-category="${p}"] :is(fieldset, .subcategory, #forwardMessageMode, #addExtension)`)]
              .filter(e => e.getBoundingClientRect().width && e.getBoundingClientRect().right > right + 1).length;
            out.narrow[p] = [c.scrollWidth - c.clientWidth, over];
          }
          w.resizeTo(1500, 950); await wait(500);
          tm.closeTab(tm.currentTabInfo);
          return out;""")
        narrow_ok = all(v[0] <= 1 and v[1] == 0 for v in res["narrow"].values())
        chat = res["chat"]
        chat_ok = (chat[0] == "Dark" and chat[2] is not None and chat[2] < 0.2) if chat[1] else (chat[0] != "Dark" and chat[2] is not None and chat[2] > 0.5)
        ok = (res["abEdit"] == ["38px", "500"] and res["tags"] and min(res["tags"]) >= 4.5
              and isinstance(res.get("history"), list) and res["history"][0] >= 6 and res["history"][1] >= 4
              and res.get("port") == ["none", "center", "7px"] and res["edit"] == [True, "400"]
              and res["preview"][0] >= 6 and res["preview"][1:] == ["8px", True] and chat_ok
              and res["days"][0] == 7 and res["days"][1] <= 1 and res["days"][2] >= 4 and narrow_ok
              and res["size"][0] <= 100 and res["size"][0] < res["size"][1] / 2
              and bool(res.get("dev")) and res["dev"][1] is True and res["dev"][0] >= 250 and res["dev"][2] >= 6 and res["dev"][3] is True)
        return ok, f"{res}"
    check("Einstellungen: Arbeitstage, Chat-Vorschau (dunkel „Dark“), Schlagwörter lesbar, Knöpfe, Update-Chronik, Ports, schmales Fenster, Schriftgröße, Kryptographie-Module", settings_details, results)

    def account_pages():
        # Kontoeinstellungen: „Add-ons and Themes“ einzeilig, Seiten dunkel in --mt-window, Überschrift mit 12 px
        # Abstand zur ersten Karte, Junk ohne doppelten Kartenabstand und mit niedrigen Adressbuch-Zeilen, deren
        # Auswahl das Kästchen nicht verdeckt, „Default: 587“ mit Abstand, Archiv-Beispiel mit Haarlinie und 8 px
        res = m.js(r"""
          w.resizeTo(1500, 950); w.MsgAccountManager(null);
          const aw = await until(() => tm.currentTabInfo.browser?.contentWindow?.document.getElementById("accounttree") && tm.currentTabInfo.browser.contentWindow, 8000);
          await wait(1200); const ad = aw.document;
          const cs = e => e.ownerDocument.defaultView.getComputedStyle(e); const R = e => e.getBoundingClientRect();
          const out = { dark: w.matchMedia("(prefers-color-scheme: dark)").matches };
          out.footer = [...ad.querySelectorAll("#accountTreeBox .sidebar-footer-label")].filter(e => R(e).width).map(e => [Math.round(R(e).height), cs(e).whiteSpace]);
          const probe = ad.createElementNS("http://www.w3.org/1999/xhtml", "div"); probe.style.color = "var(--mt-window)"; ad.documentElement.append(probe);
          const line = ad.createElementNS("http://www.w3.org/1999/xhtml", "div"); line.style.color = "var(--mt-pane-line)"; ad.documentElement.append(line);
          const winColor = cs(probe).color, lineColor = cs(line).color; probe.remove(); line.remove();
          const tree = ad.getElementById("accounttree");
          const page = async tag => { const li = [...tree.querySelectorAll("li")].find(l => (l.getAttribute("PageTag") || "") == tag);
            if (!li) return null; tree.selectedIndex = tree.rows.indexOf(li);
            return await until(() => { const d = ad.getElementById("contentFrame").contentDocument;
              return d?.readyState == "complete" && d.location.href.includes(tag) && d.getElementById("containerBox") && d; }, 8000); };
          const sub = async () => { const f = await until(() => [...ad.querySelectorAll(".dialogFrame")].find(fr => fr.contentDocument?.readyState == "complete" && fr.contentDocument.location.href != "about:blank"), 8000);
            await wait(600); return f?.contentDocument; };
          const headGap = d => { const h = d.querySelector("#containerBox > .dialogheader"); const f = [...d.querySelectorAll("#containerBox fieldset")].find(e => R(e).width);
            return h && f ? Math.round(R(f).top - R(h).bottom) : null; };
          out.gap = {}; out.bg = {};
          for (const tag of ["am-copies.xhtml", "am-junk.xhtml", "am-offline.xhtml", "am-smtp.xhtml"]) {
            const d = await page(tag); if (!d) { out.gap[tag] = "fehlt"; continue; } await wait(500);
            out.bg[tag] = cs(d.documentElement).backgroundColor == winColor;
            if (tag != "am-smtp.xhtml") out.gap[tag] = headGap(d);
            if (tag == "am-junk.xhtml") {
              const fs = [...d.querySelectorAll("#containerBox > div > fieldset")].filter(e => R(e).width);
              out.junkGap = fs.length > 1 ? Math.round(R(fs[1]).top - R(fs[0]).bottom) : null;
              const wl = d.getElementById("whiteListAbURI"); const items = [...wl.children].filter(e => R(e).width);
              // Zeilenhöhe: unter Linux mit GTK-Kästchen und Systemschrift 32 px statt höchstens 30
              out.rows = items.map(e => Math.round(R(e).height));
              const it = items[0], cb = it.querySelector("checkbox"), was = cb.checked;
              cb.checked = true; wl.selectedIndex = 0; await wait(200);
              out.sel = cs(it).backgroundColor != cs(it.querySelector(".checkbox-check")).backgroundColor;
              cb.checked = was;
            }
            if (tag == "am-copies.xhtml") {
              const b = d.getElementById("archiveHierarchyButton"); b.scrollIntoView({ block: "center" });
              setTimeout(() => b.click(), 0); const sd = await sub();
              if (sd) { const p = sd.getElementById("archiveTree").parentElement;
                out.archive = [cs(p).borderTopColor == lineColor, cs(p).borderTopLeftRadius, parseFloat(cs(p).borderTopWidth) <= 1];
                const dl = sd.querySelector("dialog"); if (dl?.cancelDialog) dl.cancelDialog(); else sd.defaultView.close(); await wait(600); }
            }
            if (tag == "am-smtp.xhtml") {
              const b = d.getElementById("addButton"); setTimeout(() => b.click(), 0); const sd = await sub();
              if (sd) { const sp = sd.getElementById("smtp.port"), l1 = sp.nextElementSibling, l2 = sd.getElementById("smtp.defaultPort");
                out.smtp = [Math.round(R(l1).left - R(sp).right), Math.round(R(l2).left - R(l1).right)];
                const dl = sd.querySelector("dialog"); if (dl?.cancelDialog) dl.cancelDialog(); else sd.defaultView.close(); await wait(600); }
            }
          }
          tm.closeTab(tm.currentTabInfo);
          return out;""")
        ok = (bool(res["footer"]) and all(h < 30 and ws == "nowrap" for h, ws in res["footer"])
              and all(res["bg"].values()) and len(res["bg"]) == 4
              and all(isinstance(v, int) and 10 <= v <= 16 for v in res["gap"].values())
              and res.get("junkGap") is not None and res["junkGap"] <= 16
              and res.get("rows") and all(22 <= h <= (30 if sys.platform == "darwin" else 34) for h in res["rows"]) and res.get("sel") is True
              and res.get("archive") == [True, "8px", True]
              and res.get("smtp") and min(res["smtp"]) >= 4)
        return ok, f"{res}"
    check("Kontoeinstellungen: Fußzeile einzeilig, Fläche --mt-window, Abstände Überschrift/Karten, Junk-Adressbücher, SMTP-Port, Archiv-Beispiel", account_pages, results)

    def account_wizards():
        # Konto-Assistenten (Feed, Newsgruppen, Chat): Knöpfe flach ohne Rahmen, 13 px, 28 px hoch und lesbar
        # (dunkel war „Cancel“ weiß auf #8F8F9D), Felder mit 7 px, Chat-Netzliste mit Haarlinie und 8 px
        res = m.js(r"""
          const rgba = c => { const v = (String(c).match(/-?[\d.]+(?:e-?\d+)?/g) || []).map(Number); const k = String(c).startsWith("color(") ? 255 : 1;
            return [v[0] * k, v[1] * k, v[2] * k, v.length > 3 ? v[3] : 1]; };
          const over = (fg, bg) => fg.slice(0, 3).map((x, i) => x * fg[3] + bg[i] * (1 - fg[3])).concat(1);
          const lum = c => { const [r, g, b] = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
          const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
          const out = {};
          // nicht modal öffnen (wie Thunderbird, aber ohne „modal“), damit das Skript weiterläuft
          for (const [name, url] of [["feed", "chrome://messenger-newsblog/content/feedAccountWizard.xhtml"],
                                     ["news", "chrome://messenger/content/AccountWizard.xhtml"],
                                     ["chat", "chrome://messenger/content/chat/imAccountWizard.xhtml"]]) {
            const ww = w.openDialog(url, "_blank", "chrome,titlebar,centerscreen,dialog=no");
            await until(() => ww.document?.readyState == "complete" && ww.document.querySelector("wizard"), 10000);
            if (!ww.document?.querySelector("wizard")) { out[name] = "nicht offen"; ww.close(); continue; }
            await wait(800);
            const wd = ww.document, wz = wd.querySelector("wizard"), cs = e => ww.getComputedStyle(e);
            const b = wz.getButton("cancel"), s = cs(b), bg = rgba(cs(wd.documentElement).backgroundColor);
            const i = wd.querySelector("wizardpage:not([hidden]) input:not([type=checkbox], [type=radio])") || wd.querySelector("input:not([type=checkbox], [type=radio])");
            const r = { contrast: contrast(over(rgba(s.color), over(rgba(s.backgroundColor), bg)), over(rgba(s.backgroundColor), bg)),
              border: s.borderTopWidth, font: s.fontSize, h: Math.round(b.getBoundingClientRect().height),
              var: cs(wz).getPropertyValue("--button-border-color").trim(), input: i ? cs(i).borderTopLeftRadius : null };
            const pl = wd.getElementById("protolist");
            if (pl) { const it = pl.querySelector("richlistitem[selected]") || pl.querySelector("richlistitem");
              if (it && !it.selected) { pl.selectedItem = it; await wait(200); }
              r.list = [cs(pl).borderTopLeftRadius, rgba(cs(pl).borderTopColor)[3], it ? cs(it).borderTopLeftRadius : null]; }
            out[name] = r;
            ww.close(); await wait(400);
          }
          return out;""")
        ok = True
        for name in ("feed", "news", "chat"):
            r = res.get(name)
            ok = ok and isinstance(r, dict) and r["contrast"] >= 4.5 and r["border"] == "0px" and r["font"] == "13px" \
                and r["h"] >= 27 and r["var"] == "transparent" and r["input"] == "7px"
        c = res.get("chat")
        ok = ok and isinstance(c, dict) and c.get("list") and c["list"][0] == "8px" and c["list"][1] <= 0.15 and c["list"][2] == "6px"
        return ok, f"{res}"
    check("Konto-Assistenten: Knöpfe flach und lesbar, Felder 7 px, Chat-Netzliste mit Haarlinie und 8 px", account_wizards, results)

    def no_placeholder_in_ui():
        # Platzhalter für blockierte Bilder nur in Mails – nicht in der Oberfläche (Lupe im Suchfeld)
        res = m.js('''
          await toMail(); await wait(500);
          const imgs = [];
          const walk = root => { for (const el of root.querySelectorAll("*")) { if (el.localName == "img") imgs.push(el); if (el.shadowRoot) walk(el.shadowRoot); } };
          walk(d);
          const bad = imgs.filter(i => /M3 3l18 18/.test(w.getComputedStyle(i).backgroundImage)).map(i => i.id || i.className || i.getAttribute("alt"));
          return { imgs: imgs.length, bad };''')
        return res["imgs"] > 0 and not res["bad"], f"{res}"
    check("Oberfläche: kein Bild-Platzhalter außerhalb von Mails", no_placeholder_in_ui, results)

    def preview_entities():
        # Text-Teil mit &zwnj; (wie Amazon Visa) – Vorschau ohne Entities
        res = m.js(r"""
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
          const root = MailServices.accounts.localFoldersServer.rootFolder;
          if (!root.containsChildNamed("Zeichen")) { root.createSubfolder("Zeichen", null); await wait(800); }
          const f = root.getChildNamed("Zeichen");
          if (!f.getTotalMessages(false)) {
            f.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage("From: Halo <h@example.invalid>\r\nSubject: Zeichen\r\nDate: Sat, 17 Oct 2026 10:00:00 +0200\r\nMessage-ID: <halo-entities@example.invalid>\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nInformationen zu deiner Karte &zwnj; &zwnj;&zwnj; Hallo &hellip; bis bald\r\n");
            await wait(800);
          }
          const a3 = await toMail(); a3.displayFolder(f.URI);
          const el = await until(() => [...a3.document.querySelectorAll('#threadTree tr[is="thread-card"] .mc-preview')].find(e => /Hallo/.test(e.textContent)), 8000);
          return { text: el?.textContent || null, visibility: d.visibilityState, rows: a3.gDBView?.rowCount };""")
        if res.get("text") is None and res.get("visibility") == "hidden":
            return True, f"Testfenster verdeckt (Karten nicht gezeichnet) – übersprungen {res}"
        text = res.get("text") or ""
        return "Hallo" in text and "&" not in text and "…" in text, f"{res}"
    check("Vorschau: HTML-Zeichen (&zwnj; …) aufgelöst", preview_entities, results)

    def tooltip_style():
        # eigene Tooltip-Fläche (sonst dunkle Schrift auf dunklem macOS-Tooltip)
        res = m.js(MESSAGE_JS + '''
          const md = a3.messageBrowser.contentDocument;
          const out = {};
          for (const [name, tip] of [["mail", d.getElementById("aHTMLTooltip")], ["message", md.getElementById("aHTMLTooltip")]]) {
            if (!tip) continue;
            const cs = tip.ownerDocument.defaultView.getComputedStyle(tip);
            out[name] = { app: cs.appearance, bg: cs.backgroundColor, color: cs.color, radius: cs.borderTopLeftRadius };
          }
          const li = md.querySelector("#messageHeader li.header-recipient");
          out.title = li?.title;
          return out;''')
        tips = [res.get("mail"), res.get("message")]
        ok = all(t and t["app"] == "none" and t["bg"] not in ("", "transparent", "rgba(0, 0, 0, 0)") and t["radius"] == "6px" for t in tips) \
            and "@" in (res.get("title") or "")
        return ok, f"{res}"
    check("Tooltips: eigene Fläche mit lesbarer Schrift", tooltip_style, results)

    def space_tips():
        res = m.js('''
          return [...d.querySelectorAll("#spacesToolbar :is(#mailButton, #addressBookButton, #calendarButton, #tasksButton, #chatButton)")].map(b => b.title);''')
        ok = len(res) == 5 and all(t and "(" not in t and "⌃" not in t for t in res)
        return ok, f"{res}"
    check("Bereiche-Leiste: Tooltips nur mit Namen", space_tips, results)

    def system_integration_check():
        # der Dialog sperrt per CSP alle Bilder außer chrome: – Haken muss trotzdem erscheinen
        res = m.js('''
          const dlg = w.openDialog("chrome://messenger/content/systemIntegrationDialog.xhtml", "_blank", "chrome,dialog=no,centerscreen");
          await wait(2000);
          const box = dlg.document.getElementById("checkMail"); box.checked = true; await wait(600);
          const cs = dlg.getComputedStyle(box.querySelector(".checkbox-check"));
          const iw = dlg.windowGlobalChild.innerWindowId;
          const blocked = (Services.console.getMessageArray() || []).filter(x => x instanceof Ci.nsIScriptError
            && x.innerWindowID == iw && /Content-Security-Policy/.test(x.errorMessage)).length;
          const out = { img: cs.backgroundImage.slice(0, 40), fill: cs.fill, bg: cs.backgroundColor, blocked };
          dlg.close(); await wait(300);
          return out;''')
        ok = res["img"].startswith('url("chrome:') and res["fill"] == "rgb(255, 255, 255)" and res["blocked"] == 0
        return ok, f"{res}"
    check("Standardprogramm-Dialog: Haken im Kästchen trotz Bildsperre", system_integration_check, results)

    def search_prefs():
        res = m.js('''
          return { gloda: Services.prefs.getBoolPref("mailnews.database.global.indexer.enabled"),
                   list: Services.prefs.getBoolPref("gloda.show_as_list_by_default"),
                   applied: Services.prefs.getBoolPref("extensions.mailcards.searchApplied", false) };''')
        return all(res.values()), f"{res}"
    check("Suche: alle Konten und einfache Liste voreingestellt", search_prefs, results)

    def search_date():
        # Datum im Suchbegriff ohne Jahr: letztes vergangenes Vorkommen, auch
        # für den 29.2. („jetzt“ im Experiment-Modul kurz umgestellt)
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
          const sd = Cu.evalInSandbox("searchDate", g);
          const p = n => String(n).padStart(2, "0");
          const f = x => x ? `${p(x.getDate())}.${p(x.getMonth() + 1)}.${x.getFullYear()}` : "-";
          const out = {};
          for (const [now, terms] of [["2026, 9, 20, 15", ["29.2", "12.10", "21.10", "31.4", "29.2.2026", "1.3.25"]], ["2028, 0, 15, 12", ["29.2"]]]) {
            Cu.evalInSandbox(`globalThis.__mcRealDate = Date; Date = class extends __mcRealDate { constructor(...a) { if (a.length) super(...a); else super(${now}); } };`, g);
            try {
              for (const t of terms) out[`${now.split(",")[0]}: ${t}`] = f(sd(t));
            } finally {
              Cu.evalInSandbox("Date = globalThis.__mcRealDate; delete globalThis.__mcRealDate;", g);
            }
          }
          return out;''' % ADDON_ID)
        expected = {"2026: 29.2": "29.02.2024", "2026: 12.10": "12.10.2026", "2026: 21.10": "21.10.2025", "2026: 31.4": "-",
                    "2026: 29.2.2026": "-", "2026: 1.3.25": "01.03.2025", "2028: 29.2": "29.02.2024"}
        bad = [f"„{k}“ → {res.get(k)}" for k, v in expected.items() if res.get(k) != v]
        return not bad, "; ".join(bad) or f"{len(expected)} Suchbegriffe richtig (29.2. ohne Jahr, ungültige Tage)"
    check("Suche: Datum ohne Jahr („29.2“) findet das letzte Vorkommen", search_date, results)

    def birthdays():
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const { VCardUtils } = ChromeUtils.importESModule("resource:///modules/VCardUtils.sys.mjs");
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          const card = VCardUtils.vCardToAbCard("BEGIN:VCARD\\r\\nVERSION:4.0\\r\\nFN:Halo Testkontakt\\r\\nBDAY:1990-03-15\\r\\nEND:VCARD\\r\\n");
          book.addCard(card);
          // Apple (Kontakte/iCloud): Geburtstag ohne Jahr als 1604 mit X-APPLE-OMIT-YEAR
          book.addCard(VCardUtils.vCardToAbCard("BEGIN:VCARD\\r\\nVERSION:3.0\\r\\nFN:Halo Applekontakt\\r\\nBDAY;X-APPLE-OMIT-YEAR=1604:1604-08-15\\r\\nEND:VCARD\\r\\n"));
          // der Kalender wird 3 s nach der Änderung neu gefüllt
          let c = null;
          for (let i = 0; i < 30 && !c; i++) { await wait(500); c = cal.manager.getCalendarById(Services.prefs.getStringPref("extensions.mailcards.birthdayCalendarId", "")); }
          if (!c) return { calendar: false };
          let all = [];
          for (let i = 0; i < 20; i++) {
            await wait(400);
            all = await c.getItemsAsArray(Ci.calICalendar.ITEM_FILTER_ALL_ITEMS, 0, null, null);
            if (all.some(i => /Halo Testkontakt/.test(i.title)) && all.some(i => /Halo Applekontakt/.test(i.title))) break;
          }
          const it = all.find(i => /Halo Testkontakt/.test(i.title));
          const apple = all.find(i => /Halo Applekontakt/.test(i.title));
          return { calendar: true, name: c.name, readOnly: c.readOnly, title: it?.title, yearly: it?.recurrenceInfo?.getRecurrenceItems()[0]?.type, allDay: it?.startDate.isDate,
                   born: it?.getProperty("DESCRIPTION") || null, apple: apple ? { year: apple.startDate.year, desc: apple.getProperty("DESCRIPTION") || null } : null };''')
        ok = res.get("calendar") and res.get("readOnly") and res.get("yearly") == "YEARLY" and res.get("allDay") and "Halo Testkontakt" in (res.get("title") or "") \
            and "1990" in (res.get("born") or "") and res.get("apple") == {"year": 2000, "desc": None}
        return ok, f"{res}"
    check("Geburtstage aus dem Adressbuch als Kalender (Apple ohne Jahr ohne „Geboren 1604“)", birthdays, results)

    def mac_photos_off():
        # Einstellungsseite (setSetting) direkt über das Experiment-Modul; den
        # Abgleich mit den macOS-Kontakten (osascript, echte Kontakte) dabei abklemmen
        res = m.js('''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
          const MP = Cu.evalInSandbox("MacPhotos", g); const api = Cu.evalInSandbox("mailCards.prototype.getAPI({})", g).mailCards;
          const PREF = "extensions.mailcards.macContactPhotos"; const dir = PathUtils.join(PathUtils.profileDir, "mail-cards-photos");
          const sync = MP.sync; MP.sync = async () => {};
          try {
            // schon einmal eingerichtet: index.json vorhanden, Pref ohne Wert
            await IOUtils.makeDirectory(dir, { ignoreExisting: true }); await IOUtils.writeUTF8(PathUtils.join(dir, "index.json"), "[]");
            Services.prefs.clearUserPref(PREF);
            const before = (await api.getSettings()).macContactPhotos;
            await api.setSetting("macContactPhotos", false);
            return { before, hasValue: Services.prefs.prefHasUserValue(PREF), enabled: await MP.enabled(), shown: (await api.getSettings()).macContactPhotos };
          } finally {
            await IOUtils.remove(dir, { recursive: true }).catch(() => {}); Services.prefs.clearUserPref(PREF); MP.sync = sync;
          }''' % ADDON_ID)
        ok = res["before"] is True and res["hasValue"] and res["enabled"] is False and res["shown"] is False
        return ok, f"{res}"
    check("Kontaktfotos: Ausschalten auf der Einstellungsseite bleibt aus (trotz vorhandener Fotoliste)", mac_photos_off, results)

    def local_ab_photo():
        # Foto im lokalen Adressbuch liegt als Datei in <Profil>/Photos (file:-Adresse)
        res = m.js('''
          const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
          const canvas = d.createElementNS("http://www.w3.org/1999/xhtml", "canvas"); canvas.width = canvas.height = 64;
          const ctx = canvas.getContext("2d"); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, 64, 64);
          ctx.fillStyle = "#c33"; ctx.beginPath(); ctx.arc(32, 32, 22, 0, 7); ctx.fill();
          const blob = await new Promise(r => canvas.toBlob(r, "image/jpeg"));
          await IOUtils.makeDirectory(PathUtils.join(PathUtils.profileDir, "Photos"), { ignoreExisting: true });
          await IOUtils.write(PathUtils.join(PathUtils.profileDir, "Photos", "halo-foto.jpg"), new Uint8Array(await blob.arrayBuffer()));
          // zu große Fotodatei (über 2 MB): nicht abgeschnitten verwenden
          const big = new Uint8Array(2.5 * 1024 * 1024); big.set([0xFF, 0xD8, 0xFF, 0xE0]);
          await IOUtils.write(PathUtils.join(PathUtils.profileDir, "Photos", "halo-gross.jpg"), big);
          const book = MailServices.ab.getDirectory("jsaddrbook://abook.sqlite");
          const newCard = (name, email, photo) => { const c = Cc["@mozilla.org/addressbook/cardproperty;1"].createInstance(Ci.nsIAbCard);
            c.displayName = name; c.primaryEmail = email; c.setProperty("PhotoName", photo); return book.addCard(c); };
          const card = newCard("Fiona Foto", "fiona.foto@example.invalid", "halo-foto.jpg");
          const bigCard = newCard("Gustav Gross", "gustav.gross@example.invalid", "halo-gross.jpg");
          try {
            const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
            const enh = Cu.evalInSandbox("enhancer", ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global);
            const bigSrc = await enh.avatars.fromAddressBook("gustav.gross@example.invalid");
            try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
            const root = MailServices.accounts.localFoldersServer.rootFolder;
            if (!root.containsChildNamed("Fotos")) { root.createSubfolder("Fotos", null); await wait(800); }
            const f = root.getChildNamed("Fotos");
            f.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessage("From - Sat Oct 17 10:00:00 2026\\r\\nFrom: Fiona Foto <fiona.foto@example.invalid>\\r\\nSubject: Halo Foto\\r\\nDate: Sat, 17 Oct 2026 10:00:00 +0200\\r\\nMessage-ID: <halo-foto@example.invalid>\\r\\n\\r\\nTest\\r\\n");
            const a3 = await toMail(); a3.displayFolder(f.URI);
            const img = await until(() => a3.document.querySelector('#threadTree tr[is="thread-card"] .mc-avatar img[src^="data:"]'), 10000);
            const av = a3.document.querySelector('#threadTree tr[is="thread-card"] .mc-avatar');
            return { photoURL: card.photoURL.slice(0, 8), img: !!img, avatar: av ? (av.querySelector("img")?.getAttribute("src") || "").slice(0, 16) || av.textContent : null,
                     big: bigSrc ? bigSrc.length : null, visibility: d.visibilityState, rows: a3.gDBView?.rowCount };
          } finally {
            book.deleteCards([card, bigCard]);
          }''' % ADDON_ID)
        # ohne gezeichnete Karten (verdecktes Testfenster) lässt sich das Bild nicht prüfen
        if not res["img"] and res.get("visibility") == "hidden":
            return res["big"] is None, f"Testfenster verdeckt (Karten nicht gezeichnet) – Mailliste übersprungen {res}"
        ok = res["photoURL"].startswith("file:") and res["img"] and res["big"] is None
        return ok, f"{res}"
    check("Kontaktfotos: Foto aus dem lokalen Adressbuch (Datei im Profil) in der Mailliste", local_ab_photo, results)

    def net_guard():
        # Absenderbilder kommen von Adressen, die der Absender bestimmt (BIMI,
        # Startseite): eine Umleitung ins lokale Netz darf gar nicht erst
        # verbunden werden; Zeitlimit und Größengrenze gelten für die ganze
        # Antwort. Lokaler Server unter einem öffentlichen Namen (localDomains)
        if not shutil.which("openssl"):
            return True, "kein openssl – übersprungen"
        host = "halo-netz.example.org"
        port, der, hits, posts, close = local_https(host)
        try:
            res = m.js('''
              const HOST = %s, PORT = %d;
              const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
              const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
              const get = Cu.evalInSandbox("fetchWithTimeout", g);
              const cert = Cc["@mozilla.org/security/x509certdb;1"].getService(Ci.nsIX509CertDB).constructX509FromBase64(%s);
              const co = Cc["@mozilla.org/security/certoverride;1"].getService(Ci.nsICertOverrideService);
              co.rememberValidityOverride(HOST, PORT, {}, cert, true);
              Services.prefs.setStringPref("network.dns.localDomains", HOST);
              const run = async (path, opts) => {
                const t = Date.now();
                try {
                  const r = await get(w, `https://${HOST}:${PORT}${path}`, opts);
                  const text = await r.text();
                  return { ok: r.ok, status: r.status, url: r.url, len: text.length, text: text.slice(-5), ms: Date.now() - t };
                } catch (e) { return { error: String(e?.message || e), ms: Date.now() - t }; }
              };
              try {
                return { redirect: await run("/umleitung"), follow: await run("/weiter"), auth: await run("/anmelden"),
                         endless: await run("/endlos", { max: 512 * 1024 }), head: await run("/endlos", { max: 200000, truncate: true }),
                         stall: await run("/stumm"),
                         post: await run("/abmelden", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
                                                        body: "List-Unsubscribe=One-Click", max: 0, truncate: true }),
                         postRedirect: await run("/abmelden-umleitung", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
                                                        body: "List-Unsubscribe=One-Click", max: 0, truncate: true, followRedirects: false }) };
              } finally {
                co.clearValidityOverride(HOST, PORT, {});
                Services.prefs.clearUserPref("network.dns.localDomains");
              }''' % (json.dumps(host), port, ADDON_ID, json.dumps(der)))
        finally:
            close()
        res["device"], res["posts"] = hits, posts
        ok = (res["redirect"].get("error") == "blocked redirect" and not hits
              and res["follow"].get("ok") and res["follow"].get("url", "").endswith("/ziel") and res["follow"].get("text") == "Grüße"
              and res["auth"].get("status") == 401
              and res["endless"].get("error") == "too large" and res["head"].get("len") == 200000
              and res["stall"].get("error") == "timeout" and res["stall"]["ms"] < 15000
              and res["post"].get("ok") and res["postRedirect"].get("ok") and res["postRedirect"].get("status") == 303
              and posts == ["List-Unsubscribe=One-Click"] * 2)
        return ok, f"{res}"
    check("Absenderbilder: Umleitung ins lokale Netz gesperrt, bevor verbunden wird; Zeitlimit und Größengrenze für die ganze Antwort; Ein-Klick-Abmeldung mit Umleitung gilt als erledigt", net_guard, results)

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

    def auto_update():
        res = m.js('''
          const last = await until(() => Services.prefs.getIntPref("extensions.mailcards.autoUpdateLast", 0), 25000);
          // seit dem Start dieses Thunderbird-Prozesses (statt fester 10 Minuten: unter Last dauert der Lauf länger)
          const start = Math.floor(Services.startup.getStartupInfo().process / 1000);
          return { last, ageSec: last ? Math.round(Date.now() / 1000 - last) : null, sinceStart: last ? last - start : null };''')
        return bool(res["last"]) and res["sinceStart"] is not None and res["sinceStart"] >= -5, f"Update-Prüfung beim Start gelaufen: {res}"
    check("Updates: Prüfung beim Start", auto_update, results)

    ENH_JS = '''
          const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const g = ExtensionParent.GlobalManager.getExtension("%s").experimentAPIManager.global;
          const enh = Cu.evalInSandbox("enhancer", g);
          const openBooks = async () => { tm.openTab("addressBookTab", {});
            return until(() => { const c = tm.currentTabInfo?.browser?.contentWindow; return c?.document?.getElementById("mcBooksHeader") && c; }, 8000); };''' % ADDON_ID

    def window_callbacks():
        # Seitenleisten-Tooltip, Popover „Neu“ und Today-Pane-Sync gehören dem Fenster, nicht dem gemeinsamen Enhancer
        res = m.js(ENH_JS + '''
          await toMail();
          return { onEnhancer: ["openNewPopupAbove", "openNewPopupBelow", "lastNewAnchor", "todayTopSync", "sidebarTip", "sideHidden", "toggleSpaceSidebar"].filter(k => k in enh),
                   sync: typeof w.__mcTodayTopSync };''')
        return not res["onEnhancer"] and res["sync"] == "function", f"{res}"
    check("Erweiterung: Fenster-Callbacks je Hauptfenster statt am gemeinsamen Enhancer", window_callbacks, results)

    def books_leak():
        # Restorer eines geschlossenen Adressbuch-Tabs werden verworfen (halten das Fenster nicht fest);
        # nach dem ersten Öffnen (einmalige Hooks) wächst die Liste aller Restorer je Öffnen und Schließen nicht mehr
        res = m.js(ENH_JS + '''
          const cw = await openBooks();
          const fns = cw ? [...(enh.winRestorers.get(cw) || [])] : [];
          const held = fns.filter(f => enh.restorers.includes(f)).length;
          tm.closeTab(tm.currentTabInfo);
          const freed = await until(() => fns.every(f => !enh.restorers.includes(f)), 6000);
          await toMail(); await wait(800);
          const n1 = enh.restorers.length;
          const cw2 = await openBooks(); await wait(800);
          const open2 = enh.restorers.length;
          tm.closeTab(tm.currentTabInfo); await toMail();
          const n2 = await until(() => enh.restorers.length == n1 && n1, 6000) || enh.restorers.length;
          return { tab: !!cw && !!cw2, fns: fns.length, held, freed, n1, open2, n2 };''')
        ok = res["tab"] and res["fns"] > 0 and res["held"] == res["fns"] and res["freed"] and res["n2"] == res["n1"]
        return ok, f"{res}"
    check("Erweiterung: Restorer geschlossener Adressbuch-Tabs werden verworfen", books_leak, results)

    def restart_cycle():
        # wie bei einem Update: stop() räumt auf (Breiten-Merkmal, Adressbuch-Überschrift, Ordnernamen),
        # ein neuer Start hängt alles wieder an
        res = m.js(ENH_JS + '''
          await toMail();
          const ad = tm.currentAbout3Pane.document;
          const fp = ad.getElementById("folderPane");
          const local = () => ad.querySelector('#folderTree > li[data-mode="all"] li[is="folder-tree-row"][data-server-type="none"]');
          const nameOf = li => li?.querySelector(":scope > .container .name")?.textContent;
          const cw = await openBooks();
          const out = { tab: !!cw, watch0: !!fp.__mcWidthWatch, local0: nameOf(local()) };
          enh.stop();
          out.watch1 = !!fp.__mcWidthWatch;
          // wie nach 3.2.0: deren stop() ließ das Merkmal als „true“ stehen
          fp.__mcWidthWatch = true;
          out.header1 = !!cw?.document.getElementById("mcBooksHeader");
          // Überschrift einer älteren Fassung (ohne Kennung) bleibt stehen: wird ersetzt
          if (cw) { const old = cw.document.createElement("div"); old.id = "mcBooksHeader"; cw.document.getElementById("books")?.before(old); }
          out.local1 = nameOf(local()); out.server = local()?._serverName;
          Cu.evalInSandbox("enhancer = new CardEnhancer({}); enhancer.start();", g);
          const owner = Cu.evalInSandbox("HOOK_OWNER", g);
          out.header2 = !!(await until(() => cw?.document.getElementById("mcBooksHeader")?.__mcOwner === owner, 8000));
          out.headers2 = cw ? cw.document.querySelectorAll("#mcBooksHeader").length : 0;
          out.watch2 = await until(() => typeof fp.__mcWidthWatch == "object", 8000);
          out.local2 = await until(() => nameOf(local()) == out.local0 && out.local0, 6000);
          tm.closeTab(tm.currentTabInfo); await toMail();
          return out;''')
        ok = (res["tab"] and res["watch0"] and not res["watch1"] and res["watch2"] and not res["header1"] and res["header2"] and res["headers2"] == 1
              and res["local0"] != res["server"] and res["local1"] == res["server"] and res["local2"])
        return ok, f"{res}"
    check("Erweiterung: Aus- und Einschalten setzt Ordnernamen und Einfügungen zurück und hängt sie wieder an; Einfügungen einer älteren Fassung werden ersetzt", restart_cycle, results)

    def local_collapse():
        # „Auf meinem Mac“ klappt auch nach einer Suche zu: der eigene Suchordner
        # (mit Trefferzahl) zählt nicht als Inhalt, ein Ordner mit Mails schon
        res = m.js(ENH_JS + '''
          const sf = enh.searchFolder(true);
          const empty = { hasSubFolders: false, getTotalMessages: () => 0 };
          const full = { hasSubFolders: false, getTotalMessages: () => 3 };
          // gleicher Name, aber kein eigener Suchordner: zählt mit Trefferzahl
          const foreign = { name: sf?.name, hasSubFolders: false, getTotalMessages: () => 3, getFlag: () => true, parent: sf?.parent, server: null };
          const root = subFolders => ({ subFolders });
          // Suchordner mit Treffern (wie nach einer Suche): als eigener Suchordner erkannt
          const hits = { hasSubFolders: false, getTotalMessages: () => 5 };
          const own = enh.isSearchFolder;
          enh.isSearchFolder = f => f === hits || own.call(enh, f);
          try {
            return { search: own.call(enh, sf), onlySearch: enh.localIsEmpty(root([sf, empty])), withHits: enh.localIsEmpty(root([hits, empty])),
                     withMail: enh.localIsEmpty(root([sf, hits, empty, full])), foreign: enh.localIsEmpty(root([foreign, empty])) };
          } finally {
            delete enh.isSearchFolder;
          }''')
        ok = res["search"] and res["onlySearch"] is True and res["withHits"] is True and res["withMail"] is False and res["foreign"] is False
        return ok, f"{res}"
    check("Ordnerliste: „Auf meinem Mac“ klappt trotz Suchordner mit Treffern zu, mit eigenen Mails nicht", local_collapse, results)

    def errors():
        res = m.js("""
          const p = PathUtils.join(PathUtils.profileDir, "mail-cards-debug.log");
          let lines = []; try { lines = (await IOUtils.readUTF8(p)).split("\\n"); } catch {}
          return lines.filter(l => /error|fehler/i.test(l) && !/preview stats/.test(l)).slice(0, 5);""")
        return not res, "; ".join(res) or "keine Fehler im Protokoll"
    check("Fehlerprotokoll der Erweiterung leer", errors, results)


if __name__ == "__main__":
    main()
