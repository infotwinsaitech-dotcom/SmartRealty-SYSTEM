from .models import SiteSettings

def site_settings(request):
    settings = SiteSettings.objects.first()
    return {
        'site': settings
    }
from .models import Notification

def notification_count(request):
    count = Notification.objects.filter(is_read=False).count()
    return {"notifications_unread_count": count}

def footer_locality_links(request):
    """
    Cheap, static (no DB query) list of locality links for the site-wide
    footer's 'Top Localities in Ahmedabad' column.
    """
    from .seo_data import TRENDING_LOCALITY_SEED, get_area_slug
    return {
        "footer_top_localities": [
            {"name": a, "slug": get_area_slug(a)}
            for a in TRENDING_LOCALITY_SEED[:8]
        ]
    }