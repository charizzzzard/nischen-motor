# <NAME DER WEBSITE> – Betriebshandbuch für Claude

Diese Website gehört zum Nischen-Portfolio. Übergeordnet gilt die Geschäftsordnung im Repo
`charizzzzard/nischen-leitstand` (`CLAUDE.md`): Rollen, Freigaben, rote Linien, Budget.
Bei Widerspruch gilt die Geschäftsordnung.

## 1. Worum es geht

- **Nische:** PLATZHALTER (aus dem Scout-Dossier im Leitstand)
- **Zielgruppe:** PLATZHALTER (wer sucht, in welcher Situation, mit welcher Absicht)
- **Herangehensweise:** PLATZHALTER (z. B. „Pflicht + Werkzeug + Vergleich“)
- **Ertragswege:** PLATZHALTER (Partnerprogramme laut `partner.yaml`, erst nach Freigabe aktiv)

## 2. Nicht verhandelbar

1. **Nichts erfinden:** keine erfundenen Tests, Testsieger, Bewertungen, Erfahrungen, Personen oder Zahlen.
   `getestet` im Frontmatter nur, wenn ein Mensch das Produkt wirklich benutzt hat.
2. **Quellenpflicht:** Jede Aussage zu Recht, Steuern, Geld, Sicherheit oder Technik braucht eine Primärquelle
   (Gesetz, Behörde, Herstellerdokument). Seiten selbst lesen, nicht aus Suchergebnissen zitieren.
3. **Kennzeichnung:** Partnerlinks nur über `partner:`-Links. Der Motor setzt `rel="sponsored"`, das Sternchen und den Werbehinweis.
4. **Keine Angstmache, kein Verkaufsdruck.** Der Check blockiert typische Formulierungen.
5. **Kein Tracking, keine fremden Skripte.** Eigene Werkzeuge laufen nur im Browser (`static/js/`).
6. **Qualität vor Menge:** höchstens 2 neue Texte pro Woche.

## 3. Rechtliche Leitplanken dieser Nische

PLATZHALTER: aus der Rechtsrecherche im Leitstand (`recht/…`) übernehmen, z. B. „keine Antworten auf individuelle Steuerfragen“.

## 4. Befehle

```bash
pip install -r requirements.txt   # installiert nischen-motor in der Version aus requirements.txt
motor build                       # baut nach _site/
motor check                       # baut und prüft (Exit 1 bei Fehlern)
python -m http.server 8765 --directory _site
```

## 5. Inhalte

- Texte: `content/artikel/<slug>.md`. Das Format zeigt `content/artikel/beispiel-ratgeber.md`.
- Seitentypen: `ratgeber` (Pflicht/Wissen), `vergleich` (mit ```vergleich-Block), `werkzeug` (mit eigenem Skript).
- Vergleichsdaten: `daten/vergleiche/<name>.yaml`. Jede Zeile mit Quelle, `stand` = Prüfdatum.
  Der Check warnt nach 30 Tagen und stoppt nach 60.
- Partner: `partner.yaml`. `aktiv: true` nur nach Freigabe und mit `einnahmen_erlaubt: true` in `site.yaml`.
- Pflichtseiten: Impressum, Datenschutz und `/werbung/` (Offenlegung, sobald Partner aktiv sind).
  Texte für Impressum und Datenschutz stellt der Inhaber bereit.
- `indexierung: true` erst, wenn keine `PLATZHALTER` mehr vorhanden sind. Der Check prüft das.

## 6. Ablauf einer Content-Session

1. `git pull`, Motor installieren.
2. Nächstes Thema aus `themenplan.yaml`: höchste Priorität, Status `offen`.
3. Recherche in Primärquellen. Text schreiben. Werkzeug oder Vergleich nur, wenn belegbar.
4. `motor check` muss „Alles in Ordnung“ melden.
5. Themenplan aktualisieren, Branch, Commit, PR. Nach grünem CI mergen.
6. Kurzer Eintrag für den Wochenbericht im Leitstand: Was ist neu, welche Kennzahlen gibt es.
