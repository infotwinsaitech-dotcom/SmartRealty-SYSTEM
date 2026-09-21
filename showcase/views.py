from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .models import ShowcaseViewer


@never_cache
@login_required(login_url="/login/")
def dashboard(request):
    """
    Sirf wahi user dekh sakta hai jiska ShowcaseViewer bana hai.
    Baaki sab (builder / agent / normal user / admin) ko 404 milega,
    taaki is page ka pata hi na chale.
    """
    viewer = (
        ShowcaseViewer.objects.filter(user=request.user, is_active=True)
        .select_related("user")
        .first()
    )
    if viewer is None:
        raise Http404()

    response = render(request, "showcase/dashboard.html", {"viewer": viewer})
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
