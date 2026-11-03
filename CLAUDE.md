# nischen-motor – Regeln für die Weiterentwicklung

Der Motor wird von allen Websites des Portfolios genutzt. Ein Fehler hier trifft alle Websites gleichzeitig.
Übergeordnet gilt die Geschäftsordnung im Repo `charizzzzard/nischen-leitstand`.

## Grundsätze

1. **Keine Regel aufweichen,** die Vertrauen schützt: Quellenpflicht, Testaussagen nur mit `getestet`, Kennzeichnung von Partnerlinks,
   keine Partner in werbefreien Kategorien, kein Tracking, keine fremden Skripte, Platzhalter-Sperre.
   Eine Lockerung braucht eine Freigabe des Inhabers (Eintrag in `entscheidungen.md` im Leitstand).
2. **Kein JavaScript im Motor.** Werkzeuge (Rechner, Generatoren) liegen als eigene Skripte in der jeweiligen Website.
3. **Keine fremden Dienste:** keine CDNs, Webfonts, Analyse- oder Werbeskripte.
4. **Barrierearm:** Klickflächen mindestens 44 px, Kontrast, Fokus sichtbar, keine horizontale Seitenrolle bei 390 px.
   Nach Änderungen an Templates oder CSS einen Screenshot bei 390 px Breite prüfen.
5. **Nichts nischenspezifisch:** Alles, was nur eine Website braucht, gehört in deren Repo (Templates überschreiben, `site.css`, `static/js`).

## Versionen

- Semantische Versionen (`MAJOR.MINOR.PATCH`). Die Version steht in `pyproject.toml` und `motor/__init__.py`;
  ein Test prüft, dass beide gleich sind.
  - PATCH: Fehlerbehebung ohne neue Pflichten für Websites
  - MINOR: neue Funktion, bestehende Websites bauen weiter
  - MAJOR: Websites müssen etwas ändern; Anleitung im CHANGELOG
- Jede Version bekommt einen Eintrag in `CHANGELOG.md` und ein Git-Tag `vX.Y.Z`.
- Websites wechseln die Version bewusst (`requirements.txt`, `.motor-version`) und prüfen danach mit `motor check`.

## Vor jedem Commit

```bash
python -m pytest     # alle Tests grün
```

Neue Prüfregeln und Bausteine brauchen einen Test in `tests/test_motor.py`.
