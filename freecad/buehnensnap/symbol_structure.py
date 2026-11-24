"""The component tree shared by native symbol files and placed segments."""

ROLES = ('CornerTL', 'CornerTR', 'CornerBL', 'CornerBR', 'PedestalFrame', 'PedestalDeck')
CATEGORIES = {'Corners': ROLES[:4], 'Frames': ('PedestalFrame',), 'Decks': ('PedestalDeck',)}
GROUPS = (('Corners', 'Corners', 'Corners'), ('Frame', 'Frame', 'Frames'),
          ('Deck', 'Deck', 'Decks'), ('Verbinder', 'Verbinder', 'Connectors'),
          ('Steckfuesse', 'Steckfüße', 'Legs'), ('Gelaender', 'Geländer', 'Railings'))


def _child(parent, names, description):
    matches = [obj for obj in parent.Group if obj.Name in names or obj.Label in names]
    if len(matches) != 1:
        raise ValueError(f'{description}: genau ein passendes Objekt erforderlich; '
                         f'gefunden: {len(matches)}.')
    return matches[0]


def variant_components(root):
    """Resolve explicit leaves within a variant, never infer roles from solids.

    Native variant containers have the same six folders as a placed segment.
    Null component shapes are deliberate placeholders for simplified symbols.
    Unsupported contents are rejected rather than silently dropped on import.
    Legacy monolithic features are handled separately by the caller.
    """
    if not hasattr(root, 'Group') or root.isDerivedFrom('PartDesign::Body'):
        return None
    result, groups = {}, []
    for name, label, category in GROUPS:
        group = _child(root, (name, label), f'{root.Label}/{label}')
        if not hasattr(group, 'Group'):
            raise ValueError(f'{root.Label}/{label} muss eine Gruppe sein.')
        groups.append(group)
        members = []
        for role in CATEGORIES.get(category, ()):
            obj = _child(group, (role, role + '2D'), f'{root.Label}/{label}/{role}')
            if not hasattr(obj, 'Shape'):
                raise ValueError(f'{role} muss ein Objekt mit fertiger Shape sein.')
            members.append(obj)
            result[role] = obj
        if set(group.Group) != set(members):
            raise ValueError(f'{root.Label}/{label}: nicht unterstützte Gruppeninhalte. '
                             'Jedes Bauteil muss einer vorgesehenen Komponente entsprechen.')
    if len(set(result.values())) != len(ROLES):
        raise ValueError(f'{root.Label}: Jede Komponentenrolle benötigt ein eigenes Objekt.')
    # App::Part also registers leaves of ordinary folders in its own Group.
    # They are the same objects, not additional root-level component instances.
    if set(root.Group) - set(groups) - set(result.values()):
        raise ValueError(f'{root.Label}: Bauteile müssen in den sechs Komponentengruppen liegen.')
    return result
