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
            return value

    except:
        return value