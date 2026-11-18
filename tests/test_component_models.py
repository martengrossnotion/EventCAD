"""Component identities, normalization and geometry preservation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import FreeCAD as App
import Part
from freecad.buehnensnap import decks, component_models


class ComponentModelsTest(unittest.TestCase):
    def test_detailed_plan_has_pickable_deck_surface_and_independent_hardware(self):
        path = next(decks.MODELS_DIR.rglob('Buetec_standard*.FCStd'))
        model = decks.deck_for_model('Test', path.relative_to(decks.MODELS_DIR).as_posix())
        parts = component_models.component_specs(model, path)
        surface = parts['PedestalDeck'][1]
        self.assertTrue(surface.Faces, 'the plate interior must be a pickable face, not just four edges')
        self.assertFalse(surface.Solids)
        self.assertAlmostEqual(surface.Area, 996 * 1996, places=3)
        self.assertTrue(any(face.isInside(App.Vector(500, 1000, model.depth), 1e-6, True)
                            for face in surface.Faces))
        self.assertFalse(any(face.isInside(App.Vector(1, 1, model.depth), 1e-6, True)
                             for face in surface.Faces), 'do not fill the surrounding aluminium frame')
        for role in component_models.ROLES[:-1]:
            self.assertFalse(parts[role][1].isNull(), 'separately controlled 2D hardware must remain available')
            self.assertTrue(parts[role][1].Edges)

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

    def test_legacy_contour_filling_keeps_holes_islands_and_open_lines(self):
        def rectangle(x, y, width, height):
            return Part.makePolygon([App.Vector(px, py, 90) for px, py in (
                (x, y), (x + width, y), (x + width, y + height),
                (x, y + height), (x, y))])

        outer = rectangle(0, 0, 100, 100)
        hole = rectangle(20, 20, 20, 20)
        island = rectangle(200, 0, 20, 20)
        line = Part.makeLine(App.Vector(300, 10, 90), App.Vector(310, 10, 90))
        legacy = Part.Compound([outer, hole, island, line])
        surface = component_models.fill_plan_contours(legacy)
        self.assertEqual(len(surface.Faces), 2)
        self.assertAlmostEqual(surface.Area, 100 * 100 - 20 * 20 + 20 * 20)
        for point in (App.Vector(10, 10, 90), App.Vector(210, 10, 90)):
            self.assertTrue(any(face.isInside(point, 1e-6, True) for face in surface.Faces))
        for point in (App.Vector(30, 30, 90), App.Vector(150, 10, 90), App.Vector(305, 10, 90)):
            self.assertFalse(any(face.isInside(point, 1e-6, True) for face in surface.Faces))
        self.assertTrue(any(edge.isSame(line) for edge in surface.Edges),
                        'filling a closed plate outline must retain explicit open lines')
        self.assertFalse(surface.Solids)
        self.assertAlmostEqual(surface.BoundBox.ZMin, 90)
        self.assertAlmostEqual(surface.BoundBox.ZMax, 90)

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
