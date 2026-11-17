# EventCAD

FreeCAD-Add-on für die Veranstaltungsplanung. Der Arbeitsbereich **Event** bringt eine eigene Werkzeugleiste mit. Über das Podest-Icon öffnet sich **BühnenSnap**, die Bibliothek zum Platzieren und Andocken von Bühnenpodesten.

## Funktionen

- Auswahl von Podestsystem und Plansymbol aus der STEP-Modellbibliothek, mit freien Planungsmaßen.
- Ein Ordner je Symbol mit STEP für 3D und FCStd für den umschaltbaren 2D-Grundriss.
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

Öffne oder erstelle einen Plan und klicke in der Event-Werkzeugleiste auf **2D-Grundriss**. Podeste erscheinen mit ihrem 2D-Symbol auf Höhe der jeweiligen Oberkante. EventCAD verwendet die **FCStd-Datei im Symbolordner** für die 2D-Darstellung und die **STEP-Datei desselben Ordners** für 3D. Die beiden Dateien dürfen unterschiedlich heißen. Mit **3D-Modell** siehst du dieselben Podeste als Volumenkörper in isometrischer Ansicht. Der Modus wird mit dem Plan gespeichert. Beim ersten Wechsel in den 2D-Grundriss ergänzt EventCAD die Symbole auch für vorhandene BühnenSnap-Podeste.

Wähle **Podestsystem** und **Plansymbol** und klicke auf **Podest an Koordinaten setzen**. Unter **Planungsmaß → Eigenes Maß** kannst du Länge, Breite und Körperhöhe frei eingeben. Aktiviere **Autosnap starten** und klicke knapp innerhalb der gewünschten Kante eines vorhandenen BühnenSnap-Podests. Das funktioniert in beiden Ansichten. Die Position vorhandener Podeste kannst du im Modellbaum ändern. Für ein anderes Modell setzt du das Podest mit dem gewünschten Plansymbol neu.

**Drehung** stellt jedes neue Podest im Grundriss **0° hochkant** oder **90° quer**. Das gilt für Startpodeste und für Autosnap. Der Klick wählt die nächstgelegene Zielkante und das nähere Ende dieser Kante. Dort liegen die Ecken bündig, auch wenn eine Platte übersteht. Ist die Position durch ein anderes Podest belegt, probiert Autosnap das andere Ende derselben Kante. Sind beide Positionen belegt, erscheint eine Meldung und der Plan wird nicht geändert.

Autosnap setzt voraus, dass die Kanten des Zielpodests parallel zu den X- und Y-Achsen des Plans verlaufen.

## STEP-Modelle hinzufügen oder austauschen

Unter `freecad/buehnensnap/resources/models/` hat jedes Podestsystem einen eigenen Unterordner. Darin liegt **für jedes Symbol ein weiterer Ordner**. Jeder Symbolordner enthält **genau eine `.step`- oder `.stp`-Datei für 3D und eine `.FCStd`-Datei für 2D**. Dateinamen und Groß-/Kleinschreibung der Endungen sind frei wählbar; ein Suffix ist nicht nötig. Die Auswahl **Plansymbol** zeigt die Symbolordner des gewählten Systems. Bekannte Kataloggrößen werden weiter als Maß angezeigt.

Beispiel:

| Symbolordner relativ zu `resources/models/` | 3D-Datei | 2D-Datei |
| --- | --- | --- |
| `buetec-standard/2000x1000/` | `2000x1000.step` | `2000x1000.FCStd` |
| `buetec-standard/Mein Podest/` | `Koerper.step` | `Grundriss.FCStd` |

Lege für ein neues Symbol einen Ordner mit den beiden Dateien an und öffne BühnenSnap erneut. Bei zusätzlichen Symbolen übernimmt EventCAD die Maße aus den äußeren Abmessungen des STEP-Modells in X, Y und Z. **Planungsmaß → Eigenes Maß** erzeugt einen Quader passend zu den eingegebenen Maßen. Ordner ohne STEP-Datei werden nicht angeboten. Ordner mit mehreren STEP-Dateien werden mit einer Warnung übersprungen.

1. Öffne in FreeCAD **Ansicht → Bedienfelder → Python-Konsole** und gib `print(App.getUserAppDataDir())` ein. Öffne im Explorer den ausgegebenen Ordner und darunter `Mod`, deinen EventCAD-Ordner und `freecad/buehnensnap/resources/models/`.
2. Suche das Modell im Unterordner des Systems. Für **BÜTEC Standard, 2 × 1 m** ist das `buetec-standard/2000x1000/2000x1000.step`. Sichere die Originaldatei, bevor du sie ersetzt.
3. Öffne die STEP-Datei als Ausgangspunkt in FreeCAD oder erstelle ein eigenes Modell. Richte das Modell so aus, dass die Plattenlänge in X, die Breite in Y und die Höhe in Z verläuft. Der gesamte Körper muss in X × Y das Katalogmaß haben. Die Trittfläche muss am höchsten Punkt liegen. Steckbeine können nach unten reichen. EventCAD setzt die Oberkante beim Platzieren automatisch auf die eingestellte Z-Höhe.
4. Wähle im Modellbaum die fertigen Volumenkörper aus. Exportiere sie über **Datei → Exportieren** als **STEP**. Speichere deine bearbeitbare 3D-Konstruktion bei Bedarf als `.FCStd` **außerhalb des Symbolordners**; dessen eine FCStd-Datei ist für das 2D-Symbol vorgesehen.
5. Ersetze die STEP-Datei im zugehörigen Symbolordner. Lass dort genau eine STEP-Datei liegen; sie darf auch anders heißen. Setze in EventCAD ein neues Podest derselben Größe und prüfe es über **3D-Modell**. EventCAD liest die Datei beim Platzieren ein. Bei einem falschen Maß oder einer ungültigen Datei erscheint eine Meldung im BühnenSnap-Bedienfeld.

Die Geometrie wird in der Plandatei gespeichert. Für bereits platzierte Podeste kannst du das neue Modell übernehmen, indem du sie neu setzt. Grundriss, Autosnap und Kollisionsprüfung verwenden die beim Platzieren gesetzten Maße. Die Darstellung verwendet die EventCAD-Farben.

## Eigene 2D-Symbole

Verwende **FreeCAD-Dateien (`.FCStd`)** für die 2D-Varianten. So bleiben Skizzen und flache Part-Geometrie direkt in FreeCAD bearbeitbar und maßhaltig. Ein Body oder eine Extrusion ist nicht nötig. SVG wird von diesem Symbol-Lader nicht eingelesen.

1. Öffne die FCStd-Datei eines vorhandenen Symbols oder erstelle ein neues FreeCAD-Dokument.
2. Erstelle dein Symbol als sichtbare Skizze, Linien oder flache Part-Fläche parallel zur **XY-Ebene**. Konstruktionen auf einer TechDraw-Seite sind keine Symbolgeometrie. Blende Hilfsgeometrie aus, die nicht zum Symbol gehört.
3. Zeichne **1:1 in Millimetern**. Die äußeren X- und Y-Abmessungen müssen zur Grundfläche des 3D-Modells passen; die Geometrie muss in einer gemeinsamen Ebene liegen. EventCAD richtet die minimale X-/Y-Koordinate an der Podestecke aus und setzt die Ebene auf die Oberkante des Podests. Drehe das 2D-Symbol nicht gegenüber der 3D-Grundfläche.
4. Speichere das Dokument **im selben Symbolordner wie die STEP-Datei**. Der Dateiname ist beliebig; lass dort genau eine `.FCStd`-Datei liegen. Die mitgelieferten Symboldateien enthalten jeweils eine bearbeitbare Part-Ebene.
5. Klicke in EventCAD auf **2D-Grundriss**, auch wenn dieser Modus bereits aktiv ist. Dabei werden geänderte Dateien erneut übernommen. Platzierung, Drehung und Autosnap richten sich weiterhin nach dem zugehörigen Podest.

Die Zuordnung erfolgt ausschließlich über den gemeinsamen Symbolordner. Beide Dateien dürfen unabhängig umbenannt werden. Am platzierten Podest steht **BühnenSnap → StageSnapModelFile** mit dem aktuellen STEP-Pfad relativ zum Modellordner. Verschiebst oder benennst du den Symbolordner selbst um, kannst du diesen Pfad dort anpassen. Bestehende Pläne mit den früheren flachen Modellpfaden werden auf die neue mitgelieferte Ordnerstruktur zugeordnet.

Die geladenen 2D-Geometrien werden im Plan eingebettet. Fehlt die FCStd-Datei, bleibt das gespeicherte Symbol erhalten; ohne gespeichertes Symbol wird der bisherige rechteckige Grundriss verwendet. Bei mehreren FCStd-Dateien oder einer defekten, räumlichen oder falsch dimensionierten Datei erscheint eine Warnung in der FreeCAD-Berichtsansicht und dieselbe Ersatzdarstellung wird verwendet. Geöffnete Quelldokumente werden beim Laden nicht verändert. Die FCStd-Dateien erscheinen nicht als zusätzliche 3D-Modelle im Dropdown.

## Aufbau

Der Quellcode liegt in `freecad/buehnensnap/`. `decks.py` enthält Katalog, Podestkörper, Grundrisssymbole und die Autosnap-Platzierung. `plan_symbols.py` sucht und lädt die 2D-Begleitdateien. `view_modes.py` verwaltet die Darstellung pro Dokument. `init_gui.py` registriert den Event-Arbeitsbereich mit seiner Werkzeugleiste.
