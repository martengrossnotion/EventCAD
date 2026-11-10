"""Local connection frames and placement shared by Event tools."""

from dataclasses import dataclass

import FreeCAD as App


UP = App.Vector(0, 0, 1)
FACE_TO_FACE = App.Rotation(UP, 180)


@dataclass(frozen=True)
class Port:
    key: str
    interface: str
    frame: App.Placement
    span: float = 0.0


def mate_ports(target_placement, target, source, offset=0.0, roll=0.0):
    """Match opposing +X normals and align +Z, with optional connector roll.

    Frames are local to their objects. Offset is measured along the target's
    local +Y. Roll is in degrees around the target's outward normal (+X).
    """
    if target.interface != source.interface:
        raise ValueError("Diese Anschlüsse sind inkompatibel.")
    mating = App.Placement(
        App.Vector(0, offset, 0),
        App.Rotation(App.Vector(1, 0, 0), roll).multiply(FACE_TO_FACE),
    )
    return (
        target_placement.multiply(target.frame)
        .multiply(mating)
        .multiply(source.frame.inverse())
    )
