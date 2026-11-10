"""Stage deck catalogue, geometry and FreeCAD document objects."""

from dataclasses import dataclass
from math import isfinite

import FreeCAD as App
import Part

from .docking import Port, UP, mate_ports


DECK_KIND = "stage-snap:deck:v1"
DECK_PORT = "stage:deck-edge"


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


CATALOG = (
    Deck("buetec-standard-2000-1000", "BÜTEC Standard · 2 × 1 m", 2000, 1000, 90),
    Deck("planning-1000-1000", "Planungsmaß · 1 × 1 m", 1000, 1000, 90),
)


def is_deck(obj):
    return (obj is not None and obj.TypeId == "Part::Box"
            and getattr(obj, "StageSnapKind", None) == DECK_KIND)


def read_deck(obj):
    return Deck(obj.StageSnapCatalogId, obj.Label, obj.Length.Value,
                obj.Width.Value, obj.Height.Value)


def seed_placement(deck, x, y, top, quarter_turn):
    rotation = App.Rotation(UP, 90 * quarter_turn)
    top_center = App.Vector(deck.length / 2, deck.width / 2, deck.depth)
    return App.Placement(App.Vector(x, y, top) - rotation.multVec(top_center), rotation)


def nearest_port_index(ports, point):
    def distance_squared(port):
        local = port.frame.inverse().multVec(point)
        beyond_end = max(0.0, abs(local.y) - port.span / 2)
        return local.x ** 2 + beyond_end ** 2

    return min(range(len(ports)), key=lambda index: distance_squared(ports[index]))


def dock_deck(target_deck, target_placement, deck, world_pick, quarter_turn, alignment):
    if (target_placement.Rotation.multVec(UP) - UP).Length > 1e-7:
        raise ValueError("Zum Andocken muss das Zielpodest waagerecht liegen.")
    target_ports = target_deck.ports()
    side = nearest_port_index(target_ports, target_placement.inverse().multVec(world_pick))
    target = target_ports[side]
    source = deck.ports()[(side + 2 - quarter_turn) % 4]
    # 'Anfang' means lower local X/Y, irrespective of the edge's outward normal.
    tangent_sign = (1, -1, -1, 1)[side]
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


def insert_deck(document, deck, placement):
    check_clear(document, deck, placement)
    document.openTransaction("Podest setzen")
    try:
        obj = document.addObject("Part::Box", "Podest")
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
        document.recompute()
    except Exception:
        document.abortTransaction()
        raise
    document.commitTransaction()
    return obj
