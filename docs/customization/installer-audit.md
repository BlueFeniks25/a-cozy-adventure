# Prüfung des bisherigen Installers

Geprüft am 18.10.2026 gegen das veröffentlichte v0.0.2-Asset und den tatsächlich heruntergeladenen offiziellen Installer. Diese Bestandsaufnahme beschreibt das bisherige Verhalten, nicht die Garantien der zusätzlichen Schutzschicht.

## Herkunft und feste Identitäten

| Artefakt | Identität | SHA-256 |
| --- | --- | --- |
| [Veröffentlichte Prism-ZIP](https://github.com/BlueFeniks25/a-cozy-adventure/releases/download/v0.0.2/A-Cozy-Adventure-Prism-v0.0.2.zip) | 94.534 Bytes | `988cd2405a67712c4fd42c602fd290170642d6d11a89da7c5f1bb075e9ddd78c` |
| Darin enthaltener offizieller Bootstrap | v0.0.3, 98.989 Bytes | `a8fbb24dc604278e97f4688e82d3d91a318b98efc08d5dbfcbcbcab6443d116c` |
| [Offizieller Installer](https://github.com/packwiz/packwiz-installer/releases/download/v0.5.14/packwiz-installer.jar) | v0.5.14 | `c9f646908d340d84773948a9a7d98bc1dae250d35e1016dc6e2b8459760b5598` |

Installer-Quellcommit: `7420866dfc6ae1f68079a166e9804b7ec31a59ca`. Bootstrap-Quellcommit: `fc4cd603d04d08c09fcd83cadb9ceedf776831e7`.

Die ZIP enthält genau `instance.cfg`, `mmc-pack.json`, `minecraft/options.txt` und `minecraft/packwiz-installer-bootstrap.jar`. Ein fertiger Installer und `packwiz.json` sind nicht enthalten. Der Pre-Launch-Befehl ist:

```text
\"$INST_JAVA\" -jar packwiz-installer-bootstrap.jar https://bluefeniks25.github.io/a-cozy-adventure/pack.toml
```

Der [Bootstrap v0.0.3](https://github.com/packwiz/packwiz-installer-bootstrap/blob/v0.0.3/src/main/java/link/infra/packwiz/installer/bootstrap/Main.java) fragt bei jedem Start GitHubs `releases/latest` ab, ursprünglich unter dem weitergeleiteten Repositorynamen `comp500/packwiz-installer`. Zum Prüfzeitpunkt meldet die offizielle API v0.5.14. Die Version ist im alten Pre-Launch-Befehl **nicht festgelegt**; daraus lässt sich die auf einem bestimmten Spielerrechner historisch ausgeführte Version nicht beweisen. Der Bootstrap selbst vergleicht Versionsnamen und besitzt keine SHA-256-Prüfung des heruntergeladenen Installers.

## Tatsächliches natives Verhalten von v0.5.14

Die maßgeblichen Ausführungspfade sind [UpdateManager.kt](https://github.com/packwiz/packwiz-installer/blob/v0.5.14/src/main/kotlin/link/infra/packwiz/installer/UpdateManager.kt) und [DownloadTask.kt](https://github.com/packwiz/packwiz-installer/blob/v0.5.14/src/main/kotlin/link/infra/packwiz/installer/DownloadTask.kt).

| Fall | Verhalten ohne zusätzliche Schutzschicht |
| --- | --- |
| Unbekannte zusätzliche Datei an anderem Pfad | Nicht im Manifest, daher nicht von der normalen Indexbereinigung betroffen. |
| Unveränderte Pack-/Indexhashes, erwarteter Pfad vorhanden | Schneller Rückweg; Existenzprüfung, keine erneute Inhaltsprüfung. |
| Spieler verändert eine offizielle Datei | Änderung kann zunächst unbemerkt bleiben. Beim späteren offiziellen Update kann der Inhalt überschrieben werden. |
| Spieler benennt `mod.jar` in `mod.jar.disabled` um | Der erwartete aktive Pfad fehlt. Installer lädt `mod.jar` erneut und lässt die deaktivierte Datei zusätzlich liegen. |
| Native optionale Auswahl auf aus | Löscht den gespeicherten aktiven Pfad ohne Inhaltsvergleich und entfernt `cachedLocation`; die Auswahl bleibt `optionValue=false`. |
| Offizielles Update einer ausgeschalteten Option | Gespeicherte Auswahl bleibt normalerweise aus; die neue Metadatei wird verarbeitet, der Nutzinhalt nicht installiert. |
| Offizielle Entfernung mit `cachedLocation` | Gespeicherter Pfad wird ohne Inhaltsvergleich gelöscht; Manifest-Eintrag wird entfernt. Umbenannte `.disabled`-Datei wird nicht gesucht. |
| Offizielle Entfernung ohne `cachedLocation` | Manifest-Eintrag wird nicht entfernt: Die Bereinigungsschleife liegt innerhalb der Prüfung auf einen vorhandenen `cachedLocation`-Wert. |
| Geänderter offizieller Dateiname | Neue Datei wird installiert, alter gespeicherter Pfad ohne Inhaltsvergleich gelöscht. |
| Persönliche Datei kollidiert mit offiziellem Zielpfad | Passender Hash kann als bereits installiert übernommen werden; abweichender Inhalt kann überschrieben werden. |
| `preserve=true` bei schon vorhandener Datei | DownloadTask überspringt das Überschreiben. Dies schützt nicht vor der separaten Bereinigung bei Entfernung aus dem Index. |
| Fehlendes `packwiz.json` | Wird als Erstinstallation behandelt. Bestehende Dateien werden dadurch nicht automatisch als persönlich erkannt. |
| Beschädigtes `packwiz.json` | Syntax-/Lesefehler führen zum Abbruch; Meldung empfiehlt das Löschen. Diese Empfehlung ist für eine sichere Eigentümerschaftsmigration ungeeignet. |
| Unterbrochener Download oder falscher Nutzdateihash | Nutzinhalt wird zunächst im Speicher gesammelt und erst nach erfolgreicher Hashprüfung geschrieben. Bereits vorher ausgeführte Entfernungen werden dadurch nicht rückgängig gemacht. |
| Abbruch beim Schreiben von Manifest oder Zieldatei | Kein vollständiger atomarer Instanz-Commit; Manifest wird direkt geschrieben. |

Die Datei `target/CachedTargetValidation.kt` enthält zwar Ansätze für `.disabled`, wird aber vom obigen UpdateManager nicht verwendet. Der aktive Downloadpfad hat weiterhin einen offenen TODO für diese Unterstützung. Das bloße Vorhandensein der Hilfsklasse ist kein Funktionsnachweis.

Die native grafische Oberfläche kann die Auswahl auch bei unverändertem Pack über ihren Optionsknopf erneut öffnen. Dagegen setzt [CLIHandler.showOptions](https://github.com/packwiz/packwiz-installer/blob/v0.5.14/src/main/kotlin/link/infra/packwiz/installer/ui/cli/CLIHandler.kt) sämtliche angezeigten Optionen auf `true`, auch bei `default=false`. Ein automatisierter Aufruf mit `-g` muss vorhandene Auswahlzustände berücksichtigen und darf diese Einschränkung nicht als vollständige Optionsverwaltung ausgeben.

## Lokales Manifestformat

[ManifestFile.kt](https://github.com/packwiz/packwiz-installer/blob/v0.5.14/src/main/kotlin/link/infra/packwiz/installer/metadata/ManifestFile.kt) und [Hash.kt](https://github.com/packwiz/packwiz-installer/blob/v0.5.14/src/main/kotlin/link/infra/packwiz/installer/metadata/hash/Hash.kt) definieren:

```json
{
  "packFileHash": {"type": "sha256", "value": "..."},
  "indexFileHash": {"type": "sha256", "value": "..."},
  "cachedFiles": {
    "mods/example.pw.toml": {
      "hash": {"type": "sha256", "value": "..."},
      "linkedFileHash": {"type": "sha512", "value": "..."},
      "cachedLocation": "mods/example.jar",
      "isOptional": true,
      "optionValue": true
    }
  },
  "cachedSide": "client"
}
```

Bei Metadateien ist `hash` der Hash des `.pw.toml`-Eintrags; `linkedFileHash` ist der Hash der heruntergeladenen Nutzdatei. Bei direkten Dateien beschreibt `hash` bereits die Nutzdatei. Der Map-Schlüssel ist der Indexpfad, nicht die Mod-ID. `cachedLocation` ist relativ zum Packordner. Ausgeschaltete native Optionen können keinen `cachedLocation`-Eintrag besitzen. `isOptional=false` und `onlyOtherSide=false` werden vom effizienten Boolean-Adapter gewöhnlich ausgelassen; `optionValue` bleibt explizit. Ein Import darf fehlende Felder deshalb nicht pauschal als beschädigt behandeln.

Eine belastbare Migration muss frühere gespeicherte Pfade und Nutzdateihashes zusammen auswerten. Der Dateiname oder die Mod-ID allein belegt keine Eigentümerschaft. Ein zuvor ausgeschalteter Eintrag ohne Zielpfad benötigt zusätzliche verifizierte historische Metadaten, um eine vorhandene `.disabled`-Datei sicher zuzuordnen. Bei fehlendem Nachweis bleibt diese Datei erhalten.

## Einstellungen und Grenzen der Migration

`options.txt` ist in v0.0.2 ein Startwert in der Prism-ZIP, kein Eintrag des Packwiz-Index. Der alte Updater setzt diese Datei daher nicht regelmäßig zurück. Die Auswahl und Reihenfolge von Ressourcenpaketen gehört weiterhin dem Spieler. Normale indizierte Konfigurationsdateien werden dagegen wie andere direkte Dateien aktualisiert und sind ohne zusätzliche Regel kein geschützter persönlicher Zustand.

Das native Pfadmodell normalisiert Pfade und sperrt unter anderem Windows-Laufwerksbuchstaben. Es ersetzt keine Prüfung von Symlinks beziehungsweise Windows-Reparse-Points: Dateioperationen können vorhandenen Verzeichnislinks folgen. Die Schutzschicht muss alle relevanten Vorfahren und Ziele vor Schreib-/Löschoperationen prüfen und ausschließlich innerhalb ihrer Instanz arbeiten.

Eine vorhandene v0.0.2-Instanz führt weiterhin den oben gespeicherten Pre-Launch-Befehl aus. Ein zusätzlicher gewöhnlicher Packwiz-Dateieintrag aktiviert keine neue Java-Einstiegsklasse. Die sichere Aktivierung einer Schutzschicht benötigt deshalb einen ausdrücklich implementierten einmaligen Umstieg des Instanzbefehls. Ein Austausch des offiziellen Bootstrap-JARs unter demselben Dateinamen würde dessen Herkunft verschleiern und ist keine geeignete Migration. Die alte Bootstrap-Datei kann unverändert erhalten bleiben; neue Java-Dateien müssen einen eigenen Namen tragen. Ein Rollout darf bestehende Spieler erst dann auf vollständigen Schutz verweisen, wenn dieser Umstieg tatsächlich stattgefunden hat.

## Ausgeführter Laufzeitnachweis für diese Bestandsaufnahme

Der heruntergeladene originale v0.5.14-Installer wurde mit Java 25.0.4.1 in einer neu angelegten temporären Instanz gegen einen lokalen HTTP-Fixture-Server gestartet. Sechs aufeinanderfolgende Läufe endeten jeweils mit Exitcode 0: Erstinstallation, manuelles Umbenennen in `.disabled`, Umstellung auf optional mit `default=false` im CLI, native Deaktivierung, offizielle Entfernung und private Neuinstallation bei einem weiteren Packzustand. Die beobachteten Dateibestände und JSON-Ausgaben bestätigen insbesondere die aktive Doppelinstallation nach Prism-Deaktivierung, die CLI-Auswahl auf an sowie den verwaisten deaktivierten Inhalt und den zurückgebliebenen Manifest-Eintrag nach nativer Entfernung. Diese Diagnose ist kein Ersatz für die vollständige End-to-End-Suite der Schutzschicht und kein Minecraft-Spielstart.

## Tatsächlich neu gebautes Serverpack

Zusätzlich wurde der aktuelle Serverpack-Builder mit den 108 Original-JARs aus der veröffentlichten v0.0.2-Server-ZIP ausgeführt. Die JARs wurden ausschließlich nach `build/customization-server-source/` extrahiert; keine Spielerinstanz war beteiligt:

```text
python scripts/build_serverpack.py --source-mods build/customization-server-source --output dist/customization/A-Cozy-Adventure-Server-protection-test.zip
```

Ergebnis: erfolgreich gebaut, 108 JARs anhand der aktuellen Packwiz-Metadaten verifiziert und 105 Konfigurationsdateien enthalten. Ein anschließender Vergleich beider ZIPs bestätigt dieselben 213 Nutzdateipfade und bytegleiche Inhalte jeder einzelnen Mod- und Konfigurationsdatei. Beide ZIP-CRC-Prüfungen bestanden. Die äußere ZIP ist wegen ihrer aktuellen Buildberichte und Metadaten nicht bytegleich zum alten Release. SHA-256 des geprüften Neubaus: `7fdf0a6543e6997fe7ee93ded402a9bee191c19020cfe18426311308629f07ad`.

Lokale, ignorierte Nachweise: `build/customization-server-comparison.json` mit Einzelhashes sämtlicher 213 Nutzdateien und `build/customization-server-source-inventory.json` mit den ursprünglichen JAR-Hashes. Es verbleibt die bereits bekannte umgebungsabhängige Warnung `armor_model_api → fabric-rendering-v1`; ein Dedicated-Server-Start und Spielbeitritt wurden durch diesen Archivvergleich nicht geprüft.
