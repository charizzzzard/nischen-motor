"""Befehle:  motor build | motor check | motor neu <ordner> | motor version"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__
from .build import MOTOR_DIR, build
from .check import bericht
from .inhalt import BuildError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="motor", description="nischen-motor: Website bauen und prüfen")
    unter = parser.add_subparsers(dest="befehl", required=True)
    for name, hilfe in (("build", "Website nach --out bauen"), ("check", "bauen und Qualität prüfen")):
        p = unter.add_parser(name, help=hilfe)
        p.add_argument("--site", default=".", help="Ordner mit site.yaml (Standard: aktueller Ordner)")
        p.add_argument("--out", default=None, help="Ausgabeordner (Standard: <site>/_site)")
    neu = unter.add_parser("neu", help="neue Website aus der Vorlage anlegen")
    neu.add_argument("ziel", help="Zielordner (darf nicht existieren oder muss leer sein)")
    unter.add_parser("version", help="Version anzeigen")
    args = parser.parse_args(argv)

    if args.befehl == "version":
        print(__version__)
        return 0
    if args.befehl == "neu":
        ziel = Path(args.ziel)
        if ziel.exists() and any(p.name != ".git" for p in ziel.iterdir()):
            print(f"FEHLER: {ziel} ist nicht leer", file=sys.stderr)
            return 1
        shutil.copytree(MOTOR_DIR / "vorlage", ziel, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        print(f"Neue Website angelegt in {ziel}. Nächste Schritte: siehe {ziel}/CLAUDE.md")
        return 0

    site = Path(args.site)
    out = Path(args.out) if args.out else site / "_site"
    if args.befehl == "check":
        return bericht(site, out)
    try:
        daten = build(site, out)
    except BuildError as exc:
        print(f"BUILD-FEHLER: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(daten['artikel'])} Artikel, {len(daten['seiten'])} Seiten, "
          f"{len(daten['kategorien'])} Kategorien -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
