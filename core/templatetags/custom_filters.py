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