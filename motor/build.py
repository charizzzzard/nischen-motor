"""Baut eine Website: <site>/content + Vorlagen + static -> Ausgabeordner."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import yaml
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .bausteine import bloecke_ersetzen, lade_partner, partner_aufloesen
from .inhalt import (Artikel, BuildError, Seite, artikel_url, datum_de, lese_frontmatter, neues_markdown,
                     pruefe_artikel_meta, text_woerter)

MOTOR_DIR = Path(__file__).resolve().parent

SITE_PFLICHT = ("name", "url", "beschreibung", "betreiber", "kategorien", "indexierung")
SITE_STANDARD = {
    "artikel_praefix": "artikel",
    "einnahmen_erlaubt": False,
    "werbung_pfad": "/werbung/",
    "offenlegung_text": ("Diese Seite enthält Partnerlinks (mit * markiert). Wenn Sie über einen solchen Link "
                         "etwas kaufen oder abschließen, erhalten wir vom Anbieter eine Provision."),
    "artikel_hinweis": "",
    "partner_kennungen": {},
    "design": {},
}
DESIGN_FARBEN = ("akzent", "text", "hintergrund", "flaeche", "linie")


def lade_site(site_dir: Path) -> dict:
    pfad = site_dir / "site.yaml"
    if not pfad.exists():
        raise BuildError(f"site.yaml fehlt in {site_dir}")
    try:
        site = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"site.yaml ist kein gültiges YAML ({exc})") from exc
    fehlend = [f for f in SITE_PFLICHT if f not in site or site[f] in (None, "")]
    if fehlend:
        raise BuildError(f"site.yaml: Pflichtfelder fehlen: {', '.join(fehlend)}")
    if not str(site["url"]).startswith("https://") or str(site["url"]).endswith("/"):
        raise BuildError("site.yaml: url muss mit https:// beginnen und ohne / enden")
    for k in site["kategorien"]:
        if not isinstance(k, dict) or not k.get("slug") or not k.get("name"):
            raise BuildError("site.yaml: jede Kategorie braucht slug und name")
    for name, farbe in (site.get("design") or {}).items():
        if name not in DESIGN_FARBEN or not re.match(r"^#[0-9a-fA-F]{3,8}$", str(farbe)):
            raise BuildError(f"site.yaml: design.{name} ungültig (erlaubt: {', '.join(DESIGN_FARBEN)} als #RRGGBB)")
    return {**SITE_STANDARD, **site}


def json_ld(daten) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2).replace("</", "<\\/")


def _env(site_dir: Path) -> Environment:
    lader = ChoiceLoader([FileSystemLoader(site_dir / "templates"), FileSystemLoader(MOTOR_DIR / "templates")])
    env = Environment(loader=lader, autoescape=select_autoescape(["html"]), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["datum"] = datum_de
    return env


def lade_artikel(site: dict, site_dir: Path, env: Environment, partner: dict) -> list[Artikel]:
    kategorien = {k["slug"] for k in site["kategorien"]}
    artikel: list[Artikel] = []
    for pfad in sorted((site_dir / "content" / "artikel").glob("*.md")):
        meta, rumpf = lese_frontmatter(pfad)
        if meta.get("entwurf"):
            continue
        pruefe_artikel_meta(pfad, meta, kategorien)
        rumpf, vergleiche = bloecke_ersetzen(rumpf, site_dir, env, pfad.name)
        md = neues_markdown()
        html = md.convert(rumpf)
        html, alle, aktiv = partner_aufloesen(html, partner, site, pfad.stem, pfad.name)
        kurz_html = neues_markdown().convert(str(meta["kurz_gesagt"]).strip().replace("\n", "\n\n"))
        kurz_html, k_alle, k_aktiv = partner_aufloesen(kurz_html, partner, site, pfad.stem, pfad.name)
        toc = [t for t in md.toc_tokens if t["level"] == 2]
        artikel.append(Artikel(pfad.stem, pfad, meta, html, toc, text_woerter(html), kurz_html,
                               artikel_url(site, pfad.stem), sorted(set(alle + k_alle)),
                               sorted(set(aktiv + k_aktiv)), vergleiche))

    nach_slug = {a.slug: a for a in artikel}
    for a in artikel:
        for s in a.meta.get("verwandt", []) or []:
            if s not in nach_slug:
                raise BuildError(f"{a.slug}.md: verwandter Artikel {s!r} existiert nicht")
            a.verwandte.append(nach_slug[s])
        for b in artikel:
            if len(a.verwandte) >= 3:
                break
            if b is not a and b not in a.verwandte and b.kategorie == a.kategorie:
                a.verwandte.append(b)
    artikel.sort(key=lambda a: (a.veroeffentlicht, a.slug), reverse=True)
    return artikel


def lade_seiten(site_dir: Path) -> list[Seite]:
    seiten = []
    for pfad in sorted((site_dir / "content" / "seiten").glob("*.md")):
        meta, rumpf = lese_frontmatter(pfad)
        if not meta.get("titel"):
            raise BuildError(f"seiten/{pfad.name}: titel fehlt")
        seiten.append(Seite(pfad.stem, meta, neues_markdown().convert(rumpf)))
    return sorted(seiten, key=lambda s: (s.meta.get("reihenfolge", 50), s.slug))


def ld_organisation(site: dict) -> dict:
    org = {"@type": "Organization", "@id": f"{site['url']}/#organisation", "name": site["name"],
           "url": f"{site['url']}/"}
    if site.get("logo"):
        org["logo"] = site["url"] + site["logo"]
    return org


def ld_artikel(site: dict, a: Artikel, kat: dict) -> list[dict]:
    url = site["url"] + a.url
    daten = {
        "@context": "https://schema.org", "@type": "Article", "headline": a.titel, "description": a.beschreibung,
        "inLanguage": "de-DE", "mainEntityOfPage": url,
        "datePublished": a.veroeffentlicht.isoformat(), "dateModified": a.aktualisiert.isoformat(),
        "author": {"@type": "Organization", "name": site.get("redaktion") or f"{site['name']}-Redaktion"},
        "publisher": ld_organisation(site), "citation": [q.get("url") for q in a.quellen if isinstance(q, dict)],
    }
    if site.get("og_bild"):
        daten["image"] = site["url"] + site["og_bild"]
    return [daten, {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Startseite", "item": f"{site['url']}/"},
            {"@type": "ListItem", "position": 2, "name": kat["name"], "item": site["url"] + kat["url"]},
            {"@type": "ListItem", "position": 3, "name": a.titel, "item": url},
        ],
    }]


def schreibe(out: Path, pfad: str, inhalt: str) -> None:
    ziel = out / pfad.lstrip("/")
    if pfad.endswith("/"):
        ziel = ziel / "index.html"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt, encoding="utf-8")


def _hash(pfad: Path) -> str | None:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:10] if pfad.is_file() else None


def build(site_dir: Path, out: Path) -> dict:
    site_dir = Path(site_dir).resolve()
    out = Path(out).resolve()
    site = lade_site(site_dir)
    env = _env(site_dir)
    partner = lade_partner(site_dir)
    artikel = lade_artikel(site, site_dir, env, partner)
    seiten = lade_seiten(site_dir)

    urls: dict[str, str] = {}
    for name, url in [(f"artikel/{a.slug}", a.url) for a in artikel] + [(f"seiten/{s.slug}", s.url) for s in seiten]:
        if url in urls:
            raise BuildError(f"Adresse {url} doppelt vergeben ({urls[url]} und {name})")
        urls[url] = name

    kategorien = []
    for k in site["kategorien"]:
        liste = [a for a in artikel if a.kategorie == k["slug"]]
        if liste:
            kategorien.append({**k, "url": f"/themen/{k['slug']}/", "artikel": liste})
    kat_nach_slug = {k["slug"]: k for k in kategorien}

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(MOTOR_DIR / "static", out)
    if (site_dir / "static").is_dir():
        shutil.copytree(site_dir / "static", out, dirs_exist_ok=True)

    favicons = []
    for datei, typ in (("favicon.ico", None), ("favicon.png", "image/png"), ("favicon.svg", "image/svg+xml")):
        if (out / datei).is_file():
            favicons.append({"href": f"/{datei}", "typ": typ})
    design = site.get("design") or {}
    design_css = (":root{" + ";".join(f"--{k}:{v}" for k, v in design.items()) + "}") if design else ""
    heute = dt.date.today()
    basis = {
        "site": site,
        "kategorien": kategorien,
        "fuss_seiten": [s for s in seiten if s.meta.get("im_fuss", True)],
        "favicons": favicons,
        "design_css": design_css,
        "versionen": {"motor_css": _hash(out / "css" / "motor.css"), "site_css": _hash(out / "css" / "site.css")},
        "jahr": heute.year,
        "ld_organisation": json_ld({"@context": "https://schema.org", **ld_organisation(site)}),
    }

    def render(vorlage: str, pfad: str, **kontext) -> None:
        schreibe(out, pfad, env.get_template(vorlage).render(**basis, pfad=pfad, **kontext))

    render("start.html", "/", artikel=artikel)
    for k in kategorien:
        render("kategorie.html", k["url"], kategorie=k)
    for a in artikel:
        kat = kat_nach_slug[a.kategorie]
        render("artikel.html", a.url, artikel=a, kategorie=kat, strukturdaten=json_ld(ld_artikel(site, a, kat)))
    for s in seiten:
        render("seite.html", s.url, seite=s)
    for t in list(artikel) + list(seiten):
        for alt in t.meta.get("alte_urls", []) or []:
            render("weiterleitung.html", alt, ziel=t.url)
    render("404.html", "/404.html")

    eintraege = [("/", max((a.aktualisiert for a in artikel), default=heute))]
    eintraege += [(k["url"], max(a.aktualisiert for a in k["artikel"])) for k in kategorien]
    eintraege += [(a.url, a.aktualisiert) for a in artikel if not a.meta.get("noindex")]
    eintraege += [(s.url, s.meta.get("aktualisiert", heute)) for s in seiten if not s.meta.get("noindex")]
    zeilen = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    zeilen += [f"  <url><loc>{xml_escape(site['url'] + p)}</loc><lastmod>{d.isoformat()}</lastmod></url>"
               for p, d in eintraege]
    zeilen.append("</urlset>")
    schreibe(out, "/sitemap.xml", "\n".join(zeilen) + "\n")

    if site["indexierung"]:
        robots = f"User-agent: *\nAllow: /\n\nSitemap: {site['url']}/sitemap.xml\n"
    else:
        robots = "# Staging-Modus: Indexierung gesperrt (site.yaml -> indexierung)\nUser-agent: *\nDisallow: /\n"
    schreibe(out, "/robots.txt", robots)

    feed = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="de">',
            f"  <title>{xml_escape(site['name'])}</title>", f'  <link href="{site["url"]}/"/>',
            f'  <link rel="self" href="{site["url"]}/feed.xml"/>', f"  <id>{site['url']}/</id>",
            f"  <updated>{max((a.aktualisiert for a in artikel), default=heute).isoformat()}T00:00:00Z</updated>"]
    for a in artikel[:20]:
        feed += ["  <entry>", f"    <title>{xml_escape(a.titel)}</title>", f'    <link href="{site["url"]}{a.url}"/>',
                 f"    <id>{site['url']}{a.url}</id>",
                 f"    <published>{a.veroeffentlicht.isoformat()}T00:00:00Z</published>",
                 f"    <updated>{a.aktualisiert.isoformat()}T00:00:00Z</updated>",
                 f"    <summary>{xml_escape(a.beschreibung)}</summary>",
                 f"    <author><name>{xml_escape(site.get('redaktion') or site['name'] + '-Redaktion')}</name></author>",
                 "  </entry>"]
    feed.append("</feed>")
    schreibe(out, "/feed.xml", "\n".join(feed) + "\n")

    if site.get("indexnow_schluessel"):
        schreibe(out, f"/{site['indexnow_schluessel']}.txt", str(site["indexnow_schluessel"]))

    return {"site": site, "artikel": artikel, "seiten": seiten, "kategorien": kategorien, "partner": partner,
            "sitemap": [site["url"] + p for p, _ in eintraege], "out": out, "site_dir": site_dir}
