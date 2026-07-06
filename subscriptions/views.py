from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import SubscriptionPlan
from .plans_config import BUILDER_PLANS, AGENT_PLANS


def pricing(request):
    """
    Public pricing page. Reads live data from the DB (so admin edits show
    up immediately) but falls back to grouping plans by name using
    plans_config.py, since audience (builder/agent) isn't stored on the
    model itself.
    """
    builder_names = [p["name"] for p in BUILDER_PLANS]
    agent_names = [p["name"] for p in AGENT_PLANS]

    all_active = SubscriptionPlan.objects.filter(is_active=True)

    builder_plans = [p for p in all_active if p.name in builder_names]
    agent_plans = [p for p in all_active if p.name in agent_names]

    # keep the order defined in plans_config.py rather than price ordering
    builder_plans.sort(key=lambda p: builder_names.index(p.name))
    agent_plans.sort(key=lambda p: agent_names.index(p.name))

    context = {
        "builder_plans": builder_plans,
        "agent_plans": agent_plans,
    }
    return render(request, "subscriptions/pricing.html", context)


@login_required
def my_subscription(request):
    """Shows the logged-in user's current plan and usage."""
    from .utils import get_plan_limits, get_active_subscription
    from core.models import Property, Agent

    sub = get_active_subscription(request.user)
    limits = get_plan_limits(request.user)

    context = {
        "subscription": sub,
        "limits": limits,
        "properties_used": Property.objects.filter(builder=request.user).count(),
        "agents_used": Agent.objects.filter(builders=request.user).count(),
    }
    return render(request, "subscriptions/my_subscription.html", context)
