"""Qualitätsprüfung: baut die Website und prüft Inhalte, Regeln und Ausgabe.

FEHLER brechen ab (Exit 1), HINWEISE nicht. Grenzwerte lassen sich je Website in site.yaml → regeln anpassen.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from .build import build
from .inhalt import BuildError

REGELN_STANDARD = {
    "min_woerter": 450,
    "min_quellen": 2,
    "beschreibung_laenge": [70, 165],
    "titel_max": 65,
    "titel_hinweis": 60,
    "pruefung_faellig_tage": 180,
    "satz_max_woerter": 28,
    "vergleich_hinweis_tage": 30,
    "vergleich_fehler_tage": 60,
    "partner_stand_hinweis_tage": 180,
    "werbefreie_kategorien": [],
    "verboten": [],
}
# Verkaufsdruck und Heilsversprechen (gilt für jede Website)
VERBOTEN_STANDARD = [
    r"100\s?% sicher", r"garantiert sicher", r"absolut sicher", r"jetzt kaufen", r"angebot nur heute",
    r"nur noch heute", r"letzte chance", r"sofort handeln, sonst",
]
# Testaussagen nur, wenn wirklich getestet wurde (Frontmatter: getestet)
TESTWOERTER = [r"testsieger", r"im test\b", r"wir haben getestet", r"unser test"]
TRACKING = [
    "googletagmanager", "google-analytics.com", "gtag(", "matomo", "plausible.io", "cdn.segment.com", "mixpanel",
    "fbq(", "connect.facebook.net", "adsbygoogle", "doubleclick.net", "amazon-adsystem", "hotjar", "clarity.ms",
]
PFLICHTSEITEN = ("impressum", "datenschutz")
PLATZHALTER = "PLATZHALTER"


class Seitenparser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.skripte: list[str] = []
        self.bilder_ohne_alt: list[str] = []
        self.h1 = 0
        self.meta: dict[str, str] = {}
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "link" and a.get("href"):
            if a.get("rel") == "canonical":
                self.canonical = a["href"]
            elif a.get("rel") in ("stylesheet", "icon"):
                self.links.append(a["href"])
        elif tag == "script" and a.get("src"):
            self.skripte.append(a["src"])
        elif tag == "img":
            if a.get("src"):
                self.links.append(a["src"])
            if "alt" not in a:
                self.bilder_ohne_alt.append(a.get("src", "?"))
        if tag == "h1":
            self.h1 += 1
        if tag == "meta" and a.get("name"):
            self.meta[a["name"]] = a.get("content", "")


def saetze(html: str) -> list[str]:
    text = re.sub(r"</(p|li|h\d|td|th|div|caption)>|<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", text)
    ergebnis = []
    for block in text.split("\n"):
        block = re.sub(r"\s+", " ", block).strip()
        ergebnis += [s for s in re.split(r"(?:(?<=[.!?])|(?<=[.!?][“\"]))\s+(?=[A-ZÄÖÜ„])", block) if s.strip()]
    return ergebnis


def _ziel_existiert(out: Path, pfad: str) -> bool:
    pfad = pfad.split("#")[0].split("?")[0]
    ziel = out / pfad.lstrip("/")
    if pfad.endswith("/") or pfad == "":
        return (ziel / "index.html").is_file()
    return ziel.is_file()


def pruefen(site_dir: Path, out: Path, heute: dt.date | None = None) -> tuple[list[str], list[str], dict | None]:
    """Gibt (fehler, hinweise, build_daten) zurück."""
    fehler: list[str] = []
    hinweise: list[str] = []
    heute = heute or dt.date.today()
    try:
        daten = build(site_dir, out)
    except BuildError as exc:
        return [str(exc)], [], None
    site, artikel, seiten, partner, out = daten["site"], daten["artikel"], daten["seiten"], daten["partner"], daten["out"]
    regeln = {**REGELN_STANDARD, **(site.get("regeln") or {})}
    verboten = VERBOTEN_STANDARD + list(regeln["verboten"])
    werbefrei = set(regeln["werbefreie_kategorien"])

    # ---------------------------------------------------- Artikel
    for a in artikel:
        name = f"artikel/{a.slug}.md"
        titel = a.meta.get("seo_titel") or a.titel
        if len(titel) > regeln["titel_max"]:
            fehler.append(f"{name}: Seitentitel zu lang ({len(titel)} > {regeln['titel_max']} Zeichen) – seo_titel kürzen")
        elif len(titel) > regeln["titel_hinweis"]:
            hinweise.append(f"{name}: Seitentitel {len(titel)} Zeichen – ab ca. {regeln['titel_hinweis']} kürzt Google")
        lo, hi = regeln["beschreibung_laenge"]
        if not lo <= len(a.beschreibung) <= hi:
            fehler.append(f"{name}: beschreibung hat {len(a.beschreibung)} Zeichen (erlaubt {lo}–{hi})")
        if a.woerter < regeln["min_woerter"]:
            fehler.append(f"{name}: nur {a.woerter} Wörter (mindestens {regeln['min_woerter']})")

        if len(a.quellen) < regeln["min_quellen"]:
            fehler.append(f"{name}: nur {len(a.quellen)} Quelle(n) (mindestens {regeln['min_quellen']})")
        for q in a.quellen:
            if not isinstance(q, dict) or not all(q.get(k) for k in ("herausgeber", "titel", "url")):
                fehler.append(f"{name}: Quelle unvollständig (herausgeber, titel, url): {q}")
            elif not str(q["url"]).startswith("https://"):
                fehler.append(f"{name}: Quelle ohne https: {q['url']}")

        if a.geprueft > heute or a.aktualisiert > heute or a.veroeffentlicht > heute:
            fehler.append(f"{name}: Datum liegt in der Zukunft")
        if a.aktualisiert < a.veroeffentlicht:
            fehler.append(f"{name}: aktualisiert liegt vor veroeffentlicht")
        alter = (heute - a.geprueft).days
        if alter > regeln["pruefung_faellig_tage"]:
            hinweise.append(f"{name}: zuletzt vor {alter} Tagen geprüft – Prüfung fällig")

        volltext = " ".join([a.titel, a.beschreibung, str(a.kurz_gesagt), a.html]).lower()
        for muster in verboten:
            if re.search(muster, volltext):
                fehler.append(f"{name}: verbotene Formulierung gefunden: /{muster}/")
        if not a.meta.get("getestet"):
            for muster in TESTWOERTER:
                if re.search(muster, volltext):
                    fehler.append(f"{name}: Testaussage /{muster}/ ohne echten Test – Feld getestet fehlt")

        if a.kategorie in werbefrei and a.partner_alle:
            fehler.append(f"{name}: Partnerlinks in werbefreier Kategorie {a.kategorie!r}: {', '.join(a.partner_alle)}")
        for v in a.vergleiche:
            alter_v = (heute - v["stand"]).days
            if alter_v > regeln["vergleich_fehler_tage"]:
                fehler.append(f"{name}: Vergleich {v['name']} ist {alter_v} Tage alt – Daten neu prüfen (stand)")
            elif alter_v > regeln["vergleich_hinweis_tage"]:
                hinweise.append(f"{name}: Vergleich {v['name']} ist {alter_v} Tage alt – bald neu prüfen")
        if a.seitentyp == "vergleich" and not a.vergleiche:
            hinweise.append(f"{name}: seitentyp vergleich, aber kein ```vergleich-Block")
        if a.seitentyp == "werkzeug" and not a.meta.get("skripte"):
            hinweise.append(f"{name}: seitentyp werkzeug, aber keine skripte")
        for s in a.meta.get("skripte") or []:
            if not (out / s.lstrip("/")).is_file():
                fehler.append(f"{name}: Skript {s} fehlt in static/")

        keyword = str(a.meta.get("keyword") or "").lower()
        if not keyword:
            hinweise.append(f"{name}: kein keyword (Haupt-Suchbegriff) im Frontmatter")
        else:
            for feld, text in (("seo_titel", titel), ("beschreibung", a.beschreibung)):
                norm = text.lower().replace("-", " ")
                fehlend = [w for w in keyword.split() if w not in norm]
                if fehlend:
                    hinweise.append(f"{name}: keyword-Wörter {fehlend} fehlen in {feld}")
        if not re.search(r'href="/[^"#]', a.html):
            hinweise.append(f"{name}: kein interner Link im Text")
        for s in saetze(a.html):
            if len(s.split()) > regeln["satz_max_woerter"]:
                hinweise.append(f"{name}: langer Satz ({len(s.split())} Wörter): „{s[:80]}…“")

    for feld in ("titel", "beschreibung"):
        for w, n in Counter(getattr(a, feld) for a in artikel).items():
            if n > 1:
                fehler.append(f"{feld} mehrfach vergeben: {w}")

    # ---------------------------------------------------- Website, Partner, Rechtsseiten
    slugs = {s.slug for s in seiten}
    for p in PFLICHTSEITEN:
        if p not in slugs:
            fehler.append(f"Pflichtseite fehlt: content/seiten/{p}.md")
    aktive_genutzt = sorted({pid for a in artikel for pid in a.partner_aktiv})
    if aktive_genutzt and not any(s.url == site["werbung_pfad"] for s in seiten):
        fehler.append(f"Partnerlinks aktiv ({', '.join(aktive_genutzt)}), aber keine Seite {site['werbung_pfad']} "
                      "(Offenlegung) vorhanden")
    for pid, p in partner.items():
        if p["aktiv"] and not site["einnahmen_erlaubt"]:
            fehler.append(f"partner.yaml: {pid} ist aktiv, aber site.yaml → einnahmen_erlaubt ist false "
                          "(Einnahmen erst nach Gewerbeanmeldung)")
        if p.get("stand") and (heute - p["stand"]).days > regeln["partner_stand_hinweis_tage"]:
            hinweise.append(f"partner.yaml: Konditionen von {pid} seit {(heute - p['stand']).days} Tagen nicht geprüft")
        if p["aktiv"] and not p.get("stand"):
            hinweise.append(f"partner.yaml: {pid} hat kein stand-Datum (wann wurden die Konditionen geprüft?)")
    for t in list(seiten) + list(artikel):
        if PLATZHALTER in t.html or PLATZHALTER in str(t.meta):
            meldung = f"{t.url}: enthält noch {PLATZHALTER}"
            (fehler if site["indexierung"] else hinweise).append(meldung)

    # ---------------------------------------------------- Ausgabe
    html_dateien = sorted(out.rglob("*.html"))
    for datei in html_dateien:
        rel = "/" + str(datei.relative_to(out)).replace("index.html", "")
        text = datei.read_text(encoding="utf-8")
        weiterleitung = 'http-equiv="refresh"' in text
        p = Seitenparser()
        p.feed(text)
        for signatur in TRACKING:
            if signatur in text.lower():
                fehler.append(f"{rel}: Tracking-/Werbe-Code gefunden ({signatur})")
        for src in p.skripte:
            if urlsplit(src).netloc or not src.startswith("/"):
                fehler.append(f"{rel}: fremdes oder relatives Skript {src} – nur eigene Skripte unter / erlaubt")
        for link in p.links:
            teile = urlsplit(link)
            if teile.scheme in ("mailto", "tel", "https", "http") or teile.netloc:
                if teile.scheme == "http":
                    hinweise.append(f"{rel}: unverschlüsselter Link {link}")
                continue
            if link.startswith("#"):
                continue
            if teile.scheme:
                fehler.append(f"{rel}: Link mit unbekanntem Schema {link!r}")
            elif not link.startswith("/"):
                fehler.append(f"{rel}: relativer Link {link!r} – bitte mit / beginnen")
            elif not _ziel_existiert(out, link):
                fehler.append(f"{rel}: Link ins Leere: {link}")
        for src in p.bilder_ohne_alt:
            fehler.append(f"{rel}: Bild ohne alt-Text: {src}")
        if weiterleitung:
            continue
        if p.h1 != 1:
            fehler.append(f"{rel}: {p.h1} H1-Überschriften (genau 1 erwartet)")
        if not p.meta.get("description"):
            fehler.append(f"{rel}: meta description fehlt")
        if not p.canonical:
            fehler.append(f"{rel}: canonical fehlt")
        if not site["indexierung"] and "noindex" not in p.meta.get("robots", ""):
            fehler.append(f"{rel}: Staging-Modus, aber noindex fehlt")

    for url in daten["sitemap"]:
        if not _ziel_existiert(out, urlsplit(url).path):
            fehler.append(f"sitemap.xml: {url} existiert nicht")
    start = (out / "index.html").read_text(encoding="utf-8")
    if not re.search(r'<link rel="icon" href="/favicon\.(ico|png)"', start):
        hinweise.append("Startseite: kein Favicon als ICO/PNG (static/favicon.png) – Google zeigt SVG-Favicons nicht an")
    robots = (out / "robots.txt").read_text(encoding="utf-8")
    if site["indexierung"] and "Disallow: /\n" in robots:
        fehler.append("robots.txt sperrt alles, obwohl indexierung: true")

    daten["html_dateien"] = len(html_dateien)
    return fehler, hinweise, daten


def bericht(site_dir: Path, out: Path) -> int:
    fehler, hinweise, daten = pruefen(site_dir, out)
    if daten:
        print(f"Geprüft: {len(daten['artikel'])} Artikel, {len(daten['seiten'])} Seiten, "
              f"{daten['html_dateien']} HTML-Dateien, {len(daten['sitemap'])} Sitemap-Einträge")
    for h in hinweise:
        print(f"HINWEIS: {h}")
    for f in fehler:
        print(f"FEHLER:  {f}")
    if fehler:
        print(f"\n{len(fehler)} Fehler – bitte beheben.")
        return 1
    print(f"\nAlles in Ordnung ({len(hinweise)} Hinweise).")
    return 0
