"""Switch the display of EventCAD objects in a FreeCAD document."""

import FreeCADGui as Gui

from .decks import deck_from_pick, is_deck, is_deck_symbol, make_deck_symbol


PLAN_MODE = "2D"
MODE_KEY = "EventCADViewMode"


def is_plan_view(document):
    return document.Meta.get(MODE_KEY) == PLAN_MODE


def active_3d_view():
    document = Gui.activeDocument()
    view = document.activeView() if document else None
    return view if hasattr(view, "addEventCallbackPivy") else None


def show_mode(document, view, mode):
    plan_view = mode == PLAN_MODE
    symbols = {}
    for obj in document.Objects:
        if is_deck_symbol(obj):
            source = deck_from_pick(obj)
            if source is None:
                document.removeObject(obj.Name)
            else:
                symbols[source.Name] = obj

    for source in document.Objects:
        if not is_deck(source):
            continue
        symbol = symbols.get(source.Name)
        visible = source.ViewObject.Visibility or bool(symbol and symbol.ViewObject.Visibility)
        if symbol is None and plan_view:
            symbol = make_deck_symbol(document, source)
        source.ViewObject.Visibility = visible and not plan_view
        if symbol is not None:
            symbol.ViewObject.Visibility = visible and plan_view

    if document.Meta.get(MODE_KEY) != mode:
        document.Meta = {**document.Meta, MODE_KEY: mode}
    document.recompute()
    view.setCameraType("Orthographic")
    if plan_view:
        view.viewTop()
    else:
        view.viewIsometric()
