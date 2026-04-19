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