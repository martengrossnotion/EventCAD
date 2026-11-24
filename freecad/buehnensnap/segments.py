"""Placed segment hierarchy and reference-based visibility controls."""

from contextlib import contextmanager

import FreeCAD as App

from .plan_symbols import global_placement
from .symbol_structure import ROLES, CATEGORIES, GROUPS
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
    if is_segment(owner):
        return owner
    # Edited results and newly added accessories need no EventCAD properties.
    parent = obj.getParentGeoFeatureGroup() if obj is not None else None
    while parent is not None:
        if is_segment(parent):
            return parent
        parent = parent.getParentGeoFeatureGroup()
    return None


def segment_area(segment):
    return getattr(segment, 'StageSnapArea', None)


def segment_groups(segment):
    return [obj for obj in segment.Group
            if getattr(obj, 'StageSnapOwner', None) == segment
            and hasattr(obj, 'StageSnapGroupRole')]


def components(segment):
    result, seen = [], set()

    def collect(group):
        for obj in getattr(group, 'Group', ()):
            if obj.Name in seen:
                continue
            seen.add(obj.Name)
            if (obj.TypeId == 'App::Link' and getattr(obj, 'StageSnapOwner', None) == segment
                    and getattr(obj, 'StageSnapRole', None) in ROLES):
                result.append(obj)
            elif hasattr(obj, 'Group'):
                collect(obj)

    collect(segment)
    return result


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
    if area is None:
        return []
    views = next((obj for obj in area.Group if obj.Label == 'Views'
                  and getattr(obj, 'StageSnapViews', False)), None)
    return list(views.Group) if views is not None else []


def apply_visibility(segment):
    enabled = {obj.StageSnapViewRole: obj.Enabled for obj in controls(segment_area(segment))}
    with updating():
        for group in segment_groups(segment):
            group.Visibility = bool(group.StageSnapUserVisible
                                    and enabled.get(group.StageSnapGroupRole, True))


class VisibilityControl:
    def onChanged(self, obj, prop):
        if (prop != 'Enabled' or _updating or obj.Document.Restoring
                or not hasattr(obj, 'Members')):
            return
        # Older saved controls still reference component links.
        if any(not hasattr(member, 'StageSnapGroupRole') for member in obj.Members):
            migrate_document(obj.Document)
        with updating():
            obj.Visibility = obj.Enabled
            for group in obj.Members:
                group.Visibility = bool(obj.Enabled and group.StageSnapUserVisible)

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
    def slotActivateDocument(self, document):
        # FreeCAD 1.0 exposes no Python document-restored observer callback.
        # Its final activation happens after both document and GUI restoration.
        if not _updating and not document.Restoring:
            migrate_document(document)

    def slotBeforeRecomputeDocument(self, document):
        # Also cover hidden/headless documents, which need not be activated.
        if not _updating and not document.Restoring and any(
                (is_segment(obj) and len(segment_groups(obj)) != len(GROUPS))
                or _needs_deck_plan_upgrade(obj)
                for obj in document.Objects):
            migrate_document(document)

    def slotChangedObject(self, obj, prop):
        if _updating or prop != 'Visibility' or obj.Document.Restoring:
            return
        if getattr(obj, 'StageSnapOwner', None) is not None and hasattr(obj, 'StageSnapUserVisible'):
            with updating():
                obj.StageSnapUserVisible = obj.Visibility
            if hasattr(obj, 'StageSnapGroupRole'):
                apply_visibility(obj.StageSnapOwner)


def install_observer():
    global _observer
    if _observer is None:
        _observer = ComponentVisibilityObserver()
        App.addDocumentObserver(_observer)


class SegmentGroupView:
    """Native geometric group: one scene mask, independent child visibility.

    A normal DocumentObjectGroup propagates show/hide to every child. The
    geometric group extension instead hides its scene subtree as a whole.
    GeometryPython supplies a placement without adding an Origin per folder.
    """

    def attach(self, view):
        if not view.hasExtension('Gui::ViewProviderGeoFeatureGroupExtension'):
            view.addExtension('Gui::ViewProviderGeoFeatureGroupExtensionPython')

    def getIcon(self):
        return ':/icons/Group.svg'

    def getDefaultDisplayMode(self):
        return 'Group'

    def dumps(self):
        return None

    def loads(self, state):
        pass


def new_segment_group(segment, name, label, role):
    document = segment.Document
    group = document.addObject('App::GeometryPython', name)
    group.addExtension('App::GeoFeatureGroupExtensionPython')
    exact_label(group, label)
    group.addProperty('App::PropertyLinkHidden', 'StageSnapOwner', 'Podest')
    group.StageSnapOwner = segment
    group.addProperty('App::PropertyString', 'StageSnapGroupRole', 'Podest')
    group.StageSnapGroupRole = role
    group.addProperty('App::PropertyBool', 'StageSnapUserVisible', 'Podest')
    group.StageSnapUserVisible = True
    for prop in ('StageSnapOwner', 'StageSnapGroupRole'):
        group.setEditorMode(prop, 2)
    group.setEditorMode('Placement', 1)
    segment.addObject(group)
    if App.GuiUp:
        group.ViewObject.Proxy = SegmentGroupView()
    return group


def _reference_value(value, old, replacement):
    if value is old:
        return replacement
    if isinstance(value, list):
        return [_reference_value(item, old, replacement) for item in value]
    if isinstance(value, tuple):
        return tuple(_reference_value(item, old, replacement) for item in value)
    return value


def _migrate_group(segment, old, role):
    """Replace only a folder, retaining geometry, names, links and placements."""
    document = segment.Document
    name, label, label2 = old.Name, old.Label, old.Label2
    children, visible = list(old.Group), old.Visibility
    # Keep the internal name so expressions referencing the folder still work.
    # Parent Group lists are rebuilt separately: their old flattened geometry
    # entries must not move children out of the new geometric container again.
    reference_token = object()
    references, expressions = [], []
    reserved = {'ExpressionEngine', 'Group', 'Label', 'Label2', 'Visibility', '_GroupTouched',
                'Placement', 'StageSnapOwner', 'StageSnapGroupRole', 'StageSnapUserVisible'}
    properties = []
    for prop in old.PropertiesList:
        if prop not in reserved:
            prop_type = old.getTypeIdOfProperty(prop)
            choices = old.getEnumerationsOfProperty(prop) if prop_type == 'App::PropertyEnumeration' else None
            properties.append((prop_type, prop, old.getGroupOfProperty(prop),
                               old.getDocumentationOfProperty(prop),
                               _reference_value(getattr(old, prop), old, reference_token),
                               old.getEditorMode(prop), choices))
    own_expressions = list(old.ExpressionEngine)
    show_in_tree = old.ViewObject.ShowInTree if App.GuiUp else True
    for source in old.InList:
        if source == old:
            continue
        for prop in source.PropertiesList:
            if prop != 'Group' and 'Link' in source.getTypeIdOfProperty(prop):
                value = getattr(source, prop)
                references.append((source, prop, _reference_value(value, old, reference_token)))
        expressions.extend((source, path, expression) for path, expression in source.ExpressionEngine)
    old.Group = []
    document.removeObject(name)
    group = new_segment_group(segment, name, label, role)
    group.Label2 = label2
    group.StageSnapUserVisible = visible
    for prop_type, prop, section, description, value, editor_mode, choices in properties:
        group.addProperty(prop_type, prop, section, description)
        if choices is not None:
            setattr(group, prop, choices)
        setattr(group, prop, _reference_value(value, reference_token, group))
        group.setEditorMode(prop, editor_mode)
    for path, expression in own_expressions:
        group.setExpression(path, expression)
    if App.GuiUp:
        group.ViewObject.ShowInTree = show_in_tree
    for child in children:
        placement = global_placement(child) if hasattr(child, 'Placement') else None
        group.addObject(child)
        if placement is not None:
            child.Placement = global_placement(group).inverse() * placement
        # Old view filters wrote Enabled into each link. Recover its real
        # individual state before replacing that behavior with a parent mask.
        if (getattr(child, 'StageSnapOwner', None) == segment
                and hasattr(child, 'StageSnapUserVisible') and child.TypeId == 'App::Link'):
            child.Visibility = child.StageSnapUserVisible
    for source, prop, value in references:
        setattr(source, prop, _reference_value(value, reference_token, group))
    for source, path, expression in expressions:
        source.setExpression(path, expression)
    return group


def ensure_segment_groups(segment):
    ordered = []
    for name, label, role in GROUPS:
        group = next((obj for obj in segment_groups(segment)
                      if obj.StageSnapGroupRole == role), None)
        if group is None:
            old = next((obj for obj in segment.Group
                        if obj.TypeId == 'App::DocumentObjectGroup' and obj.Label == label), None)
            if old is None and role in CATEGORIES:
                old = next((obj for obj in segment.Group if obj.TypeId == 'App::DocumentObjectGroup'
                            and any(getattr(child, 'StageSnapOwner', None) == segment
                                    and getattr(child, 'StageSnapRole', None) in CATEGORIES[role]
                                    for child in obj.Group)), None)
            group = _migrate_group(segment, old, role) if old is not None else new_segment_group(
                segment, name, label, role)
        if App.GuiUp and not group.ViewObject.hasExtension('Gui::ViewProviderGeoFeatureGroupExtension'):
            group.ViewObject.Proxy = SegmentGroupView()
        ordered.append(group)
    desired = [*ordered, *[obj for obj in segment.Group if obj not in ordered]]
    if list(segment.Group) != desired:
        segment.Group = desired


def refresh_members(area):
    if area is None:
        return
    segments = [obj for obj in area.Group if is_segment(obj)]
    for control in controls(area):
        members = [group for segment in segments for group in segment_groups(segment)
                   if group.StageSnapGroupRole == control.StageSnapViewRole]
        if list(control.Members) != members:
            control.Members = members


def migrate_document(document):
    """Upgrade v2.0 folders lazily/on restore; never replace their geometry."""
    placed = [obj for obj in document.Objects if is_segment(obj)]
    with updating():
        upgrade_deck_plan_templates(document)
        for segment in placed:
            ensure_segment_groups(segment)
        for area in {segment_area(segment) for segment in placed} - {None}:
            refresh_members(area)
        for segment in placed:
            apply_visibility(segment)


def _needs_deck_plan_upgrade(obj):
    # App::Link forwards these properties from its target as well. Upgrade
    # only the embedded template itself, never the placed link instance.
    return (obj is not None and obj.TypeId == 'Part::Feature'
            and getattr(obj, 'StageSnapRole', None) == 'PedestalDeck'
            and getattr(obj, 'StageSnapVariant', None) == 'Symbol2D'
            and hasattr(obj, 'StageSnapComponentKey')
            and getattr(obj, 'StageSnapPlanFaceVersion', 0) < 1)


def _mark_deck_plan_surface(template):
    if 'StageSnapPlanFaceVersion' not in template.PropertiesList:
        template.addProperty('App::PropertyInteger', 'StageSnapPlanFaceVersion', 'Podest')
        template.setEditorMode('StageSnapPlanFaceVersion', 2)
    template.StageSnapPlanFaceVersion = 1


def upgrade_deck_plan_templates(document, links=None):
    """Fill old shared deck outlines in place, without their source FCStd file.

    Preserve the existing contour, holes, open detail lines, link identities,
    placements and visibility. Frame/corner templates are never changed.
    """
    from .component_models import fill_plan_contours, deck_surface_materials
    if links is None:
        sources = {obj.StageSnapComponentKey: obj for obj in document.Objects
                   if obj.TypeId == 'Part::Feature'
                   and getattr(obj, 'StageSnapRole', None) == 'PedestalDeck'
                   and getattr(obj, 'StageSnapVariant', None) == 'Symbol3D'
                   and hasattr(obj, 'StageSnapComponentKey')}
        pairs = {obj: sources.get(obj.StageSnapComponentKey) for obj in document.Objects
                 if _needs_deck_plan_upgrade(obj)}
    else:
        pairs = {obj.StageSnapPlanTemplate: obj.StageSnap3DTemplate for obj in links
                 if obj.StageSnapRole == 'PedestalDeck'
                 and _needs_deck_plan_upgrade(obj.StageSnapPlanTemplate)}
    with updating():
        for template, source in pairs.items():
            before = template.Shape
            filled = fill_plan_contours(before)
            if not before.Faces and filled.Faces:
                template.Shape = filled
                if App.GuiUp:
                    if source is not None:
                        materials = deck_surface_materials(
                            filled, source.Shape, source.ViewObject.ShapeAppearance)
                        if materials:
                            template.ViewObject.ShapeAppearance = materials
                    else:
                        from .appearance import apply_default_materials
                        apply_default_materials(template, plan_view=True)
            _mark_deck_plan_surface(template)


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
        upgrade_deck_plan_templates(document)
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
            if role == 'PedestalDeck' and variant == 'Symbol2D':
                _mark_deck_plan_surface(template)
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
        ensure_segment_groups(segment)
        refresh_members(segment_area(segment))
        links = components(segment)
        upgrade_deck_plan_templates(segment.Document, links)
        for obj in links:
            target = obj.StageSnapPlanTemplate if plan_view else obj.StageSnap3DTemplate
            if obj.LinkedObject != target:
                placement = obj.Placement.copy()
                visible = obj.Visibility
                obj.setLink(target)
                obj.LinkTransform = False
                obj.Placement = placement
                obj.Visibility = visible
        segment.StageSnapPlanView = plan_view
    apply_visibility(segment)


def create_segment(document, deck, placement, plan_view=False, target=None):
    install_observer()
    with updating():
        migrate_document(document)
        return _create_segment(document, deck, placement, plan_view, target)


def _create_segment(document, deck, placement, plan_view, target):
    from .decks import DECK_KIND, area_for_snap
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
        for name, label, category in GROUPS:
            group = new_segment_group(segment, name, label, category)
            for role in CATEGORIES.get(category, ()):
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
                obj.Visibility = True
                for prop, variant in [('StageSnap3DTemplate', 'Symbol3D'),
                                      ('StageSnapPlanTemplate', 'Symbol2D')]:
                    obj.addProperty('App::PropertyLinkGlobal', prop, 'Podest')
                    setattr(obj, prop, templates[role, variant])
                    obj.setEditorMode(prop, 2)
                obj.setEditorMode('Placement', 1)
        refresh_members(area)
    set_segment_mode(segment, plan_view)
    return segment


install_observer()
for _document in list(App.listDocuments().values()):
    if not _document.Restoring:
        migrate_document(_document)
