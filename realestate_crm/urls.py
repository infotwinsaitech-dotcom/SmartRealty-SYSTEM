from django.contrib import admin
from django.urls import path, include   # ⚠️ include जरूरी है
from django.conf import settings
from django.conf.urls.static import static
from core import views
from .views import whatsapp_bot

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), 
    path('', views.home, name='home'),  # ✅ यही सही है
    path('builder/agents-performance/', views.agent_performance, name='agent_performance'),
    path("whatsapp/", whatsapp_bot),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)