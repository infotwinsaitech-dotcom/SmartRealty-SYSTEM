from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Core App URLs
    path('', include('core.urls')),

    # WhatsApp Bot
    path('whatsapp/', views.whatsapp_bot, name='whatsapp_bot'),

    # Agent Performance
    path(
        'builder/agents-performance/',
        views.agent_performance,
        name='agent_performance'
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )