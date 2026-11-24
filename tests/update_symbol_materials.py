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
from freecad.buehnensnap.appearance import apply_default_materials
from freecad.buehnensnap.component_models import _materials
from freecad.buehnensnap.symbol_structure import variant_components

try:
    paths = sorted((root / 'freecad/buehnensnap/resources/models').rglob('*.FCStd'))
    for path in paths:
        document = App.openDocument(str(path), hidden=True)
        before = {o.Name: (len(o.Shape.Faces), o.Shape.Volume, o.Shape.Area)
                  for o in document.Objects if hasattr(o, 'Shape') and not o.Shape.isNull()}
        for variant in ('Symbol3D', 'Symbol2D'):
            symbol = document.getObject(variant)
            components = variant_components(symbol)
            if components is None:
                apply_default_materials(symbol, variant == 'Symbol2D')
            else:
                nonempty = [obj for obj in components.values() if not obj.Shape.isNull()]
                for role, obj in components.items():
                    if obj.Shape.isNull():
                        continue
                    if len(nonempty) == 1:
                        # Simplified deck boxes retain mixed wood/metal faces.
                        apply_default_materials(obj, variant == 'Symbol2D')
                    else:
                        materials = _materials(obj.Shape, role, [])
                        if materials:
                            obj.ViewObject.ShapeAppearance = materials
            print(path.parent.name, variant, 'default component materials updated', flush=True)
        document.recompute()
        after = {o.Name: (len(o.Shape.Faces), o.Shape.Volume, o.Shape.Area)
                 for o in document.Objects if hasattr(o, 'Shape') and not o.Shape.isNull()}
        assert before == after, 'Material update must retain the exact geometry'
        document.save()
        App.closeDocument(document.Name)
    print('Updated', len(paths), 'native symbol files; geometry unchanged.', flush=True)
finally:
    Gui.getMainWindow().close()
