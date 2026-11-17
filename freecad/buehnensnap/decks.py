"""Stage deck catalogue, geometry and FreeCAD document objects."""

from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path

import FreeCAD as App
import Part

from .plan_symbols import find_plan_symbol, load_plan_shape, load_variant_shape, global_placement
from .plan_symbols import load_variant_appearance
from .appearance import apply_default_materials

DECK_KIND = "stage-snap:deck:v1"
DECK_SYMBOL_KIND = "stage-snap:deck-symbol:v1"
AREA_NUMBER_KEY = "EventCADLastDeckArea"
FRAME_GRAY = 128 / 255
MODELS_DIR = Path(__file__).resolve().parent / "resources" / "models"
MODEL_SYSTEMS = {
    "buetec-standard": "BÜTEC Standard",
    "nivtec-standard": "nivtec Standard",
    "buetec-eco": "BÜTEC Eco",
    "planning": "Planungsmaß",
}
MODEL_EXTENSIONS = {".fcstd"}
UP = App.Vector(0, 0, 1)
PLAN_EDGES = (
    ("Rechts", 0, 1),
    ("Oben", 1, 1),
    ("Links", 0, -1),
    ("Unten", 1, -1),
)


@dataclass(frozen=True)
class Deck:
    catalog_id: str
    label: str
    length: float
    width: float
    depth: float
    model_file: str | None = None

    def __post_init__(self):
        if not all(isfinite(size) and size > 0 for size in self.dimensions):
            raise ValueError("Die Podestmaße müssen größer als null sein.")

    @property
    def dimensions(self):
        return self.length, self.width, self.depth


def plate_size_label(length, width):
    return f"{length / 1000:g} × {width / 1000:g} m".replace(".", ",")


def system_decks(system_id, system_label, sizes):
    for length, width in sizes:
        size_label = plate_size_label(length, width)
        yield Deck(f"{system_id}-{length}-{width}", f"{system_label} · {size_label}",
                   length, width, 90, f"{system_id}/{length}x{width}/{length}x{width}.FCStd")


CATALOG = {
    "BÜTEC Standard": tuple(system_decks("buetec-standard", "BÜTEC Standard", (
        (2000, 1000), (1000, 1000),
    ))),
    "nivtec Standard": tuple(system_decks("nivtec-standard", "nivtec Standard", (
        (2000, 1000), (1500, 1000), (1000, 1000),
        (2000, 750), (1500, 750), (1000, 750),
        (2000, 500), (1500, 500), (1000, 500), (500, 500),
    ))),
    "Planungsmaß": (Deck("planning-1000-1000", "Planungsmaß · 1 × 1 m", 1000, 1000, 90,
                         "planning/1000x1000/1000x1000.FCStd"), None),
}


def model_systems():
    systems = MODEL_SYSTEMS.copy()
    if MODELS_DIR.is_dir():
        for folder in sorted(MODELS_DIR.iterdir(), key=lambda path: path.name.casefold()):
            if folder.is_dir() and not folder.name.startswith("."):
                systems.setdefault(folder.name, folder.name)
    return systems


def plan_symbol_models(system_id, system_label):
    folder = MODELS_DIR / system_id
    if not folder.is_dir():
        return
    files = {}
    for symbol_folder in sorted(folder.iterdir(), key=lambda path: (path.name.casefold(), path.name)):
        if not symbol_folder.is_dir() or symbol_folder.name.startswith("."):
            continue
        try:
            path = symbol_model(symbol_folder)
        except ValueError as error:
            App.Console.PrintWarning(f"Podest: {error}\n")
            continue
        if path is not None:
            files[path.relative_to(MODELS_DIR).as_posix()] = symbol_folder.name
    for deck in filter(None, CATALOG.get(system_label, ())):
        model_file = next((name for name in files
                           if Path(name).parent == Path(deck.model_file).parent), None)
        if model_file is not None:
            yield plate_size_label(deck.length, deck.width), model_file
            del files[model_file]
    for model_file in sorted(files, key=lambda name: (name.casefold(), name)):
        yield files[model_file], model_file


def deck_for_model(system_label, model_file):
    for deck in filter(None, CATALOG.get(system_label, ())):
        if Path(deck.model_file).parent == Path(model_file).parent:
            return replace(deck, model_file=model_file)

    path = MODELS_DIR / model_file
    bounds = read_model_shape(path).BoundBox
    return Deck(model_file, f"{system_label} · {path.parent.name}",
                bounds.XLength, bounds.YLength, bounds.ZLength, model_file)


def is_deck(obj):
    return (obj is not None and obj.TypeId in ("Part::Box", "Part::Feature", "App::Link")
            and getattr(obj, "StageSnapKind", None) == DECK_KIND)


def is_deck_symbol(obj):
    return (obj is not None and obj.TypeId in ("Part::FeaturePython", "App::LinkPython")
            and getattr(obj, "StageSnapKind", None) == DECK_SYMBOL_KIND)


def deck_from_pick(obj):
    if is_deck_symbol(obj):
        obj = obj.StageSnapSource
    return obj if is_deck(obj) else None


def deck_area(deck):
    parent = deck.getParentGroup()
    return parent if getattr(parent, "StageSnapAreaNumber", 0) > 0 else None


def area_for_snap(document, target):
    area = deck_area(target)
    if area is not None:
        return area

    numbers = (getattr(obj, "StageSnapAreaNumber", 0) for obj in document.Objects)
    number = max(int(document.Meta.get(AREA_NUMBER_KEY, "0")), max(numbers, default=0)) + 1
    while document.getObjectsByLabel(f"Podestfläche {number}"):
        number += 1

    area = document.addObject("App::DocumentObjectGroup", "Podestflaeche")
    area.Label = f"Podestfläche {number}"
    area.addProperty("App::PropertyInteger", "StageSnapAreaNumber", "Podest")
    area.StageSnapAreaNumber = number
    area.setEditorMode("StageSnapAreaNumber", 1)

    parent = target.getParentGroup() or target.getParentGeoFeatureGroup()
    if parent is not None:
        parent.addObject(area)
    symbols = [obj for obj in target.InList if is_deck_symbol(obj) and obj.StageSnapSource == target]
    area.addObjects([target, *symbols])
    document.Meta = {**document.Meta, AREA_NUMBER_KEY: str(number)}
    return area


class DeckPlanSymbol:
    """Place the embedded plan geometry when its source deck changes."""

    def execute(self, symbol):
        source = symbol.StageSnapSource
        if not is_deck(source) or min(source.Length.Value, source.Width.Value) <= 0:
            symbol.Shape = Part.Shape()
            return
        length, width, top = source.Length.Value, source.Width.Value, source.Height.Value
        stored = getattr(symbol, "StageSnapPlanShape", None)
        if stored is not None and not stored.isNull():
            shape = stored.copy()
            shape.translate(App.Vector(0, 0, top))
            symbol.Shape = Part.Compound([shape])
        else:
            corners = [App.Vector(x, y, top) for x, y in (
                (0, 0), (length, 0), (length, width), (0, width), (0, 0),
            )]
            symbol.Shape = Part.Face(Part.makePolygon(corners))
        symbol.Placement = source.Placement


def symbol_model(folder):
    matches = [path for path in folder.iterdir()
               if path.is_file() and path.suffix.lower() in MODEL_EXTENSIONS]
    if len(matches) > 1:
        raise ValueError(f"Symbolordner {folder.name}: Es darf nur eine FCStd-Datei "
                         "für die 3D-Darstellung enthalten sein.")
    return matches[0] if matches else None


def current_model_file(source):
    """Resolve the current FCStd in the linked symbol folder, including old plans."""
    model_file = read_deck(source).model_file
    if not model_file:
        return None
    path = MODELS_DIR / model_file
    # Before 1.6.0 files lived directly in the system folder.
    if path.parent.parent == MODELS_DIR and (path.parent / path.stem).is_dir():
        path = path.parent / path.stem / path.name
    if path.parent.is_dir():
        path = symbol_model(path.parent) or path
    model_file = path.relative_to(MODELS_DIR).as_posix()
    if "StageSnapModelFile" not in source.PropertiesList:
        source.addProperty("App::PropertyString", "StageSnapModelFile", "Podest")
    if source.StageSnapModelFile != model_file:
        source.StageSnapModelFile = model_file
    return model_file


def refresh_legacy_deck_symbol(symbol):
    """Refresh from a matching companion, retaining embedded geometry if absent."""
    source = symbol.StageSnapSource
    deck = read_deck(source)
    try:
        model_file = current_model_file(source)
        if not model_file:
            return
        path = find_plan_symbol(MODELS_DIR / model_file)
        if path is None:
            return
        shape = load_plan_shape(path, deck.length, deck.width)
    except Exception as error:
        App.Console.PrintWarning(f"Podest: 2D-Symbol für {source.Label} konnte nicht geladen "
                                 f"werden. Gespeichertes Symbol bzw. Rechteck wird verwendet.\n"
                                 f"{error}\n")
        return
    if "StageSnapPlanShape" not in symbol.PropertiesList:
        symbol.addProperty("Part::PropertyPartShape", "StageSnapPlanShape", "Podest")
        symbol.addProperty("App::PropertyString", "StageSnapPlanFile", "Podest")
        symbol.setEditorMode("StageSnapPlanShape", 2)
        symbol.setEditorMode("StageSnapPlanFile", 1)
    symbol.StageSnapPlanShape = shape
    symbol.StageSnapPlanFile = path.relative_to(MODELS_DIR).as_posix()


def deck_face_colors(deck):
    shape = deck.Shape
    faces = shape.Faces
    up = shape.Placement.Rotation.multVec(UP)
    view = deck.ViewObject
    colors = view.DiffuseColor
    if len(colors) != len(faces):
        base_color = colors[0] if colors else view.ShapeColor[:3] + (view.Transparency / 100,)
        colors = [base_color] * len(faces)
    return [(face.normalAt(0, 0).dot(up), color) for face, color in zip(faces, colors)]


def set_deck_frame_color(deck):
    faces = deck_face_colors(deck)
    if any(abs(normal) < 0.5 and max(abs(channel - FRAME_GRAY) for channel in color[:3]) > 1e-6
           for normal, color in faces):
        deck.ViewObject.DiffuseColor = [
            (FRAME_GRAY,) * 3 + color[3:] if abs(normal) < 0.5 else color
            for normal, color in faces
        ]


def make_legacy_deck_symbol(document, deck):
    container = deck_area(deck) or deck.getParentGeoFeatureGroup()
    if container is None:
        symbol = document.addObject("Part::FeaturePython", "PodestGrundriss")
    else:
        symbol = container.newObject("Part::FeaturePython", "PodestGrundriss")
    symbol.Label = f"{deck.Label} · 2D"
    symbol.addProperty("App::PropertyString", "StageSnapKind", "Podest")
    symbol.StageSnapKind = DECK_SYMBOL_KIND
    symbol.addProperty("App::PropertyLink", "StageSnapSource", "Podest")
    symbol.StageSnapSource = deck
    for name in ("StageSnapKind", "StageSnapSource", "Placement"):
        symbol.setEditorMode(name, 1)
    symbol.Proxy = DeckPlanSymbol()
    refresh_deck_symbol(symbol)
    if App.GuiUp:
        # Activate the built-in shape display of the scripted part feature.
        symbol.ViewObject.Proxy = 0
        symbol.ViewObject.ShowInTree = False
        symbol.ViewObject.ShapeColor = next(
            (color[:3] for normal, color in deck_face_colors(deck) if normal > 0.5),
            deck.ViewObject.ShapeColor,
        )
        symbol.ViewObject.LineColor = deck.ViewObject.LineColor
        symbol.ViewObject.Visibility = False
    return symbol


def read_deck(obj):
    model_file = getattr(obj, "StageSnapModelFile", "")
    if not model_file:
        # Files placed before 1.6.0 only stored the catalogue ID.
        for sizes in CATALOG.values():
            for deck in filter(None, sizes):
                if deck.catalog_id == obj.StageSnapCatalogId:
                    model_file = deck.model_file
                    break
        if not model_file and Path(obj.StageSnapCatalogId).suffix.lower() in MODEL_EXTENSIONS | {".step", ".stp"}:
            model_file = obj.StageSnapCatalogId
    return Deck(obj.StageSnapCatalogId, obj.Label, obj.Length.Value,
                obj.Width.Value, obj.Height.Value, model_file or None)


def seed_placement(deck, x, y, top, quarter_turn):
    portrait_turn = 1 if deck.length >= deck.width else 0
    rotation = App.Rotation(UP, 90 * (portrait_turn - quarter_turn))
    top_center = App.Vector(deck.length / 2, deck.width / 2, deck.depth)
    return App.Placement(App.Vector(x, y, top) - rotation.multVec(top_center), rotation)


def target_plan_size(deck, rotation):
    if (rotation.multVec(UP) - UP).Length > 1e-7:
        raise ValueError("Für Autosnap muss das Zielpodest waagerecht liegen.")
    length_axis = rotation.multVec(App.Vector(1, 0, 0))
    if abs(length_axis.y) < 1e-7:
        return deck.length, deck.width
    if abs(length_axis.x) < 1e-7:
        return deck.width, deck.length
    raise ValueError("Für Autosnap müssen die Kanten des Zielpodests parallel zu X und Y liegen.")


def snap_placements(target_deck, target_placement, deck, world_pick, quarter_turn):
    """Find the preferred and alternate corner placements on the same plan edge."""
    target_size = target_plan_size(target_deck, target_placement.Rotation)
    source_size = sorted((deck.length, deck.width), reverse=bool(quarter_turn))
    center = target_placement.multVec(App.Vector(
        target_deck.length / 2, target_deck.width / 2, target_deck.depth,
    ))
    pick = (world_pick.x - center.x, world_pick.y - center.y)

    def distance_squared(edge):
        _, normal, sign = edge
        tangent = 1 - normal
        distance = pick[normal] - sign * target_size[normal] / 2
        beyond_end = max(0, abs(pick[tangent]) - target_size[tangent] / 2)
        return distance ** 2 + beyond_end ** 2

    side, normal, sign = min(PLAN_EDGES, key=distance_squared)
    tangent = 1 - normal
    end = 1 if pick[tangent] > 0 else -1
    normal_offset = sign * (target_size[normal] + source_size[normal]) / 2
    # The signed difference also aligns corners when the new edge overhangs.
    tangent_offset = end * (target_size[tangent] - source_size[tangent]) / 2

    def at_corner(offset):
        shift = [0, 0]
        shift[normal] = normal_offset
        shift[tangent] = offset
        return seed_placement(deck, center.x + shift[0], center.y + shift[1],
                              center.z, quarter_turn)

    preferred = at_corner(tangent_offset)
    alternate = at_corner(-tangent_offset) if tangent_offset else None
    return preferred, alternate, side


def make_box(deck, placement):
    shape = Part.makeBox(*deck.dimensions)
    shape.Placement = placement
    return shape


def read_model_shape(path):
    if not path.is_file():
        raise ValueError(f"FCStd-Modell fehlt: {path}")
    try:
        return load_variant_shape(path, "Symbol3D")
    except Exception as error:
        raise ValueError(f"FCStd-Modell konnte nicht geladen werden: {path}\n{error}") from error


def load_deck_model(deck):
    path = MODELS_DIR / deck.model_file
    shape = read_model_shape(path)
    bounds = shape.BoundBox
    if abs(bounds.XLength - deck.length) > 0.1 or abs(bounds.YLength - deck.width) > 0.1:
        raise ValueError(f"FCStd-Modell {path.name}: Grundfläche muss in X × Y "
                         f"{deck.length:g} × {deck.width:g} mm messen. "
                         f"Gemessen: {bounds.XLength:g} × {bounds.YLength:g} mm.")

    # Align the footprint and the upper surface with the planning dimensions.
    shape.translate(App.Vector(-bounds.XMin, -bounds.YMin, deck.depth - bounds.ZMax))
    # Keep the imported transform inside the shape when the document object is placed.
    return Part.Compound([shape]) if not shape.Placement.isIdentity() else shape


def positive_bounds_overlap(a, b):
    axes = (
        (a.XMin, a.XMax, b.XMin, b.XMax),
        (a.YMin, a.YMax, b.YMin, b.YMax),
        (a.ZMin, a.ZMax, b.ZMin, b.ZMax),
    )
    return all(min(max_a, max_b) - max(min_a, min_b) > 1e-6
               for min_a, max_a, min_b, max_b in axes)


class DeckOverlapError(ValueError):
    """A placement intersects an existing stage deck."""


def check_clear(document, deck, placement):
    shape = make_box(deck, placement)
    bounds = shape.BoundBox
    for obj in document.Objects:
        if not is_deck(obj):
            continue
        other = make_box(read_deck(obj), global_placement(obj))
        if positive_bounds_overlap(bounds, other.BoundBox) and shape.common(other).Volume > 1e-4:
            raise DeckOverlapError(f"Das neue Podest überschneidet sich mit „{obj.Label}“.")


def snap_deck(document, target, deck, world_pick, quarter_turn, *, plan_view=False):
    preferred, alternate, side = snap_placements(
        read_deck(target), global_placement(target), deck, world_pick, quarter_turn,
    )
    try:
        obj = insert_deck(document, deck, preferred, plan_view=plan_view, target=target)
    except DeckOverlapError:
        if alternate is None:
            raise
        obj = insert_deck(document, deck, alternate, plan_view=plan_view, target=target)
    return obj, side


def insert_deck(document, deck, placement, *, plan_view=False, target=None):
    check_clear(document, deck, placement)
    document.openTransaction("Podest setzen")
    try:
        template3d, template2d = symbol_templates(document, deck)
        obj = document.addObject("App::Link", "Podest")
        obj.setLink(template3d)
        obj.LinkTransform = False
        if target is not None:
            area = area_for_snap(document, target)
            area.addObject(obj)
            container = obj.getParentGeoFeatureGroup()
            if container is not None:
                placement = global_placement(container).inverse() * placement
        obj.Label = f"Podest {obj.Name.removeprefix('Podest') or '000'} · {deck.label}"
        for name in ("Length", "Width", "Height"):
            obj.addProperty("App::PropertyLength", name, "Podest")
            obj.setEditorMode(name, 1)
        obj.Length, obj.Width, obj.Height = deck.dimensions
        obj.Placement = placement
        for prop, value in (("StageSnapKind", DECK_KIND), ("StageSnapCatalogId", deck.catalog_id),
                            ("StageSnapModelFile", deck.model_file or "")):
            obj.addProperty("App::PropertyString", prop, "Podest")
            setattr(obj, prop, value)
            if prop != "StageSnapModelFile":
                obj.setEditorMode(prop, 1)
        obj.addProperty("App::PropertyLink", "StageSnapPlanTemplate", "Podest")
        obj.StageSnapPlanTemplate = template2d
        obj.setEditorMode("StageSnapPlanTemplate", 2)
        obj.addProperty("App::PropertyLink", "StageSnap3DTemplate", "Podest")
        obj.StageSnap3DTemplate = template3d
        obj.setEditorMode("StageSnap3DTemplate", 2)
        set_deck_mode(obj, plan_view)
        document.recompute()
    except Exception:
        document.abortTransaction()
        raise
    document.commitTransaction()
    return obj


def template_group(document):
    for obj in document.Objects:
        if getattr(obj, "StageSnapTemplateLibrary", False):
            return obj
    group = document.addObject("App::DocumentObjectGroup", "EventCADSymbolvorlagen")
    group.Label = "EventCAD · Symbolvorlagen"
    group.addProperty("App::PropertyBool", "StageSnapTemplateLibrary", "Podest")
    group.StageSnapTemplateLibrary = True
    group.setEditorMode("StageSnapTemplateLibrary", 2)
    return group


def symbol_templates(document, deck):
    """Embed one immutable pair per file revision and planning dimensions."""
    if deck.model_file:
        path = MODELS_DIR / deck.model_file
        stat = path.stat()
        key = repr((str(path.resolve()), stat.st_mtime_ns, stat.st_size, deck.dimensions))
    else:
        key = repr(("custom", deck.dimensions))
    templates = {getattr(obj, "StageSnapVariant", ""): obj for obj in document.Objects
                 if obj.TypeId == "Part::Feature"
                 and getattr(obj, "StageSnapTemplateKey", None) == key}
    if "Symbol3D" in templates and "Symbol2D" in templates:
        return templates["Symbol3D"], templates["Symbol2D"]
    shape3d = load_deck_model(deck) if deck.model_file else Part.makeBox(*deck.dimensions)
    if deck.model_file:
        shape2d = load_plan_shape(path, deck.length, deck.width)
    else:
        shape2d = Part.makePlane(deck.length, deck.width)
    shape2d.translate(App.Vector(0, 0, deck.depth))
    # Freeze local transforms into the geometry; links own their placement.
    shapes = {"Symbol3D": shape3d, "Symbol2D": Part.Compound([shape2d])}
    group = template_group(document)
    for variant, shape in shapes.items():
        template = document.addObject("Part::Feature", "EventCAD" + variant)
        template.Shape = shape
        template.Label = f"{deck.label} · {variant}"
        for prop, value in (("StageSnapTemplateKey", key), ("StageSnapVariant", variant)):
            template.addProperty("App::PropertyString", prop, "Podest")
            setattr(template, prop, value)
            template.setEditorMode(prop, 2)
        group.addObject(template)
        if App.GuiUp:
            materials = load_variant_appearance(path, variant) if deck.model_file else []
            if materials:
                template.ViewObject.ShapeAppearance = materials
                template.ViewObject.LineColor = (0.23, 0.19, 0.14)
            else:
                apply_default_materials(template, variant == "Symbol2D")
            template.ViewObject.Visibility = False
        templates[variant] = template
    return templates["Symbol3D"], templates["Symbol2D"]


class LinkedPlanSymbol:
    """Synchronize placement only; geometry stays shared in the linked template."""

    def execute(self, symbol):
        source = symbol.StageSnapSource
        if source is not None:
            parent = symbol.getParentGeoFeatureGroup()
            placement = global_placement(source)
            if parent is not None:
                placement = global_placement(parent).inverse() * placement
            if symbol.Placement != placement:
                symbol.Placement = placement


def make_deck_symbol(document, deck):
    """Legacy entry point: native links now own both representations."""
    if deck.TypeId == "App::Link":
        return deck
    return make_legacy_deck_symbol(document, deck)


def set_deck_mode(source, plan_view):
    """Switch shared geometry on the same editable, placed native link.

    Version 1.7 links can be upgraded using only embedded templates, including
    when their library file is absent. Placement and visibility belong to the
    instance, never to its currently selected representation.
    """
    if source.TypeId != "App::Link":
        raise ValueError("Die gemeinsame Darstellung benötigt ein App::Link-Podest.")
    if "StageSnap3DTemplate" not in source.PropertiesList:
        source.addProperty("App::PropertyLink", "StageSnap3DTemplate", "Podest")
        source.StageSnap3DTemplate = source.LinkedObject
        source.setEditorMode("StageSnap3DTemplate", 2)
    target = source.StageSnapPlanTemplate if plan_view else source.StageSnap3DTemplate
    if target is None:
        raise ValueError(f"Die eingebettete Symbolvorlage für {source.Label} fehlt.")
    placement = source.Placement.copy()
    visible = source.Visibility
    if source.LinkedObject != target:
        source.setLink(target)
        source.LinkTransform = False
        source.Placement = placement
        source.Visibility = visible
    if App.GuiUp:
        source.ViewObject.ShowInTree = True


def refresh_deck_symbol(symbol):
    # Linked pairs are immutable snapshots; replaced files affect new placements.
    # The old per-instance proxy remains supported for previously saved plans.
    if symbol.TypeId == "App::LinkPython":
        symbol.Proxy.execute(symbol)
    else:
        refresh_legacy_deck_symbol(symbol)
