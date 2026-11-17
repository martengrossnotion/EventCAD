"""Check baked source materials, imported face order, switches and persistence."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
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
from freecad.buehnensnap import decks, plan_symbols
from freecad.buehnensnap.appearance import wood_faces, WOOD_COLOR, ALUMINIUM_COLOR


def snapshot(obj):
    return [(m.DiffuseColor, m.SpecularColor, m.Shininess, m.Transparency)
            for m in obj.ViewObject.ShapeAppearance]


try:
    paths = sorted(decks.MODELS_DIR.rglob('*.FCStd'))
    for path in paths:
        print('Checking', path.relative_to(decks.MODELS_DIR), flush=True)
        document = App.newDocument('MaterialTest')
        model = decks.deck_for_model('Test', path.relative_to(decks.MODELS_DIR).as_posix())
        source = decks.insert_deck(document, model, decks.seed_placement(model, 0, 0, 300, 1))
        for variant, template in [('Symbol3D', source.StageSnap3DTemplate),
                                  ('Symbol2D', source.StageSnapPlanTemplate)]:
            expected = plan_symbols.load_variant_appearance(path, variant)
            actual = template.ViewObject.ShapeAppearance
            assert len(actual) == len(template.Shape.Faces)
            assert [(m.DiffuseColor, m.SpecularColor) for m in actual] == [
                (m.DiffuseColor, m.SpecularColor) for m in expected]
            wood = wood_faces(template.Shape, variant == 'Symbol2D')
            if 'Buetec_standard' in path.name and variant == 'Symbol3D':
                assert len(wood) == 6 and len(actual) == 77
            for index, material in enumerate(actual):
                is_wood = index in wood
                color = WOOD_COLOR if is_wood else ALUMINIUM_COLOR
                # FCStd serializes colors with 8-bit channels.
                assert max(abs(a-b) for a, b in zip(material.DiffuseColor[:3], color)) <= 1 / 255, (index, material.DiffuseColor, color)
                assert (max(material.SpecularColor[:3]) == 0.0) == is_wood
        before = (snapshot(source.StageSnap3DTemplate), snapshot(source.StageSnapPlanTemplate))
        for plan_view in (True, False, True, False):
            decks.set_deck_mode(source, plan_view)
            document.recompute()
            assert (snapshot(source.StageSnap3DTemplate), snapshot(source.StageSnapPlanTemplate)) == before
        with TemporaryDirectory() as temp:
            saved = Path(temp) / 'Plan.FCStd'
            name = source.Name
            document.saveAs(str(saved))
            App.closeDocument(document.Name)
            document = App.openDocument(str(saved))
            source = document.getObject(name)
            assert (snapshot(source.StageSnap3DTemplate), snapshot(source.StageSnapPlanTemplate)) == before
        App.closeDocument(document.Name)
    print(f'{len(paths)} symbols: wood matte, aluminium shiny; import, switches and reopen passed.', flush=True)
finally:
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    Gui.getMainWindow().close()
