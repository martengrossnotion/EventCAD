"""Component identities, normalization and geometry preservation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import FreeCAD as App
import Part
from freecad.buehnensnap import decks, component_models


class ComponentModelsTest(unittest.TestCase):
    def test_detailed_symbol_retains_each_solid_exactly_once(self):
        path = next(decks.MODELS_DIR.rglob('Buetec_standard*.FCStd'))
        model = decks.deck_for_model('Test', path.relative_to(decks.MODELS_DIR).as_posix())
        parts = component_models.component_specs(model, path)
        self.assertEqual(list(parts), list(component_models.ROLES))
        self.assertEqual([len(parts[role][0].Solids) for role in parts], [1] * 6)
        self.assertAlmostEqual(sum(item[0].Volume for item in parts.values()),
                               decks.load_deck_model(model).Volume, places=4)
        for item in parts.values():
            self.assertFalse(item[1].Solids)
            self.assertAlmostEqual(item[1].BoundBox.ZMin, model.depth)
            self.assertAlmostEqual(item[1].BoundBox.ZMax, model.depth)

    def test_simplified_symbol_does_not_invent_corners_or_frames(self):
        model = decks.Deck('custom', 'Simple', 800, 500, 90)
        parts = component_models.component_specs(model)
        self.assertEqual(len(parts['PedestalDeck'][0].Solids), 1)
        for role in component_models.ROLES[:-1]:
            self.assertTrue(parts[role][0].isNull())
            self.assertTrue(parts[role][1].isNull())

    def test_explicit_component_names_and_custom_2d_are_honoured(self):
        document = App.newDocument('NamedComponentSource')
        try:
            shapes = []
            for index, role in enumerate(component_models.ROLES):
                obj = document.addObject('Part::Feature', role)
                obj.Shape = Part.makeBox(10, 10, 5, App.Vector(100 + index * 20, 200, -5))
                shapes.append(obj.Shape)
            document.addObject('Part::Feature', 'Symbol3D').Shape = Part.Compound(shapes)
            document.addObject('Part::Feature', 'Symbol2D').Shape = Part.makePlane(110, 10)
            obj = document.addObject('Part::Feature', 'PedestalDeck2D')
            obj.Shape = Part.makeLine(App.Vector(200, 200, 0), App.Vector(205, 200, 0))
            document.recompute()
            with TemporaryDirectory() as temp:
                path = Path(temp) / 'Named.FCStd'
                document.saveAs(str(path))
                model = decks.Deck('named', 'Named', 110, 10, 5)
                parts = component_models.component_specs(model, path)
                self.assertEqual(set(parts), set(component_models.ROLES))
                self.assertEqual(len(parts['PedestalDeck'][1].Edges), 1)
                self.assertAlmostEqual(parts['PedestalDeck'][1].BoundBox.XMin, 100)
                self.assertAlmostEqual(parts['PedestalDeck'][1].BoundBox.ZMin, 5)
                self.assertEqual(sum(len(item[0].Solids) for item in parts.values()), 6)
                self.assertEqual(App.ActiveDocument, document)
        finally:
            App.closeDocument(document.Name)
