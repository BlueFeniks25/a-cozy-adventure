# A Cozy Adventure individuell anpassen

Diese Anleitung gilt für Instanzen mit **Player Customization Protection**. Im Startfenster erscheint „Persönliche Mods und Einstellungen werden geschützt“. Die unveränderte v0.0.2-Installation benötigt zuerst den unten beschriebenen einmaligen Umstieg.

## Bestehende v0.0.2-Installation übernehmen

1. Minecraft schließen und die Instanz während des Umstiegs nicht starten. Eine normale Sicherung der gesamten Instanz ist weiterhin sinnvoll.
2. Die zur geprüften Prism-ZIP gehörende Datei mit der Endung `.migration.jar` herunterladen und per Doppelklick mit Java öffnen. Das Spiel verwendet bereits Java 25; das Hilfsprogramm benötigt mindestens Java 17. Es werden weder Python noch Git, PowerShell oder andere Entwicklerwerkzeuge benötigt.
3. Den **Instanzordner** auswählen, der `instance.cfg`, `mmc-pack.json` und `minecraft` beziehungsweise `.minecraft` enthält. Prism öffnet diesen Ordner über das Kontextmenü der Instanz.
4. Nach der Erfolgsmeldung wie gewohnt in Prism starten. Beim ersten geschützten Start wird das bisherige lokale Packwiz-Manifest ausgewertet.

Der Umstieg sichert `instance.cfg` als `instance.cfg.before-customization`, ergänzt eine eigene Java-Datei und stellt den Pre-Launch-Befehl um. Welten, Screenshots, Optionen, Shader und zusätzliche Mods werden dabei nicht verändert. Minecraft muss nicht neu installiert werden. Der unveränderte offizielle Bootstrap bleibt vorhanden.

Bei einer unbekannten eigenen Startanweisung, einer gleichnamigen abweichenden Java-Datei, fehlenden oder beschädigten Zustandsdateien hält das Programm an. Die Meldung nennt den Konflikt. **Nicht einfach `packwiz.json` oder `.cozy` löschen:** Diese Dateien enthalten den Eigentumsnachweis. Die Sicherung beziehungsweise den Fehlerbericht für die Packbetreuung aufbewahren.

Der alte v0.0.2-Befehl kann die neue Schutzschicht nicht selbst aktivieren. Vollständiger Schutz beginnt deshalb erst nach diesem Umstieg. Die v1.0.0-Kandidaten werden im Release-Branch als CI-Artefakte vorbereitet; eine neue Veröffentlichung ist gesondert erforderlich. Der [Rollout-Plan](../releases/v1.0.0-rollout.md) verlangt den Umstieg bestehender Instanzen vor Merge/Pages-Änderungen.

## Offizielle Client-Mods aus- und einschalten

Bei jedem Start bleibt das Schutzfenster vier Sekunden geöffnet. **Auswahl ändern** öffnet die Liste der offiziellen optionalen Bestandteile. Häkchen ändern, bestätigen und starten. Ohne Änderung läuft der Start automatisch weiter. Die Auswahl bleibt bei späteren Updates erhalten.

25 unabhängig nutzbare Client-Mods sind anfangs eingeschaltet. Gameplay-Mods und benötigte Bibliotheken sind Pflichtbestandteile. Beispielsweise bleiben Sodium für Iris und libIPN für Inventory Profiles Next installiert, auch wenn ihre Benutzer ausgeschaltet sind. Die [vollständige Prüfung](dependencies.md) erklärt die Auswahl.

Alternativ kann Prism eine offizielle optionale Mod deaktivieren: Es benennt ihre `.jar` in `.jar.disabled` um. Der geschützte Updater erkennt diesen Zustand anhand des gespeicherten Pfades und Inhalts und behält ihn. Dieselbe Datei in Prism wieder aktivieren oder die Startauswahl benutzen. Pflichtmods dürfen nicht deaktiviert werden.

Wenn eine ausgeschaltete Mod aktualisiert wird, bleibt ihre alte deaktivierte Datei zunächst erhalten. Erst beim Einschalten wird die aktuelle offizielle Version installiert. Wird die Mod offiziell entfernt, wird auch die nachweislich offizielle deaktivierte Datei einmalig bereinigt. Eine danach privat installierte Kopie gehört dir und bleibt bei späteren Updates erhalten.

## Eigene Client-Mods hinzufügen

In Prism **Instanz bearbeiten → Mods → Mods herunterladen / Download Mods** für die integrierte Suche verwenden (Minecraft 26.3 und Fabric prüfen). Alternativ **Hinzufügen / Add** für eine eigene JAR verwenden oder die JAR in den `mods`-Ordner der Instanz legen. Nur zur Minecraft-/Fabric-Version passende Client-Mods benutzen; erforderliche Zusatzbibliotheken und mögliche Konflikte beachten. Eine zusätzliche Mod kann die Verbindung zum Server oder das Spiel beeinträchtigen.

Dateien, die nicht offiziell verwaltet werden, bleiben erhalten. Trifft eine offizielle Datei auf denselben Namen wie eine persönliche Datei, hält das Update an. Auch eine bytegleiche Datei wird ohne Eigentumsnachweis nicht einfach übernommen. `.cozy/conflicts.txt` nennt die betroffenen Pfade. Die betreffende persönliche Datei über den Dateimanager außerhalb von `mods` beziehungsweise `resourcepacks` sichern und erneut starten. So bleibt eine rückholbare Kopie erhalten. Keine Zustandsdateien löschen, um den Konflikt zu umgehen.

Wurde eine offizielle Mod entfernt und anschließend privat wieder installiert, wird sie nicht weiter offiziell aktualisiert. Du verwaltest dann Version und Abhängigkeiten selbst. Nimmt das Pack sie später erneut auf und kollidiert der Dateiname, wird dieser Konflikt ebenfalls sichtbar gemeldet.

## Ressourcenpakete und Reihenfolge

Unter **Optionen → Ressourcenpakete** kannst du offizielle Pakete aus- und einschalten und ihre Reihenfolge ändern. Höher angeordnete Pakete haben Vorrang. Eigene ZIP-Dateien können in `resourcepacks` hinzugefügt und wieder entfernt werden. Deine Auswahl und Reihenfolge in `options.txt` werden vom Updater nicht verändert.

Die Startauswahl steuert zusätzlich, ob die offiziellen Ressourcenpaket-Dateien installiert bleiben. Für das gewöhnliche Ein- und Ausschalten im Spiel genügt das Minecraft-Menü. Entfernst du eine offizielle Datei manuell, während sie in der Startauswahl eingeschaltet bleibt, wird sie erneut heruntergeladen. Persönliche Pakete werden nicht nachgeliefert oder gelöscht.

Neue Prism-Installationen erhalten die bisherigen vier offiziellen Ressourcenpakete in derselben relativen Reihenfolge als einmaligen Startwert. Bestehende Installationen behalten ihre eigenen Optionen. Offiziell entfernte Paketdateien werden einmalig bereinigt; eine anschließende private Neuinstallation bleibt erhalten. Veraltete Einträge in `options.txt` werden nicht automatisch umsortiert oder entfernt; das Ressourcenpaket-Menü zeigt den aktuellen Bestand.

## Eigene Shader und Einstellungen

Shader-ZIPs kommen in `shaderpacks`; die Auswahl erfolgt in Iris unter den Shader-Einstellungen. Iris muss dafür in der Startauswahl aktiviert sein. Eigene Shader, deren Einstellungen sowie `options.txt` bleiben persönlich.

Mitgelieferte Konfigurationen werden nur als erste Vorgabe angelegt. Vorhandene eigene Änderungen werden nicht überschrieben. Wenn du eine bereits bekannte Konfigurationsdatei bewusst entfernst, erzwingt der Updater sie später nicht erneut. Der jeweilige Mod kann beim Spielstart seine eigenen Standardwerte erzeugen. Der Multiplayer-Server bestimmt weiterhin seine serverseitigen Spielregeln.

## Probleme mit zusätzlichen Mods eingrenzen

Minecraft schließen, eine Sicherung anlegen und zuletzt hinzugefügte persönliche Mods zunächst außerhalb des `mods`-Ordners aufbewahren. In der Startauswahl optionale Mods schrittweise ausschalten. Nach jeder Änderung erneut starten. Pflichtmods und gemeinsam benötigte Bibliotheken beibehalten. Auch Shader und zusätzliche Ressourcenpakete probeweise im Spiel deaktivieren.

Für die Packbetreuung sind der genaue Fehler, die zusätzlichen Modversionen, Prism-Konsole und gegebenenfalls `logs/latest.log` beziehungsweise ein Crashreport hilfreich. Bei Updateproblemen kommen `.cozy/conflicts.txt` und `.cozy/installer.log` hinzu. Protokolle vor dem Weitergeben auf persönliche Angaben prüfen. Der Updater startet Minecraft bei einem unaufgelösten Konflikt nicht.

Ein unterbrochener Download verändert den Spielbestand noch nicht. Nach einem Abbruch während der Übernahme setzt der nächste Start die protokollierte Transaktion fort. Ist eine betroffene Datei zwischenzeitlich verändert worden, hält das Programm zur Klärung an. Während eines Updates die Instanzdateien daher nicht parallel bearbeiten.

## Bebilderter Spielerwegweiser

[Installation, Mods, Ressourcenpakete, Tasten und FAQ auf der Website](../../index.html#wegweiser). Die sieben Abbildungen sind ausdrücklich schematisch, keine Prism-Screenshots.
