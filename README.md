# EventCAD

FreeCAD-Add-on für Veranstaltungsplanung. Der Arbeitsbereich **Event** bietet BühnenSnap zum Platzieren und Andocken von Bühnenpodesten sowie umschaltbare 2D- und 3D-Darstellungen. Voraussetzung: FreeCAD 1.0 oder neuer.

## Installation und Update

Installiere bzw. aktualisiere EventCAD über den FreeCAD Addon-Manager mit dem Repository `https://github.com/martengrossnotion/EventCAD`. Starte FreeCAD danach neu.

Manuell: **Code → Download ZIP**, entpacken und den Add-on-Ordner nach `Mod` im FreeCAD-Benutzerordner kopieren. `package.xml` muss direkt im Add-on-Ordner liegen. Den Benutzerordner ermittelst du in der FreeCAD-Python-Konsole mit `print(App.getUserAppDataDir())`; unter Windows normalerweise `%APPDATA%/FreeCAD`. Vermeide mehrere EventCAD-Installationen parallel.

## Bedienung

1. Öffne oder erstelle einen Plan und wähle den Arbeitsbereich **Event**.
2. Öffne über das Podest-Icon das BühnenSnap-Bedienfeld.
3. Wähle **Podestsystem** und **Plansymbol**. Unter **Planungsmaß → Eigenes Maß** kannst du Länge, Breite und Körperhöhe frei eingeben.
4. Setze ein Startpodest über **Podest an Koordinaten setzen**. X/Y bezeichnen die Mitte, Z die Oberkante. **Drehung** wählt 0° hochkant oder 90° quer.
5. Aktiviere **Autosnap starten** und klicke knapp innerhalb der gewünschten Kante und Ecke eines vorhandenen Podests. Bei einer Kollision wird die andere Ecke derselben Kante versucht. Sind beide Positionen belegt, bleibt der Plan unverändert.

**2D-Grundriss** zeigt die flachen Symbole auf Höhe der Podestoberkante. **3D-Modell** zeigt die Volumenkörper. Der Modus wird im Plan gespeichert. Autosnap funktioniert in beiden Ansichten; die Zielkanten müssen parallel zu den X-/Y-Achsen des Plans liegen.

## Eine FCStd-Datei pro Symbol

Unter `freecad/buehnensnap/resources/models/<System>/<Symbol>/` liegt pro Symbol genau **eine .FCStd-Datei**. Dateiname und Groß-/Kleinschreibung der Endung sind beliebig. Das Dropdown zeigt die Symbolordner des gewählten Systems; bekannte Kataloggrößen werden als Maß angezeigt. Mehrere FCStd-Dateien im selben Symbolordner führen zu einer Warnung; der Ordner wird übersprungen. STEP-Dateien werden nicht mehr als Bibliotheksmodelle verwendet.

Die FCStd-Datei enthält zwei getrennte Geometrieobjekte:

| Objektname oder eindeutige Bezeichnung | Inhalt |
| --- | --- |
| `Symbol3D` | Fertiger Volumenkörper oder Compound mehrerer Volumenkörper; auch der fertige Body ist möglich |
| `Symbol2D` | Skizze, Linien oder flache Part-Geometrie parallel zur XY-Ebene |

Die Sichtbarkeit dieser Objekte in der Quelldatei ist für den Import unerheblich. Hilfsgeometrie und weitere Konstruktionsobjekte werden nicht separat eingelesen. Beide Varianten müssen als Objekt mit fertiger `Shape` vorliegen; eine reine Dokumentgruppe reicht nicht. Für mehrere Körper eignet sich ein Part-Compound.

Beispiel: `buetec-standard/2000x1000/2000x1000.FCStd` enthält `Symbol3D` und `Symbol2D`.

## Modelle bearbeiten oder austauschen

1. Öffne die FCStd-Datei im jeweiligen Symbolordner.
2. Bearbeite das 3D-Modell oder ersetze es durch deine Originalkonstruktion. Benenne das fertige Objekt im Modellbaum eindeutig **Symbol3D**. Bei den mitgelieferten Dateien sind die internen Objektnamen bereits entsprechend gesetzt.
3. Erstelle oder bearbeite das flache Objekt und benenne es eindeutig **Symbol2D**. Zeichne 1:1 in Millimetern, parallel zur XY-Ebene. Eine TechDraw-Seite ist keine Symbolgeometrie.
4. Richte Länge in X, Breite in Y und Höhe in Z aus. Die 2D-Grundfläche muss den X-/Y-Abmessungen des 3D-Modells entsprechen. Bei Katalogmodellen muss das Modell das Katalogmaß einhalten. Der höchste Punkt des 3D-Modells gilt als Oberkante; Füße dürfen nach unten reichen. Beide Varianten werden am minimalen X/Y ausgerichtet, das 2D-Symbol auf Oberkantenhöhe gesetzt.
5. Speichere die Datei. Belasse genau eine FCStd-Datei im Symbolordner. Speichere Sicherungskopien mit Endung .FCStd außerhalb dieses Ordners.
6. Öffne BühnenSnap erneut, um zusätzliche Symbolordner einzulesen. Platziere das bearbeitete Symbol neu. Für zusätzliche Modelle werden die Planungsmaße aus der 3D-Geometrie ermittelt.

Die mitgelieferten 3D-Objekte wurden vorläufig aus den bisherigen STEP-Dateien übernommen. Sie sind statische Part-Geometrien ohne ursprüngliche Konstruktionshistorie. Die Originalkonstruktion kann später in derselben FCStd-Datei ergänzt werden.

## Wiederverwendung in großen Plänen

EventCAD speichert jede verwendete Kombination aus Modelldatei, Dateirevision und Planungsmaßen einmal als 2D-/3D-Vorlagenpaar im Plan. Die platzierten 3D-Podeste sind `App::Link`-Objekte. Die 2D-Symbole sind `App::LinkPython`-Objekte, deren Platzierung dem Podest folgt. Auch freie Planungsmaße verwenden gemeinsame Vorlagen.

Die Vorlagen liegen unter **EventCAD · Symbolvorlagen** und bleiben ausgeblendet. Sie sind keine platzierten Podeste und werden nicht in Autosnap oder Kollisionsprüfung einbezogen. Änderungen an einer Quelldatei gelten für neue Platzierungen; bereits platzierte Symbole behalten ihre eingebettete Revision. Ein Wechsel zwischen 2D und 3D lädt diese Links nicht erneut von der Festplatte. Für eine geänderte Darstellung setzt du bestehende Podeste neu.

Beide Geometrien und alle Links bleiben im Plan eingebettet. Der gespeicherte Plan lässt sich ohne die ursprünglichen Bibliotheksdateien öffnen. Vorlagen sollten im Plan nicht gelöscht oder manuell verschoben werden, solange Links auf sie verweisen.

## Bestehende Pläne

Podeste aus älteren EventCAD-Versionen bleiben auswählbar, andockbar und zwischen 2D/3D umschaltbar. Sie behalten ihre eingebettete Geometrie und werden nicht automatisch durch Links ersetzt. Neue Podeste verwenden die gemeinsame Vorlagenverwaltung. Alte STEP-Modellpfade werden beim Nachladen eines alten 2D-Symbols auf die FCStd-Datei desselben Symbolordners aufgelöst; frühere flache Katalogpfade werden ebenfalls unterstützt.

Fehlt bei einem alten Plan die Quelldatei oder ist sie ungültig, bleibt der eingebettete Grundriss erhalten; ohne eingebetteten Grundriss wird ein Rechteck verwendet. Neue Bibliothekssymbole benötigen gültige 2D- und 3D-Objekte; fehlerhafte Dateien werden beim Platzieren mit einer Fehlermeldung zurückgewiesen.

## Entwicklung und Prüfung

`decks.py` verwaltet Katalog, Vorlagen, Links und Autosnap. `plan_symbols.py` lädt die Varianten einer FCStd-Datei revisionsabhängig, ohne offene Originaldokumente zu verändern. `view_modes.py` steuert die Sichtbarkeit. `panel.py` stellt die Bedienoberfläche bereit.

Mit FreeCADs Python-Bibliotheken: `python -m unittest discover -s tests -v`. Falls bereits ein anderes EventCAD installiert ist, muss zum Testen dieses Checkouts dessen Pfad im Python-Namensraum `freecad` Vorrang haben; bereits geladene `freecad.buehnensnap`-Module müssen entfernt werden.

