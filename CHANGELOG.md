# Änderungen

## 0.1.0 – 2026-11-04

Erste Version.

- **Bauen:**
  - Artikel und Seiten aus Markdown
  - Kategorien, URL-Präfix, Weiterleitungen
  - Sitemap, robots.txt, Atom-Feed, JSON-LD, Open Graph, IndexNow-Schlüsseldatei
- **Ertrag:**
  - Partnerlinks über `partner.yaml`, aktiv oder inaktiv
  - `rel="sponsored"`, Kennzeichnung, Werbehinweis, SubID je Artikel
- **Vergleiche:** Tabellen aus `daten/vergleiche/*.yaml` mit Quelle je Zeile, Stand-Datum, alphabetisch
- **Prüfung:** `motor check` mit Regeln aus der Geschäftsordnung, Grenzwerte je Website einstellbar
- **Vorlage:** `motor neu` legt eine Website an: site.yaml, partner.yaml, Pflichtseiten mit Platzhaltern, Beispielartikel, CI, CLAUDE.md
  - CI lädt den Motor ohne Token (Repo öffentlich) und bricht ab, wenn `.motor-version` und `requirements.txt` abweichen
- **Tests:** 19 Tests (pytest)
