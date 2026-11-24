"""Pick the real 2D plate interior and drive the production autosnap callback.

Run with FreeCAD's Python libraries and QT_QPA_PLATFORM=offscreen. Native
getObjectInfo/scene picking works without an OpenGL rendering context; this
script does not compare rendered pixels.
"""

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import FreeCAD as App
import FreeCADGui as Gui
Gui.showMainWindow()
Gui.getMainWindow().hide()
import freecad
root = Path(__file__).resolve().parents[1]
freecad.__path__ = [str(root / 'freecad')]
try:
    from PySide import QtCore, QtWidgets
except ImportError:
    import PySide2
    sys.modules['PySide'] = PySide2
    from PySide2 import QtCore, QtWidgets
from pivy import coin
import Part
from freecad.buehnensnap import decks, segments, view_modes
from freecad.buehnensnap.panel import StageSnapDock
from freecad.buehnensnap.plan_symbols import global_placement


def update(document):
    document.recompute()
    QtWidgets.QApplication.processEvents()


def control_for(segment, role):
    return next(obj for obj in segments.controls(segments.segment_area(segment))
                if obj.StageSnapViewRole == role)


def deck_link(segment):
    return next(obj for obj in segments.components(segment)
                if obj.StageSnapRole == 'PedestalDeck')


def configure_view(document):
    update(document)
    App.setActiveDocument(document.Name)
    Gui.setActiveDocument(document.Name)
    view = Gui.getDocument(document.Name).activeView()
    view.setCameraType('Orthographic')
    view.viewTop()
    # Avoid fitAll's GUI animation path in an offscreen application.
    segment = next(obj for obj in document.Objects if segments.is_segment(obj))
    bounds = segments.segment_shape(segment).BoundBox
    camera = view.getCameraNode()
    camera.position.setValue(bounds.Center.x, bounds.Center.y, bounds.ZMax + 10000)
    camera.height.setValue(max(bounds.XLength, bounds.YLength) * 1.3)
    camera.nearDistance.setValue(1)
    camera.farDistance.setValue(20000)
    update(document)
    return view


def pick_local(document, segment, point):
    view = Gui.getDocument(document.Name).activeView()
    world = global_placement(deck_link(segment)).multVec(point)
    pixel = tuple(round(value) for value in view.getPointOnScreen(world))
    return pixel, view.getObjectInfo(pixel)


def assert_deck_face_pick(document, segment, point):
    pixel, hit = pick_local(document, segment, point)
    assert hit, 'clicking the plate interior must hit geometry'
    assert hit['Component'].startswith('Face'), hit
    assert decks.deck_from_pick(document.getObject(hit['Object'])) == segment, hit
    assert document.getObject(hit['Object']) == deck_link(segment), hit
    return pixel


class ClickCallback:
    """Only the Coin event wrapper is supplied; the view and picker are native."""

    def __init__(self, pixel):
        self.event = coin.SoMouseButtonEvent()
        self.event.setButton(coin.SoMouseButtonEvent.BUTTON1)
        self.event.setState(coin.SoButtonEvent.DOWN)
        self.event.setPosition(coin.SbVec2s(*pixel))
        self.handled = False

    def getEvent(self):
        return self.event

    def getAction(self):
        return self

    def setHandled(self):
        self.handled = True


def check_surface_click_and_independent_views(model):
    document = App.newDocument('SurfaceAutosnapCheck')
    panel = None
    try:
        segment = decks.insert_deck(document, model,
                                    decks.seed_placement(model, 0, 0, 300, 1), plan_view=True)
        view = configure_view(document)
        view_modes.show_mode(document, view, '2D')
        update(document)
        assert 'StageSnapPlanFaceVersion' not in deck_link(segment).PropertiesList, \
            'upgrade metadata belongs to the template, not a placed link forwarding its properties'
        center = App.Vector(model.length / 2, model.width / 2, model.depth)
        assert_deck_face_pick(document, segment, center)

        # Corners and frame keep their own nonempty 2D symbols and filters.
        for component in segments.components(segment):
            assert not component.StageSnapPlanTemplate.Shape.isNull()
        for role in ('Frames', 'Corners'):
            control_for(segment, role).Enabled = False
            update(document)
            assert_deck_face_pick(document, segment, center)
        control_for(segment, 'Decks').Enabled = False
        update(document)
        assert pick_local(document, segment, center)[1] is None, \
            'a hidden deck must not remain an invisible autosnap surface'
        control_for(segment, 'Decks').Enabled = True
        for role in ('Frames', 'Corners'):
            control_for(segment, role).Enabled = True
        update(document)

        # An interior point near the desired edge must reach the same picker
        # and deferred placement path used by a real autosnap mouse click.
        # Keep a face-test pixel outside the native pick radius of the
        # coplanar frame contour. Structured sources correctly render hardware
        # at the deck's world height, rather than below the plate.
        point = App.Vector(model.length - 100, model.width * .3, model.depth)
        pixel = assert_deck_face_pick(document, segment, point)
        panel = StageSnapDock(Gui.getMainWindow())
        panel.selected_deck = model
        panel.model_error = None
        panel.rotation.setCurrentIndex(1)
        panel.view = view
        panel.document_name = document.Name
        callback = ClickCallback(pixel)
        panel.on_click(callback)
        assert callback.handled and panel.pending is not None, panel.status.text()
        for _ in range(10):
            QtWidgets.QApplication.processEvents()
            if panel.pending is None:
                break
        placed = [obj for obj in document.Objects if segments.is_segment(obj)]
        assert len(placed) == 2, panel.status.text()
        other = next(obj for obj in placed if obj != segment)
        assert segments.segment_area(other) == segments.segment_area(segment)
        assert other.StageSnapPlanView
    finally:
        if panel is not None:
            panel.stop_snap()
            panel.close()
        App.closeDocument(document.Name)


def check_hardware_edge_click_at_the_deck_height(model):
    document = App.newDocument('HardwareEdgeAutosnapCheck')
    panel = None
    try:
        segment = decks.insert_deck(document, model,
                                    decks.seed_placement(model, 0, 0, 300, 1), plan_view=True)
        view = configure_view(document)
        view_modes.show_mode(document, view, '2D')
        control_for(segment, 'Decks').Enabled = False
        control_for(segment, 'Corners').Enabled = False
        update(document)
        point = App.Vector(model.length, model.width * .3, model.depth)
        pixel, hit = pick_local(document, segment, point)
        assert hit and hit['Component'].startswith('Edge'), 'the frame contour must be pickable'
        picked = document.getObject(hit['Object'])
        assert picked.StageSnapRole == 'PedestalFrame'
        assert decks.deck_from_pick(picked) == segment
        assert abs(hit['z'] - 300) < 1e-4, \
            'native frame rendering must use the same world height as the 2D deck'

        panel = StageSnapDock(Gui.getMainWindow())
        panel.selected_deck = model
        panel.model_error = None
        panel.rotation.setCurrentIndex(1)
        panel.view = view
        panel.document_name = document.Name
        callback = ClickCallback(pixel)
        panel.on_click(callback)
        assert callback.handled and panel.pending is not None, panel.status.text()
        for _ in range(10):
            QtWidgets.QApplication.processEvents()
            if panel.pending is None:
                break
        placed = [obj for obj in document.Objects if segments.is_segment(obj)]
        assert len(placed) == 2, panel.status.text()
        other = next(obj for obj in placed if obj != segment)
        assert segments.segment_area(other) == segments.segment_area(segment)
        assert other.StageSnapPlanView
    finally:
        if panel is not None:
            panel.stop_snap()
            panel.close()
        App.closeDocument(document.Name)


def check_embedded_wire_plan_upgrade(model):
    document = App.newDocument('EmbeddedWirePlanCheck')
    try:
        segment = decks.insert_deck(document, model,
                                    decks.seed_placement(model, 0, 0, 300, 1))
        link = deck_link(segment)
        template = link.StageSnapPlanTemplate
        template_name, link_name, segment_name = template.Name, link.Name, segment.Name
        original_3d = link.StageSnap3DTemplate.Shape.Volume
        with segments.updating():
            # Old detailed models stored four edges here, rather than a face.
            template.Shape = Part.Compound(template.Shape.Edges)
            if 'StageSnapPlanFaceVersion' in template.PropertiesList:
                template.removeProperty('StageSnapPlanFaceVersion')
            assert not template.Shape.Faces
            segment.StageSnapModelFile = 'missing-original-source.FCStd'
            document.recompute()
            with TemporaryDirectory() as temp:
                path = Path(temp) / 'LegacyWirePlan.FCStd'
                document.saveAs(str(path))
                App.closeDocument(document.Name)
                document = App.openDocument(str(path))
        segment = document.getObject(segment_name)
        segments.migrate_document(document)
        segments.set_segment_mode(segment, True)
        update(document)
        link = document.getObject(link_name)
        assert link.StageSnapPlanTemplate.Name == template_name
        assert 'StageSnapPlanFaceVersion' not in link.PropertiesList
        assert link.StageSnapPlanTemplate.Shape.Faces, \
            'embedded wire-only plates must upgrade without the original symbol file'
        assert abs(link.StageSnap3DTemplate.Shape.Volume - original_3d) < 1e-6
        configure_view(document)
        assert_deck_face_pick(document, segment,
                              App.Vector(model.length / 2, model.width / 2, model.depth))
    finally:
        App.closeDocument(document.Name)


try:
    path = next(decks.MODELS_DIR.rglob('Buetec_standard*.FCStd'))
    model = decks.deck_for_model('Test', path.relative_to(decks.MODELS_DIR).as_posix())
    check_surface_click_and_independent_views(model)
    check_hardware_edge_click_at_the_deck_height(model)
    check_embedded_wire_plan_upgrade(model)
    print('2D deck face picking, coplanar hardware edge height/picking, independent hardware views, real autosnap callbacks '
          'and source-independent embedded-wire upgrade passed.', flush=True)
finally:
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    Gui.getMainWindow().close()
