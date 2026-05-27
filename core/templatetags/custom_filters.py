from django import template

register = template.Library()

@register.filter
def format_price(value):
    try:
        value = float(value)

        if value >= 10000000:
            return f"{round(value/10000000, 2)} Cr"
        elif value >= 100000:
            return f"{round(value/100000, 2)} Lakh"
        else:
            return f"{int(value)}"
    except:
        return value