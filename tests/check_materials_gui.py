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
from freecad.buehnensnap import decks, plan_symbols, segments
from freecad.buehnensnap.appearance import wood_faces, WOOD_COLOR, ALUMINIUM_COLOR


def snapshot(obj):
    # FreeCAD's untouched default materials use decimal text before their first
    # save and binary/packed color values after reopening; compare at 1e-6.
    return [(tuple(round(v, 6) for v in m.DiffuseColor),
             tuple(round(v, 6) for v in m.SpecularColor),
             round(m.Shininess, 6), round(m.Transparency, 6))
            for m in obj.ViewObject.ShapeAppearance]


def segment_snapshot(source):
    return [(obj.StageSnapRole, snapshot(obj.StageSnap3DTemplate),
             snapshot(obj.StageSnapPlanTemplate)) for obj in segments.components(source)]


try:
    paths = sorted(decks.MODELS_DIR.rglob('*.FCStd'))
    for path in paths:
        print('Checking', path.relative_to(decks.MODELS_DIR), flush=True)
        document = App.newDocument('MaterialTest')
        model = decks.deck_for_model('Test', path.relative_to(decks.MODELS_DIR).as_posix())
        source = decks.insert_deck(document, model, decks.seed_placement(model, 0, 0, 300, 1))
        detailed = 'Buetec_standard' in path.name
        faces = 0
        for component in segments.components(source):
            template = component.StageSnap3DTemplate
            if template.Shape.isNull():
                continue
            actual = template.ViewObject.ShapeAppearance
            assert len(actual) == len(template.Shape.Faces)
            faces += len(actual)
            wood = wood_faces(template.Shape) if not detailed else (
                set(range(len(actual))) if component.StageSnapRole == 'PedestalDeck' else set())
            for index, material in enumerate(actual):
                is_wood = index in wood
                color = WOOD_COLOR if is_wood else ALUMINIUM_COLOR
                # FCStd serializes colors with 8-bit channels.
                assert max(abs(a-b) for a, b in zip(material.DiffuseColor[:3], color)) <= 1 / 255, (index, material.DiffuseColor, color)
                assert (max(material.SpecularColor[:3]) == 0.0) == is_wood
        assert faces == len(plan_symbols.load_variant_shape(path, 'Symbol3D').Faces)
        before = segment_snapshot(source)
        for plan_view in (True, False, True, False):
            decks.set_deck_mode(source, plan_view)
            document.recompute()
            assert segment_snapshot(source) == before, ('switch', before, segment_snapshot(source))
        with TemporaryDirectory() as temp:
            saved = Path(temp) / 'Plan.FCStd'
            name = source.Name
            document.saveAs(str(saved))
            App.closeDocument(document.Name)
            document = App.openDocument(str(saved))
            source = document.getObject(name)
            assert segment_snapshot(source) == before, ('reopen', before, segment_snapshot(source))
        App.closeDocument(document.Name)
    print(f'{len(paths)} symbols: wood matte, aluminium shiny; import, switches and reopen passed.', flush=True)
finally:
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    Gui.getMainWindow().close()
