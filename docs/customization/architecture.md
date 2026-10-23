# Player Customization Protection: Architektur und Betrieb

## Umfang und Entscheidung

Minecraft 26.3 und Fabric 0.19.5 bleiben unverändert. v1.0.1 entfernt ColorLight und dessen ungenutzten Standard-Config aus dem offiziellen Bestand. 24 Client-Komponenten und vier Ressourcenpakete bleiben optional; vier Client-Bibliotheken und alle `both`-Komponenten bleiben Pflicht. Der aktuelle [Abhängigkeitsnachweis](dependencies.md) wurde aus den zuvor geprüften Metadaten für unveränderte JAR-Identitäten neu berechnet.

Packwiz 0.5.14 allein erfüllt die Eigentums- und Prism-Deaktivierungsregeln nicht. Die zusätzliche Java-Schicht begrenzt sich deshalb auf Auswahl, isolierte Bereitstellung, Eigentumsabgleich und Übernahme. Sie implementiert keinen eigenen Mod-Downloader. Der unveränderte Original-Installer wird bytegenau eingebettet, vor seiner Verwendung mit dem festgelegten SHA-256 geprüft und in einem separaten JVM-Prozess ausgeführt. Seine TOML- und Gson-Bibliotheken werden mitbenutzt; eine kleine typisierte Fassade berücksichtigt die durch Upstream verkleinerten Java-APIs. Diese Anbindung ist absichtlich an die geprüfte Version gebunden.

## Start- und Updateablauf

`cozy.Launcher` prüft den Original-Installer und startet `cozy.Protector` innerhalb derselben Minecraft-Instanz. Die Prism-Anweisung lautet:

```text
\"$INST_JAVA\" -jar cozy-customization.jar --pack https://bluefeniks25.github.io/a-cozy-adventure/pack.toml
```

Der Protector sperrt parallele Updates mit einem Dateilock und setzt zuerst ein vorhandenes Übernahmejournal fort. Anschließend lädt er `pack.toml`. Wenn dessen SHA-256 unverändert ist, der gespeicherte Katalog passt und die nachgewiesenen Dateien/Aktivierungszustände stimmen, entfällt der weitere Download- und Staging-Ablauf. Abgesehen vom Lesen der Packdatei und Prüfen des Dateibestands werden keine Dateien geändert. Die Startauswahl bleibt zugänglich.

Bei einer Änderung wird ein lokaler Snapshot unter `.cozy/stage/<Versuch-ID>/source` erstellt: Pack → Index → sämtliche referenzierten Metadaten beziehungsweise Konfigurationen werden entlang der originalen Hashkette geprüft. Die originalen Mod-/Paket-Downloadangaben bleiben erhalten. Ausschließlich `mods`, `resourcepacks` und `config` sind als verwaltete Zielbereiche zugelassen.

Der Original-Installer arbeitet ausschließlich in `.cozy/stage/<Versuch-ID>/files`. Sein MultiMC-Verzeichnis zeigt ebenfalls in dieses Staging, nicht auf die echte Instanzkonfiguration. Er erhält ein frisches Manifest mit den tatsächlich gewählten Optionen. Dadurch sieht seine ungeschützte Bereinigungslogik niemals persönliche Dateien. Vorgesetzte Optionswerte verhindern zudem, dass sein CLI neue Optionen pauschal einschaltet. Nach Prozessende werden alle erforderlichen Nutzdateien erneut gegen die geprüften Downloadhashes validiert. Ein Exitcode allein gilt nicht als Erfolg.

Die tatsächlichen Minecraft-/Fabric-Komponenten werden vorab lesend gegen `mmc-pack.json` der Prism-Instanz geprüft. Stimmen sie nicht mit dem Pack überein, werden keine Spieldateien übernommen. Die Meldung nennt die benötigten Versionen, die unter Prism → Instanz bearbeiten → Version einzustellen sind. Die bisherige native automatische Bearbeitung von Launcher-Metadaten wird bewusst nicht außerhalb des Datei-Journals nachgeahmt. Damit erfordert ein zukünftiger Wechsel der Minecraft-/Fabric-Version einen zusätzlichen Prism-Schritt; normale Modpack-Updates bei unveränderten Komponenten laufen automatisch weiter. Aktuell bleiben beide Versionen unverändert.

Jeder Versuch besitzt ein eigenes Staging-Verzeichnis. Ein nach einem abrupten Abbruch weiterlaufender nativer Kindprozess kann deshalb keinen neuen Versuch überschreiben. Erfolgreiche Versuche und gewöhnliche Fehler nach beendetem Installer räumen ihr eigenes Staging auf. Offene Journale und bei abrupten Abbrüchen möglicherweise noch laufende Kindprozesse behalten ihre Quellen; solche Versuche können Speicherplatz belegen.

Erst danach wird ein vollständiger Übernahmeplan erstellt. Zuerst werden alle Konflikte geprüft. Das Journal wird atomar geschrieben, jede Dateioperation prüft den erwarteten vorherigen SHA-256 und wird einzeln atomar übernommen beziehungsweise nach erneutem Inhaltsnachweis entfernt. Der neue Eigentumszustand wird zuletzt gespeichert. Minecraft wird erst nach erfolgreichem Abschluss gestartet.

## Eigentum und Lebenszyklus

`.cozy/state.json` enthält Schema 1, aktuelle Komponentenidentitäten (den Packwiz-Indexpfad), Aktivierungszustände und für tatsächlich nachgewiesene eigene Dateien Pfad, Hashverfahren und Nutzdateihash. Es enthält außerdem den aktuellen geprüften Katalog, den Packhash und die bereits behandelten Konfigurationspfade. Namen und Fabric-Mod-IDs sind niemals Löschkriterien.

Eine vorhandene Datei wird nur dann ersetzt oder entfernt, wenn der vorherige Zustand **und** ihr aktueller Inhalt den Eigentumsnachweis liefern. Ein unbekannter bestehender Zielpfad bleibt ein Konflikt, selbst bei identischem Inhalt. Bekannte aktive Dateien und ihre eindeutig zugehörige `.disabled`-Variante werden geprüft. Mehrdeutige aktive/deaktivierte Doppelbestände halten das Update an. Veränderte Dateien werden erhalten; der Konflikt muss auch bei einer offiziellen Entfernung zuerst gelöst werden.

Ausgeschaltete Optionen ohne installierte nachgewiesene Bytes besitzen ausschließlich einen Auswahlzustand, keinen erfundenen Dateibesitz. Eine ausgeschaltete bestehende Mod darf ihre alte Datei samt altem Hash und Dateinamen behalten. Beim Einschalten wird die aktuelle offizielle Version übernommen. Die Bibliotheken für sämtliche zulässigen Optionskombinationen bleiben verfügbar.

Eine offizielle Entfernung bereinigt genau den nachweislich verwalteten Bestand einschließlich deaktivierter Varianten. Anschließend verschwindet die Komponentenidentität aus dem Eigentumszustand. Eine unklare veränderte Datei bleibt erhalten, der Konflikt wird protokolliert und das gesamte Update hält ohne Zustandsänderung an. Erst nach sicherer Klärung kann die Entfernung abgeschlossen und Eigentümerschaft freigegeben werden. Es gibt keine dauerhafte Sperrliste und keine Suche nach gleichen Namen oder IDs. Eine danach privat installierte Kopie bleibt über weitere Updates erhalten, auch mit identischem Dateinamen und identischen Bytes. Eine spätere erneute offizielle Aufnahme ist ein neuer Lebenszyklus: Existiert dann eine persönliche Datei am Ziel, wird sie nicht stillschweigend übernommen.

## Persönliche Einstellungen

Alle bestehenden indizierten Konfigurationen erhalten `preserve=true`. Der Protector behandelt Konfigurationen zusätzlich als einmalige Startwerte: vorhandene Dateien werden nicht übernommen, bereits bekannte bewusst entfernte Dateien nicht erneut erzeugt und entfernte offizielle Konfigurationen nicht gelöscht. Auch neue Dateien werden nur angelegt, wenn der Pfad noch unbekannt und unbesetzt ist. Die eigentliche Serverpack-Konfigurationsauswahl und deren Nutzinhalte bleiben unverändert; der Server besitzt weiterhin seine eigenen verbindlichen Regeln.

`options.txt` ist weiterhin **nicht** indiziert. Nur die frische Prism-ZIP enthält einen sparsamen Startwert für die bisherigen vier Ressourcenpakete. Migration und Updates verändern weder Auswahl noch Reihenfolge. `shaderpacks`, zusätzliche Ressourcenpakete, Welten, Screenshots und sonstige persönliche Dateien werden nicht als Updateziele aufgenommen.

## Migration und Zustandsverlust

Die bestehende Instanzanweisung kann nicht über ein gewöhnliches Packwiz-Manifest ersetzt werden. Deshalb wird derselbe eigenständige Java-Launcher als `.migration.jar` bereitgestellt. Die grafische Ordnerauswahl beziehungsweise `--migrate INSTANCE` unterstützt die beiden Prism-Verzeichnisnamen. Ein bekannter alter Befehl und eine eindeutige Instanzstruktur sind Voraussetzung. Die Originalkonfiguration wird gesichert; die neue Java-Datei wird bereitgestellt, anschließend wird ausschließlich der bekannte Pre-Launch-Eintrag samt Override-Einstellung umgestellt. Wiederholungen und Abbrüche vor dem abschließenden Konfigurationswechsel sind wiederaufnehmbar. Unbekannte eigene Startanweisungen bleiben unverändert. Details: [Runtime und Migration](runtime.md).

Beim ersten geschützten Start importiert der Protector die früheren Packwiz-Zielpfade und `linkedFileHash` aus `packwiz.json`. Er berücksichtigt ausgelassene native Boolean-Standardwerte sowie native deaktivierte Optionen ohne Zielpfad. Hash und Pfad prüfen auch eine durch Prism deaktivierte Datei. Zusätzliche Dateien werden nicht adoptiert. Fehlende/kaputte Metadaten erlauben keine destruktive Schätzung. Ohne Eigentumsnachweis blockieren Kollisionen eine Neuinstallation; fremde Dateien an anderen Pfaden bleiben unangetastet.

Das Originalmanifest wird bytegenau unter `.cozy/legacy-packwiz.json` archiviert und sein alter aktiver `cachedFiles`-Bestand stillgelegt. `.cozy/initialized` markiert den vollzogenen Umstieg. Fehlt danach `state.json`, hält das Programm an, anstatt eine überholte Eigentumsliste erneut zu importieren. Archivierung und Stilllegung werden beim Wiederaufnehmen des Journals idempotent abgeschlossen. Die Sicherung von `.cozy/state.json` gehört zur Instanzsicherung. Das vollständige Löschen aller Zustandsnachweise kann Eigentum prinzipiell nicht rekonstruieren; neue Zielkollisionen werden dann konservativ behandelt.

## Sicherheitsgrenzen

- Relative portable Pfade: keine Traversierung, absoluten Pfade, Laufwerke, UNC-Pfade, Steuerzeichen, Windows-Gerätealiase, alternativen Datenströme oder Prozentkodierung.
- Alle relevanten lokalen Pfade und Vorfahren werden auf Symlinks/Junctions geprüft. Quelle, Staging, Zustand und Ziele müssen in der gewählten Instanz liegen. Der Migrationsmodus darf nur die ausdrücklich gewählte Prism-Instanz einschließlich ihrer `instance.cfg` verändern.
- Metadaten werden ausschließlich über HTTPS geladen; numerisches Loopback-HTTP dient den isolierten Tests. Keine Weiterleitung auf ein anderes Protokoll. Zeit- und Größenlimits gelten für Metadaten. Die bestehenden Nutzdatei-Downloadmechanismen verbleiben beim festgelegten Original-Installer.
- Unterstützte Eigentumshashes sind SHA-1, SHA-256 und SHA-512 entsprechend dem vorhandenen Packbestand; unbekannte Verfahren werden abgewiesen. Der Original-Installer und der originale Bootstrap besitzen festgelegte SHA-256-Identitäten im Build. Es erfolgt kein dynamischer Download ausführbarer neuer Versionen beim Spieler.
- Fehler vor dem Journal verändern keine Spieldateien. Ein unterbrochener Commit wird vor jedem weiteren Update fortgesetzt. Hashabweichungen seit dem vorbereiteten Commit verhindern die Fortsetzung. Das Verfahren ist ein wiederaufnehmbarer Vorwärts-Commit, kein atomarer Austausch sämtlicher Dateien auf einmal. Während eines unvollständigen Commits darf Minecraft nicht gestartet werden.

Es ist keine Sandbox gegen einen gleichzeitig böswillig Dateien austauschenden lokalen Prozess. Pfadprüfungen und Dateioperationen haben auf normalen Dateisystemen unvermeidbare Zeitfenster; Instanzdateien dürfen während des Updates nicht parallel verändert werden. Atomare Dateiumbenennung und Dateisperren müssen vom verwendeten lokalen Dateisystem unterstützt werden. Verzeichniseinträge werden nicht plattformübergreifend gegen jeden Stromausfall synchronisiert; beschädigte Zustände werden konservativ angehalten.

## Bauen, Prüfen und Pflegen

Entwickler benötigen Python 3.11+ und JDK 17+; das Spiel benötigt weiterhin Java 25. Die festen offiziellen JARs lokal bereitstellen; Quellen und SHA-256 stehen in `build_prism.py` und `build_serverpack.py`. Der Build validiert Herkunft, ZIP-CRC und die gesamte lokale Packwiz-Definition und erstellt deterministische ZIP-/JAR-Archive ohne maschinenspezifische Daten:

```sh
python -B scripts/build_prism.py --installer build/customization/packwiz-installer.jar --bootstrap build/customization/packwiz-installer-bootstrap.jar --output dist/customization/A-Cozy-Adventure-Prism-protection.zip
python -B -m unittest discover -s tests -v
python -B scripts/generate_mods.py --check
python -B scripts/build_serverpack.py --dry-run
```

Für die echte End-to-End-Suite `PACKWIZ_INSTALLER_JAR` setzen; `COZY_REQUIRE_E2E=1` macht fehlende Werkzeuge zu einem Fehler statt einer lokalen Überspringung. Optional verwendet `COZY_TEST_JAR` das gerade gebaute Artefakt. `ACA_TEST_REPORT` bestimmt die JSON-Ausgabe mit vollständigen Dateibeständen, SHA-256 vor/nach jedem Lauf und Installerausgaben. Der Workflow `customization.yml` erzwingt diese Tests auf Windows und Linux mit Java 17 und 25 und speichert Berichte als temporäre Artefakte. Er veröffentlicht nichts.

Neue oder geänderte Mods müssen anhand ihrer **exakten JARs** erneut auditiert werden. `audit_customization.py --jars PATH` prüft alle Packwiz-Downloadhashes und liest alle verschachtelten Fabric-Metadaten. Für unabhängige Optionen müssen Pflichtbestand allein, jede einzelne Option mit Pflichtbestand und alle Optionen zusammen die deklarierte Abhängigkeits- und Konfliktprüfung bestehen. Der Nachweis ist eine kompositionelle Prüfung positiver Abhängigkeiten, keine Ausführung aller 33 Millionen Kombinationen und kein vollständiger Fabric-Laufzeittest. Nach Metadatenänderungen `packwiz refresh`, Katalog neu erzeugen und Hashprüfungen ausführen. `preserve=true` muss für alle Konfigurationen erhalten bleiben; CI prüft dies.

Offizielle Dateien über die `.pw.toml`-Definition entfernen. Keine Dateinamen-Sperrliste anlegen. Eine erneute Aufnahme verwendet die normale neue Definition und muss persönliche Kollisionen respektieren. Aktualisierungen des Java-Launchers beziehungsweise seiner Installer-Version benötigen einen neuen geprüften Build und einen ausdrücklich geplanten Werkzeugumstieg; der Launcher lädt sich nicht selbst aus einer ungesicherten Quelle nach.

## Validierung und verbleibende Grenzen

Die automatisierte Suite verwendet temporäre Prism-/Minecraft-Dateibestände und den tatsächlichen unveränderten Packwiz 0.5.14. Sie prüft Neuinstallation, mehrere Updates, persönliche Mods/Ressourcen/Shader/Einstellungen, Optionswechsel, Pflicht-/Optionsupdates, beide ursprünglichen Aktivierungszustände der vierphasigen Mod- und Ressourcen-Lebenszyklen, Namenskollisionen auch bei gleichem Hash, veränderte Dateien, fehlende/beschädigte Zustände, Download-/Prozessabbruch, teilweise übernommene Journale, native Manifestmigration, Idempotenz und Pfadangriffe. Die separaten Migrationstests führen echten Java-Code aus. Bestehende Generator-, Serverpack-, Browser- und Releaseerkennungstests bleiben bestehen.

Ein vollständiger Minecraft-GUI-Erststart, Shaderdarstellung, zusätzliche private Modkombinationen, Multiplayer-Beitritt und Dedicated-Server-Laufzeit sind durch Dateisystemtests nicht bewiesen. Die bisherigen Server-Laufzeitfragen bleiben bestehen. Der veröffentlichte Pages-Endpunkt wird durch diesen Branch nicht geändert. Bestehende Spieler erhalten ohne den einmaligen Werkzeugumstieg noch keine vollständige Schutzgarantie. Der Merge muss daher mit der Bereitstellung der geprüften Migration und ihrer Spieleranleitung koordiniert werden; kein automatisches Release ist Teil dieses PR.


## Upgrade der Schutzschicht von v1.0.0

Der vorhandene Updater ersetzt seine eigene JAR nicht automatisch. Die v1.0.1-Migrations-JAR kann den bekannten offiziellen v1.0.0-Protector bei unverändertem geschütztem Prism-Startbefehl austauschen. Zulässig ist ausschließlich SHA-256 `99dc680b056805515d48cab3800a096239b4206ee584402873107fe06023ffc6` aus GitHub-Release-Asset 656125771. Vor dem atomaren Austausch entsteht `minecraft/cozy-customization.jar.before-v1.0.1`; vorhandene abweichende Backups und unbekannte JARs führen zum Abbruch. Die komplette `.cozy`-Struktur, insbesondere `state.json`, sowie `instance.cfg` bleiben erhalten. Dieser Schritt ist vor der Packwiz-Umstellung nötig, damit auch unklarer Besitz bei einer offiziellen Entfernung mit der strengeren Regel behandelt wird. Keine Neuinstallation, kein Zustandsreset.
