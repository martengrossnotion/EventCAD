"""Load named 2D/3D geometry from a single editable FreeCAD symbol file."""

from functools import lru_cache
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

import FreeCAD as App
import Part


def find_plan_symbol(model_path):
    """Find the single native symbol file (also resolves paths in older plans)."""
    if not model_path.parent.is_dir():
        return None
    matches = [path for path in model_path.parent.iterdir()
               if path.is_file() and path.suffix.lower() == ".fcstd"]
    if len(matches) > 1:
        raise ValueError(f"Symbolordner {model_path.parent.name}: "
                         "Es darf nur eine FCStd-Symboldatei enthalten sein.")
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
    shape = load_variant_shape(path, "Symbol2D").copy()
    bounds = shape.BoundBox
    if abs(bounds.XLength - length) > 0.1 or abs(bounds.YLength - width) > 0.1:
        raise ValueError(f"Grundfläche muss in X × Y {length:g} × {width:g} mm messen. "
                         f"Gemessen: {bounds.XLength:g} × {bounds.YLength:g} mm.")
    shape.translate(App.Vector(-bounds.XMin, -bounds.YMin, -bounds.ZMin))
    # Bake the import placement into a compound before assigning the object placement.
    return Part.Compound([shape])


@lru_cache(maxsize=64)
def _read_variants(path, modified_ns, size):
    active = App.ActiveDocument
    previous = set(App.listDocuments())
    try:
        with TemporaryDirectory(prefix="eventcad-symbol-") as temp:
            copied = Path(temp) / "Symbol.FCStd"
            copyfile(path, copied)
            document = App.openDocument(str(copied), hidden=True)
            document.recompute()
            result = {}
            for name in ("Symbol3D", "Symbol2D"):
                root = document.getObject(name)
                if root is None:
                    matches = document.getObjectsByLabel(name)
                    if len(matches) > 1:
                        raise ValueError(f"Die Bezeichnung {name} muss eindeutig sein.")
                    root = matches[0] if matches else None
                if root is None:
                    continue
                if hasattr(root, "Shape") and not root.Shape.isNull():
                    shape = root.Shape.copy()
                    shape.Placement = global_placement(root)
                    result[name] = Part.Compound([shape])
                else:
                    raise ValueError(f"{name} muss ein Objekt mit fertiger Shape sein.")
            return result
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        if active is not None and active.Name in App.listDocuments():
            App.setActiveDocument(active.Name)


def load_variant_shape(path, variant):
    path = Path(path)
    revision = path.stat()
    variants = _read_variants(str(path), revision.st_mtime_ns, revision.st_size)
    if variant not in variants:
        # Old 2D-only files remain usable by legacy plans.
        if variant == "Symbol2D" and not variants:
            return _read_plan_shape(str(path), revision.st_mtime_ns, revision.st_size).copy()
        raise ValueError(f"FCStd-Symbol {path.name}: Objekt {variant} fehlt.")
    shape = variants[variant].copy()
    if not shape.isValid():
        raise ValueError(f"{variant} enthält ungültige Geometrie.")
    if variant == "Symbol3D" and not shape.Solids:
        raise ValueError("Symbol3D muss Volumenkörper enthalten.")
    if variant == "Symbol2D" and (shape.Solids or shape.BoundBox.ZLength > 0.01):
        raise ValueError("Symbol2D muss flach und parallel zur XY-Ebene liegen.")
    return shape

