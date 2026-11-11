"""With FreeCAD's Python modules available, run: python -m unittest discover -s tests."""

import unittest

import FreeCAD as App

from freecad.buehnensnap.decks import CATALOG, Deck, deck_area, insert_deck, seed_placement, snap_deck


class AutosnapTest(unittest.TestCase):
    deck = CATALOG["BÜTEC Standard"][0]
    top = 150

    def new_document(self):
        document = App.newDocument("AutosnapTest")
        self.addCleanup(App.closeDocument, document.Name)
        return document

    def add_deck(self, document, x, y, quarter_turn=0):
        width, height = (2000, 1000) if quarter_turn else (1000, 2000)
        placement = seed_placement(
            self.deck, x + width / 2, y + height / 2, self.top, quarter_turn
        )
        return insert_deck(document, self.deck, placement)

    def assert_bounds(self, obj, x, y, width, height):
        bounds = obj.Shape.BoundBox
        actual = (bounds.XMin, bounds.YMin, bounds.XMax, bounds.YMax, bounds.ZMax)
        for result, expected in zip(actual, (x, y, x + width, y + height, self.top)):
            self.assertAlmostEqual(result, expected)

    def test_corner_positions_from_the_documentation(self):
        cases = (
            (1, (800, 1500), "Rechts", (1000, 1000, 2000, 1000)),
            (1, (800, 500), "Rechts", (1000, 0, 2000, 1000)),
            (1, (430, 200), "Unten", (0, -1000, 2000, 1000)),
            (0, (800, 1000), "Rechts", (1000, 0, 1000, 2000)),
            (0, (430, 200), "Unten", (0, -2000, 1000, 2000)),
        )
        for quarter_turn, pick, expected_side, expected_bounds in cases:
            with self.subTest(quarter_turn=quarter_turn, pick=pick):
                document = self.new_document()
                target = self.add_deck(document, 0, 0)
                new_deck, side = snap_deck(
                    document, target, self.deck, App.Vector(*pick, self.top), quarter_turn
                )
                self.assertEqual(side, expected_side)
                self.assert_bounds(new_deck, *expected_bounds)
                self.assertIsNotNone(deck_area(target))
                self.assertEqual(deck_area(new_deck), deck_area(target))

    def test_collision_tries_the_other_corner_of_the_same_edge(self):
        document = self.new_document()
        target = self.add_deck(document, 0, 0)
        self.add_deck(document, 1000, 0)
        self.add_deck(document, 1000, -2000)

        new_deck, side = snap_deck(
            document, target, self.deck, App.Vector(430, 200, self.top), 1
        )

        self.assertEqual(side, "Unten")
        self.assert_bounds(new_deck, -1000, -1000, 2000, 1000)

    def test_both_blocked_corners_leave_the_document_unchanged(self):
        document = self.new_document()
        target = self.add_deck(document, 0, 0)
        self.add_deck(document, 1000, -2000)
        self.add_deck(document, -1000, -2000)
        original_names = [obj.Name for obj in document.Objects]
        original_meta = dict(document.Meta)

        with self.assertRaises(ValueError):
            snap_deck(document, target, self.deck, App.Vector(430, 200, self.top), 1)

        self.assertEqual([obj.Name for obj in document.Objects], original_names)
        self.assertEqual(document.Meta, original_meta)
        self.assertIsNone(deck_area(target))

    def test_rotation_is_absolute_with_a_landscape_target(self):
        for quarter_turn, width, height in ((0, 1000, 2000), (1, 2000, 1000)):
            with self.subTest(quarter_turn=quarter_turn):
                document = self.new_document()
                target = self.add_deck(document, 100, 200, quarter_turn=1)
                self.assert_bounds(target, 100, 200, 2000, 1000)

                new_deck, side = snap_deck(
                    document, target, self.deck, App.Vector(2090, 400, self.top), quarter_turn
                )

                self.assertEqual(side, "Rechts")
                self.assert_bounds(new_deck, 2100, 200, width, height)

    def test_seed_orientation_uses_the_longer_dimension_for_custom_sizes(self):
        deck = Deck("custom", "Eigenes Maß", 750, 1750, 120)
        for quarter_turn, width, height in ((0, 750, 1750), (1, 1750, 750)):
            with self.subTest(quarter_turn=quarter_turn):
                document = self.new_document()
                placement = seed_placement(deck, 100, 200, self.top, quarter_turn)
                obj = insert_deck(document, deck, placement)
                self.assert_bounds(obj, 100 - width / 2, 200 - height / 2, width, height)
