from django import template

register = template.Library()


@register.filter(name='format_price')
def format_price(value):
    try:
        value = float(value)
        if value >= 10000000:
            return f"{value/10000000:.1f} Cr"
        elif value >= 100000:
            return f"{value/100000:.0f} Lakh"
        else:
            return str(value)
    except Exception:
        return value


@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0
    
@register.filter(name='feature_label')
def feature_label(value):
    """
    Turns a feature flag like 'whatsapp_alerts' into 'Whatsapp Alerts'.
    Django filters can only take ONE argument, so a Python-style
    `|replace:"_"," "` is invalid syntax (that's what was crashing pricing.html
    with 'Invalid filter: replace'). Use this instead: {{ feature|feature_label }}
    """
    try:
        return str(value).replace('_', ' ').title()
    except Exception:
        return value


@register.filter
def get_item(dictionary, key):
    """Dictionary se key se value nikalo: {{ mydict|get_item:plan.id }}"""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None
    
@register.filter(name='split')
def split(value, arg):
    """Split a string by delimiter: {{ "a,b,c"|split:"," }}"""
    if value is None:
        return []
    try:
        return str(value).split(arg)
    except Exception:
        return []

AMENITY_ICON_MAP = [
    (('parking',), 'local_parking'),
    (('lift', 'elevator'), 'elevator'),
    (('gym', 'fitness'), 'fitness_center'),
    (('pool', 'swim'), 'pool'),
    (('security', 'guard', 'cctv', 'camera'), 'security'),
    (('garden', 'lawn'), 'park'),
    (('club',), 'groups'),
    (('power', 'backup', 'generator'), 'bolt'),
    (('water',), 'water_drop'),
    (('play', 'kids'), 'toys'),
    (('jog', 'track', 'walk'), 'directions_walk'),
    (('wifi', 'internet'), 'wifi'),
    (('fire',), 'local_fire_department'),
    (('temple', 'mandir', 'worship'), 'temple_hindu'),
    (('store', 'shop', 'market', 'super'), 'storefront'),
    (('school',), 'school'),
    (('hospital', 'clinic', 'medical'), 'local_hospital'),
    (('yoga', 'meditation'), 'self_improvement'),
    (('sport', 'badminton', 'tennis', 'court'), 'sports_tennis'),
    (('spa', 'sauna'), 'spa'),
    (('lounge', 'hall', 'banquet'), 'celebration'),
    (('solar',), 'solar_power'),
    (('vaastu', 'vastu'), 'architecture'),
    (('senior', 'citizen'), 'elderly'),
    (('intercom',), 'call'),
]

@register.filter
def amenity_icon(name):
    """Amenity ka naam dekh ke sahi icon return karta hai: {{ item|amenity_icon }}"""
    if not name:
        return 'check_circle'
    n = str(name).lower()
    for keywords, icon in AMENITY_ICON_MAP:
        if any(k in n for k in keywords):
            return icon
    return 'check_circle'


NEARBY_ICON_MAP = [
    (('school', 'college', 'university'), 'school'),
    (('hospital', 'clinic', 'medical'), 'local_hospital'),
    (('metro', 'train', 'railway'), 'train'),
    (('mall', 'shop', 'market', 'store'), 'shopping_bag'),
    (('airport', 'flight'), 'flight'),
    (('bus',), 'directions_bus'),
    (('park', 'garden'), 'park'),
    (('bank', 'atm'), 'account_balance'),
    (('restaurant', 'cafe', 'food'), 'restaurant'),
    (('highway', 'road'), 'add_road'),
    (('temple', 'mandir', 'church', 'mosque'), 'temple_hindu'),
    (('gym', 'fitness'), 'fitness_center'),
    (('police',), 'local_police'),
    (('petrol', 'fuel', 'gas'), 'local_gas_station'),
]

NEARBY_EMOJI = {
    'school': '🏫', 'local_hospital': '🏥', 'train': '🚇',
    'shopping_bag': '🛍️', 'flight': '✈️', 'directions_railway': '🚉',
    'directions_bus': '🚌', 'park': '🌳', 'account_balance': '🏦',
    'restaurant': '🍽️', 'atm': '🏧', 'add_road': '🛣️',
    'temple_hindu': '🛕', 'fitness_center': '🏋️', 'local_police': '🚓',
    'local_gas_station': '⛽',
}

@register.filter
def nearby_icon(place):
    """Nearby place dict ({'name':..,'icon':..}) se emoji nikalta hai: {{ place|nearby_icon }}"""
    try:
        icon = (place.get('icon') or '').strip().lower()
        name = (place.get('name') or '').strip().lower()
    except AttributeError:
        return '📍'
    if icon in NEARBY_EMOJI:
        return NEARBY_EMOJI[icon]
    for keywords, mapped_icon in NEARBY_ICON_MAP:
        if any(k in name for k in keywords):
            return NEARBY_EMOJI.get(mapped_icon, '📍')
    return '📍'