#!/usr/bin/env python3
"""Lädt eine neue Version auf addons.thunderbird.net hoch (gelisteter Kanal).

Die Schlüssel liest das Skript aus ~/.config/halo-spaces/atn.env:
    ATN_ISSUER=user:…
    ATN_SECRET=…
(Datei selbst anlegen, chmod 600 – die Schlüssel gehören nicht ins Repository.)

    python3 store/atn_upload.py --check            # nur prüfen, ob die Schlüssel gelten
    python3 store/atn_upload.py 3.0.96             # dist/halo-spaces-3.0.96-atn.xpi hochladen

Die allererste Einreichung (mit Beschreibung und Screenshots) läuft über das
Formular im Developer Hub; danach reicht dieses Skript für jede neue Version.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

API = "https://addons.thunderbird.net/api/v4"
ADDON_ID = "mail-cards@sebastian.local"
ENV = os.path.expanduser("~/.config/halo-spaces/atn.env")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def keys():
    if not os.path.exists(ENV):
        sys.exit(f"{ENV} fehlt (ATN_ISSUER=… und ATN_SECRET=…)")
    if os.stat(ENV).st_mode & 0o077:
        sys.exit(f"{ENV} ist für andere lesbar – chmod 600 {ENV}")
    values = {}
    for line in open(ENV):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.strip().split("=", 1)
            values[k.strip()] = v.strip().strip('"')
    return values["ATN_ISSUER"], values["ATN_SECRET"]


def token(issuer, secret):
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    now = int(time.time())
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps({"iss": issuer, "jti": uuid.uuid4().hex, "iat": now, "exp": now + 60}).encode())
    sig = b64(hmac.new(secret.encode(), head + b"." + body, hashlib.sha256).digest())
    return (head + b"." + body + b"." + sig).decode()


def call(method, path, data=None, content_type=None):
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "JWT " + token(*keys()))
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def upload(version):
    xpi = os.path.join(ROOT, "dist", f"halo-spaces-{version}-atn.xpi")
    if not os.path.exists(xpi):
        sys.exit(f"{xpi} fehlt – zuerst ./release.sh {version}")
    # nur für ein schon gelistetes Add-on – sonst würde ATN einen neuen,
    # nicht gelisteten Eintrag anlegen (die erste Einreichung läuft übers Formular)
    status, _ = call("GET", f"/addons/addon/{ADDON_ID}/")
    if status != 200:
        sys.exit("halo.spaces ist auf ATN noch nicht gelistet – erste Version über den Developer Hub einreichen")
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="channel"\r\n\r\nlisted\r\n'.encode(),
        (f'--{boundary}\r\nContent-Disposition: form-data; name="upload"; filename="{os.path.basename(xpi)}"\r\n'
         "Content-Type: application/x-xpinstall\r\n\r\n").encode() + open(xpi, "rb").read() + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    path = f"/addons/{ADDON_ID}/versions/{version}/"
    status, res = call("PUT", path, b"".join(parts), f"multipart/form-data; boundary={boundary}")
    if status not in (200, 201, 202):
        sys.exit(f"Hochladen fehlgeschlagen ({status}): {res}")
    print("Hochgeladen, ATN prüft das Paket …")
    for _ in range(40):
        time.sleep(15)
        status, res = call("GET", path)
        if res.get("processed"):
            if res.get("valid"):
                print("Angenommen – die Version wartet jetzt auf die Prüfung durch ATN.")
                return
            sys.exit("Von der automatischen Prüfung abgelehnt:\n" + json.dumps(res.get("validation_results"), indent=1)[:4000])
    sys.exit("ATN hat das Paket noch nicht fertig geprüft – Status später im Developer Hub ansehen.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        status, res = call("GET", "/accounts/profile/")
        if status == 200:
            print(f"Schlüssel gültig – angemeldet als {res.get('name') or res.get('username')}")
        else:
            sys.exit(f"Schlüssel ungültig oder abgelaufen ({status}): {res}")
    elif len(sys.argv) == 2:
        upload(sys.argv[1])
    else:
        sys.exit(__doc__)
