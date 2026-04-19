from django.contrib import admin
from django.urls import path, include   # ⚠️ include जरूरी है
from django.conf import settings
from django.conf.urls.static import static
from core import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), 
    path('', views.home, name='home'),  # ✅ यही सही है
    path('builder/agents-performance/', views.agent_performance, name='agent_performance'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)