"""Run with FreeCAD's Python to check real scene geometry, also offscreen.

Example: <FreeCAD>/bin/python tests/check_display_gui.py
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import FreeCAD as App
import FreeCADGui as Gui
Gui.showMainWindow()
Gui.getMainWindow().hide()
import freecad
root = Path(__file__).resolve().parents[1]
freecad.__path__ = [str(root / "freecad")]
for name in list(sys.modules):
    if name == "freecad.buehnensnap" or name.startswith("freecad.buehnensnap."):
        del sys.modules[name]
if hasattr(freecad, "buehnensnap"):
    del freecad.buehnensnap
from pivy import coin
from PySide import QtWidgets
from freecad.buehnensnap import decks, view_modes


def assert_rendered(document, source, mode):
    view = Gui.activeDocument().activeView()
    view_modes.show_mode(document, view, mode)
    QtWidgets.QApplication.processEvents()
    action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion(800, 600))
    action.apply(view.getSceneGraph())
    assert not action.getBoundingBox().isEmpty(), f"{mode}: scene has no rendered geometry"
    assert source.Visibility
    assert source.ViewObject.ShowInTree
    assert not source.StageSnap3DTemplate.Visibility
    assert not source.StageSnapPlanTemplate.Visibility
    assert bool(source.Shape.Solids) == (mode == "3D")


document = App.newDocument("UnifiedGuiCheck")
try:
    model = decks.CATALOG["BÜTEC Standard"][0]
    source = decks.insert_deck(document, model, decks.seed_placement(model, 0, 0, 150, 1))
    for mode in ("2D", "3D", "2D"):
        assert_rendered(document, source, mode)
        source.Placement = App.Placement(App.Vector(300, -200, 50),
                                         App.Rotation(App.Vector(0, 0, 1), 90))
        document.recompute()
    placement = source.Placement.copy()
    assert_rendered(document, source, "3D")
    assert source.Placement == placement
    # Reproduce a 1.7 document whose separate Python 2D link has no renderer.
    source.removeProperty("StageSnap3DTemplate")
    old = document.addObject("App::LinkPython", "PreviousPlanSymbol")
    old.setLink(source.StageSnapPlanTemplate)
    old.addProperty("App::PropertyString", "StageSnapKind")
    old.StageSnapKind = decks.DECK_SYMBOL_KIND
    old.addProperty("App::PropertyLink", "StageSnapSource")
    old.StageSnapSource = source
    old.Visibility = True
    source.Visibility = False
    assert_rendered(document, source, "2D")
    assert not old.Visibility
    assert_rendered(document, source, "3D")
    source.Visibility = False
    view_modes.show_mode(document, Gui.activeDocument().activeView(), "2D")
    assert not source.Visibility, "switch must preserve intentional hiding"
    source.Visibility = True
    with TemporaryDirectory() as temp:
        path = Path(temp) / "Plan.FCStd"
        name = source.Name
        document.saveAs(str(path))
        App.closeDocument(document.Name)
        document = App.openDocument(str(path))
        source = document.getObject(name)
        for mode in ("2D", "3D"):
            assert_rendered(document, source, mode)
            assert source.Placement == placement
    print("GUI scene geometry, shared placement, visibility and reopen checks passed.", flush=True)
finally:
    App.closeDocument(document.Name)
    Gui.getMainWindow().close()
