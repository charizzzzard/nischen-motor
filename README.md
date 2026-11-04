# nischen-motor

Statischer Website-Motor für das Nischen-Portfolio. Er baut aus Markdown eine schnelle Website und prüft sie vor jeder Veröffentlichung auf die Regeln aus der Geschäftsordnung im Repo `nischen-leitstand`.

Er ist aus der Technik von netzleicht.de abgeleitet, aber ohne deren Besonderheiten (Figuren, Gerätefilter, Echt-Check) und um Ertragsbausteine ergänzt.

## Was der Motor kann

| Bereich | Funktion |
| --- | --- |
| Inhalte | Artikel mit Frontmatter (Pflichtfelder, Quellen, Prüfdatum), Seitentypen `ratgeber`, `vergleich`, `werkzeug`, Kategorien, frei wählbares URL-Präfix, Weiterleitungen (`alte_urls`) |
| Ertrag | Partnerlinks `[Text](partner:id)` über `partner.yaml`: inaktiv → normaler Link, aktiv → `rel="sponsored"`, Sternchen, Werbehinweis oben im Artikel, SubID = Artikel-Slug |
| Vergleiche | ```` ```vergleich ```` liest `daten/vergleiche/<name>.yaml`; Quelle je Zeile, Stand-Datum, standardmäßig alphabetisch (keine Rangliste) |
| SEO | Sitemap, robots.txt (Staging sperrt), Atom-Feed, JSON-LD (Article, Breadcrumb, Organization), canonical, Open Graph, IndexNow-Schlüsseldatei |
| Gestaltung | Neutrales, barrierearmes CSS ohne fremde Schriften; Farben über `site.yaml → design`, eigenes `static/css/site.css`, Templates je Website überschreibbar |
| Prüfung | siehe unten |

### Was `motor check` prüft

- **Fehler (Abbruch):**
  - Pflichtfelder und Längen (Titel, Beschreibung, Wortzahl)
  - Quellen (Anzahl, https)
  - Datumslogik
  - Verkaufsdruck-Formulierungen
  - Testaussagen ohne `getestet`
  - Partnerlinks in werbefreien Kategorien
  - aktive Partner ohne `einnahmen_erlaubt`
  - fehlende Offenlegungsseite
  - veraltete Vergleichsdaten (> 60 Tage)
  - fehlendes Impressum oder Datenschutz
  - `PLATZHALTER` auf einer Live-Website
  - Tracker, fremde Skripte, tote interne Links, Bilder ohne alt-Text, H1, Description, canonical, Sitemap
- **Hinweise:**
  - Prüfung fällig (> 180 Tage)
  - Keyword fehlt in Titel oder Beschreibung
  - kein interner Link
  - lange Sätze
  - Vergleichsdaten > 30 Tage
  - Partner-Konditionen lange nicht geprüft
  - Favicon

Die Grenzwerte lassen sich je Website in `site.yaml → regeln` anpassen.

## Benutzung

```bash
pip install "git+https://github.com/charizzzzard/nischen-motor@v0.1.0"
motor neu meine-website      # Vorlage kopieren (site.yaml, Seiten, Beispiele, CI, CLAUDE.md)
cd meine-website
motor build                  # -> _site/
motor check                  # bauen + prüfen, Exit 1 bei Fehlern
```

**Websites binden eine feste Version ein:** `requirements.txt` und `.motor-version`.
Beide nennen dasselbe Tag; die CI der Website bricht ab, wenn sie voneinander abweichen.

Dieses Repo ist öffentlich. Die CI einer Website lädt den Motor deshalb ohne Token oder Secret.
Folge: Hier gehören keine Geheimnisse, Zugangsdaten, Partner-Kennungen, Kennzahlen oder Inhaber-Daten hinein (siehe `CLAUDE.md`).

## Entwicklung

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
python -m pytest
```

Regeln für Änderungen stehen in `CLAUDE.md`, Änderungen in `CHANGELOG.md`.
