# Website-Vorschau für AutoModpack

Stand: 23. Oktober 2026. Branch: `feature/automodpack-website`.
Basis: `e52f2291edb432401ad8aa3e8f79268f0aa39e5c`, Merge der
AutoModpack-Vorbereitung nach `main` (PR #11).

## Geändert

`index.html` behält Gestaltung, Navigation, Katalog und responsive CSS bei.
Die Hauptaktion „A Cozy Adventure installieren“ führt zur vierteiligen Anleitung:
CurseForge installieren, Fabric-Profil für 26.3 / 0.19.5 anlegen, AutoModpack
5.0.0-rc.5 hinzufügen, dem angegebenen Server beitreten und die Installation
bestätigen. Neustart und erneutes Verbinden werden ausdrücklich erklärt.

Die offizielle GitHub-Veröffentlichung wurde über die GitHub-Verbindung geprüft:
`v5.0.0-rc.5` ist veröffentlicht, als Vorabversion markiert und enthält
`automodpack-5.0.0-rc.5.jar`. Das freigegebene Lockmanifest führt dieselbe
Bootstrap-Version; die Migrationsdokumentation beschreibt diese universelle JAR
für 26.3/Fabric. Der manuelle Weg ist: offizielle JAR herunterladen, Minecraft
schließen, Profilordner öffnen und JAR unentpackt in `mods` ablegen.

Quellen:
- https://github.com/Skidamek/AutoModpack/releases/tag/v5.0.0-rc.5
- https://www.curseforge.com/minecraft/mc-mods/automodpack/files
- [Vorbereitungsstand und Laufzeitgrenzen](automodpack/README.md)

Die tatsächliche Verfügbarkeit der rc.5-Datei in der CurseForge-App konnte hier
nicht geprüft werden. Die Website behauptet sie nicht und zeigt keinen falschen
Installationsbutton. Der manuelle Profilablauf wurde beschrieben, aber nicht
in einer realen CurseForge-/Minecraft-Installation ausgeführt.
Es gibt kein veröffentlichtes CurseForge-Modpack-Projekt.

Die vier Ressourcenpakete sind optional und empfohlen. AutoModpack lädt die
Dateien; Spieler aktivieren sie unter Optionen → Ressourcenpakete, sortieren und
bestätigen mit Fertig. Reihenfolge oben nach unten:

1. FA+All Extensions v1.9.2
2. FA+Player v1.1
3. Fresh Animations v1.10.5
4. Colorful Trims RP v2.0
5. Minecraft-Standard

Beleg: [bestehender Prioritätsnachweis](releases/v1.0.0-evidence.md#ressourcenpakete)
und Dateinamen im neuen Lockmanifest. Eigene Pakete und Shader sind erlaubt;
visuelle Kompatibilität bleibt im Spiel zu prüfen. Die Tastensektion erklärt die
freie Belegung unter Optionen → Steuerung. Kein options.txt-Download.

## Katalog und Archiv

`scripts/generate_mods.py` liest vorrangig das tatsächlich vorhandene freigegebene
AutoModpack-Lockmanifest, ohne ein zweites Manifest zu erfinden. Der erzeugte
Katalog enthält 138 Einträge einschließlich Bootstrap-AutoModpack, keine
Server-only-Mods, Ressourcenpakete oder verschachtelten Bibliotheksduplikate.
Streams Reflowing 2.15.2, Fabric API 0.165.0+26.3 und AutoModpack 5.0.0-rc.5 sind
enthalten; ColorLight bleibt entfernt. Moddetails zeigen die echte Manifestversion.
126 Einträge haben hashgebundene API-Metadaten aus dem bestehenden Cache;
12 verwenden Angaben des Inventars und bestehende Kategorie-Ersatztexte.
Es wurden keine neuen individuellen Modbeschreibungen erfunden.

Alte Packwiz-Dateien liefern nur noch bestehende redaktionelle Zuordnungen,
keine zusätzliche Inventarliste. Für historische Checkouts ohne Lockmanifest
bleibt der bisherige Generatorweg erhalten. Ein vorhandenes ungültiges oder
nicht freigegebenes Lockmanifest wird abgelehnt. Der Workflow berücksichtigt
Lockmanifest-Änderungen. Konfigurations- und Zugangsdaten werden nicht exportiert.

Prism-Pflichtanleitung, ZIP-Hauptdownload, Custom-Updater-Migration, alte
Schutzversprechen und ausführliche historische Tastentabelle sind von der
Startseite entfernt. Prism bleibt als optionale Alternative erwähnt.
GitHub-Releases und Legacy-Werkzeuge bleiben als Archiv erhalten.
`assets/releases.js` wird nicht geladen; die Website fragt keine Releases mehr ab.
Die CSP erlaubt dafür auch keinen GitHub-API-Zugriff mehr.

## Prüfung

- Python-Suite: 132 Tests, erfolgreich, 15 übersprungen wegen fehlender lokaler
  Java-/Legacy-Werkzeuge oder Testvoraussetzungen (Details im Testprotokoll).
- Offline-Katalogcheck erfolgreich; 138 Einträge stimmen mit dem Manifest überein.
- Browserprüfung mit vorhandenem Chromium: Suche, kombinierte Filter, Sortierung,
  Dialoge, Bootstrap-Version, Fehlerzustände, sichere Textdarstellung, Icons,
  reduzierte Bewegung, Anker und lokale Links, Tastaturbedienung und Anleitung
  ohne JavaScript. Sechs Breiten von 320 bis 1440 Pixel ohne horizontalen Überlauf,
  auch bei geöffneten Anleitungen. Keine GitHub-Release-Abfrage.
- Keine neuen Frameworks oder Abhängigkeiten. `git diff --check` erfolgreich.
- Master, Produktionsserver, Welten, Credentials und private Schlüssel unberührt.

## Offen vor Veröffentlichung

Als Review-/Draft-PR vorbereitet; noch keine Freigabe für Pages oder Serverbetrieb.
App-Verfügbarkeit der Vorabversion, echter CurseForge-Clientstart, Serverbeitritt,
AutoModpack-Bestätigung/Neustart und Ressourcenpaketdarstellung müssen praktisch
geprüft werden. Die vorhandene AutoModpack-Vorbereitung selbst kennzeichnet
Serverabhängigkeiten und Netzwerkbetrieb ebenfalls noch als ungeprüft.

Der Shell-Git-Abruf scheiterte am nicht erreichbaren Proxy. Stattdessen wurde der
exakte `main`-Snapshot über die GitHub-Verbindung gelesen: sämtliche hinzugefügten
Blobs, der vollständige Git-Tree und das signierte Commit wurden anhand ihrer
Git-Objekthashes verifiziert und lokal übernommen. Die lokale Historie hat an
diesem Snapshot eine Shallow-Grenze; ältere vorhandene Arbeiten bleiben auf
`work` erhalten. Für einen späteren Push ist gegebenenfalls ein normaler Fetch
zum Vervollständigen der Historie nötig. Es gab keinen Push, Merge, Deploy oder
Veröffentlichung durch diese Website-Arbeit.
