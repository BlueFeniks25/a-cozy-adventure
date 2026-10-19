# A Cozy Adventure

Ein gemütliches Minecraft-Modpack mit einer statischen, deutschen Mod-Übersicht. HTML5, CSS3 und Vanilla JavaScript; keine Laufzeit-Abhängigkeiten, Datenbank, kostenpflichtigen Dienste oder API-Schlüssel im Browser.

## v1.0.0 – Release-Kandidat

Die Spielerwebsite enthält jetzt einen sichtbaren Wegweiser mit Installation, eigenen Mods, Ressourcenpaketen, Tasten und FAQ. Einstieg: [Website](index.html#wegweiser). Sieben eigene SVG-Schemata sind ausdrücklich als schematisch gekennzeichnet; die Tastenübersicht nennt nur belegte Standards oder markiert unbekannte Werte.

- [Deutsche Release Notes und Artefakte](docs/releases/v1.0.0.md)
- [Verbindlicher Rollout: Migration vor Merge/Pages](docs/releases/v1.0.0-rollout.md)
- [Quellen der Spieleranleitungen](docs/releases/v1.0.0-evidence.md)
- [Arbeitsstand und aktuelle Validierung](docs/releases/v1.0.0-progress.md)

`python -B scripts/prepare_release.py` baut mit Python 3.11+ und JDK 17+ die Prism-ZIP, Migrations-JAR und Server-ZIP unter `dist/v1.0.0/`, dazu Prüfsummen und Berichte. Es prüft die festgelegten offiziellen Werkzeuge und das ursprüngliche v0.0.2-Serverarchiv vollständig per SHA-256 und jede Mod zusätzlich gegen die unveränderten Packwiz-Hashes. Keine neuen Modversionen, keine Veröffentlichung. Bei gleicher Quelle und Werkzeugkette deterministisch; der Server manifestiert Quellcommit und Dirty-Status.

`.github/workflows/release-candidate.yml` baut dieselben Dateien auf dem Release-Branch/PR, erzwingt echte Packwiz-Tests und Browserprüfungen und stellt die Kandidaten **erst nach erfolgreichen Prüfungen** als Actions-Artefakt bereit. Prüfberichte werden auch bei Fehlern gesichert. Der Workflow hat nur Leserechte und keinen Release-/Pages-Schritt. Für lokale Browsertests kann `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium` einen vorhandenen Browser verwenden; sonst den mit Playwright gepinnten Chromium installieren.

**Die öffentlich ausgelieferte Packdefinition stammt aus main.** Neue ZIPs greifen beim Start weiter auf diesen Endpunkt zu. Ein Merge kann deshalb Bestandsinstallationen bereits vor einem GitHub-Release verändern. Zuerst Bestände sichern und mit der geprüften Migrations-JAR umstellen; danach nur zum freigegebenen Termin mergen, Pages prüfen und anschließend die Veröffentlichung separat freigeben. Minecraft-GUI und Dedicated-Server-Laufzeit sind weiterhin offene praktische Prüfungen.

Die folgenden Bestandsabschnitte dokumentieren teilweise die v0.0.2-/PR-8-Ausgangslage. Für v1.0.0 gelten die oben verlinkten Release-Unterlagen.

## Player Customization Protection

Die neue Java-Schutzschicht verwaltet 25 unabhängige Client-Mods und vier Ressourcenpakete optional, schützt persönliche Dateien und Einstellungen und beendet offizielle Eigentümerschaft nach einer einmaligen Entfernung. Der geprüfte Original-Packwiz-Installer arbeitet dafür ausschließlich in einem isolierten Staging. Bestehende v0.0.2-Instanzen benötigen einen einmaligen Java-Umstieg ihres Prism-Startbefehls; der alte Bootstrap aktiviert den Schutz nicht automatisch.

- [Spieleranleitung: A Cozy Adventure individuell anpassen](docs/customization/README.md)
- [Architektur, Migration, Sicherheitsregeln und Build](docs/customization/architecture.md)
- [Vollständige Mod- und Abhängigkeitsprüfung](docs/customization/dependencies.md)
- [Nachgewiesenes Verhalten des ursprünglichen Installers](docs/customization/installer-audit.md)

`scripts/build_prism.py` erzeugt die neue Prism-ZIP und die eigenständige `.migration.jar` aus fest geprüften offiziellen Werkzeugen. `.github/workflows/customization.yml` testet echte Packwiz-Updateabläufe in temporären Instanzen unter Windows/Linux und Java 17/25. Es erfolgt keine Veröffentlichung. Die folgenden älteren Abschnitte beschreiben weiterhin die Katalog- und v0.0.2-Ausgangslage; für die neue Installer-Erzeugung gilt die oben verlinkte Architekturdokumentation.

Die Website liegt im Repository-Stamm. Alle URLs zu eigenen Dateien sind relativ und funktionieren auch unter dem GitHub-Pages-Projektpfad `/a-cozy-adventure/`.

## Bestehende Installation und Veröffentlichungsstatus

Der Packwiz-Endpunkt bleibt:

**https://bluefeniks25.github.io/a-cozy-adventure/pack.toml**

Bei der Bestandsaufnahme antwortete er mit HTTP 200 und war bytegleich mit der lokalen Datei. Vorhanden sind `.nojekyll`, `pack.toml`, `index.toml`, `mods/`, `resourcepacks/` und `config/`. Vor der Ergänzung gab es keine eingecheckten Actions-Workflows. Die Pages-API lieferte ohne angemeldeten Zugriff HTTP 404; die genaue Einstellung unter **Settings → Pages** muss vor einer Veröffentlichung im Repository geprüft werden.

Die Website wird auf `feature/mod-catalog-website` vorbereitet. Kein Push, Merge, Release und keine Änderung der Pages-Einstellungen sind Teil dieser Vorbereitung. Der neue Workflow erzeugt ausschließlich Prüfartefakte. Das Zusammenführen in einen bereits veröffentlichten Pages-Branch kann die bestehende Veröffentlichung auslösen und erfolgt deshalb erst nach ausdrücklicher Freigabe.

## Dateien

```text
index.html                         Website und Prism-Installationsanleitung
assets/app.js                      Suche, Kategorien, Sortierung, Detaildialog
assets/releases.js                 GitHub-Releases-Abfrage und Prism-ZIP-Auswahl
assets/styles.css                  Responsives Design, ohne externe Schriftarten
assets/cozy-world.svg               Lokale Landschaftsillustration
assets/leaf.svg                     Lokales Logo und Favicon
mods.json                          Fertiger Katalog für den Browser
catalog/metadata-cache.json         Öffentliche Projektmetadaten für Offline-Betrieb
catalog/descriptions.de.json        Optionale deutsche Texte und Kategoriepräzisierungen
scripts/generate_mods.py            Generator, Python 3.11+, nur Standardbibliothek
tests/test_generator.py             Generator- und Sicherheitsprüfungen
tests/browser.cjs                  Optionale Browserprüfungen mit Playwright
.github/workflows/mod-catalog.yml   Generierung als Artefakt, ohne Veröffentlichung
```

## Lokal ansehen

Im Repository-Stamm starten:

```sh
python -B -m http.server 8000 --bind 127.0.0.1
```

Anschließend **http://127.0.0.1:8000/** öffnen. Direktes Öffnen als `file://` reicht wegen des Abrufs von `mods.json` nicht aus. Der Server ist nur für lokale Vorschauen gedacht.

## Modliste regenerieren

```sh
python -B scripts/generate_mods.py
```

Der Generator liest `pack.toml` und **ausschließlich `mods/*.pw.toml`**. Ressourcenpakete werden nicht als Mods gezählt. Er schreibt nur `mods.json` und `catalog/metadata-cache.json`. Es gibt keinen Aufruf von Packwiz, keine Downloads von Moddateien, keine Updates und keine Änderung an Packwiz-Metadaten, Ressourcenpaketen oder Konfigurationen. Ein vollständig fehlender Modbestand oder fehlerhaftes TOML führt zu einem Fehler, statt den vorhandenen Katalog zu ersetzen.

Namen, Icons und weitere Angaben kommen nach Möglichkeit aus offiziellen APIs:

1. Modrinth-Projekte werden über die in Packwiz gespeicherte Projekt-ID abgefragt.
2. Für CurseForge-Dateien wird der **gespeicherte SHA-1-/SHA-512-Dateihash** mit der Modrinth-API abgeglichen. Nur ein exakter Dateitreffer erlaubt die Übernahme der dortigen Projektmetadaten; es gibt keine unscharfe Namenssuche und keine geratenen Projekt-Slugs.
3. Die tatsächliche Packwiz-Quelle bleibt dabei **CurseForge**. Die Detailansicht bietet die CurseForge-Projektseite sowie den nachgewiesenen Modrinth-Link und benennt die Quelle des Original-Kurztextes.
4. Optional unterstützt der Generator die offizielle CurseForge-API über die Umgebungsvariable `CURSEFORGE_API_KEY`. Ein Schlüssel wird nicht benötigt. Falls verwendet, ausschließlich lokal als Umgebungsvariable oder in einem separat geprüften, vertrauenswürdigen Workflow als GitHub Secret setzen. Der mitgelieferte PR-Workflow erhält keine Secrets. Niemals einen Schlüssel in Dateien, Browsercode oder Git eintragen.

Die aktuelle Liste enthält **137 Mods**, davon **128 mit API-Metadaten** und **9 mit Packwiz-Ersatzangaben**. Diese Zahlen sind eine Bestandsaufnahme; die Website zählt stets die tatsächlich generierten Einträge.

### Deutsche Beschreibungen und Kategorien

Alle initialen Mods haben kurze, redaktionelle deutsche Beschreibungen. Die JSON-Datei `catalog/descriptions.de.json` ist eine optionale Ergänzung, keine zweite Modliste: Aufnahme und Entfernung einer Mod erfolgen immer anhand von Packwiz.

Neue Mods erscheinen **ohne manuelle Ergänzung**. Kategorien werden aus Modnamen und API-Kategorien abgeleitet. Fehlt ein deutscher Text, erscheint ein deutscher Kategorie-Ersatztext; die Detailansicht kennzeichnet ihn als solchen und zeigt, soweit vorhanden, die Original-Kurzbeschreibung. Der Generator übersetzt keine beliebigen Projekttexte automatisch. Präzise deutsche Texte für neue Mods können bei Bedarf ergänzt werden, sind aber keine Voraussetzung für den Katalogbetrieb. Automatisch zugeordnete Kategorien können ungenau sein und lassen sich ebenfalls optional präzisieren.

### Fehler und Offline-Betrieb

API-Aufrufe laufen gebündelt, verwenden einen identifizierenden User-Agent, Zeitlimits und begrenzte Wiederholungen. Bei Ausfällen bleibt ein passender Cache-Eintrag erhalten. Die Cache-Identität enthält Quelle, Projekt-ID und Dateihash; nach einem Dateiwechsel werden keine alten Metadaten für eine andere Datei übernommen. Entfernte Mods werden auch aus dem Cache entfernt. Fehler beim Lesen lokaler Dateien werden mit einem Exit-Code ungleich null gemeldet.

```sh
python -B scripts/generate_mods.py --offline
python -B scripts/generate_mods.py --check
```

`--offline` baut die JSON ohne Netzwerk aus den vorhandenen Angaben neu. `--check` schreibt nichts und prüft, ob die eingecheckte JSON einem Offline-Neubau entspricht. Ein SHA-256-Fingerabdruck deckt Änderungen an `pack.toml` und allen Mod-Metadaten ab. Ohne Zeitstempel bleibt die Ausgabe bei gleichen Eingaben identisch.

Fehlen Icons, erscheinen Initialen. Schlägt ein Bildabruf fehl, greifen ebenfalls Initialen. Bei nicht ladbarer oder ungültiger `mods.json` bietet die Website einen Fehlerhinweis mit Wiederholen-Schaltfläche. Es gibt keine iFrames und kein ungeprüftes Einfügen fremder HTML-Inhalte.

### Metadaten, Quellen und Rechte

Gespeichert werden öffentliche Namen, kurze Projektzusammenfassungen, Kategorien, Icon-URLs sowie gegebenenfalls Lizenzangaben und Projektlinks. Vollständige Projektbeschreibungen, Moddateien und fremde Webseiten werden nicht kopiert. Deutsche Kurztexte sind eigenständig formuliert. Die Detailansicht nennt die Quelle der zusätzlich gezeigten Original-Kurzbeschreibung und verlinkt die offiziellen Projektseiten.

Icons werden über die von den APIs gelieferten URLs auf `cdn.modrinth.com` bzw. `*.forgecdn.net` geladen, ohne eigene Kopien anzulegen. Dadurch können Besucher-Browser den jeweiligen Bildserver kontaktieren; es werden keine Tracker oder externen Schriftarten eingebunden. Eine Projektlizenz ist keine pauschale Lizenz für sämtliche Marken und Grafiken. Bestehende Urheberrechte bleiben bestehen; Icons können bei Rechtefragen aus den Metadaten entfernt werden. Ein API-Schlüssel oder eine Umgehung von Downloadbeschränkungen ist nicht erforderlich.

Offizielle Referenzen: [Modrinth-API](https://docs.modrinth.com/api/), [CurseForge-API und Zugangsvoraussetzungen](https://docs.curseforge.com/rest-api/).

## GitHub Actions und spätere Veröffentlichung

`mod-catalog.yml` reagiert auf Pushes und Pull Requests mit Änderungen an den Katalog-Eingaben und kann manuell gestartet werden. Er führt Generator-Tests aus, regeneriert die JSON, prüft ihre Konsistenz und kontrolliert, dass Packwiz-Dateien unverändert bleiben. Er stellt `mods.json` und den Metadaten-Cache als Artefakt für 14 Tage bereit. Actions sind an überprüfte Commit-SHAs gebunden; das Repository-Token hat nur `contents: read` und wird nicht im Checkout gespeichert.

**Die Generierung läuft automatisch. Das Artefakt wird nicht automatisch committed oder auf Pages veröffentlicht.** Für die sichere Vorbereitungsphase ist dies beabsichtigt. Vor dem später freigegebenen Merge die generierten Dateien aus dem Artefakt übernehmen oder den Generator auf dem Feature-Branch ausführen und das Ergebnis in den geprüften Änderungsstand aufnehmen. Ein Artefakt allein aktualisiert die live ausgelieferte `mods.json` nicht. Siehe [GitHub: Workflow-Artefakte](https://docs.github.com/en/actions/tutorials/store-and-share-data).

Für eine spätere, ausdrücklich freigegebene Veröffentlichung:

1. In **Settings → Pages** prüfen, welcher Branch und welches Verzeichnis derzeit den funktionierenden Packwiz-Endpunkt bereitstellen. Diese Einstellung beibehalten, sofern sie den Repository-Stamm veröffentlicht.
2. Den geprüften Website-Stand samt aktueller `mods.json` in genau diesen Branch übernehmen. `pack.toml`, `index.toml`, `.nojekyll`, Mod-Metadaten, Ressourcenpakete und Konfigurationen müssen unverändert vorhanden bleiben.
3. Nach der bestehenden Pages-Veröffentlichung sowohl `/a-cozy-adventure/` als auch `/a-cozy-adventure/pack.toml` prüfen. Keinesfalls ein ausschließlich aus Website-Dateien bestehendes Pages-Artefakt einsetzen: Das würde den Packwiz-Endpunkt entfernen.
4. Falls Pages tatsächlich aus einem anderen Verzeichnis oder einem externen Prozess veröffentlicht wird, den vollständigen bestehenden Packwiz-Auslieferungsumfang zunächst prüfen. Die Konfiguration hier wurde mangels authentifiziertem Zugriff nicht geändert.

Ein späterer vollautomatischer Betrieb der **live ausgelieferten** JSON benötigt eine gesondert freigegebene Integration: etwa generierte Dateien in einen Review-PR schreiben oder nach einer geschützten Freigabe die vollständige Pages-Auslieferung erzeugen. Das wäre eine Erweiterung des derzeit lesenden Workflows.

### Packwiz-Refresh und Serverpack-Vorbereitung

Die `.packwizignore` schließt Website-, Entwicklungs-, CI- und Dokumentationsdateien sowie künftige Build-, Download- und Cacheverzeichnisse aus. Dazu gehören `index.html`, `assets/`, `mods.json`, `catalog/`, `scripts/`, `tests/`, `.github/`, `README.md`, `docs/`, `build/` und `dist/`. `.nojekyll` bleibt für GitHub Pages im Repository, wird aber nicht mit dem Minecraft-Pack verteilt. `config/` und `resourcepacks/` bleiben im Packwiz-Bestand.

Die bestehende Regel `*.zip` schließt lokale Backups und Archive aus, nicht die über `.pw.toml` referenzierten entfernten Ressourcenpakete. Eine spätere Verteilung lokaler Ressourcenpaket-ZIPs benötigt eine ausdrücklich geprüfte Einbindung. Aus `config-review/` wird nichts automatisch übernommen.

Der aktuelle Packwiz-Bestand umfasst 137 Clientpack-Mods: 29 mit `side = "client"` und 108 mit `side = "both"`. JEI 31.15.0.79 und MezzConfig 0.6.8 sind beide mit `side = "both"` enthalten. Die vier Ressourcenpakete einschließlich Colorful Trims RP sind als `client` eingestuft. Der lokale Serverpack-Builder in `scripts/build_serverpack.py` verwendet die lokale Packwiz-Definition und eine explizite Konfigurationsauswahl. Phase A3 ergänzt `.github/workflows/serverpack.yml` für PR- und manuelle Offline-Prüfungen ohne Mod-Downloads oder Veröffentlichung von Server-ZIPs. Befehle, Prüfartefakte, Bibliothekskandidaten und die ausstehende Dedicated-Server-Prüfung sind unter [docs/serverpack/README.md](docs/serverpack/README.md) dokumentiert.

Der Katalog-Generator selbst ruft `packwiz refresh` niemals auf. Nach einem separat ausgeführten Refresh lässt sich der Katalog ohne neue API-Abfragen mit `python -B scripts/generate_mods.py --offline` regenerieren und mit `--check` prüfen.

## Installation für Mitspieler

Die Website beschreibt den [ZIP-Import in Prism Launcher](https://prismlauncher.org/wiki/help-pages/Zip-import/) und ermittelt die neueste veröffentlichte Version mit passender Installations-ZIP über die öffentliche [GitHub Releases API](https://docs.github.com/en/rest/releases/releases#list-releases). Sie verwendet `/repos/BlueFeniks25/a-cozy-adventure/releases`, einschließlich Pre-releases und stabiler Releases, und ignoriert Drafts sowie Releases ohne Veröffentlichungsdatum. Maßgeblich ist `published_at`, nicht die Reihenfolge der API-Antwort oder die Kennzeichnung als „latest“.

Die Abfrage berücksichtigt Folgeseiten mit jeweils 100 Einträgen. Nach insgesamt acht Sekunden, bei API-Fehlern, ungültigen Antworten oder mehr als zehn Seiten bleibt der Link zur [GitHub-Releases-Seite](https://github.com/BlueFeniks25/a-cozy-adventure/releases) verfügbar. Dieser Link funktioniert auch ohne JavaScript. Mod-Katalog und Release-Abfrage laufen unabhängig voneinander. Es werden weder Schlüssel noch eine Anmeldung benötigt; die Content Security Policy erlaubt dafür ausschließlich zusätzlich `api.github.com` als Verbindungsziel.

Als Installationsdatei gilt ein hochgeladenes ZIP-Asset mit `Prism`, `MultiMC`, `Install`, `Installer` oder `Installation` als Wortbestandteil, beispielsweise **`A-Cozy-Adventure-Prism-v0.1.0.zip`**. Unterstützt werden auch **`A-Cozy-Adventure.zip`** und **`A-Cozy-Adventure-v0.1.0.zip`** einschließlich Alpha-/Beta-Suffixen und üblicher Trennzeichen. Explizite Prism-Dateien haben Vorrang vor anderen passenden ZIPs desselben Releases. Archivnamen mit `backup`, `server`, `source`, `config`, `audit` oder `resourcepack` werden ausgeschlossen. GitHubs automatisch erzeugtes Quellcode-ZIP wird nicht verwendet. Die Erkennung erfolgt anhand des Asset-Namens; die ZIP muss vom Herausgeber tatsächlich als Prism-kompatible Instanz gepackt sein.

Der Download verweist unmittelbar auf das `browser_download_url`-Asset des gewählten Releases. Angezeigt werden der Versions-Tag und **Alpha**, **Beta** oder **Stable**. GitHubs `prerelease: false` ergibt Stable; Pre-releases mit `beta` oder `rc` im Tag/Namen ergeben Beta, andere Pre-releases Alpha. Bis Version 1.0.0 können somit auch Vorabversionen ohne Alpha-Suffix ausgeliefert werden.

Bei neuen Releases ist keine Änderung am Website-Code nötig. Releases ohne passendes ZIP werden übersprungen; gibt es keinen passenden Treffer, erscheint die Releases-Seite. Erstellung und Veröffentlichung von Releases oder Installations-ZIPs sind hier nicht enthalten.

## Tests

Ohne zusätzliche Installation:

```sh
python -B -m unittest discover -s tests -v
python -B scripts/generate_mods.py --check
node --check assets/app.js
node --check assets/releases.js
```

Die Generator-Tests prüfen unter anderem exakte Dateizuordnung, unveränderte TOML-Dateien, native Modrinth-Quellen, CurseForge-Fallbacks, API-Ausfälle, Cache-Veraltung, ergänzte/entfernte Mods, fehlerhafte Eingaben und den Umgang mit einem nur im Test vorhandenen Schlüssel.

Optionale Browserprüfungen mit Node.js und Playwright; die Entwicklungsabhängigkeit wird ausschließlich unter `tests/` installiert und nicht von der Website geladen:

```sh
cd tests
npm ci
npx playwright install chromium
npm test
```

Der Browsertest startet und beendet selbst einen lokalen Testserver unter dem Projektpfad `/a-cozy-adventure/`. Er prüft Suche, kombinierte Filter, Zähler, Sortierung, Dialog und Fokus-Rückgabe, sechs Breiten von 320 bis 1440 Pixeln, unveränderte Auslieferung von `pack.toml`, Ersatzicons, Fehlerzustände, sichere Textdarstellung und reduzierte Bewegung. Die Release-Prüfungen simulieren Alpha/Beta/Stable, Drafts, Veröffentlichungsreihenfolge, ZIP-Auswahl, Folgeseiten und API-Ausfälle ohne echte Releases zu erstellen oder herunterzuladen. Screenshots werden außerhalb des Repositorys im temporären Verzeichnis gespeichert.
