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
    path('auth/redirect/', views.google_login_redirect, name='google_redirect'),
     path('accounts/', include('allauth.urls')),
     path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('plans/', include('subscriptions.urls')), 
    
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
    handler404 = "core.views.custom_404"