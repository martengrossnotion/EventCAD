# EventCAD

FreeCAD-Add-on für die Veranstaltungsplanung. Der Arbeitsbereich **Event** bringt eine eigene Werkzeugleiste mit. Über das Podest-Icon öffnet sich **BühnenSnap**, die Bibliothek zum Platzieren und Andocken von Bühnenpodesten.

## Funktionen

- BÜTEC Standard 2 × 1 m, Planungsmaß 1 × 1 m und frei eingestellte Podestmaße.
- Kanten-Snap per Mausklick mit 0° oder 90° Drehung und drei Kantenausrichtungen.
- Bündige Oberkanten und Überlappungsprüfung zwischen BühnenSnap-Podesten.
- Weiterbearbeitung von `.FCStd`-Plänen, die mit dem ursprünglichen BühnenSnap-Makro angelegt wurden.

## Installation

Voraussetzung ist FreeCAD 1.0 oder neuer. Das Add-on nutzt die mit FreeCAD gelieferten Python-Bibliotheken.

1. Lade den Quellcode über **Code → Download ZIP** herunter und entpacke ihn.
2. Ermittle bei Bedarf in FreeCAD über **Ansicht → Bedienfelder → Python-Konsole** mit `print(App.getUserAppDataDir())` den Benutzerordner. Unter Windows liegt er üblicherweise in `%APPDATA%\FreeCAD`.
3. Kopiere den entpackten Ordner in den Unterordner `Mod`. Lege `Mod` bei Bedarf an. Die `package.xml` muss direkt im Add-on-Ordner liegen, etwa unter `Mod/EventCAD-main/package.xml`.
4. Starte FreeCAD neu, wähle **Event** und klicke auf das Podest-Icon.

## Bedienung

Wähle einen Podesttyp und klicke auf **Podest an Koordinaten setzen**. Aktiviere **Andocken starten** und klicke in der Draufsicht knapp innerhalb der gewünschten Kante eines vorhandenen BühnenSnap-Podests. Im Bedienfeld stellst du Drehung und Kantenausrichtung für den nächsten Klick ein.

## Aufbau

Der Quellcode liegt in `freecad/buehnensnap/`. `docking.py` berechnet die Platzierung über lokale Anschlussrahmen. `decks.py` enthält Katalog und Podestgeometrie. `init_gui.py` registriert den Event-Arbeitsbereich mit seiner Werkzeugleiste.
