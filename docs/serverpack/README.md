# Serverpack: Builder und CI

## v1.0.0-Kandidat

Der [Release-Kandidaten-Workflow](../../.github/workflows/release-candidate.yml) erweitert die bisherige Offline-CI: `scripts/prepare_release.py` verwendet das per SHA-256 gepinnte ursprüngliche v0.0.2-Serverarchiv, prüft alle 108 Original-JARs erneut gegen die unveränderten Packwiz-Hashes und baut daraus `A-Cozy-Adventure-Server-v1.0.0.zip`. 105 Konfigurationen bleiben bytegleich. Das Manifest enthält jetzt zusätzlich die Packversion. Die ZIP wird nach erfolgreichen Tests als Review-Artefakt bereitgestellt, ohne Release oder Deployment. Das erlaubt keine unkontrollierten Moddownloads und beweist weiterhin keinen bestandenen Dedicated-Server-Start. [Release Notes](../releases/v1.0.0.md).

## Bisheriger Builder und Offline-Workflow

`scripts/build_serverpack.py` erzeugt aus dem **aktuellen lokalen Git-Checkout** ein Serverarchiv für Minecraft **26.3**, Fabric Loader **0.19.5** und **Java 25**. Die veröffentlichte GitHub-Pages-Version wird nicht als Eingabe verwendet. Der aktuelle Bestand umfasst 137 Clientpack-Mods, davon 29 `client`, 108 `both`, keine `server`; vier Client-Ressourcenpakete einschließlich Colorful Trims RP. Phase A3 ergänzt ausschließlich Offline-Prüfungen über GitHub Actions. Die finale Dedicated-Server-Kompatibilität wird erst in Phase B geprüft.

## Voraussetzungen

- Python 3.11 oder neuer, ausschließlich Standardbibliothek; keine Python-Pakete zu installieren.
- Git und ein lokaler Checkout mit verfügbarem Quellcommit. Ein geänderter Arbeitsbaum ist erlaubt und wird im Manifest markiert. Zusätzlich identifiziert ein SHA-256-Fingerabdruck die tatsächlich verwendeten Eingaben.
- Exakte vorhandene Mod-JARs oder Netzwerkzugriff und Java für den ausdrücklich aktivierten offiziellen Packwiz-Installer. Java 17 wurde lokal für den Installer erfolgreich verwendet; der spätere Minecraft-Server benötigt **Java 25**.
- Schreibrechte und ausreichend Platz für temporäre JARs und das Archiv. Arbeitsverzeichnisse entstehen im Betriebssystem-Tempordner und werden anschließend entfernt.

Der Builder muss nicht installiert werden. Seine Repository-Wurzel ergibt sich aus dem Skriptpfad, nicht aus dem aktuellen Shellverzeichnis oder einem Webserver.

## Befehle

Aus dem Repository-Stamm:

```powershell
python -B scripts/build_serverpack.py --help
python -B scripts/build_serverpack.py --dry-run
python -B scripts/build_serverpack.py --source-mods "C:\Minecraft\Instanz\.minecraft\mods"
python -B scripts/build_serverpack.py --source-mods "C:\Minecraft\Instanz\.minecraft\mods" --output dist/A-Cozy-Adventure-Server.zip
python -B scripts/build_serverpack.py --download
python -B scripts/build_serverpack.py --source-mods "C:\Minecraft\Instanz\.minecraft\mods" --download --java java
```

Standardziel: **`dist/A-Cozy-Adventure-Server.zip`**. Innerhalb des Repositorys sind Ausgaben nur unter `dist/` oder `build/` erlaubt; ein ausdrücklich angegebenes Ziel außerhalb ist ebenfalls möglich. `--output` bezeichnet eine ZIP-Datei, kein Verzeichnis.

Ohne `--download` gibt es keine Netzwerkanfragen. `--source-mods` liest nur erwartete Dateinamen direkt aus dem angegebenen Verzeichnis. Zusätzliche oder clientseitige JARs werden nicht übernommen. Jede Datei muss zum gespeicherten Packwiz-Hash passen; eine neuere Version ist kein Ersatz.

## Dry-Run und Exit-Codes

`--dry-run` prüft lokale Packwiz-Hashes, Metadaten, Auswahl, Versionsbezüge und Konfigurationsentscheidungen. Mit `--source-mods` prüft er vorhandene JARs und bei vollständigem Bestand deren Abhängigkeiten. Er lädt auch zusammen mit `--download` nichts herunter, erstellt keine Ausgabedateien und gibt den Report im Terminal aus.

Eine vorhandene ZIP und ihre Reports bleiben im regulären Dry-Run unverändert. Die Meldung benennt ausdrücklich den Dry-Run und bezeichnet ihn nicht als fehlgeschlagenen Build. Tatsächliche Fehler behalten ihren Fehlerstatus und den Hinweis auf ein erhaltenes früheres Archiv.

- Exit-Code **0**, Status `planned`: gültiger Plan. Fehlende JARs bleiben als `missing` und Abhängigkeiten als `pending` sichtbar. Das ist kein erfolgreicher ZIP-Build. `readyForArchive` ist nur bei vollständig geprüften Dateien wahr.
- Exit-Code **0**, Status `built`: alle 108 JARs und die statische Abhängigkeitsprüfung bestanden; vollständiges Archiv geschrieben.
- Exit-Code **1**, Status `failed`: ungültige Metadaten, falsche Hashes, fehlende Pflichtdateien/-abhängigkeiten, deklarierte harte Konflikte oder Schreibfehler. Keine unvollständige ZIP wird veröffentlicht.

Ein bestehendes Archiv wird erst nach vollständiger Neuerstellung atomar ersetzt. Bei einem Fehler bleibt es erhalten; der neue Report bezeichnet es ausdrücklich **nicht als Ergebnis des fehlgeschlagenen Builds**. Deshalb immer den aktuellen Report prüfen.

## Offizieller Installer und CurseForge

`--download` erstellt eine isolierte temporäre Packwiz-Definition ausschließlich für noch fehlende Servermods. Konfigurationen, Ressourcenpakete und Clientmods sind darin nicht enthalten. Der Installer erhält die Definition über eine lokale `file:`-URI. Dafür ist kein HTTP-Server oder öffentlicher Port erforderlich.

Verwendet wird der [offizielle Packwiz-Installer v0.5.14](https://github.com/packwiz/packwiz-installer/releases/tag/v0.5.14), dessen SHA-256 im Skript festgelegt ist. Er wird vor dem Start geprüft und über seinen Main-Einstiegspunkt mit `-g -s server` ohne automatische Tool-Aktualisierung ausgeführt. Siehe [offiziellen Quelltext](https://github.com/packwiz/packwiz-installer/blob/v0.5.14/src/main/kotlin/link/infra/packwiz/installer/Main.kt) und [Packwiz-Installation](https://packwiz.infra.link/tutorials/installing/packwiz-installer/).

`metadata:curseforge` wird dem offiziellen Installer überlassen. Keine URL-Vermutungen, Drittanbieter-Fallbacks oder Lizenzumgehungen. Der Prozess läuft ohne interaktive Standardeingabe und mit Zeitlimit. Bei Restriktionen die exakte Datei über die im Report genannte Originalprojektseite beziehen und mit `--source-mods` bereitstellen. Aus dem Installerverzeichnis werden ausschließlich erwartete JARs nach erneuter Hash- und Metadatenprüfung übernommen.

Der frühere lokale Downloadtest konnte die damals enthaltenen 107 Originaldateien auflösen. Für die neu aufgenommenen JEI- und MezzConfig-Dateien steht diese Prüfung noch aus. Das garantiert keine zukünftige Verfügbarkeit. Der Builder installiert niemals automatisch zusätzliche Mod-Versionen.

## Auswahl und Validierung

Packwiz ist maßgeblich; `mods.json` ist keine Build-Eingabe. Eingeschlossen werden nur `side = "both"` und `side = "server"`. Unbekannte/fehlende Side-Werte sowie ungültige Dateinamen, Hashes und Projekt-/Versionsmetadaten führen zum Fehler. Die Policy erwartet aktuell 137 Mods insgesamt und 108 Servermods; Abweichungen erfordern eine neue Prüfung.

JEI 31.15.0.79 und MezzConfig 0.6.8 bleiben beide mit `side = "both"` im Clientpack und in der Serverauswahl. Für sie sind derzeit keine Konfigurationsdateien eingecheckt; die Standardwerte und das Zusammenspiel mit Polydex sind in Phase B zu prüfen.

JARs werden gegen ihre Packwiz-Hashes und `fabric.mod.json` geprüft. Eingebettete JARs, `provides`-Aliasnamen, Versionsbedingungen, `depends`, `breaks` und `conflicts` werden berücksichtigt. Minecraft 26.3, Loader 0.19.5, Java 25 und das im Loader enthaltene MixinExtras 0.5.5 bilden die Zielumgebung. Versionsbedingungen folgen der [Fabric-Spezifikation](https://wiki.fabricmc.net/documentation:fabric_mod_json_spec), einschließlich AND, OR-Arrays, Wildcards, Tilde/Caret und Build-Metadaten.

Die Prüfung bestätigt verfügbare deklarierte Abhängigkeiten und betrachtet die höchsten gefundenen Versionen eingebetteter Bibliotheken. Sie ist **kein vollständiger Fabric-Resolver**. Aktuell wird die umgebungsbedingt deaktivierte Abhängigkeit `armor_model_api -> fabric-rendering-v1` gemeldet. Ihre Behandlung ist mit dem tatsächlichen Loader in Phase B zu bestätigen. Unbekannte Bedingungen gelten nicht stillschweigend als erfüllt.

Originale Packwiz-Dateien und Konfigurationen werden nie verändert. Vor der ZIP-Erstellung wird der Eingabesnapshot erneut geprüft. Pfad-Traversal, unzulässige Windows-Namen, Dateinamenskollisionen und verlinkte Quelldateien werden abgelehnt. Der ZIP-Inhalt stammt aus einer ausdrücklichen Auswahl, nicht aus einem rekursiv kopierten Arbeitsverzeichnis.

## Konfigurationsauswahl: 105 von 226 Dateien

[config-selection.json](config-selection.json) benennt jede der **226** Konfigurationsdateien einzeln mit begründeter Entscheidung: **105 eingeschlossen, 121 ausgeschlossen**. Neue, fehlende oder doppelt klassifizierte Dateien stoppen den Build. Keine Verzeichnis-Globs zur Laufzeit.

Enthalten sind ausgewählte Kampf-/RPG-/Spell-Engine-Dateien, Better Combat, Weltgenerierung einschließlich Tectonic/Terralith, Waystones, Serene Seasons, Farmer's Delight, NPC-Basis und Spawner, Polymer-Verhalten, Xaero-Serverprofile, Lithium, FerriteCore, spark und Chunky. Gemischte Verzeichnisse werden auf Dateiebene behandelt.

Clientoberflächen, Shader/HUD, persönliche Bookmarks, generierte Reports/Caches, alte Modreste und Skin-Templates sind ausgeschlossen. Unklare Ribbits- und NPC-Dateien sind ausdrücklich ausgeschlossen und als offene Fragen dokumentiert. Gemeinsame Dateien für FrozenLib, Trinkets, Puddles & Floods und Sound Physics bleiben unverändert enthalten; ihre Serverwirkung ist zu testen.

**Keine automatische Übernahme aus `config-review/`.** Das betrifft Claims, NPC-Sicherheit, externe Texturen und Polymer-Autohost. Kein erfundener produktiver Voice-Chat-Port; manuelle Schritte stehen in [README-SERVER.md](README-SERVER.md).

## Fünf vorläufig enthaltene Bibliotheken

| Bibliothek | Befund und ausstehende Entscheidung |
| --- | --- |
| CreativeCore | Erkannter deklarierter Nutzer: AmbientSounds. Serverausschluss unbestätigt. |
| Iceberg | Erkannter Pflichtnutzer: Legendary Tooltips. Serverausschluss unbestätigt. |
| Fabric Language Kotlin | Erkannte Clientnutzer: Inventory Profiles Next, libIPN, Zoomify. Verbleibende Nutzung im Laufzeittest prüfen. |
| YACL | Im aktuellen Bestand für Zoomify benötigt. Serverausschluss unbestätigt. |
| BaguetteLib | Erkannter Nutzer: Particular Reforged. Plattformlabel allein rechtfertigt keinen Clientausschluss. |

Alle fünf bleiben `both` und im Serverarchiv enthalten. Eine mögliche spätere Reduktion auf 103 Mods wird in A2 nicht umgesetzt.

## Archiv, Manifest und Report

Das ZIP enthält ausschließlich:

- `mods/`: 108 geprüfte Original-JARs.
- `config/`: 105 ausgewählte, unveränderte Dateien.
- `README-SERVER.md`: Versionen, Installation, offene Host-Einstellungen.
- `build-manifest.json`: Quellcommit, Dirty-Markierung, Eingabe-Fingerabdruck, Modnamen, Dateinamen, Hashes, Fabric-Versionen, ausgeschlossene Mods/Konfigurationen, Abhängigkeitsbefund.
- `build-report.json` und `build-report.txt`: Status, Prüfumfang, Fehler/Warnungen, Konfigurationsfragen.

Daneben entstehen `<Ausgabename>.report.json` und `<Ausgabename>.report.txt`, auch bei Buildfehlern. Fehlende Dateien werden mit Modname, Dateiname, Hash und Originalquelle genannt. Manifest und Reports enthalten keine absoluten lokalen Verzeichnisse und keine Installer-Rohlogs. Rohlogs verbleiben im temporären Verzeichnis und werden entfernt.

Dateireihenfolge, Rechte und ZIP-Zeitstempel sind stabil; ZIP_STORED vermeidet erneute Komprimierung bereits komprimierter JARs. Bei identischen Eingaben und gleichem Quellzustand ist die Ausgabe bytegleich.

Nicht enthalten: Clientmods/-Ressourcenpakete, Shader, Website/Git, Caches, `config-review/`, Zugangsdaten, Spielstände, Minecraft-/Fabric-Server-JARs. Die Welt wird separat vorbereitet und hochgeladen. Die A1-`.packwizignore` schützt die neuen Script-/Dokumentations-/Buildpfade; `.gitignore` schließt lokale `build/`- und `dist/`-Artefakte aus.

## Tests

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/generate_mods.py --check
node --check assets/app.js
node --check assets/releases.js
```

Die Unit-/Integrationstests verwenden synthetische JARs ohne externe Netzwerkanfragen. Geprüft werden Auswahl und aktueller Packwiz-Bestand einschließlich JEI und MezzConfig, Hashes, fehlende Dateien, Pfade, Whitelist, Ressourcenpaketausschluss, Abhängigkeiten, ZIP/Manifest, Reproduzierbarkeit, Fehlerfälle und unveränderte Packwiz-Quelldateien. Installer-Aufrufe werden simuliert und auf Toolhash und lokale Eingabe geprüft.

Die bestehenden Browserprüfungen bleiben verfügbar:

```powershell
cd tests
npm ci
npm test
```

## GitHub Action: Offline-Prüfung (Phase A3)

[serverpack.yml](../../.github/workflows/serverpack.yml) läuft bei `pull_request` und unterstützt `workflow_dispatch`. Es gibt keinen Push- oder Release-Trigger und keinen Download-Schalter. PR-Prüfungen gelten ohne Pfadfilter auch für Änderungen an Konfigurationen und Ressourcenpaketen.

Der Ubuntu-Job verwendet Python 3.11 und führt die vollständigen Python-Tests, die lesende Packwiz-Hash-/Metadatenvalidierung über `load_plan()`, den Katalogcheck mit `--check` und `build_serverpack.py --dry-run` aus. Abschließend wird geprüft, dass Packwiz- und Katalogdateien während des Jobs unverändert geblieben sind. Weitere Prüfungen laufen auch nach einem vorherigen Fehler weiter, soweit der Job nicht abgebrochen wurde; ein fehlgeschlagener Schritt bleibt ein Jobfehler.

Die Action hat nur `permissions: contents: read`, verwendet SHA-gepinnte Actions und speichert keine Checkout-Zugangsdaten. Sie nutzt `pull_request`, nicht `pull_request_target`, und übergibt keine Repository-Secrets an PR-Code. Sie veröffentlicht keine Releases, Server-ZIPs, Pages-Inhalte oder Hostingänderungen.

Das einzige hochgeladene Artefakt heißt `serverpack-check-<Commit-SHA>` und wird **sieben Tage** aufbewahrt. Es enthält ausschließlich drei ausdrücklich benannte Dateien aus dem temporären Runnerverzeichnis:

- `plan.json`: Zähler, Quellcommit, Dirty-Markierung und Eingabe-Fingerabdruck. JAR-Prüfung und Dedicated-Server-Kompatibilität sind ausdrücklich als ausstehend markiert.
- `dry-run.txt`: Ausgabe des Offline-Dry-Runs, einschließlich erwarteter Originaldateien und offener Konfigurationsfragen.
- `summary.json`: Ergebnisse der fünf Prüfschritte und eindeutiger Hinweis, dass keine Mod-Downloads und keine Erstellung einer Server-ZIP stattgefunden haben.

Berichterstellung und Upload werden auch nach Prüffehlern versucht. Bei einem frühen Infrastrukturfehler können einzelne Dateien fehlen; der Bericht weist übersprungene Prüfungen aus. Es werden keine Konfigurationsinhalte, Installer-Rohlogs, Zugangsdaten oder lokalen JARs hochgeladen. Ein erfolgreiches Prüfarbeitsartefakt ist keine Serverdistribution; ohne Original-JARs bleiben deren Hash-/Abhängigkeitsprüfung und Phase B offen.

Für eine manuelle Prüfung in GitHub unter **Actions → Serverpack offline prüfen → Run workflow** den gewünschten Branch auswählen. GitHub bietet `workflow_dispatch` erst an, wenn die Workflowdefinition auf dem Default-Branch verfügbar ist; siehe [offizielle Trigger-Dokumentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch). Die lokale Vorbereitung auf `feature/serverpack-builder` allein startet keinen Remote-Lauf. Diese Aufgabe nimmt keinen Commit, Push oder Merge vor.

Vollständige Server-ZIPs werden derzeit bewusst **lokal** mit vorhandenen Original-JARs oder ausdrücklich aktiviertem offiziellem Installer erstellt. So benötigt PR-CI weder Mod-Downloads noch Plattformzugänge und verteilt keine Mod-JARs als öffentliche Buildausgabe. CurseForge-Beschränkungen, die vollständige JAR-Prüfung und Host-spezifische Entscheidungen verbleiben beim lokalen Build und bei Phase B.

### Windows-Symlinktest und Linux-Abdeckung

`test_source_symlink_cannot_import_an_unreviewed_file` wird lokal unter Windows übersprungen, wenn das System die Erstellung von Symlinks nicht erlaubt. Das ist als übersprungener Test dokumentiert und kein bestandener Sicherheitstest. Der Ubuntu-CI-Job führt denselben Test mit echten Symlinks aus. Auf anderen Plattformen als Windows führt eine fehlgeschlagene Symlinkerstellung zum Testfehler, damit fehlende Linux-Abdeckung nicht stillschweigend als Skip gilt. Ein tatsächliches CI-Ergebnis liegt erst nach einem späteren autorisierten Remote-Lauf vor.

## Host Unlimited und Phase B

ZIP lokal prüfen; Minecraft 26.3, Fabric 0.19.5 und Java 25 im Hostingpanel auswählen; Server stoppen und in einen gesicherten, sauberen Serverbestand hochladen. EULA, RAM/Startparameter und den tatsächlich zugewiesenen Voice-Chat-UDP-Port selbst festlegen. Details in `README-SERVER.md`. Keine Clientwelt automatisch übernehmen.

Phase A3 erzeugt ausschließlich die beschriebenen Prüfberichte. Automatische vollständige Builds oder Veröffentlichungen sind damit nicht freigegeben.

Phase B muss Dedicated-Start/Clientbeitritt, neue Chunks/Strukturen, Kampf/Magie, NPC-Konfiguration, Rezepte, Tod/Inventare, Claims, Voice Chat sowie Neustart/Persistenz prüfen. Claims-Adapter, NPC-Sicherheit, Polymer-Ressourcen, Backpack-Ladeort und gemeinsame bzw. ausgeschlossene Konfigurationen bleiben offen. Chunky erst mit endgültiger Weltgenerierungskonfiguration einsetzen. Eine erfolgreiche A2-ZIP belegt keine bestandenen Laufzeittests.
