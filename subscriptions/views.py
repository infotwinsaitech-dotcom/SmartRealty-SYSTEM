"""
RealShree - Razorpay Payment + Coupon Integration
All admin-customizable via Django Admin
"""

import json
import logging
import time
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Property, Agent, Lead, UserSubscription
from .models import SubscriptionPlan, RazorpayOrder, CouponCode, CouponUsage
from .utils import get_active_subscription, get_plan_limits

logger = logging.getLogger(__name__)

# Initialize Razorpay client (lazy import to avoid crash if not installed)
razorpay_client = None
try:
    import razorpay
    razorpay_client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
except ImportError:
    logger.warning("razorpay package not installed. Payment features disabled.")


# =============================================================================
# PUBLIC PRICING PAGE
# =============================================================================

def pricing(request):
    """
    Pricing page with coupon support.
    Admin can customize plans, prices, and coupons from Django Admin.

    Behaviour:
    - Logged-in BUILDER  -> sees ONLY builder plans (their own plan to claim).
    - Logged-in AGENT    -> sees ONLY agent plans (their own plan to claim).
    - Anonymous visitor  -> sees both, so the public marketing page still works.
    """
    user_role = None
    if request.user.is_authenticated:
        user_role = getattr(request.user, 'role', None)

    builder_plans = SubscriptionPlan.objects.none()
    agent_plans = SubscriptionPlan.objects.none()

    if user_role == 'builder':
        builder_plans = SubscriptionPlan.objects.filter(
            plan_type='builder',
            is_active=True
        ).order_by('display_order', 'price_monthly')
    elif user_role == 'agent':
        agent_plans = SubscriptionPlan.objects.filter(
            plan_type='agent',
            is_active=True
        ).order_by('display_order', 'price_monthly')
    else:
        # Not logged in (or some other role) -> show the full public catalogue
        builder_plans = SubscriptionPlan.objects.filter(
            plan_type='builder',
            is_active=True
        ).order_by('display_order', 'price_monthly')
        agent_plans = SubscriptionPlan.objects.filter(
            plan_type='agent',
            is_active=True
        ).order_by('display_order', 'price_monthly')

    # Check for applied coupon in session
    applied_coupon = None
    coupon_discounts = {}

    coupon_code = request.session.get('applied_coupon')
    if coupon_code:
        try:
            coupon = CouponCode.objects.get(code=coupon_code.upper(), is_active=True)
            valid, msg = coupon.is_valid()
            if valid:
                applied_coupon = coupon
                for plan in list(builder_plans) + list(agent_plans):
                    discounted = coupon.apply_discount(plan.price_monthly)
                    coupon_discounts[plan.id] = {
                        'original': float(plan.price_monthly),
                        'discounted': float(discounted),
                        'savings': float(plan.price_monthly - discounted)
                    }
            else:
                request.session.pop('applied_coupon', None)
        except CouponCode.DoesNotExist:
            request.session.pop('applied_coupon', None)

    context = {
        "builder_plans": builder_plans,
        "agent_plans": agent_plans,
        "applied_coupon": applied_coupon,
        "coupon_discounts": coupon_discounts,
        "razorpay_key_id": getattr(settings, 'RAZORPAY_KEY_ID', ''),
        "user_role": user_role,
    }
    return render(request, "subscriptions/pricing.html", context)


# =============================================================================
# COUPON MANAGEMENT
# =============================================================================

@require_POST
def apply_coupon(request):
    """AJAX: Apply coupon code"""
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
        plan_id = data.get('plan_id')

        if not code:
            return JsonResponse({"success": False, "message": "Coupon code required"})

        try:
            coupon = CouponCode.objects.get(code=code, is_active=True)
        except CouponCode.DoesNotExist:
            return JsonResponse({"success": False, "message": "Invalid coupon code"})

        valid, msg = coupon.is_valid(user=request.user if request.user.is_authenticated else None)
        if not valid:
            return JsonResponse({"success": False, "message": msg})

        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                if coupon.applicable_plans.exists() and plan not in coupon.applicable_plans.all():
                    return JsonResponse({"success": False, "message": "Coupon not valid for this plan"})
            except SubscriptionPlan.DoesNotExist:
                pass

        request.session['applied_coupon'] = code

        return JsonResponse({
            "success": True,
            "message": f"Coupon '{code}' applied!",
            "coupon": {
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "discount_value": float(coupon.discount_value),
                "description": coupon.description,
            }
        })

    except Exception as e:
        logger.error(f"Apply coupon error: {str(e)}")
        return JsonResponse({"success": False, "message": "Something went wrong"})


def remove_coupon(request):
    """Remove applied coupon"""
    request.session.pop('applied_coupon', None)
    messages.success(request, "Coupon removed")
    return redirect('subscriptions:pricing')


# =============================================================================
# RAZORPAY ORDER CREATION
# =============================================================================

@login_required
@require_POST
def create_razorpay_order(request):
    """Create Razorpay order with coupon support"""
    if razorpay_client is None:
        return JsonResponse({"success": False, "message": "Payment gateway not configured"})

    try:
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        billing_cycle = data.get('billing_cycle', 'monthly')

        if billing_cycle not in ['monthly', 'yearly']:
            return JsonResponse({"success": False, "message": "Invalid billing cycle"})

        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

        if plan.plan_type == 'builder' and request.user.role != 'builder':
            return JsonResponse({"success": False, "message": "This plan is for builders only"})
        if plan.plan_type == 'agent' and request.user.role != 'agent':
            return JsonResponse({"success": False, "message": "This plan is for agents only"})

        base_amount = plan.price_monthly if billing_cycle == 'monthly' else plan.price_yearly

        coupon = None
        discount_amount = Decimal('0')
        coupon_code = request.session.get('applied_coupon')

        if coupon_code:
            try:
                coupon = CouponCode.objects.get(code=coupon_code.upper(), is_active=True)
                valid, msg = coupon.is_valid(user=request.user, plan=plan, amount=base_amount)
                if valid:
                    discount_amount = coupon.calculate_discount_amount(base_amount)
                    base_amount = coupon.apply_discount(base_amount)
                else:
                    request.session.pop('applied_coupon', None)
                    coupon = None
            except CouponCode.DoesNotExist:
                request.session.pop('applied_coupon', None)

        # ---------------------------------------------------------------
        # FREE PLAN HANDLING (e.g. 100% discount coupon)
        # Razorpay doesn't allow ₹0 orders, so if the final amount is
        # zero or less, activate the subscription directly without
        # ever calling Razorpay.
        # ---------------------------------------------------------------
        if base_amount <= 0:
            with transaction.atomic():
                order = RazorpayOrder.objects.create(
                    user=request.user,
                    plan=plan,
                    razorpay_order_id=f"FREE_{request.user.id}_{plan.id}_{int(time.time())}",
                    razorpay_payment_id="FREE_COUPON",
                    original_amount=plan.price_monthly if billing_cycle == 'monthly' else plan.price_yearly,
                    discount_amount=discount_amount,
                    final_amount=Decimal('0'),
                    coupon=coupon,
                    billing_cycle=billing_cycle,
                    status='paid',
                    notes={
                        'user_id': request.user.id,
                        'plan_id': plan.id,
                        'plan_name': plan.name,
                        'billing_cycle': billing_cycle,
                        'coupon_code': coupon.code if coupon else None,
                        'free_via_coupon': True,
                    }
                )

                today = date.today()
                end_date = today + timedelta(days=365 if billing_cycle == 'yearly' else 30)

                UserSubscription.objects.update_or_create(
                    user=request.user,
                    defaults={
                        'plan': plan,
                        'current_order': order,
                        'start_date': today,
                        'end_date': end_date,
                        'is_active': True,
                        'auto_renew': True,
                        'payment_status': 'PAID',
                    }
                )

                if coupon:
                    CouponUsage.objects.create(
                        coupon=coupon,
                        user=request.user,
                        order=order,
                        discount_amount=discount_amount
                    )
                    coupon.used_count += 1
                    coupon.save(update_fields=['used_count'])

                request.session.pop('applied_coupon', None)

            from django.urls import reverse
            if request.user.role == 'builder':
                redirect_url = reverse('builder_dashboard')
            elif request.user.role == 'agent':
                redirect_url = reverse('agent_dashboard')
            else:
                redirect_url = reverse('subscriptions:pricing')

            return JsonResponse({
                "success": True,
                "free": True,
                "message": f"'{plan.name}' activated for free!",
                "redirect_url": redirect_url,
            })

        amount_in_paise = int(base_amount * 100)

        razorpay_order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'receipt': f"order_{request.user.id}_{plan.id}_{int(time.time())}",
            'notes': {
                'user_id': request.user.id,
                'plan_id': plan.id,
                'plan_name': plan.name,
                'billing_cycle': billing_cycle,
                'coupon_code': coupon.code if coupon else None,
            }
        }

        razorpay_order = razorpay_client.order.create(razorpay_order_data)

        with transaction.atomic():
            order = RazorpayOrder.objects.create(
                user=request.user,
                plan=plan,
                razorpay_order_id=razorpay_order['id'],
                original_amount=plan.price_monthly if billing_cycle == 'monthly' else plan.price_yearly,
                discount_amount=discount_amount,
                final_amount=base_amount,
                coupon=coupon,
                billing_cycle=billing_cycle,
                status='created',
                notes=razorpay_order_data['notes']
            )

        return JsonResponse({
            "success": True,
            "order_id": razorpay_order['id'],
            "amount": amount_in_paise,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan_name": plan.name,
            "description": f"{plan.name} - {billing_cycle.title()}",
            "prefill": {
                "name": request.user.get_full_name() or request.user.username,
                "email": request.user.email,
                "contact": getattr(request.user, 'phone', '') or '',
            },
            "coupon_applied": coupon.code if coupon else None,
            "discount_amount": float(discount_amount) if coupon else 0,
        })

    except Exception as e:
        logger.error(f"Create order error: {str(e)}")
        return JsonResponse({"success": False, "message": "Failed to create order. Please try again."})


# =============================================================================
# RAZORPAY PAYMENT VERIFICATION
# =============================================================================

@csrf_exempt
@require_POST
def razorpay_callback(request):
    """Handle Razorpay payment callback"""
    if razorpay_client is None:
        messages.error(request, "Payment gateway not configured")
        return redirect('subscriptions:pricing')

    try:
        payment_id = request.POST.get('razorpay_payment_id', '')
        order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')

        if not all([payment_id, order_id, signature]):
            messages.error(request, "Invalid payment response")
            return redirect('subscriptions:pricing')

        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception:
            RazorpayOrder.objects.filter(razorpay_order_id=order_id).update(
                status='failed',
                razorpay_payment_id=payment_id
            )
            messages.error(request, "Payment verification failed. Please try again.")
            return redirect('subscriptions:pricing')

        with transaction.atomic():
            order = get_object_or_404(
                RazorpayOrder, 
                razorpay_order_id=order_id, 
                status='created'
            )

            order.razorpay_payment_id = payment_id
            order.razorpay_signature = signature
            order.status = 'paid'
            order.save()

            today = date.today()
            if order.billing_cycle == 'yearly':
                end_date = today + timedelta(days=365)
            else:
                end_date = today + timedelta(days=30)

            subscription, created = UserSubscription.objects.update_or_create(
                user=order.user,
                defaults={
                    'plan': order.plan,
                    'current_order': order,
                    'start_date': today,
                    'end_date': end_date,
                    'is_active': True,
                    'auto_renew': True,
                    'payment_status': 'PAID',
                }
            )

            if order.coupon:
                CouponUsage.objects.create(
                    coupon=order.coupon,
                    user=order.user,
                    order=order,
                    discount_amount=order.discount_amount
                )
                order.coupon.used_count += 1
                order.coupon.save(update_fields=['used_count'])

            request.session.pop('applied_coupon', None)

        messages.success(
            request, 
            f"Payment successful! '{order.plan.name}' activated. Valid till {end_date.strftime('%d %b %Y')}."
        )

        if request.user.role == 'builder':
            return redirect('builder_dashboard')
        elif request.user.role == 'agent':
            return redirect('agent_dashboard')
        return redirect('subscriptions:pricing')

    except Exception as e:
        logger.error(f"Razorpay callback error: {str(e)}")
        messages.error(request, "Payment processing error. Please contact support.")
        return redirect('subscriptions:pricing')


@csrf_exempt
def razorpay_webhook(request):
    """Handle Razorpay webhooks for async payment confirmation"""
    if razorpay_client is None:
        return JsonResponse({"status": "gateway_not_configured"}, status=503)

    try:
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)

        if webhook_secret:
            webhook_signature = request.headers.get('X-Razorpay-Signature', '')
            body = request.body

            try:
                razorpay_client.utility.verify_webhook_signature(
                    body, webhook_signature, webhook_secret
                )
            except Exception:
                return JsonResponse({"status": "invalid_signature"}, status=400)

        payload = json.loads(request.body)
        event = payload.get('event')

        if event == 'payment.captured':
            payment = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment.get('order_id')
            payment_id = payment.get('id')

            if order_id:
                try:
                    order = RazorpayOrder.objects.get(razorpay_order_id=order_id)
                    if order.status != 'paid':
                        with transaction.atomic():
                            order.razorpay_payment_id = payment_id
                            order.status = 'paid'
                            order.save()

                            today = date.today()
                            end_date = today + timedelta(days=365 if order.billing_cycle == 'yearly' else 30)

                            UserSubscription.objects.update_or_create(
                                user=order.user,
                                defaults={
                                    'plan': order.plan,
                                    'current_order': order,
                                    'start_date': today,
                                    'end_date': end_date,
                                    'is_active': True,
                                    'payment_status': 'PAID',
                                }
                            )
                except RazorpayOrder.DoesNotExist:
                    pass

        return JsonResponse({"status": "ok"})

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JsonResponse({"status": "error"}, status=500)


# =============================================================================
# MY SUBSCRIPTION PAGE
# =============================================================================

@login_required
def my_subscription(request):
    """Shows the logged-in user's current plan, usage, and payment history"""
    sub = get_active_subscription(request.user)
    limits = get_plan_limits(request.user)

    payment_history = RazorpayOrder.objects.filter(
        user=request.user,
        status='paid'
    ).select_related('plan', 'coupon').order_by('-created_at')[:10]

    properties_used = Property.objects.filter(builder=request.user).count()
    agents_used = Agent.objects.filter(builders=request.user).count()
    leads_used = Lead.objects.filter(builder=request.user).count()

    context = {
        "subscription": sub,
        "limits": limits,
        "payment_history": payment_history,
        "properties_used": properties_used,
        "agents_used": agents_used,
        "leads_used": leads_used,
        "properties_percent": min(100, int((properties_used / limits['max_properties']) * 100)) if limits['max_properties'] > 0 else 0,
        "agents_percent": min(100, int((agents_used / limits['max_agents']) * 100)) if limits['max_agents'] > 0 else 0,
        "leads_percent": min(100, int((leads_used / limits['max_leads']) * 100)) if limits['max_leads'] > 0 else 0,
    }
    return render(request, "subscriptions/my_subscription.html", context)


# =============================================================================
# PAYMENT STATUS CHECK (AJAX)
# =============================================================================

@login_required
def check_payment_status(request, order_id):
    """AJAX: Check if payment is completed"""
    try:
        order = RazorpayOrder.objects.get(razorpay_order_id=order_id, user=request.user)
        return JsonResponse({
            "status": order.status,
            "is_paid": order.status == 'paid',
            "plan_name": order.plan.name if order.plan else None,
        })
    except RazorpayOrder.DoesNotExist:
        return JsonResponse({"status": "not_found", "is_paid": False})