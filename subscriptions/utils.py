"""
Ye helper functions core/views.py me import karke use karo.
Admin se directly DB me plans customize hote hain — no code deploy needed.
"""

from datetime import date

from django.core.exceptions import PermissionDenied
from core.models import UserSubscription
from .models import SubscriptionPlan, CouponCode


class LimitExceeded(Exception):
    """Raised when a user tries to cross their plan's limit."""
    def __init__(self, message, plan=None):
        self.plan = plan
        super().__init__(message)


def get_active_subscription(user):
    """
    Returns the user's active UserSubscription, or None if they don't have
    one (e.g. never subscribed, or it expired).
    """
    sub = getattr(user, "subscription", None)
    if sub is None:
        return None
    if not sub.is_active:
        return None
    if sub.end_date and sub.end_date < date.today():
        return None
    return sub


def get_plan_limits(user):
    """
    Returns a dict of limits for the user's current plan.
    """
    sub = get_active_subscription(user)
    if sub is None or sub.plan is None:
        return {
            "max_properties": 3,
            "max_agents": 0,
            "max_leads": 20,
            "features": [],
            "plan_name": "No active plan",
        }
    plan = sub.plan
    return {
        "max_properties": plan.max_properties,
        "max_agents": plan.max_agents,
        "max_leads": plan.max_leads,
        "features": plan.features or [],
        "plan_name": plan.name,
    }


def has_feature(user, feature_flag):
    """e.g. has_feature(request.user, 'whatsapp_alerts')"""
    return feature_flag in get_plan_limits(user)["features"]


def check_property_limit(user):
    from core.models import Property
    limits = get_plan_limits(user)
    current_count = Property.objects.filter(builder=user).count()
    if current_count >= limits["max_properties"]:
        raise LimitExceeded(
            f"Aapke '{limits['plan_name']}' plan me sirf "
            f"{limits['max_properties']} properties allowed hain. "
            f"Aap already {current_count} use kar chuke hain. "
            f"Zyada properties ke liye plan upgrade karo.",
            plan=limits["plan_name"],
        )


def check_agent_limit(user):
    from core.models import Agent
    limits = get_plan_limits(user)
    current_count = Agent.objects.filter(builders=user).count()
    if current_count >= limits["max_agents"]:
        raise LimitExceeded(
            f"Aapke '{limits['plan_name']}' plan me sirf "
            f"{limits['max_agents']} agents allowed hain. "
            f"Zyada agents add karne ke liye plan upgrade karo.",
            plan=limits["plan_name"],
        )


def check_lead_limit(user):
    from core.models import Lead
    limits = get_plan_limits(user)
    current_count = Lead.objects.filter(properties__builder=user).distinct().count()
    if current_count >= limits["max_leads"]:
        raise LimitExceeded(
            f"Aapke '{limits['plan_name']}' plan me sirf "
            f"{limits['max_leads']} leads allowed hain. "
            f"Zyada leads handle karne ke liye plan upgrade karo.",
            plan=limits["plan_name"],
        )