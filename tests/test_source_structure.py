"""Explicit FCStd component trees and their shared, source-independent instances."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import FreeCAD as App
import Part

from freecad.buehnensnap import component_models, decks, plan_symbols, segments


GROUP_ROLES = (
    ('Corners', ('CornerTL', 'CornerTR', 'CornerBL', 'CornerBR')),
    ('Frame', ('PedestalFrame',)),
    ('Deck', ('PedestalDeck',)),
    ('Verbinder', ()),
    ('Steckfüße', ()),
    ('Geländer', ()),
)


def by_label(parent, label):
    return next(obj for obj in parent.Group if obj.Label == label)


def tree(root):
    return [(group.Label, [obj.Label for obj in group.Group])
            for group in root.Group if hasattr(group, 'Group')]


class SourceStructureTest(unittest.TestCase):
    def setUp(self):
        self.previous = set(App.listDocuments())
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'Structured.FCStd'
        self.document = App.newDocument('StructuredPlan')
        self.addCleanup(self.close_documents)
        self.addCleanup(self.temp.cleanup)

    def close_documents(self):
        for name in set(App.listDocuments()) - self.previous:
            App.closeDocument(name)

    def assert_bounds(self, actual, expected):
        for field in ('XMin', 'XMax', 'YMin', 'YMax', 'ZMin', 'ZMax'):
            self.assertAlmostEqual(getattr(actual, field), getattr(expected, field), places=6,
                                   msg=field)

    def write_structured(self, *, transformed=False, leave_open=False):
        """Six arbitrary solids: identities cannot be inferred from their geometry."""
        source = App.newDocument('StructuredSource')
        expected = {}
        for variant in ('Symbol3D', 'Symbol2D'):
            root = source.addObject('App::Part', variant)
            root.Label = '3D-Modell' if variant == 'Symbol3D' else '2D-Grundriss'
            if transformed:
                root.Placement = App.Placement(
                    App.Vector(100, 200, 40 if variant == 'Symbol3D' else 45),
                    App.Rotation(App.Vector(0, 0, 1), 90))
            elif variant == 'Symbol2D':
                root.Placement.Base.z = 5
            expected[variant] = {}
            for group_index, (label, roles) in enumerate(GROUP_ROLES):
                group = source.addObject('App::DocumentObjectGroup',
                                         label.replace('ü', 'ue').replace('ß', 'ss') + variant)
                segments.exact_label(group, label)
                root.addObject(group)
                group_placement = App.Placement()
                # Ordinary folders have no Placement. Add a nested geometric
                # container only in the transform fixture, to exercise all levels.
                if transformed:
                    source.removeObject(group.Name)
                    group = source.addObject('App::Part', 'Group' + str(group_index) + variant)
                    segments.exact_label(group, label)
                    root.addObject(group)
                    group_placement = App.Placement(
                        App.Vector(group_index * 7, -group_index * 3, 0),
                        App.Rotation(App.Vector(0, 0, 1), 90 if group_index == 1 else 0))
                    group.Placement = group_placement
                for role in roles:
                    index = component_models.ROLES.index(role)
                    name = role if variant == 'Symbol3D' else role + '2D'
                    obj = source.addObject('Part::Feature', name)
                    segments.exact_label(obj, role)
                    if variant == 'Symbol3D':
                        raw = Part.makeBox(10, 10, 5)
                    else:
                        raw = Part.Compound([
                            Part.makePlane(10, 10),
                            Part.makeLine(App.Vector(0, 0, 0), App.Vector(10, 10, 0)),
                        ])
                    obj.Shape = raw
                    leaf_placement = App.Placement(
                        App.Vector(20 * index + 2, index * 3, 0),
                        App.Rotation(App.Vector(0, 0, 1), 180 if transformed and index % 2 else 0))
                    obj.Placement = leaf_placement
                    group.addObject(obj)
                    placed = raw.copy()
                    placed.Placement = root.Placement * group_placement * leaf_placement
                    expected[variant][role] = placed
        source.recompute()
        source.saveAs(str(self.path))
        whole = Part.Compound(list(expected['Symbol3D'].values()))
        model = decks.Deck('structured', 'Structured', whole.BoundBox.XLength,
                           whole.BoundBox.YLength, whole.BoundBox.ZLength)
        if not leave_open:
            App.closeDocument(source.Name)
        App.setActiveDocument(self.document.Name)
        return model, expected, source if leave_open else None

    def test_every_bundled_file_exposes_the_same_tree_as_an_inserted_segment(self):
        expected_tree = [(label, list(roles)) for label, roles in GROUP_ROLES]
        paths = sorted(decks.MODELS_DIR.rglob('*.FCStd'))
        self.assertTrue(paths)
        for index, path in enumerate(paths):
            with self.subTest(path=path.relative_to(decks.MODELS_DIR)):
                before = hashlib.sha256(path.read_bytes()).digest()
                source = App.openDocument(str(path), hidden=True)
                try:
                    raw_volumes = {}
                    for variant in ('Symbol3D', 'Symbol2D'):
                        root = source.getObject(variant)
                        self.assertIsNotNone(root)
                        self.assertEqual(root.TypeId, 'App::Part')
                        self.assertEqual(tree(root), expected_tree)
                        raw_volumes[variant] = sum(obj.Shape.Volume
                                                  for label, _ in GROUP_ROLES
                                                  for obj in by_label(root, label).Group
                                                  if not obj.Shape.isNull())
                    model = decks.deck_for_model('Test', path.relative_to(decks.MODELS_DIR).as_posix())
                    specs = component_models.component_specs(model, path)
                    segment = decks.insert_deck(
                        self.document, model, decks.seed_placement(model, index * 10000, 0, 300, 1))
                    self.assertEqual(tree(segment), expected_tree)
                    self.assertAlmostEqual(sum(item[0].Volume for item in specs.values()
                                               if not item[0].isNull()),
                                           raw_volumes['Symbol3D'], places=4)
                    self.assertEqual(sum(len(item[0].Solids) for item in specs.values()
                                         if not item[0].isNull()),
                                     6 if 'Buetec_standard' in path.name else 1)
                finally:
                    App.closeDocument(source.Name)
                self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)

    def test_nested_placements_are_applied_once_and_variants_are_preserved(self):
        model, expected, _ = self.write_structured(transformed=True)
        specs = component_models.component_specs(model, self.path)
        whole = Part.Compound(list(expected['Symbol3D'].values()))
        bounds = whole.BoundBox
        shift = App.Vector(-bounds.XMin, -bounds.YMin, model.depth - bounds.ZMax)
        loaded = plan_symbols.load_variant_shape(self.path, 'Symbol3D')
        self.assertEqual(len(loaded.Solids), 6)
        self.assertAlmostEqual(loaded.Volume, whole.Volume)
        self.assert_bounds(loaded.BoundBox, whole.BoundBox)
        for role in component_models.ROLES:
            for variant, output_index in (('Symbol3D', 0), ('Symbol2D', 1)):
                original = expected[variant][role].copy()
                original.translate(shift)
                actual = specs[role][output_index]
                self.assert_bounds(actual.BoundBox, original.BoundBox)
                self.assertEqual(len(actual.Faces), len(original.Faces))
                self.assertEqual(len(actual.Edges), len(original.Edges))
                self.assertAlmostEqual(actual.Volume, original.Volume)
                self.assertAlmostEqual(actual.Area, original.Area)
            self.assertEqual(len(specs[role][1].Edges), 5,
                             'explicit 2D details must not be regenerated from 3D')

    def test_wrong_component_group_is_rejected_without_partial_plan_objects(self):
        model, _, source = self.write_structured(leave_open=True)
        frame = by_label(source.getObject('Symbol3D'), 'Frame')
        frame.addObject(source.getObject('CornerTL'))
        source.recompute()
        source.save()
        App.closeDocument(source.Name)
        before = [obj.Name for obj in self.document.Objects]
        with self.assertRaises(ValueError):
            component_models.component_specs(model, self.path)
        self.assertEqual([obj.Name for obj in self.document.Objects], before)

    def test_missing_2d_component_is_rejected_instead_of_projected(self):
        model, _, source = self.write_structured(leave_open=True)
        source.removeObject('CornerTL2D')
        source.recompute()
        source.save()
        App.closeDocument(source.Name)
        with self.assertRaisesRegex(ValueError, 'CornerTL|2D'):
            component_models.component_specs(model, self.path)

    def test_unsupported_accessory_is_not_silently_discarded(self):
        model, _, source = self.write_structured(leave_open=True)
        group = by_label(source.getObject('Symbol3D'), 'Steckfüße')
        extra = source.addObject('Part::Feature', 'UnrecognisedLeg')
        extra.Shape = Part.makeBox(2, 2, 20)
        group.addObject(extra)
        source.recompute()
        source.save()
        App.closeDocument(source.Name)
        with self.assertRaises(ValueError):
            component_models.component_specs(model, self.path)

    def test_one_feature_cannot_satisfy_two_component_roles(self):
        model, _, source = self.write_structured(leave_open=True)
        source.removeObject('CornerTR')
        # An internal name and a conflicting label must not let one solid
        # impersonate two separate corners and be counted twice on import.
        source.getObject('CornerTL').Label = 'CornerTR'
        source.recompute()
        source.save()
        App.closeDocument(source.Name)
        with self.assertRaises(ValueError):
            component_models.component_specs(model, self.path)

    def test_import_preserves_open_source_unsaved_edits_and_active_plan(self):
        model, _, source = self.write_structured(leave_open=True)
        original = source.getObject('CornerTL')
        original.Label = 'Unsaved source edit'
        original.Placement.Base.x += 123
        before = set(App.listDocuments())
        digest = hashlib.sha256(self.path.read_bytes()).digest()
        component_models.component_specs(model, self.path)
        self.assertEqual(set(App.listDocuments()), before)
        self.assertEqual(App.ActiveDocument, self.document)
        self.assertEqual(original.Label, 'Unsaved source edit')
        self.assertAlmostEqual(original.Placement.Base.x, 125)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(), digest)

    def test_structured_instances_reuse_templates_and_reopen_without_the_source(self):
        model, _, _ = self.write_structured()
        model = decks.Deck(model.catalog_id, model.label, *model.dimensions, self.path.name)
        with patch.object(decks, 'MODELS_DIR', self.root):
            first = decks.insert_deck(self.document, model,
                                      decks.seed_placement(model, 0, 0, 300, 1))
            second = decks.insert_deck(self.document, model,
                                       decks.seed_placement(model, 2000, 0, 300, 1))
        first_components = {obj.StageSnapRole: obj for obj in segments.components(first)}
        for component in segments.components(second):
            original = first_components[component.StageSnapRole]
            self.assertEqual(component.StageSnap3DTemplate, original.StageSnap3DTemplate)
            self.assertEqual(component.StageSnapPlanTemplate, original.StageSnapPlanTemplate)
        volume = segments.segment_shape(first).Volume
        name = first.Name
        for mode in (True, False, True):
            segments.set_segment_mode(first, mode)
            self.document.recompute()
        saved = self.root / 'SavedPlan.FCStd'
        self.document.saveAs(str(saved))
        App.closeDocument(self.document.Name)
        self.path.unlink()
        self.document = App.openDocument(str(saved))
        first = self.document.getObject(name)
        for mode in (False, True, False):
            segments.set_segment_mode(first, mode)
            self.document.recompute()
            shape = segments.segment_shape(first)
            if mode:
                self.assertFalse(shape.Solids)
                self.assertEqual(len(shape.Edges), 6 * 5)
            else:
                self.assertEqual(len(shape.Solids), 6)
                self.assertAlmostEqual(shape.Volume, volume)
            self.assertAlmostEqual(shape.BoundBox.ZMax, 300)

    def test_legacy_six_solid_monolith_is_retained_whole_without_role_guessing(self):
        source = App.newDocument('LegacyMonolith')
        shape = Part.Compound([
            Part.makeBox(100, 100, 2, App.Vector(0, 0, 8)),
            Part.makeBox(100, 100, 8).cut(
                Part.makeBox(80, 80, 8, App.Vector(10, 10, 0))),
            *[Part.makeBox(5, 5, 8, App.Vector(x, y, 0))
              for x, y in ((0, 0), (95, 0), (0, 95), (95, 95))],
        ])
        source.addObject('Part::Feature', 'Symbol3D').Shape = shape
        source.addObject('Part::Feature', 'Symbol2D').Shape = Part.makePlane(100, 100)
        source.recompute()
        source.saveAs(str(self.path))
        App.closeDocument(source.Name)
        model = decks.Deck('legacy', 'Legacy monolith', 100, 100, 10)
        specs = component_models.component_specs(model, self.path)
        self.assertEqual(len(specs['PedestalDeck'][0].Solids), 6)
        self.assertAlmostEqual(specs['PedestalDeck'][0].Volume, shape.Volume)
        for role in component_models.ROLES[:-1]:
            self.assertTrue(specs[role][0].isNull())
            self.assertTrue(specs[role][1].isNull())


if __name__ == '__main__':
    unittest.main()
