# EventCAD

FreeCAD-Add-on für Veranstaltungsplanung. Der Arbeitsbereich **Event** bietet Podest zum Platzieren und Andocken von Bühnenpodesten sowie umschaltbare 2D- und 3D-Darstellungen. Voraussetzung: FreeCAD 1.0 oder neuer.

## Installation und Update

Installiere bzw. aktualisiere EventCAD über den FreeCAD Addon-Manager mit dem Repository `https://github.com/martengrossnotion/EventCAD`. Starte FreeCAD danach neu.

Manuell: **Code → Download ZIP**, entpacken und den Add-on-Ordner nach `Mod` im FreeCAD-Benutzerordner kopieren. `package.xml` muss direkt im Add-on-Ordner liegen. Den Benutzerordner ermittelst du in der FreeCAD-Python-Konsole mit `print(App.getUserAppDataDir())`; unter Windows normalerweise `%APPDATA%/FreeCAD`. Vermeide mehrere EventCAD-Installationen parallel.

## Bedienung

1. Öffne oder erstelle einen Plan und wähle den Arbeitsbereich **Event**.
2. Öffne über das Podest-Icon das Podest-Bedienfeld.
3. Wähle **Podestsystem** und **Plansymbol**. Unter **Planungsmaß → Eigenes Maß** kannst du Länge, Breite und Körperhöhe frei eingeben.
4. Setze ein Startpodest über **Podest an Koordinaten setzen**. X/Y bezeichnen die Mitte, Z die Oberkante. Die Platzierungskoordinaten werden in Metern mit zwei Nachkommastellen eingegeben (z. B. 1,25 m); Längen, Breiten und Körperhöhen bleiben in Millimetern. **Drehung** wählt 0° hochkant oder 90° quer.
5. Aktiviere **Autosnap starten** und klicke knapp innerhalb der gewünschten Kante und Ecke eines vorhandenen Podests. Bei einer Kollision wird die andere Ecke derselben Kante versucht. Sind beide Positionen belegt, bleibt der Plan unverändert.

**2D-Grundriss** zeigt die flachen Symbole auf Höhe der Podestoberkante. **3D-Modell** zeigt die Volumenkörper. Der Modus wird im Plan gespeichert. Autosnap funktioniert in beiden Ansichten; die Zielkanten müssen parallel zu den X-/Y-Achsen des Plans liegen.

Im 2D-Grundriss ist die Podestplatte eine anklickbare Fläche. Für Autosnap innerhalb dieser Fläche nahe der gewünschten Kante und Ecke klicken; Rahmenkanten müssen dafür nicht getroffen werden. Platte, Rahmen und Ecken bleiben über ihre eigenen View-Schalter getrennt sichtbar. Die automatisch erzeugte Plattenfläche verwendet den tatsächlichen oberen Umriss der Platte einschließlich vorhandener Aussparungen.

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
6. Öffne Podest erneut, um zusätzliche Symbolordner einzulesen. Platziere das bearbeitete Symbol neu. Für zusätzliche Modelle werden die Planungsmaße aus der 3D-Geometrie ermittelt.

Die mitgelieferten 3D-Objekte wurden vorläufig aus den bisherigen STEP-Dateien übernommen. Sie sind statische Part-Geometrien ohne ursprüngliche Konstruktionshistorie. Die Originalkonstruktion kann später in derselben FCStd-Datei ergänzt werden.

## Struktur der Podestflächen

Neue Platzierungen verwenden folgende feste Reihenfolge und Bezeichnungen:

| Übergeordnetes Objekt | Einträge in dieser Reihenfolge |
| --- | --- |
| Podestfläche 1 | Views, Podestsegment 001, Podestsegment 002, … |
| Views | ViewDecks, ViewCorners, ViewFrames |
| Podestsegment 001 | Corners, Frame, Deck, Verbinder, Steckfüße, Geländer |
| Corners | CornerTL, CornerTR, CornerBL, CornerBR |
| Frame | PedestalFrame |
| Deck | PedestalDeck |
| Verbinder, Steckfüße, Geländer | zunächst leer, für eigene Bauteile |

Jedes Segment ist ein App::Part mit genau einer gemeinsam bearbeitbaren Position und Drehung. Die sechs Komponenten sind native App::Link-Objekte. Ihre lokale Platzierung ist schreibgeschützt. Alle Komponenten folgen dem Segment auch beim Bearbeiten in 2D. Ein Klick auf eine Komponente wird für Autosnap ihrem Segment zugeordnet.

ViewDecks, ViewCorners und ViewFrames schalten die Untergruppen Deck, Corners und Frame ihrer eigenen Podestfläche. Ihre Members referenzieren diese Container, nicht die einzelnen Komponenten. Umschalten mit der Leertaste oder über die Eigenschaft Enabled. Die Untergruppen verwenden native geometrische Gruppen als gemeinsame Sichtbarkeitsmaske. Dadurch bleiben die individuellen Sichtbarkeitswerte aller enthaltenen Objekte erhalten; auch ein nachträglich hinzugefügter Cut oder ein eigenes Bauteil folgt seiner Untergruppe ohne zusätzliche Registrierung. Beispielsweise einen sichtbaren Cut unter Deck ablegen und dessen Ausgangsdeck sowie Schneidkörper ausgeblendet lassen: Aus-/Einschalten von ViewDecks erhält genau diese Auswahl.

Die Untergruppen erscheinen weiterhin als Ordner und besitzen keine zusätzlichen Ursprungsobjekte. Ihre lokale Platzierung bleibt unverändert; das ganze Podest wird am Segment positioniert. Verbinder, Steckfüße und Geländer werden in jedem Segment als leere Untergruppen angelegt. Sie haben zunächst keine zusätzlichen globalen View-Schalter und lassen sich einzeln über ihren Ordner ein-/ausblenden. Die View-Steuerung erzeugt keine zweite Geometrie und verschiebt keine Bauteile aus ihren Segmenten.

Der 2D-/3D-Wechsel erhält die Einzel-Sichtbarkeit und die Gruppenmasken. Er wechselt weiterhin die Vorlagen der ursprünglichen Komponentenlinks; für einen darauf aufgebauten Cut entsteht durch die Gruppensteuerung keine eigene angepasste 2D-Konstruktion.

Bereits das erste Startpodest erhält eine eigene Podestfläche. Per Autosnap oder über das Zielsegment hinzugefügte Podeste gehören derselben Fläche an. Räumlich getrennte Startplatzierungen erhalten separate Flächen. Verschieben führt noch nicht zu automatischem Trennen oder Zusammenführen von Flächen.

## Komponenten in der Symboldatei

Für eindeutig bearbeitbare Komponenten können in der FCStd-Datei zusätzlich zu Symbol3D/Symbol2D die fertigen Objekte CornerTL, CornerTR, CornerBL, CornerBR, PedestalFrame und PedestalDeck angelegt werden. Namen oder eindeutige Labels werden erkannt. Alle Teile verwenden dasselbe Koordinatensystem wie Symbol3D; T steht für die positive Y-Seite, L für die negative X-Seite. Optionale flache Varianten heißen beispielsweise PedestalDeck2D oder CornerTL2D. Ohne eigene 2D-Komponente wird bei der Platte die obere horizontale Fläche übernommen; Rahmen und Ecken erhalten projizierte Konturen. Geschlossene reine Plattenkonturen werden zu anklickbaren Flächen ergänzt. Löcher, getrennte Teilflächen und zusätzliche offene Detaillinien bleiben erhalten; eigene offene Linien werden nicht durch eine erfundene Rechteckfläche ersetzt.

Das vorhandene detaillierte Bütec-Modell wird anhand seiner sechs vorhandenen Volumenkörper in Deck, Rahmen und vier Ecken zerlegt. Es werden keine neuen Volumenkörper erfunden. Vereinfachte Gesamtmodelle ohne getrennte Bauteile bleiben vollständig unter PedestalDeck. Ihre übrigen fünf Einträge sind leere Platzhalter und bleiben unsichtbar; die Baumstruktur ist trotzdem identisch. Für getrennt schaltbare Rahmen/Ecken benötigen solche Modelle entsprechende echte Komponenten.

## Wiederverwendung in großen Plänen

EventCAD speichert jede Kombination aus Dateirevision und Planungsmaßen als gemeinsames Vorlagenset im Plan. Gleiche Komponenten verwenden dieselben eingebetteten 2D-/3D-Vorlagen. Beim Ansichtswechsel wechseln die Komponentenlinks ihr Ziel; Segmentidentität und Platzierung bleiben gleich. Die Vorlagenbibliothek und die Ursprünge der Segmentcontainer werden im Baum ausgeblendet.

Die zusätzlichen Gruppen und Links erhöhen die Zahl der Dokumentobjekte. Es gibt keine Python-Ausführung zur laufenden Positionssynchronisierung pro Bauteil. Auch der gespeicherte Plan benötigt die Originaldatei nicht mehr. Änderungen an der Bibliothek wirken auf neue Platzierungen, vorhandene Segmente behalten ihre eingebettete Revision.

Für Skripte liefert segments.segment_shape(segment) die zusammengesetzte Weltgeometrie jedes Bauteils genau einmal. Die automatisch erzeugte App::Part.Shape kann normale Untergruppen und ihre ebenfalls im geometrischen Container registrierten Links doppelt aufzählen; sie sollte deshalb nicht für Mengen-/Volumensummen verwendet werden.

## Bestehende Pläne

Version 2.1.1 ergänzt bereits eingebettete, geschlossene 2D-Plattenkonturen beim Öffnen oder Ansichtswechsel zu anklickbaren Flächen. Dafür ist keine Quelldatei nötig. Die Korrektur erhält Umrisse, Löcher, Verknüpfungen, Platzierungen und Sichtbarkeit und verändert keine Rahmen-, Eck- oder 3D-Vorlagen.

Segmentpläne aus Version 2.0 werden beim Öffnen mit geladenem Addon oder beim ersten Ansichts-/Viewwechsel auf die Untergruppensteuerung umgestellt. Die Ordner behalten ihre internen Namen und Bezeichnungen; Geometrieobjekte, Cut-Verknüpfungen und Weltpositionen bleiben erhalten. Die drei leeren Zubehörgruppen werden dabei ergänzt. Bereits offene Dokumente werden beim Laden des Segmentmoduls ebenfalls berücksichtigt. Die Änderung wird mit dem normalen Speichern des Plans dauerhaft übernommen.

Vorhandene Podeste aus Version 1.9 und älter werden nicht automatisch durch Segmentcontainer ersetzt. Ihre Identität und Referenzen bleiben erhalten. Die neue Struktur gilt für neu eingesetzte Podeste.

Links aus Version 1.7 werden beim Ansichtswechsel auf das gemeinsame Platzierungsobjekt umgestellt. Dafür werden nur ihre eingebetteten Vorlagen verwendet; die Bibliotheksdatei muss nicht vorhanden sein. Der alte separate 2D-Link wird ausgeblendet und zur Erhaltung bestehender Referenzen im Dokument belassen. Das ursprüngliche Podest bleibt das auswählbare, bearbeitbare Objekt in beiden Ansichten.

Ältere Podeste vom Typ `Part::Box` oder `Part::Feature` bleiben auswählbar, andockbar und zwischen 2D/3D umschaltbar. Sie behalten ihre bisherige Darstellung mit separatem Grundriss und werden nicht automatisch durch Links ersetzt. Neue Podeste verwenden die gemeinsame Vorlagenverwaltung. Alte STEP-Modellpfade werden beim Nachladen eines alten 2D-Symbols auf die FCStd-Datei desselben Symbolordners aufgelöst; frühere flache Katalogpfade werden ebenfalls unterstützt.

Fehlt bei einem alten Plan die Quelldatei oder ist sie ungültig, bleibt der eingebettete Grundriss erhalten; ohne eingebetteten Grundriss wird ein Rechteck verwendet. Neue Bibliothekssymbole benötigen gültige 2D- und 3D-Objekte; fehlerhafte Dateien werden beim Platzieren mit einer Fehlermeldung zurückgewiesen.

## Entwicklung und Prüfung

`decks.py` verwaltet Katalog und Autosnap. `segments.py` verwaltet Segmentbaum und View-Steuerungen, `component_models.py` liest die Bauteilgeometrien. `plan_symbols.py` lädt die Varianten einer FCStd-Datei revisionsabhängig, ohne offene Originaldokumente zu verändern. `view_modes.py` steuert die Sichtbarkeit. `panel.py` stellt die Bedienoberfläche bereit.

Mit FreeCADs Python-Bibliotheken: `python -m unittest discover -s tests -v`. Falls bereits ein anderes EventCAD installiert ist, muss zum Testen dieses Checkouts dessen Pfad im Python-Namensraum `freecad` Vorrang haben; bereits geladene `freecad.buehnensnap`-Module müssen entfernt werden.


## Materialien der Symbole

Die FCStd-Symbole speichern ihre Flächenmaterialien: Holzdeck in der bisherigen braunen Farbe, matt; Aluminiumrahmen und Eckteile grau und glänzend. Beim Einfügen bleiben die Materialien einschließlich der Flächenzuordnung erhalten. Beim detaillierten Bütec-Modell gehören auch die senkrechten Kanten der Holzplatte zum matten Deck. Die vereinfachten Quadersymbole verwenden braune, matte horizontale Flächen und graue, glänzende Seiten.

Bereits platzierte Symbole behalten die in ihrem Plan gespeicherten Materialien. Für die aktualisierten Bibliotheksmaterialien die betreffenden Podeste neu einsetzen.
