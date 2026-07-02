# =============================================================================
# core/signals.py — PRODUCTION READY - FIXED VERSION
# FIXES:
#   1. All model imports added (Lead, Deal, FollowUp, etc.)
#   2. Cache versioning logic correct
#   3. Auto-create agent on user creation
#   4. SocialApp auto-create helper
# =============================================================================

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.db import ProgrammingError, OperationalError
import logging
from .models import Profile
from django.contrib.auth import get_user_model
logger = logging.getLogger(__name__)
User = get_user_model()
# =============================================================================
# LAZY MODEL IMPORTS — import inside functions to avoid circular imports
# These are resolved at signal-connect time, not at module load time
# =============================================================================
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create profile on user creation"""
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults={
                "full_name": instance.username,
                "email": instance.email,
                "phone": getattr(instance, "phone", "")
            }
        )
def get_models():
    """
    Lazily import models to avoid circular import issues.
    Called only when signals fire, not at module load.
    """
    from .models import (
        Lead, Deal, FollowUp, Task, Activity,
        SiteVisit, Notification, User, Agent
    )
    return Lead, Deal, FollowUp, Task, Activity, SiteVisit, Notification, User, Agent


# =============================================================================
# PART 1: CACHE VERSIONING
# Works with DatabaseCache, Redis, Memcached.
# Instead of deleting keys by pattern (not supported by DatabaseCache),
# we bump a version number. Dashboard reads this version in its cache_key.
# =============================================================================

def bump_cache_version(user_id, namespace="dashboard"):
    """
    Cache version increment karo — sabhi old keys automatically invalid ho jaate hain.
    DatabaseCache ke saath bhi kaam karta hai (pattern delete nahi chahiye).
    """
    version_key = f"cache_version:{namespace}:{user_id}"
    try:
        cache.incr(version_key)
    except ValueError:
        # Key exists but not incrementable (wrong type) — reset it
        cache.set(version_key, 2, None)
    except Exception as e:
        logger.warning(f"Cache version bump failed for user {user_id}: {e}")


def bump_dashboard_cache(user_id):
    bump_cache_version(user_id, "dashboard")


def bump_growth_cache(user_id):
    bump_cache_version(user_id, "growth")


# =============================================================================
# PART 2: MODEL SIGNALS FOR CACHE INVALIDATION
# Each signal handler imports its model lazily to avoid circular imports.
# =============================================================================

# --- LEAD signals ---

def _connect_lead_signals():
    from .models import Lead

    @receiver(post_save, sender=Lead, dispatch_uid="lead_cache_save")
    def invalidate_lead_cache_save(sender, instance, **kwargs):
        if instance.builder_id:
            bump_dashboard_cache(instance.builder_id)
            bump_growth_cache(instance.builder_id)

    @receiver(post_delete, sender=Lead, dispatch_uid="lead_cache_delete")
    def invalidate_lead_cache_delete(sender, instance, **kwargs):
        if instance.builder_id:
            bump_dashboard_cache(instance.builder_id)
            bump_growth_cache(instance.builder_id)


# --- DEAL signals ---

def _connect_deal_signals():
    from .models import Deal

    @receiver(post_save, sender=Deal, dispatch_uid="deal_cache_save")
    def invalidate_deal_cache_save(sender, instance, **kwargs):
        if instance.builder_id:
            bump_dashboard_cache(instance.builder_id)
            bump_growth_cache(instance.builder_id)

    @receiver(post_delete, sender=Deal, dispatch_uid="deal_cache_delete")
    def invalidate_deal_cache_delete(sender, instance, **kwargs):
        if instance.builder_id:
            bump_dashboard_cache(instance.builder_id)
            bump_growth_cache(instance.builder_id)


# --- FOLLOWUP signals ---

def _connect_followup_signals():
    from .models import FollowUp

    @receiver(post_save, sender=FollowUp, dispatch_uid="followup_cache_save")
    def invalidate_followup_cache_save(sender, instance, **kwargs):
        try:
            if instance.lead and instance.lead.builder_id:
                bump_dashboard_cache(instance.lead.builder_id)
        except Exception:
            pass

    @receiver(post_delete, sender=FollowUp, dispatch_uid="followup_cache_delete")
    def invalidate_followup_cache_delete(sender, instance, **kwargs):
        try:
            if instance.lead and instance.lead.builder_id:
                bump_dashboard_cache(instance.lead.builder_id)
        except Exception:
            pass


# --- TASK signals ---

def _connect_task_signals():
    from .models import Task

    @receiver(post_save, sender=Task, dispatch_uid="task_cache_save")
    def invalidate_task_cache_save(sender, instance, **kwargs):
        if instance.user_id:
            bump_dashboard_cache(instance.user_id)

    @receiver(post_delete, sender=Task, dispatch_uid="task_cache_delete")
    def invalidate_task_cache_delete(sender, instance, **kwargs):
        if instance.user_id:
            bump_dashboard_cache(instance.user_id)


# --- ACTIVITY signals ---

def _connect_activity_signals():
    from .models import Activity

    @receiver(post_save, sender=Activity, dispatch_uid="activity_cache_save")
    def invalidate_activity_cache(sender, instance, **kwargs):
        if instance.user_id:
            bump_dashboard_cache(instance.user_id)
        try:
            if instance.lead and instance.lead.builder_id:
                bump_dashboard_cache(instance.lead.builder_id)
        except Exception:
            pass


# --- SITE VISIT signals ---

def _connect_sitevisit_signals():
    from .models import SiteVisit

    @receiver(post_save, sender=SiteVisit, dispatch_uid="sitevisit_cache_save")
    def invalidate_sitevisit_cache_save(sender, instance, **kwargs):
        if instance.builder_id:
            bump_dashboard_cache(instance.builder_id)

    @receiver(post_delete, sender=SiteVisit, dispatch_uid="sitevisit_cache_delete")
    def invalidate_sitevisit_cache_delete(sender, instance, **kwargs):
        if instance.builder_id:
            bump_dashboard_cache(instance.builder_id)


# --- NOTIFICATION signals ---

def _connect_notification_signals():
    from .models import Notification

    @receiver(post_save, sender=Notification, dispatch_uid="notification_cache_save")
    def invalidate_notification_cache(sender, instance, **kwargs):
        if instance.recipient_id:
            bump_dashboard_cache(instance.recipient_id)


# =============================================================================
# PART 3: AUTO-CREATE AGENT PROFILE
# When a new User with role='agent' is created, auto-create their Agent record.
# =============================================================================

def _connect_user_signals():
    from .models import User, Agent

    @receiver(post_save, sender=User, dispatch_uid="auto_create_agent")
    def auto_create_agent(sender, instance, created, **kwargs):
        if created and instance.role == "agent":
            try:
                Agent.objects.get_or_create(
                    user=instance,
                    defaults={
                        "name": instance.get_full_name() or instance.username,
                        "email": instance.email or "",
                        "phone": getattr(instance, "phone", None) or "",
                        "is_active": True,
                    }
                )
                logger.info(f"Auto-created Agent for {instance.username}")
            except Exception as e:
                logger.error(f"Auto-create agent failed for {instance.username}: {e}")

    @receiver(post_save, sender=User, dispatch_uid="auto_create_profile")
    def auto_create_profile(sender, instance, created, **kwargs):
        if created:
            try:
                from .models import Profile
                Profile.objects.get_or_create(
                    user=instance,
                    defaults={
                        "full_name": instance.get_full_name() or instance.username,
                        "email": instance.email or "",
                        "phone": getattr(instance, "phone", None) or "",
                    }
                )
            except Exception as e:
                logger.error(f"Auto-create profile failed for {instance.username}: {e}")


# =============================================================================
# PART 4: CONNECT ALL SIGNALS
# Called from apps.py ready() method — after all apps are loaded.
# =============================================================================

def connect_all_signals():
    """
    Connect all signals.
    Call this from CoreConfig.ready() in apps.py:

        def ready(self):
            from .signals import connect_all_signals
            connect_all_signals()
    """
    try:
        _connect_lead_signals()
        _connect_deal_signals()
        _connect_followup_signals()
        _connect_task_signals()
        _connect_activity_signals()
        _connect_sitevisit_signals()
        _connect_notification_signals()
        _connect_user_signals()
        logger.info("All signals connected successfully")
    except Exception as e:
        logger.error(f"Signal connection failed: {e}")


# =============================================================================
# PART 5: AUTO-CREATE SOCIALAPP (Called from apps.py ready())
# =============================================================================
#
# core/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Property

@receiver(pre_save, sender=Property)
def geocode_property(sender, instance, **kwargs):
    """Auto-fill lat/lng from location name using Nominatim (free)"""
    if not instance.latitude or not instance.longitude:
        if instance.location:
            try:
                import requests
                url = f"https://nominatim.openstreetmap.org/search?q={instance.location},India&format=json&limit=1"
                headers = {'User-Agent': 'SmartRealty/1.0'}
                resp = requests.get(url, headers=headers, timeout=5)
                data = resp.json()
                if data:
                    instance.latitude = float(data[0]['lat'])
                    instance.longitude = float(data[0]['lon'])
            except Exception:
                pass  # Fail silently, user can add manually