"""Maintainer utility: convert old flat symbols to explicit component trees.

Run with FreeCAD's Python modules and GUI available (offscreen is supported).
The geometric classification below is deliberately a one-time migration step;
normal symbol loading must only read the components stored in the FCStd file.
Already converted files are validated and left untouched.
"""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import FreeCAD as App
import FreeCADGui as Gui
import Part

import freecad

ROOT = Path(__file__).resolve().parents[1]
freecad.__path__ = [str(ROOT / "freecad")]
for module_name in list(sys.modules):
    if module_name == "freecad.buehnensnap" or module_name.startswith("freecad.buehnensnap."):
        del sys.modules[module_name]
if hasattr(freecad, "buehnensnap"):
    del freecad.buehnensnap

from freecad.buehnensnap.component_models import (
    _face_materials, _materials, _project_contours, deck_surface, fill_plan_contours,
)
from freecad.buehnensnap.plan_symbols import global_placement

ROLES = ("CornerTL", "CornerTR", "CornerBL", "CornerBR", "PedestalFrame", "PedestalDeck")
GROUPS = (("Corners", "Corners", ROLES[:4]),
          ("Frame", "Frame", ("PedestalFrame",)),
          ("Deck", "Deck", ("PedestalDeck",)),
          ("Verbinder", "Verbinder", ()),
          ("Steckfuesse", "Steckfüße", ()),
          ("Gelaender", "Geländer", ()))
MATERIAL_FIELDS = ("AmbientColor", "DiffuseColor", "SpecularColor", "EmissiveColor",
                   "Shininess", "Transparency")


@contextmanager
def duplicate_labels():
    preferences = App.ParamGet("User parameter:BaseApp/Preferences/Document")
    previous = preferences.GetBool("DuplicateLabels", False)
    preferences.SetBool("DuplicateLabels", True)
    try:
        yield
    finally:
        preferences.SetBool("DuplicateLabels", previous)


def split_legacy_shape(shape):
    """Recognise only the supplied six-solid assembly; never invent solids."""
    result = {role: Part.Shape() for role in ROLES}
    solids, bounds = shape.Solids, shape.BoundBox
    plates = [solid for solid in solids
              if solid.BoundBox.XLength > bounds.XLength * .8
              and solid.BoundBox.YLength > bounds.YLength * .8
              and solid.BoundBox.ZLength < bounds.ZLength * .5]
    if len(solids) != 6 or len(plates) != 1:
        result["PedestalDeck"] = shape
        return result
    plate = plates[0]
    remaining = [solid for solid in solids if not solid.isSame(plate)]
    frame = max(remaining, key=lambda item: item.BoundBox.XLength * item.BoundBox.YLength)
    if frame.BoundBox.XLength < bounds.XLength * .8 or frame.BoundBox.YLength < bounds.YLength * .8:
        result["PedestalDeck"] = shape
        return result
    result.update(PedestalDeck=plate, PedestalFrame=frame)
    for corner in remaining:
        if corner.isSame(frame):
            continue
        role = "Corner" + ("T" if corner.BoundBox.Center.y > bounds.Center.y else "B")
        role += "L" if corner.BoundBox.Center.x < bounds.Center.x else "R"
        if not result[role].isNull():
            return {name: shape if name == "PedestalDeck" else Part.Shape() for name in ROLES}
        result[role] = corner
    return result


def material_values(materials):
    def rounded(value):
        if isinstance(value, (float, int)):
            return round(value, 6)
        return tuple(round(component, 6) for component in value)
    return [tuple(rounded(getattr(material, field)) for field in MATERIAL_FIELDS)
            for material in materials]


def shape_values(shape):
    if shape.isNull():
        return (0, 0, 0., 0., ())
    bounds = shape.BoundBox
    return (len(shape.Solids), len(shape.Faces), round(shape.Volume, 5), round(shape.Area, 5),
            tuple(round(getattr(bounds, name), 6) for name in
                  ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax")))


def extract_legacy(document):
    whole_obj, plan_obj = (document.getObject(name) for name in ("Symbol3D", "Symbol2D"))
    whole, plan = whole_obj.Shape.copy(), plan_obj.Shape.copy()
    whole.Placement = global_placement(whole_obj)
    plan.Placement = global_placement(plan_obj)
    source_materials = tuple(whole_obj.ViewObject.ShapeAppearance)
    plan_materials = tuple(plan_obj.ViewObject.ShapeAppearance)
    parts = split_legacy_shape(whole)
    split = not parts["PedestalFrame"].isNull()
    # Keep both variants at their own original location. Only their component
    # tree changes; normalization into the placed segment happens in the loader.
    top = whole.BoundBox.ZMax
    plan_shift = App.Vector(plan.BoundBox.XMin - whole.BoundBox.XMin,
                            plan.BoundBox.YMin - whole.BoundBox.YMin,
                            plan.BoundBox.ZMin - top)
    result = {}
    for role, raw in parts.items():
        existing = _face_materials(raw, whole, source_materials)
        materials3d = _materials(raw, role, existing, preserve_mixed=not split)
        if not split and role == "PedestalDeck":
            shape2d, existing2d = plan.copy(), plan_materials
        elif role == "PedestalDeck":
            shape2d = deck_surface(raw, top)
            if shape2d.isNull():
                shape2d = _project_contours(raw, top)
            top_faces = [face for face in raw.Faces
                         if face.BoundBox.ZLength < 1e-7
                         and abs(face.BoundBox.ZMax - top) < 1e-7
                         and face.normalAt(0, 0).z > 1 - 1e-7]
            existing2d = _face_materials(Part.Compound(top_faces), raw, materials3d) if top_faces else []
            if not shape2d.isNull():
                shape2d.translate(plan_shift)
        else:
            shape2d, existing2d = _project_contours(raw, top), []
            if not shape2d.isNull():
                shape2d.translate(plan_shift)
        if role == "PedestalDeck":
            shape2d = fill_plan_contours(shape2d)
        result[role] = (raw.copy(), shape2d, materials3d,
                        _materials(shape2d, role, existing2d))
    return result, whole


def validate_tree(document):
    snapshots = {}
    for variant in ("Symbol3D", "Symbol2D"):
        root = document.getObject(variant)
        assert root is not None and root.TypeId == "App::Part", variant
        groups = [obj for obj in root.Group if obj.TypeId == "App::DocumentObjectGroup"]
        assert [obj.Label for obj in groups] == [item[1] for item in GROUPS]
        snapshots[variant] = {}
        for group, (_, label, roles) in zip(groups, GROUPS):
            assert [obj.Label for obj in group.Group] == list(roles), (variant, label)
            for obj in group.Group:
                assert obj.TypeId == "Part::Feature"
                assert obj.ViewObject.ShowInTree
                materials = obj.ViewObject.ShapeAppearance if obj.Shape.Faces else ()
                snapshots[variant][obj.Label] = (shape_values(obj.Shape), material_values(materials))
    return snapshots


def convert(path):
    document = App.openDocument(str(path), hidden=True)
    try:
        if document.getObject("Symbol3D").TypeId == "App::Part":
            validate_tree(document)
            print("Already structured:", path.relative_to(ROOT), flush=True)
            return False
        assert {obj.Name for obj in document.Objects} == {"Symbol3D", "Symbol2D"}, \
            "This utility only converts the old two-object resource format."
        specs, original = extract_legacy(document)
        expected = {variant: {role: (shape_values(values[index]), material_values(values[index + 2]))
                              for role, values in specs.items()}
                    for variant, index in (("Symbol3D", 0), ("Symbol2D", 1))}
        assert sum(len(values[0].Solids) for values in specs.values()) == len(original.Solids)
        assert abs(sum(values[0].Volume for values in specs.values()
                       if not values[0].isNull()) - original.Volume) < 1e-5
        document.removeObject("Symbol3D")
        document.removeObject("Symbol2D")
        with duplicate_labels():
            for variant, index, label in (("Symbol3D", 0, "3D-Modell"),
                                          ("Symbol2D", 1, "2D-Grundriss")):
                root = document.addObject("App::Part", variant)
                root.Label = label
                root.addProperty("App::PropertyInteger", "EventCADSourceStructureVersion", "EventCAD")
                root.EventCADSourceStructureVersion = 1
                root.Origin.ViewObject.ShowInTree = False
                for name, group_label, roles in GROUPS:
                    suffix = "2D" if index else ""
                    group = document.addObject("App::DocumentObjectGroup", name + suffix)
                    group.Label = group_label
                    root.addObject(group)
                    for role in roles:
                        obj = document.addObject("Part::Feature", role + suffix)
                        obj.Label = role
                        obj.Shape = specs[role][index]
                        group.addObject(obj)
                        materials = specs[role][index + 2]
                        if materials:
                            obj.ViewObject.ShapeAppearance = materials
                        obj.ViewObject.LineColor = (.23, .19, .14)
                        obj.Visibility = True
                    group.Visibility = True
                root.Visibility = index == 0
        document.recompute()
        assert validate_tree(document) == expected, "Conversion changed component geometry/materials."
        document.save()
        App.closeDocument(document.Name)
        document = App.openDocument(str(path), hidden=True)
        assert validate_tree(document) == expected, "Save/reopen changed component geometry/materials."
        assert document.getObject("Symbol3D").Visibility
        assert not document.getObject("Symbol2D").Visibility
        print("Converted:", path.relative_to(ROOT), "solids:", len(original.Solids),
              "volume:", round(original.Volume, 5), flush=True)
        return True
    finally:
        if document.Name in App.listDocuments():
            App.closeDocument(document.Name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    arguments = parser.parse_args()
    paths = arguments.paths or sorted((ROOT / "freecad/buehnensnap/resources/models").rglob("*.FCStd"))
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    try:
        converted = sum(convert(path.resolve()) for path in paths)
        print(f"Validated {len(paths)} symbols; converted {converted}.", flush=True)
    finally:
        Gui.getMainWindow().close()


if __name__ == "__main__":
    main()
