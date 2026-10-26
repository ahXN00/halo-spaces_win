"""Lokale Testserver für halo_test.py: SMTP und IMAP, nur auf 127.0.0.1, ohne TLS
und mit erfundenen Daten. Gerade so viel IMAP, wie Thunderbird für ein Konto
braucht (Anmelden, Ordner, Abrufen, Flaggen, Kopieren, Anhängen, IDLE) – damit
lassen sich Oberflächen prüfen, die ein Konto mit Server voraussetzen
(Abrufen-Menüs, Senden, Senden rückgängig, Abonnieren, Fehlerzustände).

    servers = MailServers()          # startet beide auf freien Ports
    servers.imap.add("INBOX", raw)   # Mail in einen Ordner legen
    servers.smtp.sent                # gesendete Mails (Absender, Empfänger, Text)
    servers.close()
"""

import re
import socketserver
import threading
import time

USER = "halo"
PASSWORD = "halo-test"


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # Thunderbird trennt Verbindungen beim Beenden einfach – das ist kein Fehler
        import sys
        if not isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            super().handle_error(request, client_address)


# ---------------------------------------------------------------- SMTP

class SMTPStore:
    def __init__(self):
        self.sent = []          # [(mail_from, [rcpt], data)]
        self.fail_next = 0      # die nächsten n Mails mit 554 ablehnen (Fehlerzustand)
        self.lock = threading.Lock()


def _smtp_handler(store):
    class Handler(socketserver.StreamRequestHandler):
        def send(self, line):
            self.wfile.write((line + "\r\n").encode())

        def handle(self):
            self.send("220 halo.test ESMTP Testserver")
            mail_from, rcpts = None, []
            while True:
                raw = self.rfile.readline()
                if not raw:
                    return
                line = raw.decode(errors="replace").rstrip("\r\n")
                cmd = line.split(" ", 1)[0].upper()
                if cmd in ("EHLO", "HELO"):
                    self.wfile.write(b"250-halo.test\r\n250-8BITMIME\r\n250 SIZE 10485760\r\n")
                elif cmd == "MAIL":
                    mail_from, rcpts = line[10:].strip(), []
                    self.send("250 OK")
                elif cmd == "RCPT":
                    rcpts.append(line[8:].strip())
                    self.send("250 OK")
                elif cmd == "DATA":
                    self.send("354 Ende mit <CRLF>.<CRLF>")
                    data = []
                    while True:
                        part = self.rfile.readline()
                        if not part or part in (b".\r\n", b".\n"):
                            break
                        data.append(part[1:] if part.startswith(b"..") else part)
                    with store.lock:
                        if store.fail_next > 0:
                            store.fail_next -= 1
                            self.send("554 Abgelehnt (Testserver)")
                            continue
                        store.sent.append((mail_from, rcpts, b"".join(data).decode(errors="replace")))
                    self.send("250 OK angenommen")
                elif cmd == "RSET":
                    mail_from, rcpts = None, []
                    self.send("250 OK")
                elif cmd == "NOOP":
                    self.send("250 OK")
                elif cmd == "QUIT":
                    self.send("221 Tschüss")
                    return
                else:
                    self.send("502 Nicht unterstützt")
    return Handler


# ---------------------------------------------------------------- IMAP

class Message:
    def __init__(self, uid, raw, flags=()):
        self.uid = uid
        self.raw = raw.replace("\r\n", "\n").replace("\n", "\r\n").encode()
        self.flags = set(flags)
        self.date = time.strftime("%d-%b-%Y %H:%M:%S +0000", time.gmtime())

    def header(self):
        return self.raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"

    def header_fields(self, names, negate=False):
        names = {n.lower() for n in names}
        out, keep = [], False
        for line in self.header().split(b"\r\n"):
            if not line:
                continue
            if line[:1] in (b" ", b"\t"):
                if keep:
                    out.append(line)
                continue
            name = line.split(b":", 1)[0].decode(errors="replace").lower()
            keep = (name in names) != negate
            if keep:
                out.append(line)
        return b"\r\n".join(out) + b"\r\n\r\n"

    def text(self):
        parts = self.raw.split(b"\r\n\r\n", 1)
        return parts[1] if len(parts) > 1 else b""


class Mailbox:
    def __init__(self, name):
        self.name = name
        self.messages = []
        self.next_uid = 1
        self.uidvalidity = int(time.time()) % 100000 + 1
        self.subscribed = True


class IMAPStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.boxes = {}
        for name in ("INBOX", "Sent", "Drafts", "Trash", "Archive", "Projekte"):
            self.boxes[name] = Mailbox(name)
        self.boxes["Projekte"].subscribed = False  # für den Abonnieren-Dialog
        self.fail_login = False
        self.log = []  # empfangene Befehle (zur Fehlersuche)

    def add(self, box, raw, flags=()):
        with self.lock:
            mb = self.boxes.setdefault(box, Mailbox(box))
            mb.messages.append(Message(mb.next_uid, raw, flags))
            mb.next_uid += 1


_TOKEN = re.compile(r'\(|\)|\[|\]|"(?:[^"\\]|\\.)*"|\{\d+\}|[^\s()\[\]]+')


def _imap_handler(store):
    class Handler(socketserver.StreamRequestHandler):
        def out(self, data):
            if isinstance(data, str):
                data = data.encode()
            self.wfile.write(data + b"\r\n")

        def read_command(self):
            line = self.rfile.readline()
            if not line:
                return None
            data = line
            # Literale {n}: Inhalt nachlesen und getrennt merken (Platzhalter LITERALn)
            self.literals = []
            while True:
                m = re.search(rb"\{(\d+)\+?\}\r?\n$", data)
                if not m:
                    break
                if not m.group(0).startswith(b"{" + m.group(1) + b"+"):
                    self.out("+ weiter")
                self.literals.append(self.rfile.read(int(m.group(1))))
                data = data[:m.start()] + f"LITERAL{len(self.literals) - 1}".encode() + self.rfile.readline()
            return data.decode(errors="replace").rstrip("\r\n")

        def handle(self):
            self.box = None
            self.out("* OK [CAPABILITY IMAP4rev1 IDLE NAMESPACE UIDPLUS ID ENABLE AUTH=PLAIN] halo.test IMAP Testserver bereit")
            while True:
                line = self.read_command()
                if line is None:
                    return
                if not line.strip():
                    continue
                store.log.append(line[:200])
                tag, _, rest = line.partition(" ")
                cmd, _, args = rest.partition(" ")
                cmd = cmd.upper()
                uid = False
                if cmd == "UID":
                    uid = True
                    cmd, _, args = args.partition(" ")
                    cmd = cmd.upper()
                try:
                    if self.dispatch(tag, cmd, args, uid) == "bye":
                        return
                except Exception as e:  # Testserver: Fehler als BAD melden statt abzubrechen
                    self.out(f"{tag} BAD {type(e).__name__}: {e}")

        def strip(self, s):
            s = s.strip()
            return s[1:-1].replace('\\"', '"') if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s

        def dispatch(self, tag, cmd, args, uid):
            ok = lambda text="erledigt": self.out(f"{tag} OK {cmd} {text}")
            if cmd == "CAPABILITY":
                self.out("* CAPABILITY IMAP4rev1 IDLE NAMESPACE UIDPLUS ID ENABLE AUTH=PLAIN")
                ok()
            elif cmd == "NOOP" or cmd == "CHECK":
                if self.box:
                    self.known = len(self.box.messages)
                    self.out(f"* {self.known} EXISTS")
                ok()
            elif cmd == "LOGIN":
                lit = lambda x: self.literals[int(x[7:])].decode() if x.startswith("LITERAL") else self.strip(x)
                user, pw = [lit(x) for x in _TOKEN.findall(args)[:2]]
                if store.fail_login or user != USER or pw != PASSWORD:
                    self.out(f"{tag} NO [AUTHENTICATIONFAILED] Anmeldung abgelehnt")
                else:
                    ok()
            elif cmd == "AUTHENTICATE":
                self.out("+ ")
                import base64
                cred = base64.b64decode(self.rfile.readline().strip() or b"").split(b"\0")
                if store.fail_login or len(cred) < 3 or cred[1].decode() != USER or cred[2].decode() != PASSWORD:
                    self.out(f"{tag} NO [AUTHENTICATIONFAILED] Anmeldung abgelehnt")
                else:
                    ok()
            elif cmd == "LOGOUT":
                self.out("* BYE Tschüss")
                ok()
                return "bye"
            elif cmd == "ID":
                self.out('* ID ("name" "halo-testserver")')
                ok()
            elif cmd == "ENABLE":
                self.out("* ENABLED")
                ok()
            elif cmd == "NAMESPACE":
                self.out('* NAMESPACE (("" "/")) NIL NIL')
                ok()
            elif cmd in ("LIST", "LSUB"):
                ref, pattern = [self.strip(x) for x in _TOKEN.findall(args)[-2:]]
                rx = re.compile("^" + re.escape(pattern).replace(r"\*", ".*").replace("%", "[^/]*") + "$")
                with store.lock:
                    for name, mb in store.boxes.items():
                        if rx.match(name) and (cmd == "LIST" or mb.subscribed):
                            special = {"Sent": r" \Sent", "Drafts": r" \Drafts", "Trash": r" \Trash", "Archive": r" \Archive"}.get(name, "")
                            self.out(f'* {cmd} (\\HasNoChildren{special}) "/" "{name}"')
                ok()
            elif cmd in ("SUBSCRIBE", "UNSUBSCRIBE"):
                name = self.strip(args)
                with store.lock:
                    if name in store.boxes:
                        store.boxes[name].subscribed = cmd == "SUBSCRIBE"
                ok()
            elif cmd == "CREATE":
                with store.lock:
                    store.boxes.setdefault(self.strip(args), Mailbox(self.strip(args)))
                ok()
            elif cmd == "DELETE":
                with store.lock:
                    store.boxes.pop(self.strip(args), None)
                ok()
            elif cmd in ("SELECT", "EXAMINE"):
                name = self.strip(args.split(" (")[0])
                mb = store.boxes.get("INBOX" if name.upper() == "INBOX" else name)
                if not mb:
                    self.out(f"{tag} NO Ordner fehlt")
                    return
                self.box = mb
                self.known = len(mb.messages)
                self.out(r"* FLAGS (\Answered \Flagged \Deleted \Seen \Draft $Forwarded $Junk $NotJunk)")
                self.out(r"* OK [PERMANENTFLAGS (\Answered \Flagged \Deleted \Seen \Draft $Forwarded $Junk $NotJunk \*)] ok")
                self.out(f"* {len(mb.messages)} EXISTS")
                self.out("* 0 RECENT")
                self.out(f"* OK [UIDVALIDITY {mb.uidvalidity}] ok")
                self.out(f"* OK [UIDNEXT {mb.next_uid}] ok")
                self.out(f"{tag} OK [{'READ-ONLY' if cmd == 'EXAMINE' else 'READ-WRITE'}] {cmd} erledigt")
            elif cmd == "STATUS":
                name = self.strip(_TOKEN.findall(args)[0])
                mb = store.boxes.get("INBOX" if name.upper() == "INBOX" else name)
                if not mb:
                    self.out(f"{tag} NO Ordner fehlt")
                    return
                unseen = sum(1 for m in mb.messages if "\\Seen" not in m.flags)
                self.out(f'* STATUS "{mb.name}" (MESSAGES {len(mb.messages)} UNSEEN {unseen} UIDNEXT {mb.next_uid} UIDVALIDITY {mb.uidvalidity} RECENT 0)')
                ok()
            elif cmd == "APPEND":
                toks = _TOKEN.findall(args)
                name = self.strip(toks[0])
                flags = []
                if "(" in toks:
                    i = toks.index("(")
                    flags = toks[i + 1:toks.index(")")]
                last = toks[-1]
                raw = self.literals[int(last[7:])].decode(errors="replace") if last.startswith("LITERAL") else self.strip(last)
                store.add(name, raw, flags)
                mb = store.boxes[name]
                ok_text = f"[APPENDUID {mb.uidvalidity} {mb.next_uid - 1}] APPEND erledigt"
                self.out(f"{tag} OK {ok_text}")
            elif cmd == "CLOSE":
                self.expunge(silent=True)
                self.box = None
                ok()
            elif cmd == "EXPUNGE":
                self.expunge()
                ok()
            elif cmd == "IDLE":
                # während IDLE neue Mails melden (wie ein echter Server: „* n EXISTS“)
                import select
                self.out("+ idling")
                # (auch, was seit der letzten Meldung an diese Verbindung hinzukam)
                seen = getattr(self, "known", 0)
                while True:
                    ready, _, _ = select.select([self.connection], [], [], 0.3)
                    if ready:
                        line = self.rfile.readline()
                        if not line or line.strip().upper() == b"DONE":
                            break
                    elif self.box and len(self.box.messages) != seen:
                        seen = self.known = len(self.box.messages)
                        self.out(f"* {seen} EXISTS")
                        self.wfile.flush()
                self.out(f"{tag} OK IDLE beendet")
            elif cmd in ("FETCH", "STORE", "SEARCH", "COPY", "MOVE"):
                if not self.box:
                    self.out(f"{tag} NO kein Ordner gewählt")
                    return
                getattr(self, cmd.lower())(tag, args, uid)
            else:
                self.out(f"{tag} BAD unbekannter Befehl {cmd}")

        def expunge(self, silent=False):
            if not self.box:
                return
            with store.lock:
                i = 0
                while i < len(self.box.messages):
                    if "\\Deleted" in self.box.messages[i].flags:
                        self.box.messages.pop(i)
                        if not silent:
                            self.out(f"* {i + 1} EXPUNGE")
                    else:
                        i += 1

        def select_set(self, spec, uid):
            msgs = self.box.messages
            out = []
            top = (msgs[-1].uid if msgs else 0) if uid else len(msgs)
            for part in spec.split(","):
                lo, _, hi = part.partition(":")
                lo = top if lo == "*" else int(lo)
                hi = lo if not hi else (top if hi == "*" else int(hi))
                lo, hi = min(lo, hi), max(lo, hi)
                for seq, m in enumerate(msgs, 1):
                    key = m.uid if uid else seq
                    if lo <= key <= hi and (seq, m) not in out:
                        out.append((seq, m))
            return out

        def fetch(self, tag, args, uid):
            spec, _, items = args.partition(" ")
            items = items.strip()
            if items.startswith("(") and items.endswith(")"):
                items = items[1:-1]
            items_up = items.upper()
            for seq, m in self.select_set(spec, uid):
                parts = []
                if uid or "UID" in items_up:
                    parts.append(f"UID {m.uid}".encode())
                if "FLAGS" in items_up:
                    parts.append(f"FLAGS ({' '.join(sorted(m.flags))})".encode())
                if "RFC822.SIZE" in items_up:
                    parts.append(f"RFC822.SIZE {len(m.raw)}".encode())
                if "INTERNALDATE" in items_up:
                    parts.append(f'INTERNALDATE "{m.date}"'.encode())
                for sect in re.findall(r"(BODY(?:\.PEEK)?\[[^\]]*\](?:<\d+\.\d+>)?|RFC822\.HEADER|RFC822(?![.\w]))", items, re.I):
                    up = sect.upper()
                    peek = ".PEEK" in up
                    inner = re.search(r"\[(.*)\]", sect)
                    inner = inner.group(1) if inner else ""
                    iu = inner.upper()
                    if up == "RFC822.HEADER" or iu == "HEADER":
                        data = m.header()
                    elif iu.startswith("HEADER.FIELDS.NOT"):
                        data = m.header_fields(re.findall(r"[\w-]+", inner[len("HEADER.FIELDS.NOT"):]), negate=True)
                    elif iu.startswith("HEADER.FIELDS"):
                        data = m.header_fields(re.findall(r"[\w-]+", inner[len("HEADER.FIELDS"):]))
                    elif iu == "TEXT" or iu == "1":
                        data = m.text()
                    else:
                        data = m.raw
                    rng = re.search(r"<(\d+)\.(\d+)>", sect)
                    name = re.sub(r"\.PEEK", "", sect, flags=re.I)
                    if rng:
                        start, length = int(rng.group(1)), int(rng.group(2))
                        data = data[start:start + length]
                        name = name.split("<")[0] + f"<{start}>"
                    parts.append(name.encode() + b" {" + str(len(data)).encode() + b"}\r\n" + data)
                    if not peek and up != "RFC822.HEADER":
                        m.flags.add("\\Seen")
                if "BODYSTRUCTURE" in items_up:
                    parts.append(f'BODYSTRUCTURE ("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "8BIT" {len(m.text())} {m.text().count(b"\n")})'.encode())
                self.wfile.write(f"* {seq} FETCH (".encode() + b" ".join(parts) + b")\r\n")
            self.out(f"{tag} OK FETCH erledigt")

        def store(self, tag, args, uid):
            spec, mode, flags = args.split(" ", 2)
            flags = set(re.findall(r"[\\$]?\w+", flags))
            silent = ".SILENT" in mode.upper()
            for seq, m in self.select_set(spec, uid):
                if mode.startswith("+"):
                    m.flags |= flags
                elif mode.startswith("-"):
                    m.flags -= flags
                else:
                    m.flags = set(flags)
                if not silent:
                    self.out(f"* {seq} FETCH (UID {m.uid} FLAGS ({' '.join(sorted(m.flags))}))")
            self.out(f"{tag} OK STORE erledigt")

        def search(self, tag, args, uid):
            keys = args.upper()
            hits = []
            for seq, m in enumerate(self.box.messages, 1):
                if "UNSEEN" in keys and "\\Seen" in m.flags:
                    continue
                if "UNDELETED" in keys and "\\Deleted" in m.flags:
                    continue
                hits.append(str(m.uid if uid else seq))
            self.out("* SEARCH " + " ".join(hits))
            self.out(f"{tag} OK SEARCH erledigt")

        def copy(self, tag, args, uid, move=False):
            spec, _, dest = args.partition(" ")
            dest = self.strip(dest)
            target = store.boxes.get("INBOX" if dest.upper() == "INBOX" else dest)
            if not target:
                self.out(f"{tag} NO [TRYCREATE] Ordner fehlt")
                return
            chosen = self.select_set(spec, uid)
            src, dst = [], []
            with store.lock:
                for _, m in chosen:
                    target.messages.append(Message(target.next_uid, m.raw.decode(errors="replace"), m.flags))
                    src.append(str(m.uid))
                    dst.append(str(target.next_uid))
                    target.next_uid += 1
            if move:
                for _, m in chosen:
                    m.flags.add("\\Deleted")
                self.expunge()
            self.out(f"{tag} OK [COPYUID {target.uidvalidity} {','.join(src)} {','.join(dst)}] erledigt")

        def move(self, tag, args, uid):
            self.copy(tag, args, uid, move=True)

    return Handler


class MailServers:
    def __init__(self):
        self.smtp = SMTPStore()
        self.imap = IMAPStore()
        self._servers = []
        for store, factory, attr in ((self.smtp, _smtp_handler, "smtp_port"), (self.imap, _imap_handler, "imap_port")):
            srv = _Server(("127.0.0.1", 0), factory(store))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            setattr(self, attr, srv.server_address[1])
            self._servers.append(srv)

    def close(self):
        for srv in self._servers:
            srv.shutdown()
            srv.server_close()
