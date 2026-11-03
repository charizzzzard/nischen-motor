"""Bausteine im Text: Vergleichstabellen aus Daten und Partnerlinks.

Vergleich (im Markdown):
    ```vergleich
    daten: rechnungsprogramme
    ```
    liest daten/vergleiche/rechnungsprogramme.yaml der Website.

Partnerlink (im Markdown):
    [Zum Anbieter](partner:sevdesk)
    wird über partner.yaml aufgelöst. Ist der Partner nicht aktiv, entsteht ein normaler Link
    auf fallback_url – ohne Provision, ohne Kennzeichnung.
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from pathlib import Path
from urllib.parse import quote

import yaml
from jinja2 import Environment

from .inhalt import BuildError, datum_de

BLOCK = re.compile(r"^```(vergleich)[ \t]*\n(.*?)\n```[ \t]*$", re.M | re.S)
PARTNER_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PARTNER_LINK = re.compile(r'<a href="partner:([^"]*)"([^>]*)>(.*?)</a>', re.S)


def lade_partner(site_dir: Path) -> dict[str, dict]:
    pfad = site_dir / "partner.yaml"
    if not pfad.exists():
        return {}
    try:
        daten = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"partner.yaml ist kein gültiges YAML ({exc})") from exc
    if not isinstance(daten, dict):
        raise BuildError("partner.yaml muss ein YAML-Objekt sein (id: {…})")
    for pid, p in daten.items():
        if not PARTNER_ID.match(str(pid)):
            raise BuildError(f"partner.yaml: ungültige id {pid!r} (nur a-z, 0-9, -)")
        if not isinstance(p, dict):
            raise BuildError(f"partner.yaml: {pid} muss ein Objekt sein")
        for feld in ("name", "fallback_url"):
            if not p.get(feld):
                raise BuildError(f"partner.yaml: {pid} braucht {feld}")
        if not str(p["fallback_url"]).startswith("https://"):
            raise BuildError(f"partner.yaml: {pid}.fallback_url muss mit https:// beginnen")
        p["aktiv"] = bool(p.get("aktiv", False))
        if p["aktiv"] and not str(p.get("url", "")).startswith("https://"):
            raise BuildError(f"partner.yaml: {pid} ist aktiv, braucht aber eine url mit https://")
        if p.get("stand") is not None and not isinstance(p["stand"], dt.date):
            raise BuildError(f"partner.yaml: {pid}.stand muss ein Datum JJJJ-MM-TT sein")
    return daten


def partner_url(p: dict, site: dict, slug: str) -> str:
    kennungen = site.get("partner_kennungen") or {}
    url = str(p["url"]).replace("{slug}", quote(slug, safe=""))
    if "{kennung}" in url:
        netzwerk = p.get("netzwerk")
        if not netzwerk or not kennungen.get(netzwerk):
            raise BuildError(f"partner.yaml: {p['name']} braucht site.yaml → partner_kennungen.{netzwerk or '?'}")
        url = url.replace("{kennung}", quote(str(kennungen[netzwerk]), safe=""))
    return url


def partner_aufloesen(html: str, partner: dict, site: dict, slug: str, quelle: str) -> tuple[str, list[str], list[str]]:
    """Ersetzt partner:-Links. Gibt (html, alle_ids, aktive_ids) zurück."""
    alle: list[str] = []
    aktiv: list[str] = []

    def ersetze(m: re.Match) -> str:
        pid, rest, text = m.group(1), m.group(2), m.group(3)
        if pid not in partner:
            raise BuildError(f"{quelle}: unbekannter Partner {pid!r} (fehlt in partner.yaml)")
        p = partner[pid]
        alle.append(pid)
        if not p["aktiv"]:
            href = htmllib.escape(p["fallback_url"], quote=True)
            return f'<a href="{href}" rel="noopener"{rest}>{text}</a>'
        aktiv.append(pid)
        href = htmllib.escape(partner_url(p, site, slug), quote=True)
        return (f'<a href="{href}" rel="sponsored noopener" class="partnerlink" data-partner="{pid}"{rest}>'
                f'{text}<span class="partnerlink__marke" aria-hidden="true">*</span>'
                f'<span class="unsichtbar"> (Partnerlink)</span></a>')

    return PARTNER_LINK.sub(ersetze, html), sorted(set(alle)), sorted(set(aktiv))


def lade_vergleich(site_dir: Path, name: str, quelle: str) -> dict:
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name or ""):
        raise BuildError(f"{quelle}: Block „vergleich“ braucht daten: <name> (a-z, 0-9, -)")
    pfad = site_dir / "daten" / "vergleiche" / f"{name}.yaml"
    if not pfad.exists():
        raise BuildError(f"{quelle}: Vergleichsdaten fehlen: daten/vergleiche/{name}.yaml")
    try:
        v = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"daten/vergleiche/{name}.yaml ist kein gültiges YAML ({exc})") from exc
    for feld in ("titel", "stand", "spalten", "eintraege"):
        if not v.get(feld):
            raise BuildError(f"daten/vergleiche/{name}.yaml: {feld} fehlt")
    if not isinstance(v["stand"], dt.date):
        raise BuildError(f"daten/vergleiche/{name}.yaml: stand muss ein Datum JJJJ-MM-TT sein")
    spalten_ids = []
    for s in v["spalten"]:
        if not isinstance(s, dict) or not s.get("id") or not s.get("name"):
            raise BuildError(f"daten/vergleiche/{name}.yaml: jede Spalte braucht id und name")
        spalten_ids.append(s["id"])
    for e in v["eintraege"]:
        if not isinstance(e, dict) or not e.get("name"):
            raise BuildError(f"daten/vergleiche/{name}.yaml: jeder Eintrag braucht einen name")
        if not str(e.get("quelle", "")).startswith("https://"):
            raise BuildError(f"daten/vergleiche/{name}.yaml: {e['name']} braucht eine quelle mit https://")
        werte = e.get("werte") or {}
        unbekannt = set(werte) - set(spalten_ids)
        if unbekannt:
            raise BuildError(f"daten/vergleiche/{name}.yaml: {e['name']} hat unbekannte Spalten {sorted(unbekannt)}")
        e["werte"] = {k: str(w) for k, w in werte.items()}
    if v.get("sortierung", "alphabetisch") == "alphabetisch":
        v["eintraege"] = sorted(v["eintraege"], key=lambda e: str(e["name"]).lower())
    v["name"] = name
    v["stand_text"] = datum_de(v["stand"])
    v["mit_partner"] = any(e.get("partner") for e in v["eintraege"])
    return v


def bloecke_ersetzen(rumpf: str, site_dir: Path, env: Environment, quelle: str) -> tuple[str, list[dict]]:
    """Ersetzt ```vergleich-Blöcke durch HTML. Gibt (text, genutzte_vergleiche) zurück."""
    genutzt: list[dict] = []

    def ersetze(m: re.Match) -> str:
        try:
            daten = yaml.safe_load(m.group(2)) or {}
        except yaml.YAMLError as exc:
            raise BuildError(f"{quelle}: Block „vergleich“ ist kein gültiges YAML ({exc})") from exc
        v = lade_vergleich(site_dir, str(daten.get("daten", "")), quelle)
        genutzt.append({"name": v["name"], "stand": v["stand"]})
        html = env.get_template("_vergleich.html").render(v=v)
        return "\n\n" + "\n".join(z for z in html.splitlines() if z.strip()) + "\n\n"

    return BLOCK.sub(ersetze, rumpf), genutzt
