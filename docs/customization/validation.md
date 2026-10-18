# Validierungsnachweis

Prüfdatum: 18.10.2026. Sämtliche Update-/Migrationstests liefen ausschließlich in neu angelegten temporären Instanzen. Existierende Spielerinstanzen wurden nicht gestartet oder verändert. Für die Bestandsaufnahme wurden Original-JARs ausschließlich lesend anhand ihrer Packwiz-Hashes geprüft.

## Lokal tatsächlich ausgeführt

| Prüfung | Ergebnis |
| --- | --- |
| Vollständige Python-Suite gegen gebautes Java-Artefakt | 103 Tests ausgeführt; 101 bestanden, zwei wegen fehlender Windows-Symlinkrechte übersprungen; 96,032 Sekunden |
| Darin echte Schutz-/Packwiz-End-to-End-Suite | 27/27 bestanden, keine Überspringung; 95 protokollierte Schritte mit SHA-256-Dateibeständen vorher/nachher und Prozessausgaben |
| Native Implementierung | Original Packwiz 0.5.14, festgelegter SHA-256; Testaufrufe prüfen dessen wirkliche Ausführung und Nutzdateihashes |
| Windows-Linkschutz | Echter temporärer Junction-Zielpfad abgewiesen; externer Sentinel unverändert; Traversierung ebenfalls geprüft |
| Java-17-Laufzeit | Zusätzlich beide Neuinstallations-/anfangs-deaktiviert-Tests mit lokalem Java 17 bestanden; vollständige Suite lokal mit Java 25 |
| Prism-Build und Migration | 14 Tests, 13 bestanden und ein Symlink-Rechtetest übersprungen; in den 103 Gesamttests enthalten |
| Browser-/Releaseerkennung | 137-Mod-Katalogprüfungen und 29 Release-Szenarien bestanden |
| Katalog und JavaScript-Syntax | `generate_mods.py --check`, beide `node --check` und `git diff --check` bestanden |
| Packwiz | `packwiz refresh` ausgeführt; anschließender Refresh idempotent; alle 367 Indexeinträge/Hashes geprüft; 226 Konfigurationen mit `preserve=true` |
| Abhängigkeiten | 137 Original-JAR-Hashes, 307 Fabric-Metadaten einschließlich eingebetteter JARs geprüft; 25 unabhängige Optionen, vier erforderliche Client-Bibliotheken |
| Tatsächlicher Serverpack-Neubau | 108 Moddateien und 105 Konfigurationen bytegleich zum veröffentlichten v0.0.2-Payload; beide ZIP-CRC-Prüfungen bestanden |

Die beiden übersprungenen generellen Symlinktests betreffen den bisherigen Serverpack- beziehungsweise neuen Migrationstest. Die neue End-to-End-Schutzprüfung verwendet unter Windows bei fehlenden Symlinkrechten eine echte Junction und wurde ausgeführt. Linux-CI prüft reguläre Symlinks zusätzlich.

Die Lebenszyklusprüfungen verwenden sowohl für ColorLight als auch für Ressourcenpakete jeweils ursprünglich aktive und deaktivierte Installationen. Sie entfernen den offiziellen Bestand, installieren danach **dieselben Bytes unter demselben Namen privat** und prüfen weitere offizielle Updates. Dazu kommen private Dateien, geänderte Configs, bewusst entfernte Configs, Ressourcen-Reihenfolge, Shader, spätere Reaktivierung, Pflicht-/Optionsversionswechsel, veränderte offizielle Dateien, Kollisionen einschließlich identischer Hashes, beschädigte/fehlende Zustände, tatsächliche Downloadunterbrechung und Prozessbeendigung, weiterlaufender nativer Kindprozess, Journal-Wiederaufnahme und native Legacy-Manifestmigration. Ein unveränderter Start fordert ausschließlich `pack.toml` an und verändert keinen Dateiinhalt.

## Artefakte und Reproduktion

Die lokalen ausführlichen Nachweise liegen Git-ignoriert unter:

- `build/customization-e2e/final-report.json`: 95 Hashinventar-/Protokollschritte; tatsächlicher Installerhash und geprüfter Launcherhash.
- `build/customization-e2e/final-unittest.log`: vollständige Ausgabe der 103 Tests.
- `build/customization-server-comparison.json`: Einzelhashvergleich aller 213 Server-Nutzdateien.
- `dist/customization/A-Cozy-Adventure-Prism-protection.zip` und `.migration.jar`: geprüfte Buildausgaben, keine Veröffentlichung.

Der vollständige lokale Schlusslauf verwendete JAR-SHA-256 `9427890f5cee03be2bbd2d669b8858270ac1d860e81522d5baf7734aca496277`. Danach wurde ausschließlich der Copyright-/MIT-Lizenztext von Upstream als zusätzliche Ressource eingebettet. Dass alle übrigen JAR-Einträge bytegleich zum vollständig geprüften Artefakt sind, wurde durch Rekonstruktion und denselben SHA-256 nachgewiesen. Die abschließende Datei mit Lizenzressource (`e03b565e13e867a6c0d1e42ce4a493868fff283df6d9d4331bbc7e426e68e5b0`) bestand zusätzlich beide Neuinstallationsprüfungen; der abschließende Prism-ZIP-SHA-256 ist `69fa7bb18c078d2e6bc289d6d4c05b0930051b8d9ad782cd163a59cdf7558de2`. JDK-Unterschiede können Bytecode und damit Artefakthashes ändern, ohne die innerhalb eines identischen Werkzeugstands deterministische Archivierung zu verändern.

Der tatsächliche Server-Neubau hat SHA-256 `7fdf0a6543e6997fe7ee93ded402a9bee191c19020cfe18426311308629f07ad`; das ursprüngliche Archiv `95f6ff8346cb45c3303555bf8837b1cbd15ca96ce736711ce5101d36256d0f36`. Die ZIPs unterscheiden sich durch neue Buildprovenienz, ihre 213 Nutzdateien sind identisch.

`customization.yml` baut und prüft den eingecheckten Stand erneut unter Windows/Linux und Java 17/25. Dort werden die vollständigen Tests gegen das jeweilige **fertige** JAR erzwungen und Berichte sowie Prism-/Migrationsdateien als temporäre Review-Artefakte gespeichert. Die genauen GitHub-Check-Ergebnisse gehören zum PR und werden nicht vorab als erfolgreich behauptet. Es gibt keinen Release-/Pages-Deploy-Schritt.

## Nicht nachgewiesen

Kein vollständiger Minecraft-GUI-Erststart, Shaderbildtest, Multiplayer-Beitritt oder Dedicated-Server-Laufzeittest. Statische Abhängigkeitsprüfungen ersetzen keine vollständige Fabric-Auflösung. Die bekannte bisherige Serverwarnung `armor_model_api → fabric-rendering-v1` bleibt unverändert und ist bereits in der Serverdokumentation eingeordnet. Weitere Grenzen und der zwingende einmalige Migrationseinstieg sind in der [Architekturdokumentation](architecture.md) beschrieben.
