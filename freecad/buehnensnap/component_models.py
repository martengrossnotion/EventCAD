"""Read reusable stage components without inventing missing solid geometry."""

from functools import lru_cache
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

import FreeCAD as App
import Part

from .appearance import ALUMINIUM_COLOR, ALUMINIUM_SPECULAR, WOOD_COLOR
from .plan_symbols import global_placement, load_variant_appearance, load_variant_shape
from .symbol_structure import ROLES, variant_components

_MATERIAL_FIELDS = ("AmbientColor", "DiffuseColor", "SpecularColor", "EmissiveColor",
                    "Shininess", "Transparency")


def _named_object(document, name):
    obj = document.getObject(name)
    if obj is not None:
        return obj
    matches = document.getObjectsByLabel(name)
    if len(matches) > 1:
        raise ValueError(f"Die Komponentenbezeichnung {name} muss eindeutig sein.")
    return matches[0] if matches else None


@lru_cache(maxsize=64)
def _read_named_components(path, modified_ns, size, gui_up):
    """Copy out values from a private file, preserving any open user document."""
    active = App.ActiveDocument
    previous = set(App.listDocuments())
    try:
        with TemporaryDirectory(prefix="eventcad-components-") as temp:
            copied = Path(temp) / "Components.FCStd"
            copyfile(path, copied)
            document = App.openDocument(str(copied), hidden=True)
            document.recompute()
            result = {}
            roots = [_named_object(document, variant) for variant in ('Symbol3D', 'Symbol2D')]
            trees = [variant_components(root) if root is not None else None for root in roots]
            structured = any(tree is not None for tree in trees)
            if structured:
                if any(tree is None for tree in trees):
                    raise ValueError('Symbol3D und Symbol2D müssen dieselbe Komponentenstruktur enthalten.')
                for variant, tree in zip(('Symbol3D', 'Symbol2D'), trees):
                    for role, obj in tree.items():
                        shape = obj.Shape.copy()
                        if not shape.isNull():
                            shape.Placement = global_placement(obj)
                            shape = Part.Compound([shape])
                        materials = tuple(obj.ViewObject.ShapeAppearance) if gui_up else ()
                        key = role + ('2D' if variant == 'Symbol2D' else '')
                        result[key] = (shape, materials)
                return result, True
            for name in (*ROLES, *(role + "2D" for role in ROLES)):
                obj = _named_object(document, name)
                if obj is None:
                    continue
                if not hasattr(obj, "Shape") or obj.Shape.isNull():
                    raise ValueError(f"Komponente {name} muss eine fertige Shape enthalten.")
                shape = obj.Shape.copy()
                shape.Placement = global_placement(obj)
                materials = tuple(obj.ViewObject.ShapeAppearance) if gui_up else ()
                result[name] = (Part.Compound([shape]), materials)
            return result, False
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        if active is not None and active.Name in App.listDocuments():
            App.setActiveDocument(active.Name)


def _face_materials(component, source, source_materials):
    """Extract source face materials before moving the component's location."""
    if not source_materials or component.isNull():
        return []
    if len(source_materials) == 1:
        return [source_materials[0]] * len(component.Faces)
    result = []
    source_faces = source.Faces
    for face in component.Faces:
        index = next((i for i, original in enumerate(source_faces) if face.isSame(original)), None)
        result.append(source_materials[index] if index is not None and index < len(source_materials)
                      else None)
    return result


def _materials(shape, role, existing, preserve_mixed=False):
    if not App.GuiUp or shape.isNull():
        return []
    wood = role == "PedestalDeck"
    result = []
    for index in range(len(shape.Faces)):
        source = existing[0] if len(existing) == 1 else existing[index] if index < len(existing) else None
        material = App.Material()
        if source is not None:
            for field in _MATERIAL_FIELDS:
                setattr(material, field, getattr(source, field))
        else:
            material.DiffuseColor = WOOD_COLOR if wood else ALUMINIUM_COLOR
            material.Shininess = 0.9
            material.Transparency = 0.0
        if preserve_mixed and source is not None:
            # The entire simplified solid may contain both wood and aluminium
            # face appearances. Its container name must not flatten that data.
            pass
        elif wood:
            material.SpecularColor = (0.0, 0.0, 0.0)
        elif source is None or max(source.SpecularColor[:3]) == 0.0:
            material.SpecularColor = ALUMINIUM_SPECULAR
        result.append(material)
    return result


def _project_contours(shape, top):
    if shape.isNull():
        return Part.Shape()
    import TechDraw
    projected = TechDraw.project(shape, App.Vector(0, 0, 1))
    # Visible sharp/smooth contours only; hidden underside edges are unnecessary.
    contours = [part for part in projected[:2] if not part.isNull() and part.Edges]
    if not contours:
        return Part.Shape()
    result = Part.Compound(contours)
    result.translate(App.Vector(0, 0, top - result.BoundBox.ZMin))
    return result


def _top_faces(shape):
    if shape.isNull():
        return []
    top = shape.BoundBox.ZMax
    return [face for face in shape.Faces
            if face.BoundBox.ZLength < 1e-7 and abs(face.BoundBox.ZMax - top) < 1e-7
            and face.normalAt(0, 0).z > 1 - 1e-7]


def deck_surface(shape, top):
    """Copy the actual upper plate faces, including their holes and cutouts."""
    faces = _top_faces(shape)
    if not faces:
        return Part.Shape()
    result = Part.Compound([face.copy() for face in faces])
    result.translate(App.Vector(0, 0, top - result.BoundBox.ZMax))
    return result


def fill_plan_contours(shape):
    """Make closed legacy plate contours pickable without changing their outline.

    Explicit open lines are retained. FaceMakerBullseye also preserves nested
    holes and disconnected islands instead of replacing them with a rectangle.
    """
    if shape.isNull() or shape.Faces or not shape.Edges or shape.BoundBox.ZLength > 0.01:
        return shape
    closed, open_edges = [], []
    try:
        for edges in Part.sortEdges(shape.Edges):
            wire = Part.Wire(edges)
            if wire.isClosed():
                closed.append(wire)
            else:
                open_edges.extend(edges)
        if not closed:
            return shape
        surface = Part.makeFace(closed, 'Part::FaceMakerBullseye')
        if surface.isNull() or not surface.isValid() or not surface.Faces:
            return shape
        return Part.Compound([surface, *open_edges])
    except Part.OCCError:
        return shape


def deck_surface_materials(plan, source, source_materials):
    faces = _top_faces(source)
    existing = _face_materials(Part.Compound(faces), source, source_materials) if faces else []
    return _materials(plan, 'PedestalDeck', existing)


def component_specs(deck, model_path=None):
    """Return all six roles as (shape3d, shape2d, materials3d, materials2d).

    Structured sources already contain the component tree and both variants.
    Copy those explicit parts without splitting solids or projecting geometry.
    Legacy monolithic symbols remain whole under PedestalDeck.
    """
    if model_path is None and getattr(deck, "model_file", None):
        # Lazy import avoids a cycle when decks imports this module.
        from .decks import MODELS_DIR
        model_path = MODELS_DIR / deck.model_file
    if model_path is None:
        whole = Part.makeBox(*deck.dimensions)
        plan = Part.makePlane(deck.length, deck.width)
        source_materials = []
        named = {}
        structured = False
    else:
        path = Path(model_path)
        whole = load_variant_shape(path, "Symbol3D")
        plan = load_variant_shape(path, "Symbol2D")
        source_materials = load_variant_appearance(path, "Symbol3D")
        revision = path.stat()
        named, structured = _read_named_components(str(path), revision.st_mtime_ns,
                                                   revision.st_size, bool(App.GuiUp))
    bounds = whole.BoundBox
    if abs(bounds.XLength - deck.length) > 0.1 or abs(bounds.YLength - deck.width) > 0.1:
        raise ValueError(f"Die Komponenten-Grundfläche muss {deck.length:g} × {deck.width:g} mm messen.")
    plan_bounds = plan.BoundBox
    if abs(plan_bounds.XLength - deck.length) > 0.1 or abs(plan_bounds.YLength - deck.width) > 0.1:
        raise ValueError("Die 2D-Grundfläche stimmt nicht mit den Podestmaßen überein.")
    shift = App.Vector(-bounds.XMin, -bounds.YMin, deck.depth - bounds.ZMax)
    plan_shift = App.Vector(-plan_bounds.XMin, -plan_bounds.YMin,
                            deck.depth - plan_bounds.ZMin)
    explicit = [role for role in ROLES if role in named]
    if explicit and len(explicit) != len(ROLES):
        raise ValueError('Benannte Komponenten müssen alle sechs Bauteile explizit enthalten: '
                         + ', '.join(role for role in ROLES if role not in named))
    parts = {role: Part.Shape() for role in ROLES}
    if not explicit:
        parts['PedestalDeck'] = whole
    result = {}
    for role in ROLES:
        if role in named:
            raw, existing = named[role]
            raw = raw.copy()
            if (not raw.isNull() and (not raw.isValid() or not raw.Solids)) or (
                    raw.isNull() and not structured):
                raise ValueError(f"{role} muss gültige Volumengeometrie enthalten.")
        else:
            raw = parts[role]
            existing = _face_materials(raw, whole, source_materials)
        mixed = role == "PedestalDeck" and not explicit
        materials3d = _materials(raw, role, existing, preserve_mixed=structured or mixed)
        shape3d = raw.copy()
        if not shape3d.isNull():
            shape3d.translate(shift)
            shape3d = Part.Compound([shape3d])
        planar_name = role + "2D"
        if planar_name in named:
            shape2d, existing2d = named[planar_name]
            shape2d = shape2d.copy()
            if not shape2d.isNull() and (not shape2d.isValid() or shape2d.Solids
                                        or shape2d.BoundBox.ZLength > 0.01):
                raise ValueError(f"{planar_name} muss flach und parallel zur XY-Ebene sein.")
            if not shape2d.isNull():
                shape2d.translate(plan_shift if structured else App.Vector(
                    shift.x, shift.y, deck.depth - shape2d.BoundBox.ZMin))
                shape2d = Part.Compound([shape2d])
        elif role == "PedestalDeck" and role not in named:
            shape2d = plan.copy()
            plan_bounds = shape2d.BoundBox
            shape2d.translate(App.Vector(-plan_bounds.XMin, -plan_bounds.YMin,
                                        deck.depth - plan_bounds.ZMin))
            shape2d = Part.Compound([shape2d])
            existing2d = load_variant_appearance(model_path, "Symbol2D") if model_path else []
        elif role == 'PedestalDeck':
            shape2d = deck_surface(shape3d, deck.depth)
            if shape2d.isNull():
                shape2d = _project_contours(shape3d, deck.depth)
            existing2d = _face_materials(Part.Compound(_top_faces(shape3d)), shape3d, materials3d)
        else:
            shape2d = _project_contours(shape3d, deck.depth)
            existing2d = []
        if role == 'PedestalDeck' and not structured:
            shape2d = fill_plan_contours(shape2d)
        materials2d = _materials(shape2d, role, existing2d, preserve_mixed=structured)
        result[role] = (shape3d, shape2d, materials3d, materials2d)
    return result
