# Änderungsabhängige CI

Die vier fachlichen Prüfworkflows laufen automatisch ausschließlich für Pull Requests und zusätzlich manuell. `ci-static.yml` führt zusätzlich bei Pushes auf `release/**` und `feature/**` nur die kurzen Routing-/Build-Eingaberegressionen und Python-Syntaxprüfung aus; damit sind auch Branches ohne offenen PR prüfbar. Dieser Lauf baut keine Kandidaten und startet keine Java- oder Browserumgebung. Der vollständige PR-Diff vom Merge-Base zur PR-Spitze ist maßgeblich, niemals nur der letzte Commit. Umbenennungen berücksichtigen alte und neue Pfade. Fehlende Git-Objekte brechen die Prüfung ab; unbekannte Dateien und Änderungen der CI selbst aktivieren vorsichtshalber alle Prüfbereiche. Alle Jobs verwenden nur Leserechte und Checkouts ohne persistierte Zugangsdaten.

| Eingaben | Prüfungen |
| --- | --- |
| `mods/`, `config/`, `resourcepacks/`, `pack.toml`, `index.toml`, `.packwizignore` | Packwiz-Hashkette, Side-/Metadatenprüfung, Generator, Abhängigkeitssnapshot, Linux/Java-17-Schutzregressionen und vollständiger Artefaktbau |
| `index.html`, `assets/`, `mods.json`, `catalog/`, Browser-Tests und npm-Lockdatei | Website-/Katalogprüfungen, HTML-Verknüpfungen über vorhandene Tests, JavaScript-Syntax, Playwright/Chromium mit sechs Ansichtsbreiten und Release-Download-Szenarien |
| Java-Schutzcode, Prism-/Serverbuilder, Audit oder zugehörige Schutztests | Vollständige Schutzprüfungen auf Windows/Linux mit Java 17 und 25; kein zusätzlicher Browserlauf ohne Website-/CI-Änderung |
| Gewöhnliche Markdown-Dateien | Nur leichte CI-Regressionen, Python-Syntax und explizite Umfangsberichte; keine Java-/Browserinstallation und kein Kandidatenbau |
| Tatsächliche Build-Eingaben unter `docs/` | Server-Auswahlrichtlinie, `README-SERVER.md`, Packwiz-Lizenz, Abhängigkeitssnapshot sowie Release Notes und Rollout der aktuellen Packversion bleiben berücksichtigt |

Änderungen an `scripts/generate_mods.py` betreffen Website und Katalog, am Releasebuilder den Pack-/Artefaktbereich. Unbekannte Skripte lösen alle Bereiche aus. Kombinierte Änderungen erhalten die Vereinigung der benötigten Prüfungen. Bei Änderungen an geprüften Mod-Identitäten ist ein neu geprüfter Abhängigkeitssnapshot erforderlich; ein alter Snapshot darf neue oder aktualisierte JARs nicht bestätigen.

## Zuständigkeit und Required Checks

- `serverpack.yml`: ausschließlich `test_serverpack.py`, Packwiz-/Side-/Dateiauswahlprüfung und Abhängigkeitsvalidierung ohne Moddownloads.
- `mod-catalog.yml`: ausschließlich `test_generator.py` und Konsistenz der eingecheckten Daten. Keine wiederholten öffentlichen API-Aufrufe oder verdeckte Neugenerierung im PR.
- `customization.yml`: ausschließlich `test_prism.py` und `test_customization.py`. Echte Packwiz-Updates sind mit `COZY_REQUIRE_E2E=1` Pflicht; fehlende Werkzeuge oder die veröffentlichte Referenz-JAR sind Fehler. Die Plattformmatrix bleibt für relevante Änderungen vollständig erhalten. Bei Packänderungen läuft dieselbe Schutzsuite einmal auf Linux/Java 17.
- `release-candidate.yml`: schnelle CI-/Release-Regressionen, separater Browserjob, Artefaktbau und Prüfsummen. Keine zweite vollständige Python-/Schutzsuite im Kandidatenjob.

Bestehende Jobnamen `candidate`, `catalog`, `validate` und die vier `protect`-Matrixnamen bleiben erhalten. Keine automatischen Workflow-Pfadfilter: Bei unveränderten Eingaben schließen die Jobs mit einem expliziten Umfangsbericht ab. Sie geben damit einen erfolgreichen Routingentscheid, keinen nachgeholten vollständigen Testnachweis aus. Alte Läufe derselben Workflow-/PR-Referenz werden durch `cancel-in-progress` beendet. Der zusätzliche bisherige Push-Kandidatenbau entfällt. `pr-metadata.yml` ist eine getrennte, vertrauenswürdige Push-Metadatenpflege ohne Builds; für andere Releaseversionen ist dieser historische PR-10-Helfer nicht erforderlich.

Die tatsächlichen Branch-Protection-Einstellungen benötigen Administration-Leserechte und müssen separat gegen diese Namen geprüft werden; der verbundene GitHub-Zugang liefert dafür HTTP 403. Keine Schutzregel wurde geändert.

## Caches und Installationen

Node 22 verwendet den npm-Cache aus `tests/package-lock.json`; `npm ci` prüft weiterhin die Lockdatei und Paketintegrität. Chromium wird ausschließlich aus der exakt installierten Playwright-Version bereitgestellt. Der Browsercache verwendet Ubuntu 24.04, Betriebssystem, Architektur, Playwright-Version und Lockdateihash ohne ungenaue Restore-Schlüssel. `playwright install chromium` läuft idempotent auch nach Cachetreffern. Systembibliotheken werden getrennt mit `install-deps chromium` eingerichtet und besitzen einen eigenen Timeout; ein Browsercache ersetzt keine Systempakete. Ein Container wurde geprüft, aber nicht eingeführt: Er würde alle Browserprüfungen an ein zusätzlich zu pflegendes, exakt versionsgleiches Image binden.

Offizielle Packwiz-Werkzeuge, die veröffentlichte Migrationsreferenz und das historische Server-Quellarchiv werden exakt nach Build-/Werkzeugdefinition und Plattform gecacht. Sämtliche Bytes werden auch nach Cachetreffern erneut gegen die festgelegten Hashes und JAR-Struktur geprüft. Buildoutputs oder erfolgreiche Testergebnisse werden nie als Ersatz für Prüfungen wiederverwendet. Downloads und Installationen haben begrenzte Netzwerk-/Schrittzeitlimits.

## Vollständige Release-Abnahme

Vor jeder Stable-Veröffentlichung `release-candidate.yml` manuell mit `workflow_dispatch` auf dem endgültigen Quellstand starten. Dieser Lauf erzwingt Browser, Artefaktbau und per wiederverwendbaren Workflows auch Katalog, Packprüfung und die gesamte Schutzmatrix. Nur wenn alle Bereiche erfolgreich sind, erzeugt `full-acceptance` den Nachweis `full-acceptance-<SHA>/acceptance.json`. Er enthält Quell-SHA, Umfang und die Ergebnisse desselben Laufs. Ein automatischer Mod- oder Dokumentationscheck ist kein solcher Nachweis.

Die Review-Artefakte des Kandidatenjobs können früher vorliegen; sie sind allein keine Freigabe. Quell-SHA, erfolgreichen vollständigen Abnahmelauf, Artefakte und `SHA256SUMS.txt` gemeinsam prüfen. Es gibt weiterhin keinen automatischen Stable-Release-, Merge-, Tag- oder Deployment-Schritt. Ein späterer Veröffentlichungsprozess muss diesen Nachweis für exakt seinen Quellstand voraussetzen. Minecraft-GUI und Dedicated-Server-Laufzeit bleiben wie zuvor separate praktische Abnahmen.

Die Version, Artefaktnamen und beigepackten Release-Dokumente werden aus `pack.toml` abgeleitet; Versionen mit unsicheren Pfadzeichen werden abgelehnt. Für neue Versionen die passenden Notes und Rollout-Dateien bereitstellen, keinen Workflow kopieren. Das historisch SHA-256-gepinnte Serverarchiv liefert nur noch unveränderte JARs. Fehlende/neue Versionen werden durch den bereits vorhandenen offiziellen Packwiz-Downloadpfad bezogen und gegen aktuelle Packwiz-Hashes sowie Fabric-Metadaten geprüft; manuell erforderliche Downloads bleiben harte Buildfehler. Die bisherigen versionsspezifischen Regressionsasserts bleiben bewusst bestehen und müssen bei späterer fachlicher Änderung überprüft werden.

## Messung

Ausgangsstand `1800f3d` (tatsächliche PR-Läufe vom 23.10.2026):

| GitHub-Lauf | Job | Dauer ohne Warteschlange |
| --- | --- | --- |
| [39951015406](https://github.com/BlueFeniks25/a-cozy-adventure/actions/runs/39951015406) | candidate | 3:12 min |
| derselbe | Python-Gesamtsuite | 1:52 min |
| derselbe | Browserinstallation | 0:19 min |
| derselbe | Browserprüfungen | 0:34 min |
| [39951015454](https://github.com/BlueFeniks25/a-cozy-adventure/actions/runs/39951015454) | catalog | 0:17 min |
| [39951015396](https://github.com/BlueFeniks25/a-cozy-adventure/actions/runs/39951015396) | validate | 0:13 min |
| [39951015600](https://github.com/BlueFeniks25/a-cozy-adventure/actions/runs/39951015600) | protect Linux Java 17 / 25 | 2:32 / 1:51 min |
| derselbe | protect Windows Java 17 / 25 | 3:56 / 4:33 min |

Der berichtete hängende Push-Lauf wurde nicht aus diesen PR-Läufen abgeleitet. Neue Messwerte dürfen erst nach tatsächlichen Actions-Ergebnissen ergänzt werden. Routingtests decken Mod-, Website-, Dokumentations-, Updater- und Mischänderungen sowie frühe PR-Commits, Umbenennungen und ungültige Basisreferenzen ab. Unterschiedliche Prüfumfänge und kalte/warme Caches bei Vergleichen ausdrücklich angeben.
