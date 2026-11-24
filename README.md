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

Im 2D-Grundriss ist die Podestplatte eine anklickbare Fläche. Für Autosnap innerhalb dieser Fläche nahe der gewünschten Kante und Ecke klicken; Rahmenkanten müssen dafür nicht getroffen werden. Platte, Rahmen und Ecken bleiben über ihre eigenen View-Schalter getrennt sichtbar. Die mitgelieferte Plattenfläche entspricht dem tatsächlichen oberen Umriss der Platte einschließlich vorhandener Aussparungen.

## Eine FCStd-Datei pro Symbol

Unter `freecad/buehnensnap/resources/models/<System>/<Symbol>/` liegt pro Symbol genau **eine .FCStd-Datei**. Dateiname und Groß-/Kleinschreibung der Endung sind beliebig. Das Dropdown zeigt die Symbolordner des gewählten Systems; bekannte Kataloggrößen werden als Maß angezeigt. Mehrere FCStd-Dateien im selben Symbolordner führen zu einer Warnung; der Ordner wird übersprungen. STEP-Dateien werden nicht mehr als Bibliotheksmodelle verwendet.

Die FCStd-Datei enthält zwei native Part-Container. Beide enthalten bereits dieselbe Komponentenstruktur wie ein später platziertes Podestsegment:

| Objektname oder eindeutige Bezeichnung | Inhalt |
| --- | --- |
| `Symbol3D` (Label „3D-Modell“) | 3D-Komponenten in den sechs Untergruppen |
| `Symbol2D` (Label „2D-Grundriss“) | Fertige flache Komponenten in denselben sechs Untergruppen |

| Untergruppe in jeder Variante | Enthaltene Objekte in dieser Reihenfolge |
| --- | --- |
| `Corners` | `CornerTL`, `CornerTR`, `CornerBL`, `CornerBR` |
| `Frame` | `PedestalFrame` |
| `Deck` | `PedestalDeck` |
| `Verbinder` | zunächst leer |
| `Steckfüße` | zunächst leer |
| `Geländer` | zunächst leer |

Die sichtbaren Bezeichnungen der Komponenten sind in beiden Varianten identisch. Die internen 2D-Objektnamen tragen zur Unterscheidung das Suffix `2D`, beispielsweise `PedestalDeck2D`. Die Quelldatei lässt sich direkt in FreeCAD öffnen, aufklappen und komponentenweise bearbeiten. Die Sichtbarkeit beim Speichern beeinflusst den Import nicht.

Beim Laden werden die vorhandenen Komponenten und ihre gespeicherten 2D-/3D-Geometrien übernommen. Es gibt keine automatische Zerlegung des Gesamtmodells und keine erneute Projektion der strukturierten 2D-Komponenten. Die Gruppen und ihre Zuordnungen werden geprüft; fehlende oder falsch einsortierte Komponenten ergeben eine Fehlermeldung. Die Zubehörgruppen bleiben zunächst leer. Zusätzliche Inhalte darin werden ausdrücklich abgewiesen, solange kein entsprechender Zubehörimport implementiert ist; sie werden nicht stillschweigend verworfen.

Beispiel: `buetec-standard/2000x1000/2000x1000.FCStd` enthält `Symbol3D` und `Symbol2D`.

## Modelle bearbeiten oder austauschen

1. Öffne die FCStd-Datei im jeweiligen Symbolordner.
2. Klappe **3D-Modell** auf und bearbeite die Bauteile unter Corners, Frame und Deck. Ein fertiger Body oder ein Compound kann als Komponente dienen, wenn er eine fertige Shape besitzt. Gruppen und Komponentenbezeichnungen beibehalten.
3. Bearbeite die passenden Bauteile unter **2D-Grundriss**. Zeichne 1:1 in Millimetern, parallel zur XY-Ebene. Die Platte sollte als Fläche vorliegen, damit ihre Innenseite anklickbar ist. Eine TechDraw-Seite ist keine Symbolgeometrie. Änderungen an der 3D-Geometrie erzeugen keine automatische neue 2D-Variante.
4. Richte Länge in X, Breite in Y und Höhe in Z aus. Die 2D-Grundfläche muss den X-/Y-Abmessungen des 3D-Modells entsprechen. Bei Katalogmodellen muss das Modell das Katalogmaß einhalten. Der höchste Punkt des 3D-Modells gilt als Oberkante; Füße dürfen nach unten reichen. Beide Varianten werden am minimalen X/Y ausgerichtet, das 2D-Symbol auf Oberkantenhöhe gesetzt.
5. Speichere die Datei. Belasse genau eine FCStd-Datei im Symbolordner. Speichere Sicherungskopien mit Endung .FCStd außerhalb dieses Ordners.
6. Öffne Podest erneut, um zusätzliche Symbolordner einzulesen. Platziere das bearbeitete Symbol neu. Für zusätzliche Modelle werden die Planungsmaße aus der 3D-Geometrie ermittelt.

Die mitgelieferten 3D-Objekte stammen aus den bisherigen STEP-Dateien. Sie liegen nun als ausdrücklich benannte Komponenten vor, weiterhin ohne ursprüngliche Konstruktionshistorie. Die Originalkonstruktion kann später innerhalb derselben Struktur ergänzt werden. Vereinfachte Quadersymbole behalten ihren vollständigen Körper unter Deck. Ihre Rahmen-/Eckobjekte sind ausdrücklich leere Platzhalter; es werden keine Bauteile erfunden.

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

Die Rollen der Bauteile stehen bereits in der oben beschriebenen Quellstruktur fest. Alle Teile einer Variante verwenden deren gemeinsames Koordinatensystem; T steht für die positive Y-Seite, L für die negative X-Seite. Beim Import wird jede Variante als Ganzes normalisiert. Die relativen Positionen ihrer Komponenten bleiben erhalten, auch bei verschobenen oder gedrehten Quellcontainern. Die gemeinsame Normalisierung ist nötig, weil bisherige 3D- und 2D-Quellen unterschiedliche Ursprünge besitzen können.

Alle 14 mitgelieferten Symboldateien besitzen diese Struktur für beide Varianten. Das detaillierte Bütec-Modell enthält sechs echte 3D-Komponenten. Seine vorhandenen Volumenkörper, die matten Holzflächen und glänzenden Aluminiumflächen bleiben erhalten. Die 2D-Platte ist eine anklickbare Fläche; Rahmen und Ecken besitzen eigene gespeicherte Konturen.

Alte monolithische FCStd-Dateien mit Symbol3D/Symbol2D bleiben ladbar. Ohne explizite Komponenten wird deren gesamte Geometrie unter PedestalDeck übernommen; der Lader errät keine Bauteilrollen aus den Volumenkörpern mehr. Die ältere flache Variante mit sechs ausdrücklich benannten 3D-Komponenten bleibt ebenfalls kompatibel. Nur bei diesem Altformat können fehlende 2D-Komponenten noch aus dem 3D-Modell abgeleitet werden.

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

`decks.py` verwaltet Katalog und Autosnap. `segments.py` verwaltet Segmentbaum und View-Steuerungen, `component_models.py` liest die Bauteilgeometrien. `symbol_structure.py` definiert die gemeinsame Quell-/Segmentstruktur und prüft die Komponentenpfade. `plan_symbols.py` lädt die Varianten einer FCStd-Datei revisionsabhängig, ohne offene Originaldokumente zu verändern. `view_modes.py` steuert die Sichtbarkeit. `panel.py` stellt die Bedienoberfläche bereit.

`tests/convert_symbol_structure.py` ist ein einmaliges Maintainer-Werkzeug für die Konvertierung alter Bibliotheksdateien. Nur dieses Werkzeug zerlegt gegebenenfalls das alte Bütec-Gesamtmodell und speichert die ausdrücklich benannten Komponenten und 2D-Formen in der Quelle. Es wird beim Platzieren nicht ausgeführt.

Mit FreeCADs Python-Bibliotheken: `python -m unittest discover -s tests -v`. Falls bereits ein anderes EventCAD installiert ist, muss zum Testen dieses Checkouts dessen Pfad im Python-Namensraum `freecad` Vorrang haben; bereits geladene `freecad.buehnensnap`-Module müssen entfernt werden.


## Materialien der Symbole

Die FCStd-Symbole speichern ihre Flächenmaterialien: Holzdeck in der bisherigen braunen Farbe, matt; Aluminiumrahmen und Eckteile grau und glänzend. Beim Einfügen bleiben die Materialien einschließlich der Flächenzuordnung erhalten. Beim detaillierten Bütec-Modell gehören auch die senkrechten Kanten der Holzplatte zum matten Deck. Die vereinfachten Quadersymbole verwenden braune, matte horizontale Flächen und graue, glänzende Seiten.

Bereits platzierte Symbole behalten die in ihrem Plan gespeicherten Materialien. Für die aktualisierten Bibliotheksmaterialien die betreffenden Podeste neu einsetzen.
