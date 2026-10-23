#!/usr/bin/env python3
"""Baut das Komplettpaket wie build.sh, aber ohne zsh/zip – läuft auch unter Windows.

Design (CSS) + Symbole + Erweiterung → dist/halo-spaces-<version>.xpi
und die Store-Variante dist/halo-spaces-<version>-atn.xpi (ohne update_url).
Aufruf: python build.py
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(ROOT, "extension")


def pack(out, manifest=None):
    """Packt extension/ als XPI; versteckte Dateien und Ordner (wie zip -x '.*') bleiben draußen.
    manifest: geänderter Inhalt für manifest.json (Store-Variante)."""
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(EXT):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for f in sorted(files):
                if f.startswith("."):
                    continue
                path = os.path.join(base, f)
                name = os.path.relpath(path, EXT).replace(os.sep, "/")
                if name == "manifest.json" and manifest is not None:
                    z.writestr(name, manifest)
                else:
                    z.write(path, name)


def main():
    # Bereiche-CSS in userChrome.css einfügen, dann als theme.css in die Erweiterung
    subprocess.run([sys.executable, os.path.join(ROOT, "chrome", "merge_spaces.py")], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(os.path.join(ROOT, "chrome", "userChrome.css"), os.path.join(EXT, "theme.css"))

    manifest = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))
    version = manifest["version"]
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", f"halo-spaces-{version}.xpi")
    pack(out)

    # Variante für addons.thunderbird.net: ohne update_url – dort kommen Updates
    # vom Store selbst; der Store verlangt für Experiment-Add-ons eine Obergrenze
    g = manifest["browser_specific_settings"]["gecko"]
    g.pop("update_url", None)
    g["strict_max_version"] = open(os.path.join(ROOT, "store", "max-version"), encoding="utf-8").read().strip()
    pack(os.path.join(ROOT, "dist", f"halo-spaces-{version}-atn.xpi"), json.dumps(manifest, indent=2, ensure_ascii=False))
    print(os.path.relpath(out, ROOT).replace(os.sep, "/"))


if __name__ == "__main__":
    main()
