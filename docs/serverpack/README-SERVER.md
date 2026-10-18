# A Cozy Adventure – Dedicated Server

Dieses Archiv enthält Mods und eine geprüfte Auswahl vorhandener Konfigurationen. Es enthält **keine Welt und kein Minecraft-/Fabric-Server-JAR**. Die endgültige Dedicated-Server-Kompatibilität muss in Phase B getestet werden.

## Voraussetzungen und Installation bei Host Unlimited

1. Einen neuen bzw. gesicherten Server mit **Minecraft 26.3**, **Fabric Loader 0.19.5** und **Java 25** im Hostingpanel einrichten. Ein vom Panel gewählter anderer Loaderstand muss korrigiert werden; dieses Archiv aktualisiert keine Versionen.
2. Den Server stoppen. Das Archiv in das Server-Hauptverzeichnis entpacken, sodass `mods/` und `config/` direkt dort liegen. Bei einer bestehenden Installation zuvor sichern und einen sauberen Modbestand herstellen; ein ZIP-Upload entfernt keine alten oder clientseitigen JARs.
3. Das vom Hoster eingerichtete Fabric-Server-Startziel verwenden. Kein beliebiges Mod-JAR als Startdatei auswählen. RAM und Startparameter entsprechend dem gebuchten Tarif einstellen.
4. Die Minecraft-EULA selbst prüfen und, falls akzeptiert, über den vorgesehenen Ablauf bestätigen. Das Archiv setzt `eula=true` nicht automatisch.
5. Zunächst mit einer separaten Testwelt starten. Die endgültige Welt wird später gesondert vorbereitet und hochgeladen; dieses Archiv enthält keine Spielstände.
6. Mit dem vollständigen A-Cozy-Adventure-Clientpack verbinden. Es enthält alle 137 Mods einschließlich JEI und MezzConfig und insbesondere das **Colorful Trims RP**. Das Serverarchiv enthält keine Client-Ressourcenpakete oder Shader.

## Offene Host- und Konfigurationsentscheidungen

- **Simple Voice Chat:** Den tatsächlich zugewiesenen **UDP-Port** bei Host Unlimited ermitteln. Nach dem ersten Start `config/voicechat/voicechat-server.properties` manuell prüfen und den zugewiesenen Port setzen. Bei Bedarf auch `voice_host` mit dem Hoster abstimmen. Es wird kein Port als produktive Vorgabe mitgeliefert. TCP-Spielport und UDP-Voice-Port sind unterschiedliche Anforderungen.
- **Open Parties and Claims:** Serverkonfiguration und Schutz-/Berechtigungseinstellungen beim ersten Start prüfen. Die im Quellrepository unter `config-review/` abgelegte Datei ist nicht enthalten. Ihre Adapter `prometheus` und `argonauts_guilds` dürfen ohne die entsprechenden Mods nicht ungeprüft übernommen werden.
- **Easy NPC:** Rechte zum Erstellen/Bearbeiten von NPCs und Regeln für externe Texturen vor einer öffentlichen Nutzung prüfen. Sicherheitsdateien aus `config-review/` wurden nicht automatisch eingebunden. Skin-Templates und lokale UI-Konfigurationen wurden nicht übernommen.
- **Polymer:** Eine zusätzliche Ressourcenpaketauslieferung müsste ausdrücklich eingerichtet werden. Autohost ist hier nicht konfiguriert. Der alte Verweis auf `world/resources.zip` ist kein mitgeliefertes Asset.
- **Traveler's Backpack:** Prüfen, ob die beigefügte `config/travelersbackpack-server.toml` am tatsächlichen Dedicated-Server-Ladeort wirksam ist. Der Builder erfindet keine Welt-/Defaultkonfigurationen.
- **Gemeinsame Einstellungen:** Die ausgewählten Common-Dateien bleiben unverändert. Wirksame Einstellungen für FrozenLib, Trinkets, Puddles & Floods und Sound Physics sowie nicht übernommene Ribbits-/NPC-Einstellungen im Test bestätigen.
- **Weltgenerierung:** Tectonic, Terralith, Climate Rivers und Strukturen gemeinsam prüfen. Erst danach die endgültige Welt vorbereiten und gegebenenfalls Chunky verwenden.

## Nachweis und Tests

`build-manifest.json` nennt den Quellcommit, den Zustand des lokalen Arbeitsbaums, den Eingabe-Fingerabdruck, eingeschlossene JARs mit Hashes und Fabric-Versionen sowie ausgeschlossene Mods und Konfigurationen. Ein als geändert markierter Arbeitsbaum wird durch den Fingerabdruck zusätzlich beschrieben; der Commit allein identifiziert dann nicht alle Eingaben.

`build-report.json` und `build-report.txt` dokumentieren Dateiprüfung, statische Abhängigkeitsprüfung und offene Konfigurationsfragen. Eine erfolgreiche ZIP-Erstellung bestätigt Hashes und verfügbare deklarierte Abhängigkeiten, aber weder eine vollständige Fabric-Konfliktauflösung noch den erfolgreichen Serverstart.

Vor der Freigabe Clientbeitritt, neue Chunks, Kampf/Magie, NPC-Konfiguration, Rezeptabgleich, Tod und Inventarwiederherstellung, Claims, Voice Chat sowie Neustart und Persistenz testen. Zugangsdaten, IP-Adressen, neue Spielstände oder lokal erzeugte Serverdateien nicht als Build-Eingaben zurückkopieren.
