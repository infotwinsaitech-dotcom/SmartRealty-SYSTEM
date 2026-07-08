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
    
@register.filter
def get_item(dictionary, key):
    """Dictionary se key se value nikalo: {{ mydict|get_item:plan.id }}"""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None