"""Stage deck catalogue, geometry and FreeCAD document objects."""

from dataclasses import dataclass
from math import isfinite

import FreeCAD as App
import Part

from .docking import Port, UP, mate_ports


DECK_KIND = "stage-snap:deck:v1"
DECK_SYMBOL_KIND = "stage-snap:deck-symbol:v1"
DECK_PORT = "stage:deck-edge"
AREA_NUMBER_KEY = "EventCADLastDeckArea"
FLEXIBLE = "flexible"


@dataclass(frozen=True)
class Deck:
    catalog_id: str
    label: str
    length: float
    width: float
    depth: float

    def __post_init__(self):
        if not all(isfinite(size) and size > 0 for size in self.dimensions):
            raise ValueError("Die Podestmaße müssen größer als null sein.")

    @property
    def dimensions(self):
        return self.length, self.width, self.depth

    def ports(self):
        length, width, top = self.dimensions
        # Counterclockwise from the local +X side. Each origin is on the top.
        edges = (
            ("Rechts", length, width / 2, width),
            ("Oben", length / 2, width, length),
            ("Links", 0, width / 2, width),
            ("Unten", length / 2, 0, length),
        )
        return tuple(
            Port(key, DECK_PORT, App.Placement(
                App.Vector(x, y, top), App.Rotation(UP, 90 * index)
            ), span)
            for index, (key, x, y, span) in enumerate(edges)
        )


def plate_size_label(length, width):
    return f"{length / 1000:g} × {width / 1000:g} m".replace(".", ",")


def system_decks(system_id, system_label, sizes):
    for length, width in sizes:
        size_label = plate_size_label(length, width)
        yield Deck(f"{system_id}-{length}-{width}", f"{system_label} · {size_label}",
                   length, width, 90)


CATALOG = {
    "BÜTEC Standard": tuple(system_decks("buetec-standard", "BÜTEC Standard", (
        (2000, 1000), (1000, 1000),
    ))),
    "nivtec Standard": tuple(system_decks("nivtec-standard", "nivtec Standard", (
        (2000, 1000), (1500, 1000), (1000, 1000),
        (2000, 750), (1500, 750), (1000, 750),
        (2000, 500), (1500, 500), (1000, 500), (500, 500),
    ))),
    "Planungsmaß": (Deck("planning-1000-1000", "Planungsmaß · 1 × 1 m", 1000, 1000, 90), None),
}


def is_deck(obj):
    return (obj is not None and obj.TypeId == "Part::Box"
            and getattr(obj, "StageSnapKind", None) == DECK_KIND)


def is_deck_symbol(obj):
    return (obj is not None and obj.TypeId == "Part::FeaturePython"
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
    area.addProperty("App::PropertyInteger", "StageSnapAreaNumber", "BühnenSnap")
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
    """Regenerate the selectable plan face when its source deck changes."""

    def execute(self, symbol):
        source = symbol.StageSnapSource
        if not is_deck(source) or min(source.Length.Value, source.Width.Value) <= 0:
            symbol.Shape = Part.Shape()
            return
        length, width, top = source.Length.Value, source.Width.Value, source.Height.Value
        corners = [App.Vector(x, y, top) for x, y in (
            (0, 0), (length, 0), (length, width), (0, width), (0, 0),
        )]
        symbol.Shape = Part.Face(Part.makePolygon(corners))
        symbol.Placement = source.Placement


def make_deck_symbol(document, deck):
    container = deck_area(deck) or deck.getParentGeoFeatureGroup()
    if container is None:
        symbol = document.addObject("Part::FeaturePython", "PodestGrundriss")
    else:
        symbol = container.newObject("Part::FeaturePython", "PodestGrundriss")
    symbol.Label = f"{deck.Label} · 2D"
    symbol.addProperty("App::PropertyString", "StageSnapKind", "BühnenSnap")
    symbol.StageSnapKind = DECK_SYMBOL_KIND
    symbol.addProperty("App::PropertyLink", "StageSnapSource", "BühnenSnap")
    symbol.StageSnapSource = deck
    for name in ("StageSnapKind", "StageSnapSource", "Placement"):
        symbol.setEditorMode(name, 1)
    symbol.Proxy = DeckPlanSymbol()
    if App.GuiUp:
        # Activate the built-in shape display of the scripted part feature.
        symbol.ViewObject.Proxy = 0
        symbol.ViewObject.ShowInTree = False
        symbol.ViewObject.ShapeColor = deck.ViewObject.ShapeColor
        symbol.ViewObject.LineColor = deck.ViewObject.LineColor
        symbol.ViewObject.Visibility = False
    return symbol


def read_deck(obj):
    return Deck(obj.StageSnapCatalogId, obj.Label, obj.Length.Value,
                obj.Width.Value, obj.Height.Value)


def seed_placement(deck, x, y, top, quarter_turn):
    rotation = App.Rotation(UP, 90 * quarter_turn)
    top_center = App.Vector(deck.length / 2, deck.width / 2, deck.depth)
    return App.Placement(App.Vector(x, y, top) - rotation.multVec(top_center), rotation)


def nearest_port_index(ports, point, *, prefer_long=False):
    def distance_key(port):
        local = port.frame.inverse().multVec(point)
        beyond_end = max(0.0, abs(local.y) - port.span / 2)
        distance = local.x ** 2 + beyond_end ** 2
        if prefer_long:
            # Treat floating-point noise at a shared corner as a tie.
            return round(distance, 12), -port.span
        return distance

    return min(range(len(ports)), key=lambda index: distance_key(ports[index]))


def dock_deck(target_deck, target_placement, deck, world_pick, quarter_turn, alignment):
    if (target_placement.Rotation.multVec(UP) - UP).Length > 1e-7:
        raise ValueError("Zum Andocken muss das Zielpodest waagerecht liegen.")
    target_ports = target_deck.ports()
    local_pick = target_placement.inverse().multVec(world_pick)
    flexible = alignment == FLEXIBLE
    side = nearest_port_index(target_ports, local_pick, prefer_long=flexible)
    target = target_ports[side]
    source_ports = deck.ports()
    source_index = (side + 2 - quarter_turn) % 4
    source = source_ports[source_index]
    # 'Anfang' means lower local X/Y, irrespective of the edge's outward normal.
    tangent_sign = (1, -1, -1, 1)[side]
    if flexible:
        if target.span < max(target_deck.length, target_deck.width):
            raise ValueError("Klicke für „Flexibel“ knapp innerhalb einer langen Zielkante.")
        if source.span > min(deck.length, deck.width):
            source = source_ports[(source_index - 1) % 4]
        if source.span > target.span:
            raise ValueError("Die kurze Kante des neuen Podests ist länger als die Zielkante.")
        cursor_along_edge = target.frame.inverse().multVec(local_pick).y
        alignment = 1 if cursor_along_edge * tangent_sign > 0 else -1

    offset = alignment * tangent_sign * (target.span - source.span) / 2
    return mate_ports(target_placement, target, source, offset), target.key


def make_box(deck, placement):
    shape = Part.makeBox(*deck.dimensions)
    shape.Placement = placement
    return shape


def positive_bounds_overlap(a, b):
    axes = (
        (a.XMin, a.XMax, b.XMin, b.XMax),
        (a.YMin, a.YMax, b.YMin, b.YMax),
        (a.ZMin, a.ZMax, b.ZMin, b.ZMax),
    )
    return all(min(max_a, max_b) - max(min_a, min_b) > 1e-6
               for min_a, max_a, min_b, max_b in axes)


def check_clear(document, deck, placement):
    shape = make_box(deck, placement)
    bounds = shape.BoundBox
    for obj in document.Objects:
        if not is_deck(obj):
            continue
        other = make_box(read_deck(obj), obj.getGlobalPlacement())
        if positive_bounds_overlap(bounds, other.BoundBox) and shape.common(other).Volume > 1e-4:
            raise ValueError(f"Das neue Podest überschneidet sich mit „{obj.Label}“.")


def insert_deck(document, deck, placement, *, plan_view=False, target=None):
    check_clear(document, deck, placement)
    document.openTransaction("Podest setzen")
    try:
        if target is None:
            obj = document.addObject("Part::Box", "Podest")
        else:
            area = area_for_snap(document, target)
            obj = area.newObject("Part::Box", "Podest")
            container = obj.getParentGeoFeatureGroup()
            if container is not None:
                placement = container.getGlobalPlacement().inverse() * placement
        obj.Label = f"Podest {obj.Name.removeprefix('Podest') or '000'} · {deck.label}"
        obj.Length, obj.Width, obj.Height = deck.dimensions
        obj.Placement = placement
        for prop, value in (("StageSnapKind", DECK_KIND), ("StageSnapCatalogId", deck.catalog_id)):
            obj.addProperty("App::PropertyString", prop, "BühnenSnap")
            setattr(obj, prop, value)
            obj.setEditorMode(prop, 1)
        if App.GuiUp:
            obj.ViewObject.ShapeColor = (0.76, 0.63, 0.41)
            obj.ViewObject.LineColor = (0.23, 0.19, 0.14)
            symbol = make_deck_symbol(document, obj)
            obj.ViewObject.Visibility = not plan_view
            symbol.ViewObject.Visibility = plan_view
        document.recompute()
    except Exception:
        document.abortTransaction()
        raise
    document.commitTransaction()
    return obj
