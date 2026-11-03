"""Inhalte laden: Frontmatter, Markdown, Datenmodell."""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import markdown
import yaml

MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
LESETEMPO_WOERTER_PRO_MINUTE = 200
ARTIKEL_PFLICHTFELDER = (
    "titel", "beschreibung", "kategorie", "veroeffentlicht",
    "aktualisiert", "geprueft", "kurz_gesagt", "quellen",
)
SEITENTYPEN = ("ratgeber", "vergleich", "werkzeug")


class BuildError(Exception):
    """Fehler in Inhalten oder Konfiguration, der den Build abbricht."""


def slugify(text: str, sep: str = "-") -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", sep, text).strip(sep)


def datum_de(d: dt.date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def lese_frontmatter(pfad: Path) -> tuple[dict, str]:
    text = pfad.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise BuildError(f"{pfad.name}: Frontmatter fehlt (Datei muss mit --- beginnen)")
    try:
        _, kopf, rumpf = text.split("---\n", 2)
    except ValueError as exc:
        raise BuildError(f"{pfad.name}: Frontmatter nicht abgeschlossen") from exc
    try:
        daten = yaml.safe_load(kopf) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"{pfad.name}: Frontmatter ist kein gültiges YAML ({exc})") from exc
    if not isinstance(daten, dict):
        raise BuildError(f"{pfad.name}: Frontmatter ist kein YAML-Objekt")
    return daten, rumpf


def neues_markdown() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=["extra", "admonition", "sane_lists", "toc"],
        extension_configs={
            "toc": {"slugify": lambda value, separator: slugify(value, separator), "toc_depth": "2"}
        },
        output_format="html",
    )


def text_woerter(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html).split())


@dataclass
class Artikel:
    slug: str
    quelle: Path
    meta: dict
    html: str
    toc: list[dict]
    woerter: int
    kurz_html: str
    url: str
    partner_alle: list[str] = field(default_factory=list)
    partner_aktiv: list[str] = field(default_factory=list)
    vergleiche: list[dict] = field(default_factory=list)
    verwandte: list["Artikel"] = field(default_factory=list)

    @property
    def lesezeit(self) -> int:
        return max(1, math.ceil(self.woerter / LESETEMPO_WOERTER_PRO_MINUTE))

    @property
    def seitentyp(self) -> str:
        return self.meta.get("seitentyp", "ratgeber")

    def __getattr__(self, name):  # erlaubt artikel.titel im Template
        try:
            return self.__dict__["meta"][name]
        except KeyError:
            raise AttributeError(name) from None


@dataclass
class Seite:
    slug: str
    meta: dict
    html: str

    @property
    def url(self) -> str:
        return self.meta.get("pfad", f"/{self.slug}/")


def artikel_url(site: dict, slug: str) -> str:
    praefix = str(site.get("artikel_praefix", "artikel")).strip("/")
    return f"/{praefix}/{slug}/" if praefix else f"/{slug}/"


def pruefe_artikel_meta(pfad: Path, meta: dict, kategorien: set[str]) -> None:
    fehlend = [f for f in ARTIKEL_PFLICHTFELDER if not meta.get(f)]
    if fehlend:
        raise BuildError(f"{pfad.name}: Pflichtfelder fehlen: {', '.join(fehlend)}")
    if meta["kategorie"] not in kategorien:
        raise BuildError(f"{pfad.name}: unbekannte Kategorie {meta['kategorie']!r}")
    for feld in ("veroeffentlicht", "aktualisiert", "geprueft"):
        if not isinstance(meta[feld], dt.date):
            raise BuildError(f"{pfad.name}: {feld} muss ein Datum JJJJ-MM-TT sein")
    if meta.get("seitentyp", "ratgeber") not in SEITENTYPEN:
        raise BuildError(f"{pfad.name}: seitentyp muss einer von {', '.join(SEITENTYPEN)} sein")
    if not isinstance(meta["quellen"], list):
        raise BuildError(f"{pfad.name}: quellen muss eine Liste sein")
    skripte = meta.get("skripte") or []
    if not isinstance(skripte, list) or not all(isinstance(s, str) and s.startswith("/") for s in skripte):
        raise BuildError(f"{pfad.name}: skripte muss eine Liste lokaler Pfade sein (beginnend mit /)")
