"""Maintainer utility: bake the default materials into the supplied FCStd files."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
import FreeCAD as App
import FreeCADGui as Gui
Gui.showMainWindow()
Gui.getMainWindow().hide()
import freecad
root = Path(__file__).resolve().parents[1]
freecad.__path__ = [str(root / 'freecad')]
for name in list(sys.modules):
    if name == 'freecad.buehnensnap' or name.startswith('freecad.buehnensnap.'):
        del sys.modules[name]
if hasattr(freecad, 'buehnensnap'):
    del freecad.buehnensnap
from freecad.buehnensnap.appearance import apply_default_materials, wood_faces

try:
    paths = sorted((root / 'freecad/buehnensnap/resources/models').rglob('*.FCStd'))
    for path in paths:
        document = App.openDocument(str(path), hidden=True)
        before = {o.Name: (len(o.Shape.Faces), o.Shape.Volume, o.Shape.Area)
                  for o in document.Objects if hasattr(o, 'Shape')}
        for variant in ('Symbol3D', 'Symbol2D'):
            symbol = document.getObject(variant)
            apply_default_materials(symbol, variant == 'Symbol2D')
            print(path.parent.name, variant, len(wood_faces(symbol.Shape, variant == 'Symbol2D')),
                  'wood faces of', len(symbol.Shape.Faces), flush=True)
        document.recompute()
        after = {o.Name: (len(o.Shape.Faces), o.Shape.Volume, o.Shape.Area)
                 for o in document.Objects if hasattr(o, 'Shape')}
        assert before == after, 'Material update must retain the exact geometry'
        document.save()
        App.closeDocument(document.Name)
    print('Updated', len(paths), 'native symbol files; geometry unchanged.', flush=True)
finally:
    Gui.getMainWindow().close()
