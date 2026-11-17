"""Check real Qt coordinate fields and metre-to-millimetre placement conversion.

Run with <FreeCAD>/bin/python tests/check_panel_gui.py.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import FreeCAD as App
import FreeCADGui as Gui
Gui.showMainWindow()
Gui.getMainWindow().hide()
import freecad
freecad.__path__ = [str(Path(__file__).resolve().parents[1] / "freecad")]
for name in list(sys.modules):
    if name == "freecad.buehnensnap" or name.startswith("freecad.buehnensnap."):
        del sys.modules[name]
if hasattr(freecad, "buehnensnap"):
    del freecad.buehnensnap
from PySide import QtCore
from freecad.buehnensnap import panel
from freecad.buehnensnap.commands import PodestCommand
from freecad.buehnensnap.decks import Deck

doc = App.newDocument("PanelCoordinateCheck")
dock = panel.StageSnapDock(Gui.getMainWindow())
try:
    assert dock.windowTitle() == "Podest"
    assert PodestCommand().GetResources()["MenuText"] == "Podest"
    assert dock.objectName() == "BuehnenSnapPodestPanel"
    for field in (dock.x, dock.y, dock.z):
        assert field.decimals() == 2
        assert field.suffix() == " m"
        assert field.singleStep() == 0.01
        assert (field.minimum(), field.maximum()) == (-1000, 1000)
        field.setLocale(QtCore.QLocale("de_DE"))
        assert field.text() == "0,00 m"
    for field, text in zip((dock.x, dock.y, dock.z), ("1,23 m", "-2,34 m", "0,56 m")):
        field.lineEdit().setText(text)
        field.interpretText()
    assert [field.value() for field in (dock.x, dock.y, dock.z)] == [1.23, -2.34, 0.56]
    assert all(field.suffix() == " mm" for field in (dock.length, dock.width, dock.depth))

    # Use the actual placement calculation after the panel converts input units.
    deck = Deck("panel-test", "Test podest", 2000, 1000, 90)
    doc.addObject("App::FeaturePython", "Existing")
    with patch.object(dock, "current_deck", return_value=deck), \
            patch.object(panel, "insert_deck", return_value=SimpleNamespace(Label="Test")) as insert:
        dock.add_seed()
    insert.assert_called_once()
    placed = insert.call_args.args[2]
    top_center = placed.multVec(App.Vector(deck.length / 2, deck.width / 2, deck.depth))
    assert (top_center - App.Vector(1230, -2340, 560)).Length < 1e-8, top_center
    print("Podest naming, decimal metre inputs, mm dimensions and negative-coordinate placement passed.", flush=True)
finally:
    dock.close()
    App.closeDocument(doc.Name)
    Gui.getMainWindow().close()
