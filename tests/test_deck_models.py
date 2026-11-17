"""Run with FreeCAD's Python modules available."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import FreeCAD as App
import Part

from freecad.buehnensnap import decks


class DeckModelTest(unittest.TestCase):
    deck = decks.CATALOG["BÜTEC Standard"][0]

    def setUp(self):
        self.document = App.newDocument("DeckModelTest")
        self.addCleanup(self.close_document)

    def close_document(self):
        if self.document.Name in App.listDocuments():
            App.closeDocument(self.document.Name)

    def add_deck(self, x=0):
        placement = decks.seed_placement(self.deck, x, 0, 150, 1)
        return decks.insert_deck(self.document, self.deck, placement)

    def test_every_fixed_size_has_a_model(self):
        for sizes in decks.CATALOG.values():
            for deck in filter(None, sizes):
                with self.subTest(deck=deck.catalog_id):
                    self.assertIsNotNone(deck.model_file)
                    self.assertAlmostEqual(decks.load_deck_model(deck).BoundBox.ZMax, deck.depth)

    def test_uploaded_buetec_model_has_its_own_plan_symbol_and_uses_real_dimensions(self):
        filename = "Buetec_standard_1x2m-Buetec_standard_1x2m.step"
        entries = dict(decks.plan_symbol_models("buetec-standard", "BÜTEC Standard"))
        self.assertIn("2 × 1 m", entries)
        model = decks.deck_for_model("BÜTEC Standard", entries[Path(filename).stem])
        for actual, expected in zip(model.dimensions, (1000, 2000, 90)):
            self.assertAlmostEqual(actual, expected)

        target = self.add_deck()
        placement = target.Placement.multVec(App.Vector(1950, 700, 90))
        obj, side = decks.snap_deck(self.document, target, model, placement, 1)
        self.assertEqual(side, "Rechts")
        self.assertEqual(len(obj.Shape.Solids), 6)
        self.assertAlmostEqual(obj.Shape.BoundBox.XMin, target.Shape.BoundBox.XMax)

    def test_additional_models_are_discovered_only_in_the_selected_system(self):
        with TemporaryDirectory() as temp, patch.object(decks, "MODELS_DIR", Path(temp)):
            folder = Path(temp) / "buetec-eco"
            folder.mkdir()
            (folder / ".gitkeep").touch()
            (folder / "Leerer Ordner").mkdir()
            filename = "Kleines Podest.STP"
            symbol_folder = folder / "Kleines Podest"
            symbol_folder.mkdir()
            Part.makeBox(735, 520, 44).exportStep(str(symbol_folder / filename))
            entries = list(decks.plan_symbol_models("buetec-eco", "BÜTEC Eco"))
            self.assertEqual(entries, [("Kleines Podest", f"buetec-eco/Kleines Podest/{filename}")])
            self.assertEqual(list(decks.plan_symbol_models("buetec-standard", "BÜTEC Standard")), [])
            model = decks.deck_for_model("BÜTEC Eco", entries[0][1])
            self.assertEqual(model.dimensions, (735, 520, 44))

    def test_replacing_the_file_affects_new_placements_and_embeds_the_shape(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / self.deck.model_file
            path.parent.mkdir(parents=True)
            Part.makeBox(*self.deck.dimensions).exportStep(str(path))
            with patch.object(decks, "MODELS_DIR", directory):
                original = self.add_deck()
                plate = Part.makeBox(*self.deck.dimensions, App.Vector(25, 50, 75))
                leg = Part.makeBox(50, 50, 300, App.Vector(50, 75, -225))
                Part.Compound([plate, leg]).exportStep(str(path))
                replacement = self.add_deck(3000)

            self.assertEqual(original.TypeId, "Part::Feature")
            self.assertEqual(len(original.Shape.Solids), 1)
            self.assertEqual(len(replacement.Shape.Solids), 2)
            bounds = replacement.Shape.BoundBox
            for actual, expected in zip((bounds.XMin, bounds.YMin, bounds.ZMin, bounds.ZMax),
                                        (2000, -500, -240, 150)):
                self.assertAlmostEqual(actual, expected)

            symbol = decks.make_deck_symbol(self.document, replacement)
            self.document.recompute()
            self.assertAlmostEqual(symbol.Shape.BoundBox.ZMax, 150)
            self.assertAlmostEqual(symbol.Shape.BoundBox.XMin, 2000)

            plan = directory / "Plan.FCStd"
            name = replacement.Name
            self.document.saveAs(str(plan))
            self.close_document()
            path.unlink()
            self.document = App.openDocument(str(plan))
            self.assertEqual(len(self.document.getObject(name).Shape.Solids), 2)

    def test_wrong_dimensions_leave_the_document_unchanged(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / self.deck.model_file
            path.parent.mkdir(parents=True)
            Part.makeBox(1000, 2000, 90).exportStep(str(path))
            with patch.object(decks, "MODELS_DIR", directory):
                with self.assertRaisesRegex(ValueError, "2000 × 1000 mm"):
                    self.add_deck()
        self.assertFalse(self.document.Objects)

    def test_imported_deck_can_snap_to_legacy_box(self):
        legacy = self.document.addObject("Part::Box", "OldPodest")
        legacy.Length, legacy.Width, legacy.Height = self.deck.dimensions
        legacy.addProperty("App::PropertyString", "StageSnapKind")
        legacy.StageSnapKind = decks.DECK_KIND
        legacy.addProperty("App::PropertyString", "StageSnapCatalogId")
        legacy.StageSnapCatalogId = self.deck.catalog_id
        self.document.recompute()

        new, side = decks.snap_deck(self.document, legacy, self.deck, App.Vector(1950, 700, 90), 1)
        self.assertEqual(side, "Rechts")
        self.assertAlmostEqual(new.Shape.BoundBox.XMin, 2000)
        self.assertAlmostEqual(new.Shape.BoundBox.ZMax, 90)
