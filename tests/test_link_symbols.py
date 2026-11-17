"""Integration coverage for native symbol files and in-document instances."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import FreeCAD as App
from freecad.buehnensnap.segments import components, segment_shape
import Part

from freecad.buehnensnap import decks, plan_symbols


class LinkSymbolTest(unittest.TestCase):
    def setUp(self):
        self.previous = set(App.listDocuments())
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.model = self.root / "test-system/Test Symbol/Native.FCStd"
        self.model.parent.mkdir(parents=True)
        self.patch = patch.object(decks, "MODELS_DIR", self.root)
        self.patch.start()
        self.document = App.newDocument("LinkSymbolTest")
        self.deck = decks.Deck("native-test", "Native test", 800, 500, 90,
                               self.model.relative_to(self.root).as_posix())
        self.write_model()

    def tearDown(self):
        self.patch.stop()
        for name in set(App.listDocuments()) - self.previous:
            App.closeDocument(name)
        self.temp.cleanup()

    def write_model(self, extra_solid=False, leave_open=False, hidden=False):
        previous_mtime = self.model.stat().st_mtime_ns if self.model.exists() else 0
        source = App.newDocument("NativeSymbolSource")
        solid = source.addObject("Part::Feature", "Symbol3D")
        shapes = [Part.makeBox(800, 500, 90)]
        if extra_solid:
            shapes.append(Part.makeBox(30, 30, 100, App.Vector(20, 20, -100)))
        solid.Shape = Part.Compound(shapes)
        flat = source.addObject("Part::Feature", "Symbol2D")
        flat.Shape = Part.Compound([
            Part.makePlane(800, 500),
            Part.makeLine(App.Vector(0, 0, 0), App.Vector(800, 500, 0)),
        ])
        if hidden:
            flat.Visibility = False
            solid.Visibility = False
        source.recompute()
        source.saveAs(str(self.model))
        revision = max(self.model.stat().st_mtime_ns, previous_mtime + 1000000)
        os.utime(self.model, ns=(revision, revision))
        if not leave_open:
            App.closeDocument(source.Name)
        App.setActiveDocument(self.document.Name)
        return source if leave_open else None

    def insert(self, x=0, quarter_turn=1):
        placement = decks.seed_placement(self.deck, x, 0, 275, quarter_turn)
        return decks.insert_deck(self.document, self.deck, placement)

    def symbol(self, source):
        decks.set_deck_mode(source, True)
        self.document.recompute()
        return source

    def assert_vector(self, actual, expected):
        self.assertLess((actual - expected).Length, 1e-7)

    def test_both_variants_use_shared_in_document_templates(self):
        first, second = self.insert(), self.insert(2000)
        flat_first, flat_second = self.symbol(first), self.symbol(second)
        self.document.recompute()
        self.assertEqual(first.TypeId, "App::Part")
        self.assertIs(flat_first, first)
        self.assertIs(flat_second, second)
        self.assertEqual(next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').LinkedObject, next(c for c in components(second) if c.StageSnapRole == 'PedestalDeck').LinkedObject)
        self.assertEqual(next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').StageSnap3DTemplate, next(c for c in components(second) if c.StageSnapRole == 'PedestalDeck').StageSnap3DTemplate)
        self.assertEqual(next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').StageSnapPlanTemplate, next(c for c in components(second) if c.StageSnapRole == 'PedestalDeck').StageSnapPlanTemplate)
        self.assertNotEqual(next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').StageSnap3DTemplate, next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').StageSnapPlanTemplate)
        self.assertFalse(any(obj.TypeId == "App::LinkPython" for obj in self.document.Objects))
        for template in (next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').StageSnap3DTemplate, next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').StageSnapPlanTemplate):
            self.assertEqual(template.Document, self.document)
            self.assertIn("StageSnapComponentKey", template.PropertiesList)
            self.assertNotIn("StageSnapKind", template.PropertiesList)
            self.assertFalse(decks.is_deck(template))
            self.assertFalse(decks.is_deck_symbol(template))
        self.assertEqual(decks.deck_from_pick(first), first)
        self.assertEqual(decks.deck_from_pick(flat_first), first)
        self.assertEqual(len(segment_shape(flat_first).Edges), 5)
        self.assertAlmostEqual(segment_shape(flat_first).BoundBox.ZMax, 275)

    def test_file_revision_only_changes_new_instances(self):
        first = self.insert()
        self.write_model(extra_solid=True)
        second = self.insert(2000)
        third = self.insert(4000)
        self.assertNotEqual(next(c for c in components(first) if c.StageSnapRole == 'PedestalDeck').LinkedObject, next(c for c in components(second) if c.StageSnapRole == 'PedestalDeck').LinkedObject)
        self.assertEqual(next(c for c in components(second) if c.StageSnapRole == 'PedestalDeck').LinkedObject, next(c for c in components(third) if c.StageSnapRole == 'PedestalDeck').LinkedObject)
        self.assertEqual(len(segment_shape(first).Solids), 1)
        self.assertEqual(len(segment_shape(second).Solids), 2)

    def test_saved_plan_reopens_without_source_file(self):
        source = self.insert()
        self.symbol(source)
        name = source.Name
        self.document.recompute()
        saved = self.root / "StandalonePlan.FCStd"
        self.document.saveAs(str(saved))
        App.closeDocument(self.document.Name)
        self.model.unlink()
        self.document = App.openDocument(str(saved))
        source = self.document.getObject(name)
        self.document.recompute()
        self.assertEqual(len(segment_shape(source).Edges), 5)
        self.assertAlmostEqual(segment_shape(source).BoundBox.ZMax, 275)
        decks.set_deck_mode(source, False)
        self.document.recompute()
        self.assertEqual(len(segment_shape(source).Solids), 1)
        self.assertEqual(decks.deck_from_pick(source), source)
        self.assertEqual(next(c for c in components(source) if c.StageSnapRole == 'PedestalDeck').LinkedObject.Document, self.document)
        decks.set_deck_mode(source, True)
        self.document.recompute()
        self.assertEqual(len(segment_shape(source).Edges), 5)

    def test_plan_symbol_tracks_movement_in_rotated_parent(self):
        source = self.insert()
        for obj in list(self.document.Objects):
            if decks.is_deck_symbol(obj) and obj.StageSnapSource == source:
                self.document.removeObject(obj.Name)
        parent = self.document.addObject("App::Part", "MovedParent")
        parent.Placement = App.Placement(App.Vector(500, -250, 35),
                                         App.Rotation(App.Vector(0, 0, 1), 90))
        parent.addObject(source)
        symbol = self.symbol(source)
        source.Placement.Base = App.Vector(35, 80, 185)
        self.document.recompute()
        self.assertEqual(symbol.getParentGeoFeatureGroup(), parent)
        expected = parent.Placement * source.Placement
        for plan_view in (False, True):
            decks.set_deck_mode(source, plan_view)
            self.document.recompute()
            for point in (App.Vector(0, 0, 90), App.Vector(800, 500, 90)):
                self.assert_vector(plan_symbols.global_placement(source).multVec(point),
                                   expected.multVec(point))

    def test_legacy_box_remains_pickable_and_accepts_link_snap(self):
        old = self.document.addObject("Part::Box", "LegacyPodest")
        old.Length, old.Width, old.Height = self.deck.dimensions
        old.addProperty("App::PropertyString", "StageSnapKind")
        old.StageSnapKind = decks.DECK_KIND
        old.addProperty("App::PropertyString", "StageSnapCatalogId")
        old.StageSnapCatalogId = self.deck.catalog_id
        self.document.recompute()
        self.assertEqual(decks.deck_from_pick(old), old)
        new, side = decks.snap_deck(self.document, old, self.deck,
                                    App.Vector(790, 400, 90), 1)
        self.assertEqual(new.TypeId, "App::Part")
        self.assertEqual(side, "Rechts")
        self.assertAlmostEqual(segment_shape(new).BoundBox.XMin, 800)
        self.assertAlmostEqual(segment_shape(new).BoundBox.ZMax, 90)

    def test_explicit_hidden_objects_load_independently_of_visibility(self):
        self.write_model(hidden=True)
        solid = plan_symbols.load_variant_shape(self.model, "Symbol3D")
        flat = plan_symbols.load_variant_shape(self.model, "Symbol2D")
        self.assertEqual(len(solid.Solids), 1)
        self.assertFalse(flat.Solids)
        self.assertEqual(len(flat.Edges), 5)

    def test_source_document_and_unsaved_changes_are_preserved(self):
        source = self.write_model(leave_open=True)
        source.getObject("Symbol2D").Label = "Unsaved edit"
        before = set(App.listDocuments())
        shape = plan_symbols.load_variant_shape(self.model, "Symbol2D")
        self.assertEqual(len(shape.Edges), 5)
        self.assertEqual(set(App.listDocuments()), before)
        self.assertEqual(App.ActiveDocument, self.document)
        self.assertEqual(source.getObject("Symbol2D").Label, "Unsaved edit")

    def test_native_file_is_discovered_without_step_companion(self):
        entries = list(decks.plan_symbol_models("test-system", "Test system"))
        self.assertEqual(entries, [("Test Symbol", self.deck.model_file)])

    def test_missing_solid_variant_rejects_placement_without_partial_objects(self):
        source = App.openDocument(str(self.model))
        source.removeObject("Symbol3D")
        source.save()
        App.closeDocument(source.Name)
        App.setActiveDocument(self.document.Name)
        before = [obj.Name for obj in self.document.Objects]
        with self.assertRaisesRegex(ValueError, "Symbol3D"):
            self.insert()
        self.assertEqual([obj.Name for obj in self.document.Objects], before)

    def test_spatial_plan_variant_rejects_placement_without_partial_objects(self):
        source = App.openDocument(str(self.model))
        source.getObject("Symbol2D").Shape = Part.makeBox(800, 500, 20)
        source.recompute()
        source.save()
        App.closeDocument(source.Name)
        App.setActiveDocument(self.document.Name)
        before = [obj.Name for obj in self.document.Objects]
        with self.assertRaisesRegex(ValueError, "Symbol2D"):
            self.insert()
        self.assertEqual([obj.Name for obj in self.document.Objects], before)

    def test_unique_variant_labels_are_accepted_and_ambiguous_labels_rejected(self):
        source = App.newDocument("LabelSymbolSource")
        solid = source.addObject("Part::Feature", "SolidGeometry")
        solid.Label = "Symbol3D"
        solid.Shape = Part.makeBox(800, 500, 90)
        flat = source.addObject("Part::Feature", "PlanGeometry")
        flat.Label = "Symbol2D"
        flat.Shape = Part.makePlane(800, 500)
        source.recompute()
        source.saveAs(str(self.model))
        App.closeDocument(source.Name)
        App.setActiveDocument(self.document.Name)
        self.assertEqual(len(plan_symbols.load_variant_shape(self.model, "Symbol3D").Solids), 1)
        self.assertFalse(plan_symbols.load_variant_shape(self.model, "Symbol2D").Solids)
        source = App.openDocument(str(self.model))
        duplicate = source.addObject("Part::Feature", "DuplicatePlanGeometry")
        preferences = App.ParamGet("User parameter:BaseApp/Preferences/Document")
        allow_duplicates = preferences.GetBool("DuplicateLabels", False)
        try:
            preferences.SetBool("DuplicateLabels", True)
            duplicate.Label = "Symbol2D"
        finally:
            preferences.SetBool("DuplicateLabels", allow_duplicates)
        duplicate.Shape = Part.makePlane(800, 500)
        source.recompute()
        source.save()
        App.closeDocument(source.Name)
        App.setActiveDocument(self.document.Name)
        with self.assertRaisesRegex(ValueError, "eindeutig"):
            plan_symbols.load_variant_shape(self.model, "Symbol2D")


if __name__ == "__main__":
    unittest.main()
