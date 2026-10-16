#!/usr/bin/env python3
"""Fügt chrome/spaces.css als markierten Block in chrome/userChrome.css ein (ersetzt einen vorhandenen Block)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
START = "/* ==== Bereiche: Kalender, Aufgaben, Adressbuch, Chat, Einstellungen ==== */"
END = "/* ==== Ende Bereiche ==== */"
block = open(os.path.join(HERE, "spaces.css")).read().strip()
if not block.startswith(START):
    raise SystemExit("spaces.css muss mit der Start-Markierung beginnen")
block = block + "\n" + END + "\n"
p = os.path.join(HERE, "userChrome.css")
css = open(p).read()
if START in css:
    a = css.index(START)
    b = css.index(END, a) + len(END)
    css = css[:a] + block.rstrip("\n") + css[b:]
else:
    css = css.rstrip("\n") + "\n\n" + block
open(p, "w").write(css)
print("Bereiche-Block eingefügt:", len(block), "Zeichen")
