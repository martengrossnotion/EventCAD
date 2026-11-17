"""Placed segment hierarchy and reference-based visibility controls."""

from contextlib import contextmanager

import FreeCAD as App

from .plan_symbols import global_placement

ROLES = ('CornerTL', 'CornerTR', 'CornerBL', 'CornerBR', 'PedestalFrame', 'PedestalDeck')
CATEGORIES = {'Corners': ROLES[:4], 'Frames': ('PedestalFrame',), 'Decks': ('PedestalDeck',)}
_updating = 0
_observer = None


def exact_label(obj, label):
    """Set repeated folder/part labels without changing the user's preference."""
    params = App.ParamGet('User parameter:BaseApp/Preferences/Document')
    previous = params.GetBool('DuplicateLabels', False)
    try:
        params.SetBool('DuplicateLabels', True)
        obj.Label = label
    finally:
        params.SetBool('DuplicateLabels', previous)


@contextmanager
def updating():
    global _updating
    _updating += 1
    try:
        yield
    finally:
        _updating -= 1


def is_segment(obj):
    return obj is not None and bool(getattr(obj, 'StageSnapSegment', False))


def segment_from_pick(obj):
    if is_segment(obj):
        return obj
    owner = getattr(obj, 'StageSnapOwner', None) if obj is not None else None
    return owner if is_segment(owner) else None


def segment_area(segment):
    return getattr(segment, 'StageSnapArea', None)


def components(segment):
    return [child for group in segment.Group if group.TypeId == 'App::DocumentObjectGroup'
            for child in getattr(group, 'Group', ())
            if getattr(child, 'StageSnapOwner', None) == segment]


def segment_shape(segment):
    """Aggregate each component once (App::Part may list nested links twice)."""
    if not is_segment(segment):
        return segment.Shape
    import Part
    shapes = []
    for obj in components(segment):
        if obj.LinkedObject.Shape.isNull():
            continue
        shape = obj.LinkedObject.Shape.copy()
        shape.Placement = global_placement(obj) * shape.Placement
        shapes.append(shape)
    return Part.Compound(shapes) if shapes else Part.Shape()


def controls(area):
    views = next((obj for obj in area.Group if obj.Label == 'Views'
                  and getattr(obj, 'StageSnapViews', False)), None)
    return list(views.Group) if views is not None else []


def apply_visibility(segment):
    if not App.GuiUp:
        return
    enabled = {obj.StageSnapViewRole: obj.Enabled for obj in controls(segment_area(segment))}
    with updating():
        for obj in components(segment):
            category = next(key for key, roles in CATEGORIES.items() if obj.StageSnapRole in roles)
            template = obj.LinkedObject
            available = template is not None and not template.Shape.isNull()
            obj.ViewObject.Visibility = bool(obj.StageSnapUserVisible
                                              and enabled.get(category, True) and available)


class VisibilityControl:
    def onChanged(self, obj, prop):
        if prop != 'Enabled' or _updating or not hasattr(obj, 'Members'):
            return
        if App.GuiUp:
            with updating():
                obj.ViewObject.Visibility = obj.Enabled
        owners = {member.StageSnapOwner for member in obj.Members
                  if getattr(member, 'StageSnapOwner', None) is not None}
        for owner in owners:
            apply_visibility(owner)

    def execute(self, obj):
        pass


class VisibilityControlView:
    def __init__(self, view):
        view.Proxy = self

    def getIcon(self):
        return ':/icons/Group.svg'

    def claimChildren(self):
        # Members stay exclusively under their physical segment.
        return []

    def onChanged(self, view, prop):
        if prop == 'Visibility' and not _updating:
            obj = view.Object
            if hasattr(obj, 'Enabled') and obj.Enabled != view.Visibility:
                obj.Enabled = view.Visibility

    def attach(self, view):
        from pivy import coin
        view.addDisplayMode(coin.SoGroup(), 'Group')

    def getDisplayModes(self, view):
        return ['Group']

    def getDefaultDisplayMode(self):
        return 'Group'

    def dumps(self):
        return None

    def loads(self, state):
        pass


class ComponentVisibilityObserver:
    def slotChangedObject(self, view, prop):
        if _updating or prop != 'Visibility':
            return
        try:
            obj = view.Object
        except (ReferenceError, RuntimeError):
            return
        if getattr(obj, 'StageSnapOwner', None) is not None and hasattr(obj, 'StageSnapUserVisible'):
            with updating():
                obj.StageSnapUserVisible = view.Visibility
            apply_visibility(obj.StageSnapOwner)


def install_observer():
    global _observer
    if App.GuiUp and _observer is None:
        import FreeCADGui as Gui
        _observer = ComponentVisibilityObserver()
        Gui.addDocumentObserver(_observer)


def new_group(document, name, parent, label=None):
    group = document.addObject('App::DocumentObjectGroup', name)
    exact_label(group, label or name)
    parent.addObject(group)
    return group


def ensure_views(area):
    existing = controls(area)
    if existing:
        return existing
    document = area.Document
    views = new_group(document, 'Views', area)
    views.addProperty('App::PropertyBool', 'StageSnapViews', 'Podest')
    views.StageSnapViews = True
    views.setEditorMode('StageSnapViews', 2)
    for category in ('Decks', 'Corners', 'Frames'):
        obj = document.addObject('App::FeaturePython', 'View' + category)
        exact_label(obj, 'View' + category)
        obj.addProperty('App::PropertyString', 'StageSnapViewRole', 'Podest')
        obj.StageSnapViewRole = category
        obj.setEditorMode('StageSnapViewRole', 2)
        obj.addProperty('App::PropertyLinkListHidden', 'Members', 'Podest')
        obj.setEditorMode('Members', 2)
        obj.addProperty('App::PropertyBool', 'Enabled', 'Podest')
        obj.Enabled = True
        obj.Proxy = VisibilityControl()
        views.addObject(obj)
        if App.GuiUp:
            VisibilityControlView(obj.ViewObject)
            with updating():
                obj.ViewObject.DisplayMode = 'Group'
                obj.ViewObject.Visibility = True
    area.Group = [views, *[obj for obj in area.Group if obj != views]]
    return controls(area)


def create_area(document):
    from .decks import AREA_NUMBER_KEY
    number = max(int(document.Meta.get(AREA_NUMBER_KEY, '0')),
                 max((getattr(obj, 'StageSnapAreaNumber', 0) for obj in document.Objects), default=0)) + 1
    while document.getObjectsByLabel(f'Podestfläche {number}'):
        number += 1
    area = document.addObject('App::DocumentObjectGroup', 'Podestflaeche')
    area.Label = f'Podestfläche {number}'
    area.addProperty('App::PropertyInteger', 'StageSnapAreaNumber', 'Podest')
    area.StageSnapAreaNumber = number
    area.setEditorMode('StageSnapAreaNumber', 1)
    document.Meta = {**document.Meta, AREA_NUMBER_KEY: str(number)}
    ensure_views(area)
    return area


def component_templates(document, deck):
    from .decks import MODELS_DIR, template_group
    from .component_models import component_specs
    path = MODELS_DIR / deck.model_file if deck.model_file else None
    revision = (str(path.resolve()), path.stat().st_mtime_ns, path.stat().st_size) if path else ('custom',)
    key = repr((revision, deck.dimensions))
    existing = {(obj.StageSnapRole, obj.StageSnapVariant): obj for obj in document.Objects
                if obj.TypeId == 'Part::Feature'
                and getattr(obj, 'StageSnapComponentKey', None) == key}
    if len(existing) == 12:
        return existing
    specs = component_specs(deck, path)
    library = template_group(document)
    if App.GuiUp:
        library.ViewObject.ShowInTree = False
    for role in ROLES:
        shape3d, shape2d, materials3d, materials2d = specs[role]
        for variant, shape, materials in [('Symbol3D', shape3d, materials3d),
                                          ('Symbol2D', shape2d, materials2d)]:
            template = document.addObject('Part::Feature', 'Template' + role + variant[-2:])
            template.Label = f'{deck.label} · {role} · {variant[-2:]}'
            template.Shape = shape
            for prop, value in [('StageSnapComponentKey', key), ('StageSnapRole', role),
                                ('StageSnapVariant', variant)]:
                template.addProperty('App::PropertyString', prop, 'Podest')
                setattr(template, prop, value)
                template.setEditorMode(prop, 2)
            library.addObject(template)
            if App.GuiUp:
                if materials:
                    template.ViewObject.ShapeAppearance = materials
                template.ViewObject.LineColor = (0.23, 0.19, 0.14)
                template.ViewObject.Visibility = False
            existing[role, variant] = template
    return existing


def set_segment_mode(segment, plan_view):
    with updating():
        for obj in components(segment):
            target = obj.StageSnapPlanTemplate if plan_view else obj.StageSnap3DTemplate
            if obj.LinkedObject != target:
                placement = obj.Placement.copy()
                obj.setLink(target)
                obj.LinkTransform = False
                obj.Placement = placement
        segment.StageSnapPlanView = plan_view
    apply_visibility(segment)


def create_segment(document, deck, placement, plan_view=False, target=None):
    from .decks import DECK_KIND, area_for_snap
    install_observer()
    templates = component_templates(document, deck)
    area = area_for_snap(document, target) if target is not None else create_area(document)
    ensure_views(area)
    number = max((getattr(obj, 'StageSnapSegmentNumber', 0) for obj in area.Group), default=0) + 1
    segment = document.addObject('App::Part', 'Podestsegment')
    exact_label(segment, f'Podestsegment {number:03d}')
    for prop in ('StageSnapSegment', 'StageSnapPlanView'):
        segment.addProperty('App::PropertyBool', prop, 'Podest')
        segment.setEditorMode(prop, 2)
    segment.StageSnapSegment = True
    segment.addProperty('App::PropertyInteger', 'StageSnapSegmentNumber', 'Podest')
    segment.StageSnapSegmentNumber = number
    segment.setEditorMode('StageSnapSegmentNumber', 2)
    segment.addProperty('App::PropertyLinkHidden', 'StageSnapArea', 'Podest')
    segment.StageSnapArea = area
    segment.setEditorMode('StageSnapArea', 2)
    for prop, value in [('StageSnapKind', DECK_KIND), ('StageSnapCatalogId', deck.catalog_id),
                        ('StageSnapModelFile', deck.model_file or '')]:
        segment.addProperty('App::PropertyString', prop, 'Podest')
        setattr(segment, prop, value)
        segment.setEditorMode(prop, 1)
    for name, value in zip(('Length', 'Width', 'Height'), deck.dimensions):
        segment.addProperty('App::PropertyLength', name, 'Podest')
        setattr(segment, name, value)
        segment.setEditorMode(name, 1)
    area.addObject(segment)
    container = segment.getParentGeoFeatureGroup()
    segment.Placement = global_placement(container).inverse() * placement if container else placement
    if App.GuiUp:
        segment.Origin.ViewObject.ShowInTree = False
    with updating():
        for label, roles in [('Corners', ROLES[:4]), ('Frame', ('PedestalFrame',)),
                              ('Deck', ('PedestalDeck',))]:
            group = new_group(document, label, segment)
            for role in roles:
                obj = document.addObject('App::Link', role)
                exact_label(obj, role)
                obj.setLink(templates[role, 'Symbol3D'])
                obj.LinkTransform = False
                group.addObject(obj)
                obj.addProperty('App::PropertyLinkHidden', 'StageSnapOwner', 'Podest')
                obj.StageSnapOwner = segment
                obj.setEditorMode('StageSnapOwner', 2)
                obj.addProperty('App::PropertyString', 'StageSnapRole', 'Podest')
                obj.StageSnapRole = role
                obj.setEditorMode('StageSnapRole', 2)
                obj.addProperty('App::PropertyBool', 'StageSnapUserVisible', 'Podest')
                obj.StageSnapUserVisible = True
                for prop, variant in [('StageSnap3DTemplate', 'Symbol3D'),
                                      ('StageSnapPlanTemplate', 'Symbol2D')]:
                    obj.addProperty('App::PropertyLinkGlobal', prop, 'Podest')
                    setattr(obj, prop, templates[role, variant])
                    obj.setEditorMode(prop, 2)
                obj.setEditorMode('Placement', 1)
        for control in controls(area):
            control.Members = [*control.Members, *[obj for obj in components(segment)
                               if obj.StageSnapRole in CATEGORIES[control.StageSnapViewRole]]]
    set_segment_mode(segment, plan_view)
    return segment


install_observer()
