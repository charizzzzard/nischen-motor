"""Tests für nischen-motor. Aufruf: python -m pytest"""
from __future__ import annotations

import datetime as dt
import shutil
import tomllib
from pathlib import Path

import pytest

import motor
from motor.build import MOTOR_DIR, build
from motor.check import pruefen
from motor.cli import main as cli_main

HEUTE = dt.date(2026, 11, 3)
SATZ = "Dieser Satz ist ein ruhiger Beispielsatz mit genau zwölf Wörtern für den Test."


def text(woerter: int = 500) -> str:
    saetze = [SATZ] * (woerter // 13 + 1)
    return "\n\n".join(" ".join(saetze[i:i + 4]) for i in range(0, len(saetze), 4))


def artikel_md(slug: str, *, kategorie: str = "grundlagen", rumpf: str = "", extra: str = "",
               titel: str | None = None, datum: str = "2026-11-01") -> str:
    titel = titel or f"Rechnung schreiben Anleitung {slug}"
    return f"""---
titel: "{titel}"
beschreibung: "Rechnung schreiben leicht gemacht: Pflichtangaben, Beispiele und Quellen für {slug} – ruhig erklärt."
keyword: "rechnung schreiben"
kategorie: {kategorie}
veroeffentlicht: {datum}
aktualisiert: {datum}
geprueft: {datum}
kurz_gesagt: |
  Die direkte Antwort in einem Satz.
quellen:
  - herausgeber: BMJ
    titel: "§ 14 UStG"
    url: https://www.gesetze-im-internet.de/ustg_1980/__14.html
  - herausgeber: BMF
    titel: "Rechnungen"
    url: https://www.bundesfinanzministerium.de/
{extra}---

## Erster Abschnitt

{rumpf}

Mehr in den [Grundlagen](/themen/grundlagen/).

{text()}
"""


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """Minimale, gültige Website ohne Platzhalter."""
    d = tmp_path / "site"
    (d / "content" / "artikel").mkdir(parents=True)
    (d / "content" / "seiten").mkdir(parents=True)
    (d / "daten" / "vergleiche").mkdir(parents=True)
    (d / "static").mkdir()
    shutil.copy(MOTOR_DIR / "vorlage" / "static" / "favicon.png", d / "static" / "favicon.png")
    (d / "site.yaml").write_text("""
name: "Test-Ratgeber"
url: "https://www.test-ratgeber.de"
beschreibung: "Testseite"
betreiber: "Test Betreiber"
indexierung: true
einnahmen_erlaubt: true
artikel_praefix: "ratgeber"
partner_kennungen:
  awin: "4711"
kategorien:
  - {slug: grundlagen, name: Grundlagen}
  - {slug: sicherheit, name: Sicherheit}
regeln:
  werbefreie_kategorien: [sicherheit]
""", encoding="utf-8")
    (d / "partner.yaml").write_text("""
aktiv-partner:
  name: "Aktiv GmbH"
  netzwerk: awin
  aktiv: true
  fallback_url: "https://aktiv.example/"
  url: "https://www.awin1.com/cread.php?awinmid=1&awinaffid={kennung}&clickref={slug}"
  stand: 2026-11-01
inaktiv-partner:
  name: "Inaktiv AG"
  aktiv: false
  fallback_url: "https://inaktiv.example/"
""", encoding="utf-8")
    (d / "daten" / "vergleiche" / "programme.yaml").write_text("""
titel: "Programme"
stand: 2026-11-01
spalten:
  - {id: preis, name: "Preis"}
eintraege:
  - {name: "Zeta", quelle: "https://zeta.example/", werte: {preis: "5 €"}}
  - {name: "Alpha", partner: aktiv-partner, quelle: "https://alpha.example/", werte: {preis: "9 €"}}
""", encoding="utf-8")
    for slug, titel in (("impressum", "Impressum"), ("datenschutz", "Datenschutz"), ("werbung", "Werbung")):
        (d / "content" / "seiten" / f"{slug}.md").write_text(f"---\ntitel: {titel}\n---\n\nText.\n", encoding="utf-8")
    (d / "content" / "artikel" / "basis.md").write_text(artikel_md("basis"), encoding="utf-8")
    return d


def schreibe_artikel(site: Path, slug: str, **kw) -> None:
    (site / "content" / "artikel" / f"{slug}.md").write_text(artikel_md(slug, **kw), encoding="utf-8")


def test_version_konsistent():
    pyproject = tomllib.loads((MOTOR_DIR.parent / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == motor.__version__


def test_gueltige_site_ohne_fehler(site, tmp_path):
    fehler, hinweise, daten = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert fehler == []
    out = tmp_path / "out"
    for datei in ("index.html", "ratgeber/basis/index.html", "themen/grundlagen/index.html",
                  "impressum/index.html", "sitemap.xml", "robots.txt", "feed.xml", "404.html", "css/motor.css"):
        assert (out / datei).is_file(), datei
    assert "Sitemap: https://www.test-ratgeber.de/sitemap.xml" in (out / "robots.txt").read_text()


def test_partner_inaktiv_ist_normaler_link(site, tmp_path):
    schreibe_artikel(site, "inaktiv", rumpf="Siehe [Anbieter](partner:inaktiv-partner).")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    html = (tmp_path / "out" / "ratgeber" / "inaktiv" / "index.html").read_text()
    assert fehler == []
    assert 'href="https://inaktiv.example/" rel="noopener"' in html
    assert "sponsored" not in html
    assert "Hinweis zu Werbung" not in html


def test_partner_aktiv_gekennzeichnet(site, tmp_path):
    schreibe_artikel(site, "aktiv", rumpf="Siehe [Anbieter](partner:aktiv-partner).")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    html = (tmp_path / "out" / "ratgeber" / "aktiv" / "index.html").read_text()
    assert fehler == []
    assert 'rel="sponsored noopener"' in html
    assert "awinaffid=4711&amp;clickref=aktiv" in html
    assert "Hinweis zu Werbung" in html
    assert "(Partnerlink)" in html


def test_unbekannter_partner_bricht_ab(site, tmp_path):
    schreibe_artikel(site, "falsch", rumpf="[x](partner:gibt-es-nicht)")
    fehler, _, daten = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert daten is None and "unbekannter Partner" in fehler[0]


def test_einnahmen_nicht_erlaubt(site, tmp_path):
    yaml_text = (site / "site.yaml").read_text().replace("einnahmen_erlaubt: true", "einnahmen_erlaubt: false")
    (site / "site.yaml").write_text(yaml_text)
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("einnahmen_erlaubt ist false" in f for f in fehler)


def test_werbefreie_kategorie(site, tmp_path):
    schreibe_artikel(site, "sicher", kategorie="sicherheit", rumpf="[x](partner:inaktiv-partner)",
                     titel="Rechnung schreiben sicher")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("werbefreier Kategorie" in f for f in fehler)


def test_offenlegungsseite_pflicht_bei_aktiven_partnern(site, tmp_path):
    (site / "content" / "seiten" / "werbung.md").unlink()
    schreibe_artikel(site, "aktiv", rumpf="[x](partner:aktiv-partner)")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("Offenlegung" in f for f in fehler)


def test_testaussage_ohne_getestet(site, tmp_path):
    schreibe_artikel(site, "test", rumpf="Unser Testsieger ist klar.")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("Testaussage" in f for f in fehler)
    schreibe_artikel(site, "test", rumpf="Unser Testsieger ist klar.", extra='getestet: "Testzugang 01.11.2026"\n')
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert not any("Testaussage" in f for f in fehler)


def test_verkaufsdruck_verboten(site, tmp_path):
    schreibe_artikel(site, "druck", rumpf="Angebot nur heute!")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("verbotene Formulierung" in f for f in fehler)


def test_vergleich_tabelle_und_alter(site, tmp_path):
    schreibe_artikel(site, "vergleich", rumpf="```vergleich\ndaten: programme\n```", extra="seitentyp: vergleich\n")
    fehler, hinweise, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    html = (tmp_path / "out" / "ratgeber" / "vergleich" / "index.html").read_text()
    assert fehler == []
    assert html.index("Alpha") < html.index("Zeta")  # alphabetisch
    assert "Stand: 1. November 2026" in html
    assert 'rel="sponsored noopener"' in html and "Hinweis zu Werbung" in html
    fehler, hinweise, _ = pruefen(site, tmp_path / "out", heute=dt.date(2027, 1, 15))
    assert any("Vergleich programme" in f for f in fehler)


def test_platzhalter_blockiert_live(site, tmp_path):
    (site / "content" / "seiten" / "impressum.md").write_text("---\ntitel: Impressum\n---\n\nPLATZHALTER\n")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("PLATZHALTER" in f for f in fehler)


def test_pflichtseiten(site, tmp_path):
    (site / "content" / "seiten" / "datenschutz.md").unlink()
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("datenschutz" in f for f in fehler)


def test_fremdes_skript_verboten(site, tmp_path):
    (site / "templates").mkdir()
    (site / "templates" / "404.html").write_text(
        '{% extends "base.html" %}{% block kopf %}<script src="https://cdn.example/x.js"></script>{% endblock %}'
        '{% block inhalt %}<h1>Nicht gefunden</h1>{% endblock %}')
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("fremdes oder relatives Skript" in f for f in fehler)


def test_kurze_texte_und_lange_beschreibung(site, tmp_path):
    (site / "content" / "artikel" / "kurz.md").write_text(
        artikel_md("kurz").split("## Erster Abschnitt")[0] + "Nur kurz.\n", encoding="utf-8")
    fehler, _, _ = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert any("Wörter" in f for f in fehler)


def test_doppelte_adresse(site, tmp_path):
    (site / "content" / "seiten" / "basis.md").write_text("---\ntitel: Basis\npfad: /ratgeber/basis/\n---\n\nx\n")
    fehler, _, daten = pruefen(site, tmp_path / "out", heute=HEUTE)
    assert daten is None and "doppelt" in fehler[0]


def test_vorlage_baut_und_prueft(tmp_path):
    ziel = tmp_path / "neu"
    assert cli_main(["neu", str(ziel)]) == 0
    fehler, hinweise, daten = pruefen(ziel, tmp_path / "out", heute=HEUTE)
    assert fehler == []  # Staging: Platzhalter sind nur Hinweise
    assert any("PLATZHALTER" in h for h in hinweise)
    assert daten["artikel"] == []  # Beispiel ist Entwurf


def test_neu_verweigert_vollen_ordner(tmp_path):
    (tmp_path / "voll").mkdir()
    (tmp_path / "voll" / "datei.txt").write_text("x")
    assert cli_main(["neu", str(tmp_path / "voll")]) == 1


def test_build_direkt(site, tmp_path):
    daten = build(site, tmp_path / "out")
    assert [a.slug for a in daten["artikel"]] == ["basis"]
    assert daten["artikel"][0].url == "/ratgeber/basis/"
