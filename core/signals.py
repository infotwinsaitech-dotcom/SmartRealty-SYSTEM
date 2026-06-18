from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Agent

@receiver(post_save, sender=User)
def auto_create_agent(sender, instance, created, **kwargs):
    if created and instance.role == "agent":
        agent, _ = Agent.objects.get_or_create(
            user=instance,
            defaults={
                "name": instance.username,
                "email": instance.email,
                "phone": getattr(instance, "phone", ""),
            }
        )

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Lead, Deal, FollowUp, Task


def invalidate_dashboard_cache(user_id):
    """Delete all dashboard cache keys for a user"""
    # DatabaseCache mein pattern delete nahi hota
    # Isliye specific keys delete karte hain
    # Note: Production mein Redis ho toh pattern delete possible hai
    cache.delete(f"dashboard_v2:{user_id}:*")
    cache.delete(f"growth:{user_id}:*")


@receiver(post_save, sender=Lead)
@receiver(post_delete, sender=Lead)
def invalidate_lead_cache(sender, instance, **kwargs):
    """Jab lead add/update/delete ho toh cache clear karo"""
    if instance.builder:
        invalidate_dashboard_cache(instance.builder.id)


@receiver(post_save, sender=Deal)
@receiver(post_delete, sender=Deal)
def invalidate_deal_cache(sender, instance, **kwargs):
    """Jab deal add/update/delete ho toh cache clear karo"""
    if instance.builder:
        invalidate_dashboard_cache(instance.builder.id)


@receiver(post_save, sender=FollowUp)
@receiver(post_delete, sender=FollowUp)
def invalidate_followup_cache(sender, instance, **kwargs):
    """Jab followup add/update/delete ho toh cache clear karo"""
    if instance.lead and instance.lead.builder:
        invalidate_dashboard_cache(instance.lead.builder.id)


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def invalidate_task_cache(sender, instance, **kwargs):
    """Jab task add/update/delete ho toh cache clear karo"""
    if instance.user:
        invalidate_dashboard_cache(instance.user.id)

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site

def create_social_app():
    """Auto-create Google SocialApp if credentials exist"""
    from django.conf import settings
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    secret = getattr(settings, 'GOOGLE_SECRET', '')
    
    if not client_id or not secret:
        return
    
    site = Site.objects.get_or_create(pk=1, defaults={'domain': 'smartrealty-system.onrender.com', 'name': 'SmartRealty'})[0]
    
    SocialApp.objects.get_or_create(
        provider='google',
        defaults={
            'name': 'Google',
            'client_id': client_id,
            'secret': secret,
        }
    ).sites.add(site)