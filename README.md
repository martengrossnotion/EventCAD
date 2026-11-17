# EventCAD

FreeCAD-Add-on für die Veranstaltungsplanung. Der Arbeitsbereich **Event** bringt eine eigene Werkzeugleiste mit. Über das Podest-Icon öffnet sich **BühnenSnap**, die Bibliothek zum Platzieren und Andocken von Bühnenpodesten.

## Funktionen

- Auswahl von Podestsystem und Plansymbol aus der STEP-Modellbibliothek, mit freien Planungsmaßen.
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

Wähle **Podestsystem** und **Plansymbol** und klicke auf **Podest an Koordinaten setzen**. Unter **Planungsmaß → Eigenes Maß** kannst du Länge, Breite und Körperhöhe frei eingeben. Aktiviere **Autosnap starten** und klicke knapp innerhalb der gewünschten Kante eines vorhandenen BühnenSnap-Podests. Das funktioniert in beiden Ansichten. Die Position vorhandener Podeste kannst du im Modellbaum ändern. Für ein anderes Modell setzt du das Podest mit dem gewünschten Plansymbol neu.

**Drehung** stellt jedes neue Podest im Grundriss **0° hochkant** oder **90° quer**. Das gilt für Startpodeste und für Autosnap. Der Klick wählt die nächstgelegene Zielkante und das nähere Ende dieser Kante. Dort liegen die Ecken bündig, auch wenn eine Platte übersteht. Ist die Position durch ein anderes Podest belegt, probiert Autosnap das andere Ende derselben Kante. Sind beide Positionen belegt, erscheint eine Meldung und der Plan wird nicht geändert.

Autosnap setzt voraus, dass die Kanten des Zielpodests parallel zu den X- und Y-Achsen des Plans verlaufen.

## STEP-Modelle hinzufügen oder austauschen

Unter `freecad/buehnensnap/resources/models/` hat jedes Podestsystem einen eigenen Unterordner. Lege zusätzliche `.step`- oder `.stp`-Dateien im gewünschten Ordner ab und öffne BühnenSnap erneut. Im Dropdown **Plansymbol** erscheinen diese Modelle mit ihrem Dateinamen. Bei zusätzlichen Dateien übernimmt EventCAD die Maße aus den äußeren Abmessungen des Modells in X, Y und Z. **Planungsmaß → Eigenes Maß** erzeugt einen Quader passend zu den eingegebenen Maßen.

1. Öffne in FreeCAD **Ansicht → Bedienfelder → Python-Konsole** und gib `print(App.getUserAppDataDir())` ein. Öffne im Explorer den ausgegebenen Ordner und darunter `Mod`, deinen EventCAD-Ordner und `freecad/buehnensnap/resources/models/`.
2. Suche das Modell im Unterordner des Systems. Für **BÜTEC Standard, 2 × 1 m** ist das `buetec-standard/2000x1000.step`. Sichere die Originaldatei, bevor du sie ersetzt.
3. Öffne die STEP-Datei als Ausgangspunkt in FreeCAD oder erstelle ein eigenes Modell. Richte das Modell so aus, dass die Plattenlänge in X, die Breite in Y und die Höhe in Z verläuft. Der gesamte Körper muss in X × Y das Katalogmaß haben. Die Trittfläche muss am höchsten Punkt liegen. Steckbeine können nach unten reichen. EventCAD setzt die Oberkante beim Platzieren automatisch auf die eingestellte Z-Höhe.
4. Wähle im Modellbaum die fertigen Volumenkörper aus. Exportiere sie über **Datei → Exportieren** als **STEP**. Speichere deine bearbeitbare FreeCAD-Konstruktion bei Bedarf zusätzlich als `.FCStd`.
5. Ersetze die Datei im Add-on-Ordner unter demselben Namen einschließlich `.step`. Setze in EventCAD ein neues Podest derselben Größe und prüfe es über **3D-Modell**. EventCAD liest die Datei beim Platzieren ein. Bei einem falschen Maß oder einer ungültigen Datei erscheint eine Meldung im BühnenSnap-Bedienfeld.

Die Geometrie wird in der Plandatei gespeichert. Für bereits platzierte Podeste kannst du das neue Modell übernehmen, indem du sie neu setzt. Grundriss, Autosnap und Kollisionsprüfung verwenden die beim Platzieren gesetzten Maße. Die Darstellung verwendet die EventCAD-Farben.

## Aufbau

Der Quellcode liegt in `freecad/buehnensnap/`. `decks.py` enthält Katalog, Podestkörper, Grundrisssymbole und die Autosnap-Platzierung. `view_modes.py` verwaltet die Darstellung pro Dokument. `init_gui.py` registriert den Event-Arbeitsbereich mit seiner Werkzeugleiste.
