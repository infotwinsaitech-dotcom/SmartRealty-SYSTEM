# core/templatetags/social_safe.py
from django import template
from allauth.socialaccount.models import SocialApp
from django.core.exceptions import MultipleObjectsReturned

register = template.Library()


@register.simple_tag
def get_google_login_url():
    """Safe Google login URL — handles MultipleObjectsReturned"""
    try:
        app = SocialApp.objects.filter(provider='google').first()
        if app:
            return f"/accounts/google/login/?process=login"
        return ""
    except MultipleObjectsReturned:
        # Multiple apps exist — use first one
        app = SocialApp.objects.filter(provider='google').first()
        if app:
            return f"/accounts/google/login/?process=login"
        return ""
    except Exception:
        return ""