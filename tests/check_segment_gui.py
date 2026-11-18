"""Exercise native subgroup masks, edited geometry and legacy plan migration.

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
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
from pivy import coin
import Part
from freecad.buehnensnap import decks, segments, view_modes


def by_label(parent, label):
    return next(obj for obj in parent.Group if obj.Label == label)


def components(segment):
    return [obj for group in segment.Group if hasattr(group, "Group") for obj in group.Group
            if getattr(obj, "StageSnapOwner", None) == segment and obj.TypeId == "App::Link"]


def update(document):
    document.recompute()
    QtWidgets.QApplication.processEvents()


def filter_for(segment, role):
    return by_label(by_label(segments.segment_area(segment), "Views"), "View" + role)


def scene_bounds(document):
    update(document)
    action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion(800, 600))
    action.apply(Gui.getDocument(document.Name).activeView().getSceneGraph())
    bounds = action.getBoundingBox()
    # Coin returns a reference owned by the action. Copy values before that
    # action is released, otherwise subsequent comparisons use dangling data.
    return None if bounds.isEmpty() else (tuple(bounds.getMin().getValue()),
                                         tuple(bounds.getMax().getValue()))


def assert_scene(document):
    assert scene_bounds(document) is not None, "all segment geometry disappeared"


def check_cut_group_mask():
    """Observe real rendering bounds, including objects added after registration."""
    document = App.newDocument("CutGroupMaskCheck")
    try:
        model = decks.Deck("custom", "Cut mask test", 800, 500, 90)
        segment = decks.insert_deck(document, model, decks.seed_placement(model, 0, 0, 275, 1))
        group = by_label(segment, "Deck")
        source = next(obj for obj in components(segment) if obj.StageSnapRole == "PedestalDeck")
        filter_for(segment, "Frames").Enabled = False
        filter_for(segment, "Corners").Enabled = False
        control = filter_for(segment, "Decks")
        registered = list(control.Members)

        # Use an independent editable shape, as users may replace the link with
        # either copied geometry or a boolean result without addon properties.
        source.ViewObject.Visibility = False
        base = document.addObject("Part::Feature", "CutBase")
        base.Shape = Part.makeBox(300, 200, 80)
        group.addObject(base)
        tool = document.addObject("Part::Feature", "CutTool")
        tool.Shape = Part.makeBox(100, 100, 100, App.Vector(250, 50, -10))
        group.addObject(tool)
        cut = document.addObject("Part::Cut", "EditedDeck")
        group.addObject(cut)
        cut.Base, cut.Tool = base, tool
        update(document)
        base.ViewObject.Visibility = False
        tool.ViewObject.Visibility = False
        cut.ViewObject.Visibility = True

        marker = document.addObject("Part::Feature", "LaterDeckGeometry")
        marker.Shape = Part.makeBox(10, 10, 10, App.Vector(100000, 0, 0))
        group.addObject(marker)
        marker.ViewObject.Visibility = True
        assert list(control.Members) == registered, "adding geometry must not require member registration"
        assert not hasattr(cut, "StageSnapOwner") and not hasattr(marker, "StageSnapOwner")
        bounds = scene_bounds(document)
        assert bounds is not None and bounds[1][0] > 90000

        def assert_local_visibility():
            assert not source.ViewObject.Visibility
            assert not base.ViewObject.Visibility
            assert not tool.ViewObject.Visibility
            assert cut.ViewObject.Visibility
            assert marker.ViewObject.Visibility

        for enabled in (False, True, False, True):
            control.Enabled = enabled
            assert_local_visibility()
            masked_bounds = scene_bounds(document)
            assert (masked_bounds is None) == (not enabled), \
                "the subgroup must mask the actual scene while preserving child visibility"
            if enabled:
                assert masked_bounds[1][0] > 90000, "later geometry disappeared from the group"

        for plan_view in (True, False):
            segments.set_segment_mode(segment, plan_view)
            update(document)
            assert_local_visibility()

        with TemporaryDirectory() as temp:
            saved = Path(temp) / "CutGroupMask.FCStd"
            names = segment.Name, source.Name, base.Name, tool.Name, cut.Name, marker.Name
            control.Enabled = False
            document.saveAs(str(saved))
            App.closeDocument(document.Name)
            document = App.openDocument(str(saved))
            segment, source, base, tool, cut, marker = [document.getObject(name) for name in names]
            control = filter_for(segment, "Decks")
            assert not control.Enabled
            assert scene_bounds(document) is None, "saved disabled group reappeared after reopening"
            assert_local_visibility()
            control.Enabled = True
            assert scene_bounds(document)[1][0] > 90000
            assert_local_visibility()
    finally:
        App.closeDocument(document.Name)


def check_legacy_cut_migration():
    """Opening a v2.0 folder layout upgrades a real edited boolean result."""
    document = App.newDocument("LegacyCutMigrationCheck")
    try:
        with segments.updating():
            area = segments.create_area(document)
            parent = document.addObject("App::Part", "RotatedParent")
            parent.Placement = App.Placement(App.Vector(600, 1200, 50),
                                             App.Rotation(App.Vector(0, 0, 1), 90))
            parent.addObject(area)
            segment = document.addObject("App::Part", "LegacySegment")
            segment.addProperty("App::PropertyBool", "StageSnapSegment", "Podest")
            segment.StageSnapSegment = True
            segment.addProperty("App::PropertyBool", "StageSnapPlanView", "Podest")
            segment.addProperty("App::PropertyLinkHidden", "StageSnapArea", "Podest")
            segment.StageSnapArea = area
            area.addObject(segment)
            segment.Placement = App.Placement(App.Vector(-300, 150, 200), App.Rotation())
            group = document.addObject("App::DocumentObjectGroup", "LegacyDeck")
            segments.exact_label(group, "Deck")
            segment.addObject(group)
            template = document.addObject("Part::Feature", "LegacyDeckTemplate")
            template.Shape = Part.makeBox(300, 200, 80)
            template.Visibility = False
            source = document.addObject("App::Link", "LegacyPedestalDeck")
            source.setLink(template)
            source.LinkTransform = False
            source.addProperty("App::PropertyLinkHidden", "StageSnapOwner", "Podest")
            source.StageSnapOwner = segment
            source.addProperty("App::PropertyString", "StageSnapRole", "Podest")
            source.StageSnapRole = "PedestalDeck"
            source.addProperty("App::PropertyBool", "StageSnapUserVisible", "Podest")
            source.StageSnapUserVisible = True
            for prop in ("StageSnap3DTemplate", "StageSnapPlanTemplate"):
                source.addProperty("App::PropertyLinkGlobal", prop, "Podest")
                setattr(source, prop, template)
            group.addObject(source)
            tool = document.addObject("Part::Feature", "LegacyCutTool")
            tool.Shape = Part.makeBox(100, 100, 100, App.Vector(250, 50, -10))
            group.addObject(tool)
            cut = document.addObject("Part::Cut", "LegacyEditedDeck")
            group.addObject(cut)
            cut.Base, cut.Tool = source, tool
            control = filter_for(segment, "Decks")
            control.Members = [source]
        from freecad.buehnensnap.plan_symbols import global_placement
        with TemporaryDirectory() as temp:
            saved = Path(temp) / "LegacyCut.FCStd"
            with segments.updating():
                # Finish writing the old-format fixture before any new
                # recompute/activation hook gets a chance to upgrade it.
                update(document)
                source.Visibility = False
                source.StageSnapUserVisible = False
                tool.Visibility = False
                cut.Visibility = True
                update(document)
                assert cut.Shape.Volume > 0
                retained = source, tool, cut
                placements = {obj.Name: global_placement(obj).copy() for obj in retained}
                control.Enabled = False
                control.Visibility = False
                names = segment.Name, source.Name, tool.Name, cut.Name, group.Name
                document.saveAs(str(saved))
            App.closeDocument(document.Name)
            document = App.openDocument(str(saved))
            segment, source, tool, cut, group = [document.getObject(name) for name in names]
            update(document)
            assert group.hasExtension("App::GeoFeatureGroupExtension"), \
                "opening a legacy plan must upgrade its folders automatically"
            assert group.ViewObject.hasExtension("Gui::ViewProviderGeoFeatureGroupExtension")
            control = filter_for(segment, "Decks")
            assert list(control.Members) == [group]
            assert not control.Enabled and not group.Visibility
            assert not source.Visibility and not tool.Visibility and cut.Visibility
            assert cut.Base == source and cut.Tool == tool
            for obj in (source, tool, cut):
                assert global_placement(obj) == placements[obj.Name], \
                    "migrating an edited legacy subgroup changed a world placement"
            assert scene_bounds(document) is None, "disabled migrated category leaked its edited result"
            control.Enabled = True
            assert scene_bounds(document) is not None
            assert not source.Visibility and not tool.Visibility and cut.Visibility
            assert cut.Shape.Volume > 0
    finally:
        App.closeDocument(document.Name)


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
    assert [obj.Label for obj in first.Group if hasattr(obj, "Group")] == [
        "Corners", "Frame", "Deck", "Verbinder", "Steckfüße", "Geländer"]
    assert len(components(first)) == 6
    assert all(obj.TypeId == "App::Link" for obj in components(first))
    assert all(obj.StageSnap3DTemplate.Shape.Solids for obj in components(first)), \
        "the detailed symbol must split into six real solid components"
    assert all(obj.StageSnapRole == obj.Label for obj in components(first))
    assert all(obj.ViewObject.Visibility for obj in components(first))
    assert not first.Origin.ViewObject.ShowInTree
    for label, category in (("Deck", "Decks"), ("Frame", "Frames"), ("Corners", "Corners")):
        group = by_label(first, label)
        assert group in filter_for(first, category).Members
        assert group.hasExtension("App::GeoFeatureGroupExtension")
    for label in ("Verbinder", "Steckfüße", "Geländer"):
        group = by_label(first, label)
        assert group.hasExtension("App::GeoFeatureGroupExtension")
        assert group.Group == []

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
    assert not by_label(first, "Deck").ViewObject.Visibility
    assert not by_label(third, "Deck").ViewObject.Visibility
    assert first_deck.ViewObject.Visibility and third_deck.ViewObject.Visibility, \
        "category masking must not change component visibility"
    assert second_deck.ViewObject.Visibility, "a different area's filter must remain independent"
    deck_filter.Enabled = True
    update(doc)
    assert deck_filter.ViewObject.Visibility
    assert by_label(first, "Deck").ViewObject.Visibility and by_label(third, "Deck").ViewObject.Visibility
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
        assert not by_label(first, "Frame").ViewObject.Visibility
        assert not by_label(third, "Frame").ViewObject.Visibility
        assert by_label(first, "Frame").Group[0].ViewObject.Visibility
        assert by_label(third, "Frame").Group[0].ViewObject.Visibility
        assert by_label(second, "Frame").Group[0].ViewObject.Visibility
        frames.Enabled = True
        update(doc)
        assert by_label(first, "Frame").Group[0].ViewObject.Visibility
        assert not hidden.ViewObject.Visibility
    check_cut_group_mask()
    check_legacy_cut_migration()
    print("Segment geometry, native sharing, subgroup scene masks, edited cuts, "
          "per-area filters, mode changes, reopen and legacy migration checks passed.", flush=True)
finally:
    App.closeDocument(doc.Name)
    Gui.getMainWindow().close()
