"""Default wood/aluminium materials for the supplied stage symbols."""

import FreeCAD as App

WOOD_COLOR = (0.76, 0.63, 0.41)
ALUMINIUM_COLOR = (128 / 255,) * 3
ALUMINIUM_SPECULAR = (0.5333333,) * 3


def wood_faces(shape, plan_view=False):
    """Identify the broad wooden plate in the supplied compound models.

    Simplified single-box symbols represent wood on the horizontal faces and
    aluminium on their sides. Detailed symbols retain every face of the deck
    solid, including its vertical edges; frame/corner faces stay aluminium.
    """
    if plan_view:
        return set(range(len(shape.Faces)))
    bounds = shape.BoundBox
    plates = [solid for solid in shape.Solids
              if solid.BoundBox.XLength > bounds.XLength * 0.8
              and solid.BoundBox.YLength > bounds.YLength * 0.8
              and solid.BoundBox.ZLength < bounds.ZLength * 0.5]
    if plates:
        plate = max(plates, key=lambda solid: solid.Volume)
        return {index for index, face in enumerate(shape.Faces)
                if any(face.isSame(wood) for wood in plate.Faces)}
    up = shape.Placement.Rotation.multVec(App.Vector(0, 0, 1))
    return {index for index, face in enumerate(shape.Faces)
            if abs(face.normalAt(0, 0).dot(up)) > 0.5}


def apply_default_materials(symbol, plan_view=False):
    if not App.GuiUp:
        return
    wood = wood_faces(symbol.Shape, plan_view)
    materials = []
    for index in range(len(symbol.Shape.Faces)):
        material = App.Material()
        material.DiffuseColor = WOOD_COLOR if index in wood else ALUMINIUM_COLOR
        material.SpecularColor = (0.0, 0.0, 0.0) if index in wood else ALUMINIUM_SPECULAR
        material.Shininess = 0.9
        material.Transparency = 0.0
        materials.append(material)
    if materials:
        symbol.ViewObject.ShapeAppearance = materials
    symbol.ViewObject.LineColor = (0.23, 0.19, 0.14)
