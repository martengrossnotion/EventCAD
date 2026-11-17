"""One physical deck keeps its identity, transform and visibility in both modes."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import FreeCAD as App
from freecad.buehnensnap.segments import components, segment_shape
import Part

from freecad.buehnensnap import decks
from freecad.buehnensnap.plan_symbols import global_placement


class UnifiedDisplayTest(unittest.TestCase):
    def setUp(self):
        self.previous = set(App.listDocuments())
        self.document = App.newDocument("UnifiedDisplayTest")
        self.deck = decks.Deck("custom", "Test deck", 800, 500, 90)

    def tearDown(self):
        for name in set(App.listDocuments()) - self.previous:
            App.closeDocument(name)

    def insert(self, plan_view=False):
        placement = decks.seed_placement(self.deck, 1200, 900, 275, 1)
        return decks.insert_deck(self.document, self.deck, placement,
                                  plan_view=plan_view)

    def mode(self, source, plan_view):
        decks.set_deck_mode(source, plan_view)
        self.document.recompute()

    def assert_placement(self, actual, expected):
        self.assertLess((actual.Base - expected.Base).Length, 1e-7)
        for axis in (App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)):
            self.assertLess((actual.Rotation.multVec(axis)
                             - expected.Rotation.multVec(axis)).Length, 1e-7)

    def test_switch_reuses_same_object_without_a_second_display_object(self):
        source = self.insert()
        original = source.Name
        original_objects = [obj.Name for obj in self.document.Objects]
        placement = source.Placement
        for plan_view in (True, False, True):
            self.mode(source, plan_view)
            self.assertIs(self.document.getObject(original), source)
            self.assertEqual([obj.Name for obj in self.document.Objects], original_objects)
            self.assertEqual(source.TypeId, "App::Part")
            for child in components(source):
                self.assertEqual(child.LinkedObject, child.StageSnapPlanTemplate if plan_view
                                 else child.StageSnap3DTemplate)
            self.assert_placement(source.Placement, placement)
            self.assertEqual(bool(segment_shape(source).Solids), not plan_view)
            self.assertFalse(any(decks.is_deck_symbol(obj) for obj in self.document.Objects))
            self.assertFalse(any(obj.TypeId == "App::LinkPython" for obj in self.document.Objects))

    def test_moving_and_rotating_in_2d_survives_3d_and_back(self):
        source = self.insert(plan_view=True)
        self.assertFalse(segment_shape(source).Solids)
        moved = App.Placement(App.Vector(4200, -725, 610),
                              App.Rotation(App.Vector(0, 0, 1), 90))
        source.Placement = moved
        self.document.recompute()
        plan_bounds = segment_shape(source).BoundBox
        for plan_view in (False, True):
            self.mode(source, plan_view)
            self.assert_placement(source.Placement, moved)
            bounds = segment_shape(source).BoundBox
            for attr in ("XMin", "XMax", "YMin", "YMax", "ZMax"):
                self.assertAlmostEqual(getattr(bounds, attr), getattr(plan_bounds, attr))
            self.assertEqual(decks.deck_from_pick(source), source)

    def test_mode_switch_preserves_explicit_visibility(self):
        source = self.insert()
        for visible in (False, True):
            source.Visibility = visible
            for plan_view in (True, False, True):
                self.mode(source, plan_view)
                self.assertEqual(source.Visibility, visible)

    def test_snap_uses_placement_edited_in_2d(self):
        source = self.insert(plan_view=True)
        source.Placement = App.Placement(App.Vector(3000, 4000, 200),
                                         App.Rotation(App.Vector(0, 0, 1), 90))
        self.document.recompute()
        picked = source.Placement.multVec(App.Vector(790, 400, 90))
        placed, side = decks.snap_deck(self.document, source, self.deck, picked, 1,
                                       plan_view=True)
        self.assertFalse(segment_shape(placed).Solids)
        before = segment_shape(placed).BoundBox
        self.mode(source, False)
        self.mode(placed, False)
        for attr in ("XMin", "XMax", "YMin", "YMax", "ZMax"):
            self.assertAlmostEqual(getattr(segment_shape(placed).BoundBox, attr), getattr(before, attr))
        self.assertGreater(len(segment_shape(placed).Solids), 0)

    def test_transformed_parent_and_local_edit_survive_mode_changes(self):
        source = self.insert(plan_view=True)
        parent = self.document.addObject("App::Part", "Parent")
        parent.Placement = App.Placement(App.Vector(150, -320, 60),
                                         App.Rotation(App.Vector(0, 0, 1), 90))
        parent.addObject(source)
        source.Placement = App.Placement(App.Vector(740, 290, 220),
                                         App.Rotation(App.Vector(0, 0, 1), 180))
        expected = parent.Placement * source.Placement
        for plan_view in (False, True):
            self.mode(source, plan_view)
            self.assertEqual(source.getParentGeoFeatureGroup(), parent)
            self.assert_placement(global_placement(source), expected)

    def test_v17_link_gains_3d_reference_without_loading_source_file(self):
        solid, plan = decks.symbol_templates(self.document, self.deck)
        source = self.document.addObject("App::Link", "LegacyPodest")
        source.setLink(solid)
        source.LinkTransform = False
        source.addProperty("App::PropertyLink", "StageSnapPlanTemplate")
        source.StageSnapPlanTemplate = plan
        source.addProperty("App::PropertyString", "StageSnapModelFile")
        original_template = source.LinkedObject
        template_name = original_template.Name
        source.StageSnapModelFile = "missing-system/missing-symbol/missing.FCStd"
        original_placement = source.Placement
        with TemporaryDirectory() as temp:
            saved = Path(temp) / "PreviousVersionPlan.FCStd"
            name = source.Name
            self.document.saveAs(str(saved))
            App.closeDocument(self.document.Name)
            self.document = App.openDocument(str(saved))
            source = self.document.getObject(name)
            original_template = self.document.getObject(template_name)
            self.mode(source, True)
            self.assertIn("StageSnap3DTemplate", source.PropertiesList)
            self.assertEqual(source.StageSnap3DTemplate, original_template)
            self.assertFalse(segment_shape(source).Solids)
            self.mode(source, False)
            self.assertEqual(source.LinkedObject, original_template)
            self.assertEqual(len(segment_shape(source).Solids), 1)
            self.assert_placement(source.Placement, original_placement)


if __name__ == "__main__":
    unittest.main()
