"""Load editable, planar FreeCAD companions of the STEP models."""

from functools import lru_cache
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

import FreeCAD as App
import Part


def find_plan_symbol(model_path):
    """Use the single FCStd in the symbol folder, independent of its filename."""
    if not model_path.parent.is_dir():
        return None
    matches = [path for path in model_path.parent.iterdir()
               if path.is_file() and path.suffix.lower() == ".fcstd"]
    if len(matches) > 1:
        raise ValueError(f"Symbolordner {model_path.parent.name}: "
                         "Es darf nur eine FCStd-Datei für die 2D-Darstellung enthalten sein.")
    return matches[0] if matches else None


def visible_shape(obj):
    if not getattr(obj, "Visibility", True):
        return False
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None:
        if not getattr(parent, "Visibility", True):
            return False
        # A visible Body already supplies its final shape, including its Tip.
        if parent.isDerivedFrom("Part::Feature") and not parent.Shape.isNull():
            return False
        parent = parent.getParentGeoFeatureGroup()
    return True


def global_placement(obj):
    # FreeCAD 1.0's getGlobalPlacement can fail for ordinary document groups,
    # which have no Placement of their own. Only geometric containers transform.
    placement = obj.Placement
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None:
        if hasattr(parent, "Placement"):
            placement = parent.Placement * placement
        parent = parent.getParentGeoFeatureGroup()
    return placement


@lru_cache(maxsize=64)
def _read_plan_shape(path, modified_ns, size):
    """Cache by file revision. A private copy leaves open source files alone."""
    active = App.ActiveDocument
    previous = set(App.listDocuments())
    try:
        with TemporaryDirectory(prefix="eventcad-2d-") as temp:
            copied = Path(temp) / "Symbol.FCStd"
            copyfile(path, copied)
            document = App.openDocument(str(copied), hidden=True)
            document.recompute()
            shapes = []
            for obj in document.Objects:
                if (obj.isDerivedFrom("Part::Feature") and not obj.Shape.isNull()
                        and visible_shape(obj)):
                    shape = obj.Shape.copy()
                    shape.Placement = global_placement(obj)
                    shapes.append(shape)
            if not shapes:
                raise ValueError("Die Datei enthält keine sichtbare Skizze oder Part-Geometrie.")
            shape = Part.Compound(shapes)
            if not shape.isValid() or shape.Solids or shape.BoundBox.ZLength > 0.01:
                raise ValueError("Das 2D-Symbol muss flach und parallel zur XY-Ebene liegen.")
            return shape
    finally:
        # openDocument can leave a new document behind even when opening fails.
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        if active is not None and active.Name in App.listDocuments():
            App.setActiveDocument(active.Name)


def load_plan_shape(path, length, width):
    revision = path.stat()
    shape = _read_plan_shape(str(path), revision.st_mtime_ns, revision.st_size).copy()
    bounds = shape.BoundBox
    if abs(bounds.XLength - length) > 0.1 or abs(bounds.YLength - width) > 0.1:
        raise ValueError(f"Grundfläche muss in X × Y {length:g} × {width:g} mm messen. "
                         f"Gemessen: {bounds.XLength:g} × {bounds.YLength:g} mm.")
    shape.translate(App.Vector(-bounds.XMin, -bounds.YMin, -bounds.ZMin))
    # Bake the import placement into a compound before assigning the object placement.
    return Part.Compound([shape])
