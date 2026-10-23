# A Cozy Adventure: lokaler Master → geprüfte AutoModpack-Dateien

Stand: **Phase 1–3 vorbereitet**, keine Veröffentlichung und kein Serverstart.
Der Branch `feature/automodpack-preparation` ergänzt die bestehende Installation.
Die öffentliche Packwiz-Installation, Website, alten Downloads und Updater bleiben
unverändert. Diese Werkzeuge führen weder Git-Befehle noch Netzwerkzugriffe aus.

## Der normale Ablauf

Voraussetzung: Python **3.11 oder neuer**. PowerShell im Repository öffnen:

```powershell
cd C:\Minecraft-Modpack
```

1. Mods in der Master-Instanz ändern und lokal testen. Anschließend Minecraft
   schließen, damit sich die Eingaben während der Vorbereitung nicht verändern.
2. Änderungen anzeigen:

   ```powershell
   python -B scripts/master_pack.py scan
   ```

3. Einen neuen Review-Ordner erzeugen. Für jeden Durchlauf einen neuen Namen
   verwenden; vorhandene Ausgaben werden niemals überschrieben:

   ```powershell
   python -B scripts/master_pack.py scan --output build/review-01
   ```

   `report.txt` enthält den lesbaren Bericht, `report.json` die maschinenlesbare
   Fassung und `candidate.json` den **noch nicht freigegebenen** Gesamtbestand.

4. Den Bericht und gegebenenfalls den Kandidaten mit Codex prüfen. Danach den
   konkreten Kandidaten ausdrücklich **lokal** freigeben:

   ```powershell
   python -B scripts/master_pack.py approve --candidate build/review-01/candidate.json
   ```

5. Die Installationsdateien in einen neuen lokalen Ordner vorbereiten:

   ```powershell
   python -B scripts/master_pack.py prepare --output dist/review-01
   ```

`approve` aktualisiert nur das versionierbare Lockmanifest und nötige
Konfigurationssnapshots im Repository. `prepare` erzeugt nur lokale Dateien.
Es folgt **kein Commit, Push, Upload, Serverstart oder Publish**. Ein unveränderter
Bestand kann direkt mit `prepare` erneut reproduziert werden; `approve` ist dafür
nicht erforderlich.

Der Standardpfad ist die lokale Prism-Instanz
`A Cozy Adventure – Schutztest` unter `%APPDATA%\PrismLauncher\instances`.
Alternativ bei jedem Befehl denselben expliziten Pfad angeben:

```powershell
python -B scripts/master_pack.py scan --master 'C:\Pfad\zur\Prism-Instanz'
```

Akzeptiert werden der Instanzordner und dessen `minecraft`- beziehungsweise
`.minecraft`-Ordner. `mmc-pack.json` muss die freigegebenen Minecraft-/Fabric-Versionen
angeben. Andere oder mehrdeutige Instanzen werden abgelehnt. Die Master-Instanz
wird immer ausschließlich gelesen.

## Was automatisch erkannt wird

- Neue, entfernte, aktualisierte und umbenannte Mods anhand tatsächlicher
  Fabric-ID, Version, Dateiname und SHA-256; auch gleiche Versionsnummern mit
  veränderten Bytes werden als Änderung erkannt.
- Doppelte Mod-IDs, unlesbare JARs, fehlende freigegebene Dateien und unbekannte
  Dateien im Modordner. Auch `.jar.disabled` muss bewusst geprüft werden.
- Änderungen ausschließlich an freigegebenen Konfigurationen und Ressourcenpaketen.
- Fehlende Pflichtabhängigkeiten und unpassende deklarierte Versionsbereiche
  getrennt für Client und Server; eingebettete Fabric-JARs und `provides`-Aliase
  werden berücksichtigt.

Eine von Fabric erzeugte `automodpack-generated.jar` wird nur dann als technisches
Artefakt ausgeklammert, wenn ID/Version sowie Länge und SHA-1 exakt zur
`26.3-fabric`-Implementierung in der installierten universellen AutoModpack-JAR
passen. Gleicher Dateiname allein genügt niemals. Die Implementierung wird von
AutoModpack selbst erzeugt und gehört nicht ins Verteilungspaket.

Exitcodes für `scan`: **0** = unverändert, **1** = Änderungen zur Prüfung,
**2** = Fehler oder offene Zuordnung/Quelle. Die Codes 1 und 2 ändern keine
Freigabe. `approve` und `prepare` liefern bei Erfolg 0, bei Abbruch 2.

## Neue Mods und Quellen prüfen

Neue Mods erhalten absichtlich keine automatisch freigegebene Seiteneinstufung.
Im Kandidaten müssen `side` (`client`, `server`, `both`) und `sideReason` bewusst
gesetzt werden. `environment: "*"` bedeutet nicht automatisch, dass die JAR in
den Dedicated-Server-Modordner gehört: Die bisherigen 28 Client-Ausschlüsse
bleiben bei bekannten Mods erhalten. Eine explizite Fabric-Client-JAR kann nicht
als Servermod freigegeben werden.

Prisms lokale Dateien unter `mods/.index/*.pw.toml` können eine Quelle für neue
oder aktualisierte Mods liefern. Sie werden nur akzeptiert, wenn ihr Dateihash
zur aktuellen JAR passt. Alte Quellen werden bei einem Update **nicht** weiter
verwendet. Manuell heruntergeladene JARs ohne passende Metadaten bleiben blockiert,
bis die Quelle geprüft und im Kandidaten ergänzt wurde, zum Beispiel:

```json
{
  "provider": "modrinth",
  "projectId": "PROJEKT-ID",
  "versionId": "VERSIONS-ID",
  "url": "https://modrinth.com/project/PROJEKT-ID/version/VERSIONS-ID",
  "hashes": {"sha512": "OFFIZIELLER-DATEIHASH"}
}
```

Alternativ sind CurseForge-Projekt-/Datei-IDs und eine öffentliche HTTPS-Dateiseite
möglich. Keine Token-URLs oder Zugangsdaten eintragen. `approve` prüft die
Quellenhashes erneut, lädt aber keine Daten herunter. Die erste Quellenfreigabe
beruht auf dem überprüften Packwiz-Bestand, den bereits geprüften offiziellen
Streams-/AutoModpack-Dateien und den aktuellen lokalen Prism-Metadaten.

Ein Update von AutoModpack muss außerdem bewusst mit `pack.automodpack` im
Kandidaten abgestimmt werden. Die aktuelle Freigabe bleibt bei **5.0.0-rc.5**.
Eine neue Minecraft-/Fabric-Version erfordert ebenfalls eine gesonderte Prüfung;
die Werkzeuge ändern keine Launcherdateien.

Ein Kandidat ist an den Hash des bisherigen Lockmanifests gebunden. Er kann
keinen inzwischen geänderten Freigabestand unbemerkt überschreiben. Die Master-
Dateien werden bei Freigabe und Vorbereitung erneut gelesen und geprüft.

## Versionierbare Dateien und Auswahl

| Datei | Aufgabe |
|---|---|
| `pack.lock.json` | Freigegebene Plattform, alle Mod-IDs/Versionen/Dateinamen/Hashes/Quellen/Seiten, Gruppen und Dateiauswahl |
| `defaults/<sha256>.txt` | Unveränderte Bytes einer freigegebenen Textkonfiguration; Hashname ermöglicht nachvollziehbare Änderungen |
| `selection-policy.json` | Dokumentierte Ausschlüsse und gesondert zu prüfende bisherige Serverkonfigurationen |
| `scripts/master_pack.py` (Repositoryroot) | Scanner, lokale Freigabe und Vorbereitung |
| `tests/test_master_pack.py` (Repositoryroot) | Isolierte Offline-Tests und Prüfungen des eingecheckten Ausgangsstands |

Die Konfigurationssnapshots werden durch `.gitattributes` ohne Zeilenumwandlung
gespeichert. Identische Eingaben erzeugen dieselben Manifest- und Paketbytes;
Zeitstempel und private Quellpfade sind kein Bestandteil des Ausgabeberichts.
Die Git-Dateien enthalten keine Mod-JARs oder Ressourcenpaket-ZIPs.
`version` ist die tatsächlich deklarierte Fabric-Version. Falls eine bestehende
JAR dort beispielsweise `unspecified` angibt, wird keine Versionsnummer aus ihrem
Dateinamen erfunden; Quelle und Dateihashes identifizieren weiterhin die genaue Datei.

**Ausgangsstand:** 138 Mods, davon 28 Client-Mods und 110 Serverkandidaten
einschließlich AutoModpack. 137 Mods werden als Client-Packinhalt vorbereitet;
AutoModpack selbst wird separat zur Ersteinrichtung bereitgestellt.

Seit dem ersten Prüfbericht wurde Fabric API in der maßgeblichen Master-Instanz
auf **0.165.0+26.3** aktualisiert. Diese JAR stimmt mit dem SHA-512-Hash ihrer
lokalen Prism-Modrinth-Metadaten überein und ist im neuen Manifest erfasst.
Die alten Packwiz-Dateien behalten unverändert ihren bisherigen Bestand.

Streams Reflowing bleibt bei **2.15.2**. Sowohl Welt-/Gameplay-Datei als auch
Clientdatei sind bytegenau übernommen. Tectonic, Terralith, Lithostitched und die
Wilder-Wild-Worldgen-Einstellungen bleiben erhalten. Die genaue Auswahl umfasst
113 Konfigurationen: 97 gemeinsame und 16 Client-Standarddateien.

Tectonic SHA-256:

```text
88ac9fd71410c3ba66e5a775a4d38ebd3fec819184996f3d6c3091188532adb1
```

Streams-Gameplay-Konfiguration SHA-256:

```text
c0b6a62d370b365df6f183f7fe0c7562e73272bfae6f6d9e85e2db732da31cff
```

Gemeinsame Gameplay-/Worldgen-Dateien werden im Clientpack verbindlich verteilt.
Die 16 Client-Standarddateien sind `editable`. Das schützt spätere Spieleränderungen
nur bis zur nächsten Inhaltsänderung derselben Quelldatei; deshalb neue Defaults
immer bewusst prüfen. Die persönliche `options.txt` wird überhaupt nicht verteilt.

Die folgenden Ressourcenpakete werden in zwei empfohlenen, abwählbaren Gruppen
vorbereitet: Colorful Trims RP sowie Fresh Animations mit Player Extension und All
Extensions. AutoModpack aktiviert sie nicht selbst. Spieler wählen sie einmal im
Minecraft-Ressourcenpaketmenü aus. Ashen, Patrix und Solas bleiben ausgeschlossen.

## Schutz persönlicher Dateien

Es gibt keine rekursive Kopie der Master-Instanz und kein `config/**` als
unbegrenzte Quelldateiauswahl. Nur explizite Einträge im Lockmanifest werden
übernommen. Die Freigabe lehnt bekannte persönliche Pfade, ColorLight,
Zugangsdatenfelder, private Schlüssel, unsichere Pfade und Symlinks/Junctions ab.
Neue Konfigurationspfade benötigen zusätzlich eine bewusste manuelle Sichtprüfung;
die technische Erkennung ersetzt diese Prüfung nicht.

Insbesondere ausgeschlossen bleiben Welten, lokale Karten, Wegpunkte, Screenshots,
Logs, Caches, `.cozy`, `.fabric`, persönliche Profile, Voice-Chat-Spielerlisten,
Sodium-Hardwaredaten, Iris-Einstellungen, `servers.dat`, `options.txt` und
AutoModpack-Credentials. Auch eine verbliebene `config/colorlight.json` gelangt
nicht ins Paket. Colorful Trims und Glowing Trims sind andere Mods und bleiben
enthalten.

Die bisherigen Xaero-Serverprofile sowie Chunky-/Spark-Konfigurationen werden
ebenfalls nicht automatisch aus der persönlichen Master-Instanz exportiert.
Die neun ausgesparten Legacy-Serverkonfigurationen sind in
`selection-policy.json` einzeln aufgeführt. Vor dem Dedicated-Server-Test sind
Claims, Xaero-Serverregeln, NPC-Rechte, Voice-Port und Polymer-Ressourcen separat
zu prüfen. Es werden keine neuen Welt-/Serverkonfigurationen erfunden.

## Inhalt einer vorbereiteten Ausgabe

```text
dist/review-01/
  pack.lock.json
  build-report.json
  SHA256SUMS.txt
  bootstrap-client/mods/automodpack-5.0.0-rc.5.jar
  server/
    mods/                            110 Serverkandidaten
    config/                          97 gemeinsame Konfigurationen
    automodpack/
      server.conf
      host-modpack/
        main/mods/                   137 Client-Pack-Mods
        main/config/                 113 geprüfte Konfigurationen
        colorful-trims/resourcepacks/
        animations/resourcepacks/
```

Die gemeinsame Mod-JAR liegt bei Bedarf in beiden getrennten Ausgaben. Client-
only-JARs liegen niemals unter `server/mods`. Künftige server-only-JARs liegen
nicht im Clientpack. AutoModpack selbst liegt unter `server/mods` und im separaten
Client-Bootstrap, niemals im verwalteten Modpackinhalt.

`server.conf` wird aus dem freigegebenen Manifest mit der Syntax von rc.5
erzeugt: `selection`, `from-server`, `exclude`, `editable`. `from-server: []`
verhindert die unkontrollierte Aufnahme zusätzlicher Dateien aus dem Serverroot.
Alle Gruppenordner enthalten ausschließlich die vorbereitete Auswahl.

`generate-modpack-on-start: false` verhindert ungeprüftes Veröffentlichen beim
Neustart. `self-updater: false` hält die AutoModpack-Version kontrolliert.
`HOLEPUNCH` verwendet den Minecraft-Port; ein zusätzlicher Download-Port wird
nicht erfunden. Ob das am konkreten Hoster funktioniert, bleibt ein späterer
Netzwerktest. Voice Chat benötigt unabhängig davon den zugewiesenen UDP-Port.

Es fehlen absichtlich Minecraft-/Fabric-Serverstarter, EULA-Zustimmung, Welt,
Serveradresse, Zertifikate, private Schlüssel und Download-Zugangsdaten. Das
Paket ist kein Uploadbefehl und darf nicht über eine laufende Installation
entpackt werden. `SHA256SUMS.txt` prüft sämtliche anderen Ausgabedateien;
`build-report.json` nennt zusätzlich die bereitgestellten Nutzdateien und offene
statische Abhängigkeitswarnungen.

## Offline prüfen

```powershell
python -B -m unittest discover -s tests -p test_master_pack.py -v
python -B -m unittest discover -s tests -v
python -B scripts/generate_mods.py --check
```

Die neue Testsuite verwendet ausschließlich temporäre, künstliche Prism-Instanzen.
Sie prüft Auswahl, Seitentrennung, Hashes, Quellen, unbekannte/fehlende Mods,
Abhängigkeiten, Freigaben, unveränderte Master-Dateien, persönliche Daten,
ColorLight, reproduzierbare Ausgabe und Pfadschutz. Die bestehenden Java-/Packwiz-
Regressionstests arbeiten ebenfalls nur mit isolierten Fixtures und lokal
vorhandenen Werkzeug-JARs. Fehlende alte Release-Artefakte werden nicht heruntergeladen.

Der Versionsbereichsparser wird als reine Hilfsfunktion aus dem bestehenden
`build_serverpack.py` wiederverwendet. Weder Packwiz-Planer noch Downloader oder
Updater werden dafür aufgerufen. Ein vollständiger Fabric-Resolver und der echte
Serverstart werden durch diese statische Prüfung nicht ersetzt. Aktuell bleibt
`armor_model_api -> fabric-rendering-v1` als explizite Laufzeitprüffrage bestehen,
weil das vorhandene eingebettete Rendering-Modul auf dem Server deaktiviert ist.

## Nächster Schritt: isolierter Dedicated-Server-Test (noch nicht ausgeführt)

1. Separates Testverzeichnis außerhalb der Master- und Produktionsinstallation
   anlegen; Fabric 0.19.5, Minecraft 26.3 und Java 25 bereitstellen.
2. Nur den vorbereiteten `server/`-Inhalt dort verwenden. EULA separat prüfen.
   Server mit einer neuen Testwelt starten und Abhängigkeiten/Clientklassen prüfen.
3. Die Vorschau der AutoModpack-Generation prüfen, dann ausschließlich auf diesem
   Testserver bewusst eine Generation erzeugen. Das Vorbereitungstool führt weder
   `/automodpack generate` noch einen Start aus.
4. Mit einer frischen Testclient-Instanz und ausschließlich AutoModpack als
   Bootstrap verbinden; Zertifikatsfingerabdruck prüfen, Installation und Neustart
   testen. Die Master-Instanz bleibt davon getrennt.
5. Modupdate, Modentfernung, Gruppenwahl und Erhalt persönlicher Clientdateien
   kontrollieren. Danach neue Chunks, Streams/Tectonic/Terralith/Climate Rivers,
   Inventare, Kampf, NPCs, Claims, Voice Chat und Neustart/Persistenz prüfen.
6. Erst nach bestandenem Test über Git-Integration, Pages-Migration,
   Legacy-Rückbau und Host-Unlimited-Rollout entscheiden. Ein Pack-Rollback
   ersetzt keine gesicherte Welt und keine passenden Serverdateien.

Offizielle Referenzen für den installierten Stand:

- [AutoModpack v5.0.0-rc.5](https://github.com/Skidamek/AutoModpack/releases/tag/v5.0.0-rc.5)
- [Konfigurationsschema rc.5](https://github.com/Skidamek/AutoModpack/blob/v5.0.0-rc.5/docs/configuration/server-config.mdx)
- [Dateiauswahl und Client-/Server-Trennung](https://github.com/Skidamek/AutoModpack/blob/v5.0.0-rc.5/docs/pack-content.mdx)
- [Download-Modi und Ports](https://github.com/Skidamek/AutoModpack/blob/v5.0.0-rc.5/docs/how-it-works/hosting.mdx)
- [Generationen und Veröffentlichung](https://github.com/Skidamek/AutoModpack/blob/v5.0.0-rc.5/docs/how-it-works/generations.mdx)
