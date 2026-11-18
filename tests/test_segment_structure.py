"""Integration requirements for grouped, independently visible podest segments."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import FreeCAD as App

from freecad.buehnensnap import decks, segments
from freecad.buehnensnap.plan_symbols import global_placement


def by_label(parent, label):
    return next(obj for obj in parent.Group if obj.Label == label)


def components(segment):
    # App::Part includes nested geometric children in Group as well. The tree
    # claims those through their document groups, so inspect that hierarchy.
    return [obj for group in segment.Group if hasattr(group, "Group") for obj in group.Group
            if getattr(obj, "StageSnapOwner", None) == segment and obj.TypeId == "App::Link"]


class SegmentStructureTest(unittest.TestCase):
    def setUp(self):
        self.previous = set(App.listDocuments())
        self.document = App.newDocument("SegmentStructureTest")
        self.deck = decks.Deck("custom", "Test deck", 800, 500, 90)

    def tearDown(self):
        for name in set(App.listDocuments()) - self.previous:
            App.closeDocument(name)

    def insert(self, x=0, *, plan_view=False, target=None):
        placement = decks.seed_placement(self.deck, x, 0, 275, 1)
        return decks.insert_deck(self.document, self.deck, placement,
                                 plan_view=plan_view, target=target)

    def assert_placement(self, actual, expected):
        self.assertLess((actual.Base - expected.Base).Length, 1e-7)
        for axis in (App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)):
            self.assertLess((actual.Rotation.multVec(axis)
                             - expected.Rotation.multVec(axis)).Length, 1e-7)

    def test_exact_tree_and_editable_segment_placement(self):
        segment = self.insert()
        area = segments.segment_area(segment)
        self.assertEqual(area.Label, "Podestfläche 1")
        self.assertEqual([obj.Label for obj in area.Group], ["Views", "Podestsegment 001"])
        views = by_label(area, "Views")
        self.assertEqual([obj.Label for obj in views.Group],
                         ["ViewDecks", "ViewCorners", "ViewFrames"])
        self.assertTrue(all(obj.TypeId == "App::FeaturePython" for obj in views.Group))
        self.assertTrue(all(obj.Enabled for obj in views.Group))
        self.assertEqual(segment.TypeId, "App::Part")
        self.assertEqual([obj.Label for obj in segment.Group if hasattr(obj, "Group")],
                         ["Corners", "Frame", "Deck", "Verbinder", "Steckfüße", "Geländer"])
        self.assertEqual([obj.Label for obj in by_label(segment, "Corners").Group],
                         ["CornerTL", "CornerTR", "CornerBL", "CornerBR"])
        self.assertEqual([obj.Label for obj in by_label(segment, "Frame").Group], ["PedestalFrame"])
        self.assertEqual([obj.Label for obj in by_label(segment, "Deck").Group], ["PedestalDeck"])
        for label, category in (("Deck", "Decks"), ("Frame", "Frames"), ("Corners", "Corners")):
            group = by_label(segment, label)
            self.assertTrue(group.hasExtension("App::GeoFeatureGroupExtension"))
            self.assertEqual(by_label(views, "View" + category).Members, [group])
        for label in ("Verbinder", "Steckfüße", "Geländer"):
            group = by_label(segment, label)
            self.assertTrue(group.hasExtension("App::GeoFeatureGroupExtension"))
            self.assertEqual(group.Group, [])
        self.assertNotIn("ReadOnly", segment.getEditorMode("Placement"))
        for component in components(segment):
            self.assertEqual(component.TypeId, "App::Link")
            self.assertIn("ReadOnly", component.getEditorMode("Placement"))
            self.assertEqual(component.StageSnapOwner, segment)
            self.assertTrue(component.StageSnapRole)
            self.assertTrue(component.StageSnapUserVisible)
            self.assertIsNotNone(component.StageSnap3DTemplate)
            self.assertIsNotNone(component.StageSnapPlanTemplate)

    def test_repeated_segments_share_embedded_component_templates(self):
        preferences = App.ParamGet("User parameter:BaseApp/Preferences/Document")
        duplicate_labels_before = preferences.GetBool("AllowDuplicateLabels", False)
        first = self.insert()
        second = self.insert(1000, target=first)
        self.assertEqual(preferences.GetBool("AllowDuplicateLabels", False), duplicate_labels_before)
        self.assertEqual(segments.segment_area(first), segments.segment_area(second))
        first_components = {obj.Label: obj for obj in components(first)}
        for obj in components(second):
            original = first_components[obj.Label]
            self.assertEqual(obj.StageSnap3DTemplate, original.StageSnap3DTemplate)
            self.assertEqual(obj.StageSnapPlanTemplate, original.StageSnapPlanTemplate)
            self.assertNotEqual(obj, original)
            self.assertEqual(obj.LinkedObject.Document, self.document)
        views = by_label(segments.segment_area(first), "Views")
        for label, category in (("Deck", "Decks"), ("Frame", "Frames"), ("Corners", "Corners")):
            self.assertEqual(by_label(views, "View" + category).Members,
                             [by_label(first, label), by_label(second, label)])
        self.assertFalse(any(obj.TypeId == "App::LinkPython" for obj in self.document.Objects))

    def test_ordinary_geometry_belongs_to_its_container_without_member_metadata(self):
        """Additional editable shapes must not be registered as link components."""
        segment = self.insert()
        deck_group = by_label(segment, "Deck")
        control = by_label(by_label(segments.segment_area(segment), "Views"), "ViewDecks")
        original_components = list(components(segment))
        added = self.document.addObject("Part::Box", "EditedDeck")
        deck_group.addObject(added)
        self.document.recompute()
        self.assertEqual(control.Members, [deck_group])
        self.assertFalse(hasattr(added, "StageSnapOwner"))
        self.assertEqual(components(segment), original_components)
        self.assert_placement(global_placement(added), global_placement(segment) * added.Placement)
        before = global_placement(added)
        for plan_view in (True, False):
            segments.set_segment_mode(segment, plan_view)
            self.document.recompute()
            self.assertIn(added, deck_group.Group)
            self.assert_placement(global_placement(added), before)

    def test_legacy_groups_migrate_without_moving_or_recreating_geometry(self):
        """A saved pre-container segment keeps its geometry and world placement."""
        import Part
        document = self.document
        area = segments.create_area(document)
        parent = document.addObject("App::Part", "LegacyParent")
        parent.Placement = App.Placement(App.Vector(800, -200, 60),
                                         App.Rotation(App.Vector(0, 0, 1), 90))
        parent.addObject(area)
        segment = document.addObject("App::Part", "LegacySegment")
        segment.addProperty("App::PropertyBool", "StageSnapSegment", "Podest")
        segment.StageSnapSegment = True
        segment.addProperty("App::PropertyBool", "StageSnapPlanView", "Podest")
        segment.addProperty("App::PropertyLinkHidden", "StageSnapArea", "Podest")
        segment.StageSnapArea = area
        area.addObject(segment)
        segment.Placement = App.Placement(App.Vector(300, 700, 200),
                                          App.Rotation(App.Vector(0, 0, 1), 180))
        template = document.addObject("Part::Feature", "LegacyTemplate")
        template.Shape = Part.makeBox(800, 500, 90)
        references = {}
        for label, category in (("Corners", "Corners"), ("Frame", "Frames"), ("Deck", "Decks")):
            group = document.addObject("App::DocumentObjectGroup", label)
            segments.exact_label(group, label)
            segment.addObject(group)
            links = []
            for role in segments.CATEGORIES[category]:
                link = document.addObject("App::Link", role)
                link.setLink(template)
                link.LinkTransform = False
                link.Placement = App.Placement(App.Vector(12, 24, 36), App.Rotation())
                group.addObject(link)
                link.addProperty("App::PropertyLinkHidden", "StageSnapOwner", "Podest")
                link.StageSnapOwner = segment
                link.addProperty("App::PropertyString", "StageSnapRole", "Podest")
                link.StageSnapRole = role
                link.addProperty("App::PropertyBool", "StageSnapUserVisible", "Podest")
                link.StageSnapUserVisible = role != "CornerTL"
                for prop in ("StageSnap3DTemplate", "StageSnapPlanTemplate"):
                    link.addProperty("App::PropertyLinkGlobal", prop, "Podest")
                    setattr(link, prop, template)
                links.append(link)
            by_label(by_label(area, "Views"), "View" + category).Members = links
            references[label] = links
        extra = document.addObject("Part::Box", "LegacyEditedDeck")
        by_label(segment, "Deck").addObject(extra)
        with segments.updating():
            document.recompute()
        retained = [template, extra, *[obj for links in references.values() for obj in links]]
        placements = {obj.Name: global_placement(obj).copy() for obj in retained}
        names = [obj.Name for obj in retained]

        segments.migrate_document(document)
        document.recompute()
        self.assertEqual([obj.Label for obj in segment.Group if hasattr(obj, "Group")],
                         ["Corners", "Frame", "Deck", "Verbinder", "Steckfüße", "Geländer"])
        for obj, name in zip(retained, names):
            self.assertEqual(document.getObject(name), obj)
            self.assert_placement(global_placement(obj), placements[name])
        for label, category in (("Deck", "Decks"), ("Frame", "Frames"), ("Corners", "Corners")):
            group = by_label(segment, label)
            self.assertTrue(group.hasExtension("App::GeoFeatureGroupExtension"))
            self.assertEqual(by_label(by_label(area, "Views"), "View" + category).Members, [group])
        self.assertIn(extra, by_label(segment, "Deck").Group)
        for label in ("Verbinder", "Steckfüße", "Geländer"):
            group = by_label(segment, label)
            self.assertTrue(group.hasExtension("App::GeoFeatureGroupExtension"))
            self.assertEqual(group.Group, [])
        self.assertFalse(references["Corners"][0].StageSnapUserVisible)
        all_names = [obj.Name for obj in document.Objects]
        segments.migrate_document(document)
        self.assertEqual([obj.Name for obj in document.Objects], all_names,
                         "migration must be idempotent")

    def test_renamed_legacy_folder_keeps_properties_expressions_and_incoming_links(self):
        document = self.document
        area = segments.create_area(document)
        segment = document.addObject("App::Part", "LegacyCustomSegment")
        segment.addProperty("App::PropertyBool", "StageSnapSegment", "Podest")
        segment.StageSnapSegment = True
        segment.addProperty("App::PropertyLinkHidden", "StageSnapArea", "Podest")
        segment.StageSnapArea = area
        area.addObject(segment)
        group = document.addObject("App::DocumentObjectGroup", "LegacyCustomDeck")
        segments.exact_label(group, "Mein zugeschnittenes Deck")
        group.Label2 = "Werkstattvariante"
        segment.addObject(group)
        template = document.addObject("Part::Box", "CustomDeckTemplate")
        source = document.addObject("App::Link", "CustomDeckLink")
        source.setLink(template)
        source.LinkTransform = False
        source.addProperty("App::PropertyLinkHidden", "StageSnapOwner", "Podest")
        source.StageSnapOwner = segment
        source.addProperty("App::PropertyString", "StageSnapRole", "Podest")
        source.StageSnapRole = "PedestalDeck"
        group.addObject(source)
        by_label(by_label(area, "Views"), "ViewDecks").Members = [source]
        group.addProperty("App::PropertyLength", "UserLength", "Benutzerdaten")
        group.UserLength = 12.5
        group.addProperty("App::PropertyFloat", "UserFactor", "Benutzerdaten")
        group.UserFactor = 3.0
        group.addProperty("App::PropertyFloat", "ComputedFactor", "Benutzerdaten")
        group.setExpression("ComputedFactor", "UserFactor * 2")
        holder = document.addObject("App::FeaturePython", "ExternalFolderReference")
        holder.addProperty("App::PropertyLink", "SelectedFolder", "Benutzerdaten")
        holder.SelectedFolder = group
        holder.addProperty("App::PropertyFloat", "ExternalFactor", "Benutzerdaten")
        holder.setExpression("ExternalFactor", "LegacyCustomDeck.ComputedFactor + 1")
        with segments.updating():
            document.recompute()
        original_name = group.Name
        self.assertAlmostEqual(group.ComputedFactor, 6.0)
        self.assertAlmostEqual(holder.ExternalFactor, 7.0)

        segments.migrate_document(document)
        document.recompute()
        replacement = document.getObject(original_name)
        self.assertTrue(replacement.hasExtension("App::GeoFeatureGroupExtension"))
        self.assertEqual(replacement.Label, "Mein zugeschnittenes Deck")
        self.assertEqual(replacement.Label2, "Werkstattvariante")
        self.assertAlmostEqual(replacement.UserLength.Value, 12.5)
        self.assertAlmostEqual(replacement.UserFactor, 3.0)
        self.assertAlmostEqual(replacement.ComputedFactor, 6.0)
        self.assertTrue(any(path == "ComputedFactor" for path, _ in replacement.ExpressionEngine))
        self.assertEqual(holder.SelectedFolder, replacement)
        self.assertAlmostEqual(holder.ExternalFactor, 7.0)
        self.assertIn(source, replacement.Group)
        self.assertEqual(by_label(by_label(area, "Views"), "ViewDecks").Members, [replacement])
        replacement.UserFactor = 5.0
        document.recompute()
        self.assertAlmostEqual(replacement.ComputedFactor, 10.0)
        self.assertAlmostEqual(holder.ExternalFactor, 11.0)

    def test_component_picks_resolve_to_the_single_segment(self):
        segment = self.insert()
        self.assertTrue(segments.is_segment(segment))
        self.assertTrue(decks.is_deck(segment))
        for obj in [segment, *components(segment)]:
            self.assertEqual(segments.segment_from_pick(obj), segment)
            self.assertEqual(decks.deck_from_pick(obj), segment)
        self.assertIsNone(decks.deck_from_pick(None))

    def test_parent_transform_and_2d_edit_survive_mode_changes(self):
        segment = self.insert(plan_view=True)
        parent = self.document.addObject("App::Part", "MovedParent")
        parent.Placement = App.Placement(App.Vector(150, -320, 60),
                                         App.Rotation(App.Vector(0, 0, 1), 90))
        parent.addObject(segments.segment_area(segment))
        segment.Placement = App.Placement(App.Vector(740, 290, 220),
                                          App.Rotation(App.Vector(0, 0, 1), 180))
        expected = parent.Placement * segment.Placement
        local = {obj.Name: obj.Placement.copy() for obj in components(segment)}
        names = [obj.Name for obj in self.document.Objects]
        for plan_view in (False, True, False):
            segments.set_segment_mode(segment, plan_view)
            self.document.recompute()
            self.assertEqual([obj.Name for obj in self.document.Objects], names)
            self.assert_placement(global_placement(segment), expected)
            for obj in components(segment):
                self.assert_placement(obj.Placement, local[obj.Name])
                self.assert_placement(global_placement(obj), expected * local[obj.Name])
                self.assertEqual(obj.LinkedObject, obj.StageSnapPlanTemplate if plan_view
                                 else obj.StageSnap3DTemplate)

    def test_area_filters_and_user_hiding_survive_reopen(self):
        first = self.insert()
        second = self.insert(1500)
        first_area, second_area = (segments.segment_area(obj) for obj in (first, second))
        self.assertNotEqual(first_area, second_area)
        filter_first = by_label(by_label(first_area, "Views"), "ViewDecks")
        filter_second = by_label(by_label(second_area, "Views"), "ViewDecks")
        hidden = by_label(first, "Deck").Group[0]
        hidden.StageSnapUserVisible = False
        filter_first.Enabled = False
        self.document.recompute()
        self.assertTrue(filter_second.Enabled)
        filter_first.Enabled = True
        self.document.recompute()
        self.assertFalse(hidden.StageSnapUserVisible)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "Segments.FCStd"
            names = first.Name, second.Name, hidden.Name, filter_first.Name, filter_second.Name
            self.document.saveAs(str(path))
            App.closeDocument(self.document.Name)
            self.document = App.openDocument(str(path))
            first, second, hidden, filter_first, filter_second = [
                self.document.getObject(name) for name in names]
            self.document.recompute()
            self.assertFalse(hidden.StageSnapUserVisible)
            self.assertTrue(filter_first.Enabled)
            self.assertTrue(filter_second.Enabled)
            self.assertEqual(hidden.StageSnapOwner, first)
            filter_first.Enabled = False
            self.document.recompute()
            self.assertTrue(filter_second.Enabled)
            segments.set_segment_mode(first, True)
            segments.set_segment_mode(first, False)
            self.assertFalse(hidden.StageSnapUserVisible)

    def test_collision_and_snap_use_segment_envelope(self):
        first = self.insert(plan_view=True)
        with self.assertRaises(decks.DeckOverlapError):
            self.insert()
        pick = global_placement(first).multVec(App.Vector(790, 400, 90))
        second, side = decks.snap_deck(self.document, first, self.deck, pick, 1, plan_view=True)
        self.assertTrue(segments.is_segment(second))
        self.assertEqual(side, "Rechts")
        self.assertEqual(segments.segment_area(first), segments.segment_area(second))
        before = global_placement(second)
        segments.set_segment_mode(second, False)
        self.document.recompute()
        self.assert_placement(global_placement(second), before)
        self.assertAlmostEqual((global_placement(second).Base
                                - global_placement(first).Base).x, self.deck.length)


if __name__ == "__main__":
    unittest.main()
