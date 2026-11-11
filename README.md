# EventCAD

FreeCAD-Add-on für die Veranstaltungsplanung. Der Arbeitsbereich **Event** bringt eine eigene Werkzeugleiste mit. Über das Podest-Icon öffnet sich **BühnenSnap**, die Bibliothek zum Platzieren und Andocken von Bühnenpodesten.

## Funktionen

- Getrennte Auswahl für Podestsystem und Plattenmaß mit BÜTEC Standard, nivtec Standard und freien Planungsmaßen.
- Umschaltbarer 2D-Grundriss und isometrisches 3D-Modell in der Event-Werkzeugleiste.
- Autosnap per Mausklick an die nächste Kante und Ecke, mit Ausweichposition bei Kollision.
- Bündige Oberkanten und Überlappungsprüfung zwischen BühnenSnap-Podesten.
- Weiterbearbeitung von `.FCStd`-Plänen, die mit dem ursprünglichen BühnenSnap-Makro angelegt wurden.

## Installation

Voraussetzung ist FreeCAD 1.0 oder neuer. Das Add-on nutzt die mit FreeCAD gelieferten Python-Bibliotheken.

1. Lade den Quellcode über **Code → Download ZIP** herunter und entpacke ihn.
2. Ermittle bei Bedarf in FreeCAD über **Ansicht → Bedienfelder → Python-Konsole** mit `print(App.getUserAppDataDir())` den Benutzerordner. Unter Windows liegt er üblicherweise in `%APPDATA%\FreeCAD`.
3. Kopiere den entpackten Ordner in den Unterordner `Mod`. Lege `Mod` bei Bedarf an. Die `package.xml` muss direkt im Add-on-Ordner liegen, etwa unter `Mod/EventCAD-main/package.xml`.
4. Starte FreeCAD neu, wähle **Event** und klicke auf das Podest-Icon.

## Bedienung

Öffne oder erstelle einen Plan und klicke in der Event-Werkzeugleiste auf **2D-Grundriss**. Podeste erscheinen als flache, anklickbare Flächen auf Höhe der jeweiligen Oberkante. Mit **3D-Modell** siehst du dieselben Podeste als Volumenkörper in isometrischer Ansicht. Der Modus wird mit dem Plan gespeichert. Beim ersten Wechsel in den 2D-Grundriss ergänzt EventCAD die Symbole auch für vorhandene BühnenSnap-Podeste.

Wähle **Podestsystem** und **Plattenmaß** und klicke auf **Podest an Koordinaten setzen**. Unter **Planungsmaß → Eigenes Maß** kannst du Länge, Breite und Körperhöhe frei eingeben. Aktiviere **Autosnap starten** und klicke knapp innerhalb der gewünschten Kante eines vorhandenen BühnenSnap-Podests. Das funktioniert in beiden Ansichten. Änderungen an vorhandenen Podesten nimmst du im Modellbaum vor.

**Drehung** stellt jedes neue Podest im Grundriss **0° hochkant** oder **90° quer**. Das gilt für Startpodeste und für Autosnap. Der Klick wählt die nächstgelegene Zielkante und das nähere Ende dieser Kante. Dort liegen die Ecken bündig, auch wenn eine Platte übersteht. Ist die Position durch ein anderes Podest belegt, probiert Autosnap das andere Ende derselben Kante. Sind beide Positionen belegt, erscheint eine Meldung und der Plan wird nicht geändert.

Autosnap setzt voraus, dass die Kanten des Zielpodests parallel zu den X- und Y-Achsen des Plans verlaufen.

## Aufbau

Der Quellcode liegt in `freecad/buehnensnap/`. `decks.py` enthält Katalog, Podestkörper, Grundrisssymbole und die Autosnap-Platzierung. `view_modes.py` verwaltet die Darstellung pro Dokument. `init_gui.py` registriert den Event-Arbeitsbereich mit seiner Werkzeugleiste.
