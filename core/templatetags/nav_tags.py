from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def nav_class(context, url_name):
    request = context.get('request')

    # safety check
    if not request or not hasattr(request, 'resolver_match'):
        return "text-slate-400 hover:text-white hover:bg-slate-800/50"

    current_url = request.resolver_match.url_name

    if current_url == url_name:
        return "bg-[#1E3A8A] text-white"

    return "text-slate-400 hover:text-white hover:bg-slate-800/50"

register = template.Library()

@register.simple_tag
def is_active(request, url):
    if request.path == url:
        return "bg-[#1E3A8A] text-white"
    return "text-slate-400 hover:text-white hover:bg-slate-800/50"