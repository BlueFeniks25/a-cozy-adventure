# Vorbereitete Welt und gemeinsame Xaero-Karte

## Aktueller Stand

Unified Xaero Worldmap 2.0.4 ist noch nicht verifiziert integriert. Diese Anleitung trennt sichere Weltübertragung von offenen modabhängigen Schritten. Genaue Unified-Speicherpfade, Upload-/Importfunktionen und Formatgrenzen müssen anhand der offiziellen passenden Fabric-Version nachgewiesen werden. Es gibt bislang keinen erfolgreichen Zwei-Client-Synchronisierungstest.

## Chunky-Welt mit 6.000 Blöcken Radius übertragen

1. Lokale Welt nach abgeschlossenem Chunky-Lauf speichern und Minecraft vollständig beenden. Den kompletten tatsächlichen Weltordner aus der Prism-Instanz sichern, einschließlich `level.dat`, `region`, `entities`, `poi`, Nether/End und zusätzlichen Dimensions-/Moddaten. Die ursprüngliche lokale Kopie unverändert behalten. Pack/Minecraft/Fabric müssen auf beiden Seiten übereinstimmen.
2. Dedicated Server sauber stoppen; nicht nur den Weltordner überschreiben. Vollständigen bisherigen Serverordner sichern, externe Welt-/Kartenpfade zusätzlich sichern und Wiederherstellung kontrollieren. Bestehende Welt umbenennen oder separat archivieren. Nie zwei Welten durch Überkopieren vermischen.
3. Vorbereitete Welt als vollständigen Ordner auf den Server kopieren. `level-name` in `server.properties` muss auf diesen Ordner zeigen. Nicht unbesehen die gesamte lokale `options.txt` oder Clientkonfiguration auf den Server übernehmen. Erst in einer Kopie prüfen, ob Spawn, Dimensionen, Inventare und UUID-Zuordnung stimmen.
4. Nach Abschluss der offenen Modprüfung Server mit dem passenden Serverpack einschließlich verpflichtender Unified-Version starten; erst dann Clients mit derselben geprüften Mod verbinden. Neue Gebiete gemeinsam erkunden. Ob A erkundete Flächen an B und einen späteren Spieler C verteilt werden, muss praktisch geprüft werden.

**Chunky erzeugt Weltchunks. Das bedeutet nicht, dass Xaero-Kartenflächen bereits erkundet oder in einem gemeinsamen Kartenspeicher vorhanden sind.** Ein Radius von 6.000 Blöcken ist keine automatisch aufgedeckte Weltkarte.

## Bestehende lokale Xaero-Daten

`XaeroWorldMap/`, `XaeroWaypoints/` und vorhandene Xaero-Einstellungen in der Clientinstanz vollständig sichern. Sie werden durch den Pack-Updater nicht verwaltet oder gelöscht. Lokale Singleplayer- und Multiplayer-Karten können unterschiedliche Server-/Weltidentitäten verwenden. Eine vollständige Client-Neuinstallation besitzt diese lokalen Daten zunächst nicht.

Es wurde kein verlässlicher unterstützter Unified-Importweg verifiziert. Daher keine automatische Konvertierung und kein blindes Kopieren lokaler Karten in einen geratenen Serverordner. Nach Freigabe der passenden Version ausschließlich den offiziell dokumentierten Import-/Uploadweg mit einer **Kopie** der Daten am Testserver verwenden. Wenn dafür kein verlässlicher Weg belegt werden kann, Originaldaten lokal behalten und die gemeinsame Karte durch erneute Erkundung aufbauen. Wegpunkte, private Einstellungen und erkundete Kartenflächen sind getrennte Datenarten; ihre vollständige gegenseitige Synchronisierung ist nicht belegt.

## Persistenz und Backup

Das Ziel ist eine serverseitig dauerhafte gemeinsame Karte. Der konkrete Speicherort der gewünschten Unified-Version ist **offen**. Bis er verifiziert ist, umfasst ein sicheres Backup den vollständigen gestoppten Serverordner plus alle externen Welt-/Kartenpfade; Welt und gemeinsame Karte immer als zusammengehörigen Stand sichern. Anschließend konkrete Pfade, Weltzuordnung und Wiederherstellung hier ergänzen.

Ein reguläres Modpack-Update darf weder die Welt noch Kartenverzeichnisse überschreiben. Beim Serverneustart muss dieselbe Welt mit derselben bestätigten Datenablage verwendet werden. Dauerhaftigkeit, Wiederaufnahme und Abgleich an einen neu installierten Client müssen vor Freigabe praktisch geprüft werden. Erst dann kann beschrieben werden, welche vorhandenen gemeinsamen Flächen ein neuer Spieler tatsächlich erhält. Private lokale Altbestände werden dadurch nicht automatisch wiederhergestellt.

Bei Minecraft-/Xaero-Versionswechseln können sich Kartenformate ändern. **Kein Versprechen automatischer Übernahme bei jedem zukünftigen Minecraft-Update.** Vorher vollständiges Backup, Upstream-Kompatibilitäts-/Migrationshinweise der exakten Versionen lesen und Migration in separater Kopie testen. Nur dokumentierte Konvertierung verwenden. Falls inkompatibel: Originalbackup und passenden alten Softwarestand behalten, über unterstützten Import oder neuen gemeinsamen Kartenbestand entscheiden. Nie einzige vorhandene Kartendaten durch einen Teststart überschreiben.
