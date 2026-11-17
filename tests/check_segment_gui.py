"""Exercise real FreeCAD view providers for podest component filters and links.

Run with <FreeCAD>/bin/python tests/check_segment_gui.py.
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
from PySide import QtWidgets
from pivy import coin
from freecad.buehnensnap import decks, segments, view_modes


def by_label(parent, label):
    return next(obj for obj in parent.Group if obj.Label == label)


def components(segment):
    return [obj for group in segment.Group if hasattr(group, "Group") for obj in group.Group]


def update(document):
    document.recompute()
    QtWidgets.QApplication.processEvents()


def filter_for(segment, role):
    return by_label(by_label(segments.segment_area(segment), "Views"), "View" + role)


def assert_scene(document):
    update(document)
    action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion(800, 600))
    action.apply(Gui.activeDocument().activeView().getSceneGraph())
    assert not action.getBoundingBox().isEmpty(), "all segment geometry disappeared"


doc = App.newDocument("SegmentGuiCheck")
try:
    path = next(decks.MODELS_DIR.rglob("Buetec_standard*.FCStd"))
    model = decks.deck_for_model("BÜTEC Standard", path.relative_to(decks.MODELS_DIR).as_posix())
    first = decks.insert_deck(doc, model, decks.seed_placement(model, 0, 0, 150, 1))
    second = decks.insert_deck(doc, model,
                               decks.seed_placement(model, model.length + 1000, 0, 150, 1))
    third = decks.insert_deck(doc, model,
                              decks.seed_placement(model, 0, model.width, 150, 1), target=first)
    assert_scene(doc)
    assert [obj.Label for obj in first.Group if hasattr(obj, "Group")] == ["Corners", "Frame", "Deck"]
    assert len(components(first)) == 6
    assert all(obj.TypeId == "App::Link" for obj in components(first))
    assert all(obj.StageSnap3DTemplate.Shape.Solids for obj in components(first)), \
        "the detailed symbol must split into six real solid components"
    assert all(obj.StageSnapRole == obj.Label for obj in components(first))
    assert all(obj.ViewObject.Visibility for obj in components(first))
    assert not first.Origin.ViewObject.ShowInTree

    first_deck = by_label(first, "Deck").Group[0]
    third_deck = by_label(third, "Deck").Group[0]
    second_deck = by_label(second, "Deck").Group[0]
    assert first_deck.StageSnap3DTemplate == third_deck.StageSnap3DTemplate
    assert first_deck.StageSnap3DTemplate == second_deck.StageSnap3DTemplate

    # The GUI eye toggle and property Enabled must drive the same per-area filter.
    deck_filter = filter_for(first, "Decks")
    assert deck_filter.Enabled and deck_filter.ViewObject.Visibility
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(deck_filter)
    Gui.runCommand('Std_ToggleVisibility', 0)
    update(doc)
    assert not deck_filter.Enabled
    assert not first_deck.ViewObject.Visibility and not third_deck.ViewObject.Visibility
    assert second_deck.ViewObject.Visibility, "a different area's filter must remain independent"
    deck_filter.Enabled = True
    update(doc)
    assert deck_filter.ViewObject.Visibility
    assert first_deck.ViewObject.Visibility and third_deck.ViewObject.Visibility

    # An explicitly hidden part must not be restored by category or mode changes.
    hidden = by_label(first, "Corners").Group[0]
    hidden.ViewObject.Visibility = False
    update(doc)
    assert not hidden.StageSnapUserVisible
    corners = filter_for(first, "Corners")
    corners.Enabled = False
    update(doc)
    corners.Enabled = True
    update(doc)
    assert not hidden.ViewObject.Visibility
    assert not hidden.StageSnapUserVisible
    assert all(obj.ViewObject.Visibility for obj in by_label(third, "Corners").Group)
    placement = first.Placement.copy()
    for plan_view in (True, False, True):
        segments.set_segment_mode(first, plan_view)
        update(doc)
        assert first.Placement == placement
        assert not hidden.ViewObject.Visibility
        assert not hidden.StageSnapUserVisible
        assert_scene(doc)

    for mode in ('3D', '2D', '3D'):
        view_modes.show_mode(doc, Gui.activeDocument().activeView(), mode)
        update(doc)
        assert not hidden.ViewObject.Visibility
        for segment in (first, second, third):
            assert segment.StageSnapPlanView == (mode == '2D')
        assert_scene(doc)

    with TemporaryDirectory() as temp:
        saved = Path(temp) / "SegmentFilters.FCStd"
        names = first.Name, second.Name, third.Name, hidden.Name
        doc.saveAs(str(saved))
        App.closeDocument(doc.Name)
        doc = App.openDocument(str(saved))
        first, second, third, hidden = [doc.getObject(name) for name in names]
        assert_scene(doc)
        assert not hidden.StageSnapUserVisible and not hidden.ViewObject.Visibility
        frames = filter_for(first, "Frames")
        frames.ViewObject.Visibility = False
        update(doc)
        assert not frames.Enabled
        assert not by_label(first, "Frame").Group[0].ViewObject.Visibility
        assert not by_label(third, "Frame").Group[0].ViewObject.Visibility
        assert by_label(second, "Frame").Group[0].ViewObject.Visibility
        frames.Enabled = True
        update(doc)
        assert by_label(first, "Frame").Group[0].ViewObject.Visibility
        assert not hidden.ViewObject.Visibility
    print("Segment geometry, native sharing, per-area GUI filters, user hiding and reopen checks passed.", flush=True)
finally:
    App.closeDocument(doc.Name)
    Gui.getMainWindow().close()
