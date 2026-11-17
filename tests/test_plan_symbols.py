"""Exercise actual FCStd imports with FreeCAD's Python modules available."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import FreeCAD as App
import Part
import Sketcher

from freecad.buehnensnap import decks, plan_symbols


class PlanSymbolTest(unittest.TestCase):
    def setUp(self):
        self.previous_documents = set(App.listDocuments())
        self.addCleanup(self.close_documents)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(plan_symbols._read_plan_shape.cache_clear)
        self.patch = patch.object(decks, "MODELS_DIR", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.document = App.newDocument("PlanSymbolTest")
        self.model_file = "test-system/Bütec kleine Bühne/Modell.step"
        self.deck = decks.Deck("old-catalog-id", "Testpodest", 800, 500, 90,
                               self.model_file)
        self.model_path = self.root / self.model_file
        self.model_path.parent.mkdir(parents=True)
        Part.makeBox(*self.deck.dimensions).exportStep(str(self.model_path))
        self.symbol_path = self.model_path.with_name("Grundriss.FCStd")

    def close_documents(self):
        for name in set(App.listDocuments()) - self.previous_documents:
            App.closeDocument(name)

    def plan_shape(self, diagonals=1, offset=None):
        length, width, _ = self.deck.dimensions
        shapes = [Part.makePlane(length, width)]
        if diagonals:
            shapes.append(Part.makeLine(App.Vector(0, 0, 0), App.Vector(length, width, 0)))
        if diagonals > 1:
            shapes.append(Part.makeLine(App.Vector(length, 0, 0), App.Vector(0, width, 0)))
        shape = Part.Compound(shapes)
        if offset is not None:
            shape.translate(offset)
        return shape

    def write_symbol(self, shape=None, path=None, *, hidden_solid=False, leave_open=False):
        path = path or self.symbol_path
        path.parent.mkdir(parents=True, exist_ok=True)
        symbol_document = App.newDocument("SymbolSource")
        feature = symbol_document.addObject("Part::Feature", "PlanGeometry")
        feature.Shape = shape if shape is not None else self.plan_shape()
        if hidden_solid:
            hidden = symbol_document.addObject("Part::Feature", "HiddenModel")
            hidden.Shape = Part.makeBox(25, 25, 25)
            hidden.Visibility = False
        symbol_document.recompute()
        symbol_document.saveAs(str(path))
        if not leave_open:
            App.closeDocument(symbol_document.Name)
        App.setActiveDocument(self.document.Name)
        return symbol_document if leave_open else None

    def add_symbol(self, quarter_turn=1):
        placement = decks.seed_placement(self.deck, 1234, 2345, 275, quarter_turn)
        source = self.document.addObject("Part::Feature", "LegacyDeck")
        source.Shape = Part.makeBox(*self.deck.dimensions)
        source.Placement = placement
        for name, value in zip(("Length", "Width", "Height"), self.deck.dimensions):
            source.addProperty("App::PropertyLength", name)
            setattr(source, name, value)
        for name, value in (("StageSnapKind", decks.DECK_KIND),
                            ("StageSnapCatalogId", self.deck.catalog_id),
                            ("StageSnapModelFile", self.model_file)):
            source.addProperty("App::PropertyString", name)
            setattr(source, name, value)
        symbol = decks.make_deck_symbol(self.document, source)
        self.document.recompute()
        return source, symbol

    def assert_vector(self, actual, expected):
        self.assertLess((actual - expected).Length, 1e-7)

    def test_pairing_uses_the_symbol_directory_and_ignores_filenames(self):
        self.model_path.with_name("Modell.svg").touch()
        other = self.root / "other-system" / self.symbol_path.name
        other.parent.mkdir()
        other.touch()
        self.assertIsNone(plan_symbols.find_plan_symbol(self.model_path))
        self.symbol_path.touch()
        self.assertEqual(plan_symbols.find_plan_symbol(self.model_path), self.symbol_path)

    def test_extension_case_is_accepted_and_ambiguous_fcstd_files_are_rejected(self):
        path = self.symbol_path.with_suffix(".fcstd")
        path.touch()
        self.assertEqual(plan_symbols.find_plan_symbol(self.model_path), path)
        path.with_name("Alternative.FCStd").touch()
        with self.assertRaises(ValueError):
            plan_symbols.find_plan_symbol(self.model_path)

    def test_companion_is_not_a_separate_model_in_the_dropdown(self):
        self.write_symbol()
        entries = list(decks.plan_symbol_models("test-system", "Testsystem"))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], self.model_path.parent.name)
        self.assertEqual(entries[0][1], self.symbol_path.relative_to(self.root).as_posix())

    def test_ambiguous_fcstd_folder_is_not_offered_in_the_dropdown(self):
        self.write_symbol()
        self.symbol_path.with_name("Second.FCStd").write_bytes(self.symbol_path.read_bytes())
        self.assertEqual(list(decks.plan_symbol_models("test-system", "Testsystem")), [])

    def test_geometry_is_loaded_at_the_deck_top_with_both_rotations(self):
        self.write_symbol(self.plan_shape(offset=App.Vector(101, -67, 42)))
        for quarter_turn in (0, 1):
            with self.subTest(quarter_turn=quarter_turn):
                source, symbol = self.add_symbol(quarter_turn)
                try:
                    self.assertEqual(len(symbol.Shape.Edges), 5)
                    self.assertEqual(symbol.StageSnapPlanFile,
                                     self.symbol_path.relative_to(self.root).as_posix())
                    bounds, source_bounds = symbol.Shape.BoundBox, source.Shape.BoundBox
                    self.assertAlmostEqual(bounds.XMin, source_bounds.XMin)
                    self.assertAlmostEqual(bounds.XMax, source_bounds.XMax)
                    self.assertAlmostEqual(bounds.YMin, source_bounds.YMin)
                    self.assertAlmostEqual(bounds.YMax, source_bounds.YMax)
                    self.assertAlmostEqual(bounds.ZMin, 275)
                    self.assertAlmostEqual(bounds.ZMax, 275)
                    self.assertIs(decks.deck_from_pick(symbol), source)
                finally:
                    self.document.removeObject(symbol.Name)
                    self.document.removeObject(source.Name)
                    self.document.recompute()

    def test_symbol_tracks_source_placement_inside_a_transformed_part(self):
        self.write_symbol()
        source, initial = self.add_symbol()
        self.document.removeObject(initial.Name)
        group = self.document.addObject("App::Part", "ParentPart")
        group.Placement = App.Placement(App.Vector(500, -250, 35),
                                        App.Rotation(App.Vector(0, 0, 1), 90))
        group.addObject(source)
        symbol = decks.make_deck_symbol(self.document, source)
        source.Placement.Base = App.Vector(35, 80, 185)
        self.document.recompute()
        self.assertIs(symbol.getParentGeoFeatureGroup(), group)
        for point in (App.Vector(0, 0, 90), App.Vector(800, 500, 90)):
            self.assert_vector(symbol.getGlobalPlacement().multVec(point),
                               source.getGlobalPlacement().multVec(point))
        self.assertAlmostEqual(symbol.Shape.BoundBox.ZMin, source.Shape.BoundBox.ZMax)

    def test_replacing_the_file_refreshes_an_existing_symbol(self):
        self.write_symbol()
        source, symbol = self.add_symbol()
        self.assertEqual(len(symbol.Shape.Edges), 5)
        self.write_symbol(self.plan_shape(diagonals=2))
        decks.refresh_deck_symbol(symbol)
        symbol.touch()
        self.document.recompute()
        self.assertEqual(len(symbol.Shape.Edges), 6)
        self.assertIs(symbol.StageSnapSource, source)

    def test_current_model_file_overrides_the_old_catalog_id(self):
        self.write_symbol()
        source, symbol = self.add_symbol()
        current = self.root / "test-system/Anderes Symbol/Neuer Dateiname.step"
        current.parent.mkdir()
        current.write_bytes(self.model_path.read_bytes())
        companion = current.with_name("Anderer Grundriss.FCStd")
        self.write_symbol(self.plan_shape(diagonals=2), companion)
        source.StageSnapModelFile = current.relative_to(self.root).as_posix()
        source.Label = "Unabhängiger Objektname"
        decks.refresh_deck_symbol(symbol)
        symbol.touch()
        self.document.recompute()
        self.assertEqual(len(symbol.Shape.Edges), 6)
        self.assertEqual(symbol.StageSnapPlanFile, companion.relative_to(self.root).as_posix())
        renamed_model = current.with_name("Beliebig umbenannt.STP")
        renamed_companion = companion.with_name("Vollkommen anderer Planname.FCStd")
        current.rename(renamed_model)
        companion.rename(renamed_companion)
        decks.refresh_deck_symbol(symbol)
        symbol.touch()
        self.document.recompute()
        self.assertEqual(len(symbol.Shape.Edges), 6)
        self.assertEqual(source.StageSnapModelFile,
                         renamed_companion.relative_to(self.root).as_posix())
        self.assertEqual(symbol.StageSnapPlanFile,
                         renamed_companion.relative_to(self.root).as_posix())

    def test_legacy_catalog_id_still_finds_a_companion(self):
        catalog_deck = decks.CATALOG["BÜTEC Standard"][0]
        path = self.root / catalog_deck.model_file
        companion = path.with_name("Grundriss.FCStd")
        self.write_symbol(Part.makePlane(catalog_deck.length, catalog_deck.width), companion)
        source = self.document.addObject("Part::Box", "LegacyDeck")
        source.Length, source.Width, source.Height = catalog_deck.dimensions
        source.addProperty("App::PropertyString", "StageSnapKind")
        source.StageSnapKind = decks.DECK_KIND
        source.addProperty("App::PropertyString", "StageSnapCatalogId")
        source.StageSnapCatalogId = catalog_deck.catalog_id
        symbol = decks.make_deck_symbol(self.document, source)
        self.document.recompute()
        self.assertEqual(symbol.StageSnapPlanFile, companion.relative_to(self.root).as_posix())
        self.assertAlmostEqual(symbol.Shape.Area, 2000000)

    def test_missing_and_invalid_companions_leave_a_usable_rectangle(self):
        for content in (None, "corrupt", "solid", "wrong-size"):
            with self.subTest(content=content):
                if content == "corrupt":
                    self.symbol_path.write_text("This is not a FreeCAD file.")
                elif content == "solid":
                    self.write_symbol(Part.makeBox(800, 500, 20))
                elif content == "wrong-size":
                    self.write_symbol(Part.makePlane(10, 10))
                before = set(App.listDocuments())
                source, symbol = self.add_symbol()
                self.assertEqual(set(App.listDocuments()), before)
                self.assertEqual(len(symbol.Shape.Edges), 4)
                self.assertAlmostEqual(symbol.Shape.Area, 400000)
                self.assertFalse(symbol.Shape.isNull())
                self.document.removeObject(symbol.Name)
                self.document.removeObject(source.Name)
                self.document.recompute()

    def test_hidden_solids_are_ignored_when_importing_plan_geometry(self):
        self.write_symbol(hidden_solid=True)
        shape = plan_symbols.load_plan_shape(self.symbol_path, 800, 500)
        self.assertEqual(len(shape.Edges), 5)
        self.assertFalse(shape.Solids)

    def test_a_visible_sketch_is_supported(self):
        document = App.newDocument("SketchSource")
        sketch = document.addObject("Sketcher::SketchObject", "PlanSketch")
        points = [App.Vector(x, y, 0) for x, y in
                  ((0, 0), (800, 0), (800, 500), (0, 500), (0, 0))]
        sketch.addGeometry([Part.LineSegment(a, b) for a, b in zip(points, points[1:])], False)
        document.recompute()
        document.saveAs(str(self.symbol_path))
        App.closeDocument(document.Name)
        shape = plan_symbols.load_plan_shape(self.symbol_path, 800, 500)
        self.assertEqual(len(shape.Edges), 4)
        self.assertAlmostEqual(shape.BoundBox.XLength, 800)
        self.assertAlmostEqual(shape.BoundBox.YLength, 500)

    def test_source_plane_in_an_ordinary_document_group_is_imported_once(self):
        document = App.newDocument("GroupedSymbolSource")
        group = document.addObject("App::DocumentObjectGroup", "SymbolGroup")
        plane = document.addObject("Part::Feature", "PlanGeometry")
        plane.Shape = Part.makePlane(800, 500)
        plane.Placement.Base = App.Vector(120, -40, 35)
        group.addObject(plane)
        document.recompute()
        document.saveAs(str(self.symbol_path))
        App.closeDocument(document.Name)
        App.setActiveDocument(self.document.Name)
        shape = plan_symbols.load_plan_shape(self.symbol_path, 800, 500)
        self.assertEqual(len(shape.Faces), 1)
        self.assertEqual(len(shape.Edges), 4)
        self.assertAlmostEqual(shape.Area, 400000)
        self.assert_vector(App.Vector(shape.BoundBox.XMin, shape.BoundBox.YMin,
                                      shape.BoundBox.ZMin), App.Vector(0, 0, 0))

    def test_source_plane_in_a_transformed_part_uses_the_parent_placement_once(self):
        document = App.newDocument("PartSymbolSource")
        group = document.addObject("App::Part", "SymbolPart")
        group.Placement = App.Placement(App.Vector(325, -140, 65),
                                        App.Rotation(App.Vector(0, 0, 1), 90))
        plane = document.addObject("Part::Feature", "PlanGeometry")
        # Parent rotation changes this 500 x 800 plane to the required 800 x 500.
        plane.Shape = Part.makePlane(500, 800)
        plane.Placement.Base = App.Vector(30, 45, 25)
        group.addObject(plane)
        document.recompute()
        document.saveAs(str(self.symbol_path))
        App.closeDocument(document.Name)
        App.setActiveDocument(self.document.Name)
        shape = plan_symbols.load_plan_shape(self.symbol_path, 800, 500)
        self.assertEqual(len(shape.Faces), 1)
        self.assertEqual(len(shape.Edges), 4)
        self.assertAlmostEqual(shape.Area, 400000)
        self.assertAlmostEqual(shape.BoundBox.XLength, 800)
        self.assertAlmostEqual(shape.BoundBox.YLength, 500)
        self.assert_vector(App.Vector(shape.BoundBox.XMin, shape.BoundBox.YMin,
                                      shape.BoundBox.ZMin), App.Vector(0, 0, 0))

    def test_open_source_document_and_active_plan_are_preserved(self):
        source_document = self.write_symbol(leave_open=True)
        source_document.getObject("PlanGeometry").Label = "Unsaved edit"
        before = set(App.listDocuments())
        shape = plan_symbols.load_plan_shape(self.symbol_path, 800, 500)
        self.assertEqual(len(shape.Edges), 5)
        self.assertEqual(set(App.listDocuments()), before)
        self.assertIs(App.ActiveDocument, self.document)
        self.assertEqual(source_document.getObject("PlanGeometry").Label, "Unsaved edit")

    def test_embedded_symbol_survives_reopening_without_model_or_companion(self):
        self.write_symbol(self.plan_shape(diagonals=2))
        source, symbol = self.add_symbol()
        symbol_name = symbol.Name
        saved = self.root / "Plan.FCStd"
        self.document.saveAs(str(saved))
        App.closeDocument(self.document.Name)
        self.model_path.unlink()
        self.symbol_path.unlink()
        plan_symbols._read_plan_shape.cache_clear()
        self.document = App.openDocument(str(saved))
        symbol = self.document.getObject(symbol_name)
        decks.refresh_deck_symbol(symbol)
        symbol.touch()
        self.document.recompute()
        self.assertEqual(len(symbol.Shape.Edges), 6)
        self.assertAlmostEqual(symbol.Shape.BoundBox.ZMax, 275)
        self.assertIsNotNone(decks.deck_from_pick(symbol))


if __name__ == "__main__":
    unittest.main()

