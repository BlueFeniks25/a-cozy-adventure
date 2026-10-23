# Lokale Vorbereitung: Prüfnachweis

Datum: 23. Oktober 2026. Branch: `feature/automodpack-preparation`.
Baseline: `d1f5759325f40f706c3e29408d5faa5ea14c0b21`.

## Ergebnis

- 138 Mod-JARs im freigegebenen Manifest, einschließlich Streams Reflowing
  2.15.2 und AutoModpack 5.0.0-rc.5 mit den zuvor geprüften SHA-256-Hashes.
- Aktuelle Master-Ergänzung gegenüber dem Prüfbericht: Fabric API
  0.165.0+26.3; passend zu den lokalen Prism-Quellenmetadaten geprüft.
- 110 Serverkandidaten, 137 verwaltete Client-Mods, separate AutoModpack-JAR
  zur Client-Ersteinrichtung, 113 Konfigurationsdateien und vier optionale
  Ressourcenpakete in zwei empfohlenen Gruppen.
- Tectonic und Streams-Gameplay-Konfiguration stimmen mit den im Prüfbericht
  festgehaltenen SHA-256-Hashes überein.
- Legacy-Packwiz-Dateien einschließlich aller 365 Indexeinträge unverändert.
  Keine vorhandene versionierte Datei wurde geändert.

## Ausgeführte Prüfungen

Die gesamte Python-Suite umfasst **162 Tests**: keine Fehler, keine Fehlschläge,
vier übersprungene Tests. Die neue Master-Pack-Suite umfasst davon **46 Tests**.
Die übersprungenen Prüfungen betreffen dreimal fehlende Symlink-Berechtigungen
des Windows-Kontos und einmal eine lokal nicht vorhandene veröffentlichte
v1.0.0-Updater-JAR. Die fehlende JAR wurde nicht heruntergeladen. Der zusätzliche
reale Windows-Junction-Test ist erfolgreich.

Die unveränderten Browserprüfungen für Mod-Katalog, Spieleranleitung und
Release-Auswahl sind mit einem bereits vorhandenen Chromium erfolgreich.
Es wurde kein Browser nachinstalliert. Der Offline-Katalogcheck
`python -B scripts/generate_mods.py --check` ist ebenfalls erfolgreich.

Zwei unabhängige Vorbereitungen des tatsächlichen Master-Bestands liefern
identische `SHA256SUMS.txt`, `build-report.json`, `pack.lock.json` und
`server/automodpack/server.conf`. Sämtliche **465** in `SHA256SUMS.txt`
aufgeführten Dateien beider Ausgaben wurden erneut gehasht: keine Abweichung.
Die Prüfsummenliste selbst ist nicht in sich selbst enthalten.

Die lokalen Ausgaben liegen unter:

```text
dist/automodpack-phase-1-3/
build/automodpack-repro-check/
build/automodpack-initial-review/
build/automodpack-validation/
```

`build/automodpack-validation/` enthält insbesondere den vollständigen Python-
Testbericht, eine JSON-Zusammenfassung, isolierte Legacy-E2E-Nachweise,
`reproducibility.json` und den erneuten Abgleich der ausgewählten Master-Eingaben.
Diese Build-/Dist-Dateien bleiben ignorierte lokale Artefakte.

## Verbleibende Laufzeitprüfung

Die statische Prüfung meldet
`armor_model_api -> fabric-rendering-v1` ausdrücklich als offene Serverprüfung:
Das Rendering-Modul ist in Fabric API enthalten, auf dem Server aber gemäß
Metadaten deaktiviert. Das Paket behauptet deshalb keinen bestandenen Fabric-
Serverstart. Der vollständige Fabric-Abhängigkeitsresolver, Clientklassenzugriffe,
AutoModpack-Verbindungsaufbau und Worldgen-Verhalten bleiben im isolierten Test
zu bestätigen; Details stehen in der [Anleitung](README.md).

Weder Master-Instanz noch Serverwelt wurden verändert. Es gab keinen Serverstart,
Upload, Commit, Push, Merge, Release oder eine Website-Veröffentlichung.
