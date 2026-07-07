from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from core.models import SubscriptionPlan, UserSubscription
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


@login_required
def subscribe(request, plan_id):
    """
    Activates a plan for the logged-in user.

    NOTE: Abhi koi payment gateway connected nahi hai, isliye plan
    select karte hi turant activate ho jata hai. Jab Razorpay (ya koi
    aur gateway) integrate karo, tab ye view sirf "PENDING" order create
    kare aur payment-success webhook/callback me is_active=True set kare
    — filhaal free-flow hai taaki panel access test kar sako.
    """
    if request.method != "POST":
        return redirect("subscriptions:pricing")

    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

    today = date.today()
    UserSubscription.objects.update_or_create(
        user=request.user,
        defaults={
            "plan": plan,
            "start_date": today,
            "end_date": today + timedelta(days=30),
            "is_active": True,
            "auto_renew": True,
            "payment_status": "PAID" if plan.price_monthly == 0 else "PENDING",
        },
    )

    messages.success(request, f"'{plan.name}' plan activate ho gaya! Ab aap apna panel use kar sakte ho.")

    if request.user.role == "builder":
        return redirect("builder_dashboard")
    elif request.user.role == "agent":
        return redirect("agent_dashboard")
    return redirect("subscriptions:pricing")
