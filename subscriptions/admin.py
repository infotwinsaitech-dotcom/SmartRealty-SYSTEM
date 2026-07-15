"""
RealShree - Subscription Admin Panel
Admin can fully customize plans, coupons, and view all payments
NOTE: UserSubscription is in core/models.py - we reference it, don't redefine it.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import now
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages

from .models import SubscriptionPlan, RazorpayOrder, CouponCode, CouponUsage
from core.models import UserSubscription


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    readonly_fields = ['user', 'order', 'discount_amount', 'used_at']
    can_delete = False
    max_num = 0


class RazorpayOrderInline(admin.TabularInline):
    """Show Razorpay orders linked to a USER (not UserSubscription)"""
    model = RazorpayOrder
    fk_name = 'user'
    extra = 0
    readonly_fields = ['razorpay_order_id', 'final_amount', 'billing_cycle', 'status', 'created_at']
    can_delete = False
    max_num = 0


# =============================================================================
# SUBSCRIPTION PLAN ADMIN
# =============================================================================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name", "plan_type_badge", "price_monthly", "price_yearly",
        "max_properties", "max_agents", "max_leads", 
        "is_active", "is_popular", "display_order"
    )
    list_filter = ("plan_type", "is_active", "is_popular")
    search_fields = ("name", "description")
    list_editable = ("is_active", "is_popular", "display_order", "price_monthly", "price_yearly")
    ordering = ("display_order", "price_monthly")

    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "plan_type", "description", "is_active", "is_popular", "display_order")
        }),
        ("Pricing (Admin Customizable)", {
            "fields": ("price_monthly", "price_yearly"),
            "description": "Admin yaha se directly price change kar sakta hai. No code deploy needed."
        }),
        ("Limits (Admin Customizable)", {
            "fields": ("max_properties", "max_agents", "max_leads"),
            "description": "Kitni properties, agents, aur leads allowed hain - yaha se customize karo."
        }),
        ("Features", {
            "fields": ("features",),
            "description": 'JSON list me feature flags daalo. Example: ["whatsapp_alerts", "auto_lead_assignment", "advanced_analytics"]'
        }),
        ("Razorpay Integration", {
            "fields": ("razorpay_plan_id_monthly", "razorpay_plan_id_yearly"),
            "classes": ("collapse",),
            "description": "Auto-generated Razorpay plan IDs. Manual edit only if needed."
        }),
    )

    def plan_type_badge(self, obj):
        colors = {"builder": "#fbbf24", "agent": "#60a5fa"}
        return format_html(
            '<span style="background:{};color:#000;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            colors.get(obj.plan_type, "#9ca3af"),
            obj.plan_type.upper()
        )
    plan_type_badge.short_description = "Type"


# =============================================================================
# COUPON CODE ADMIN
# =============================================================================

@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code", "discount_display", "usage_stats", 
        "validity_status", "is_active", "created_at"
    )
    list_filter = ("discount_type", "is_active", "valid_from", "valid_until")
    search_fields = ("code", "description")
    list_editable = ("is_active",)
    ordering = ("-created_at",)

    fieldsets = (
        ("Coupon Details", {
            "fields": ("code", "description", "is_active")
        }),
        ("Discount Settings", {
            "fields": ("discount_type", "discount_value"),
            "description": "Percentage (%) ya Fixed Amount (Rs.) - admin choose kar sakta hai."
        }),
        ("Usage Limits", {
            "fields": ("max_uses", "max_uses_per_user", "used_count"),
            "description": "0 = unlimited. Per-user limit bhi set kar sakte ho."
        }),
        ("Validity Period", {
            "fields": ("valid_from", "valid_until"),
            "description": "Kab se kab tak coupon valid hai."
        }),
        ("Applicability", {
            "fields": ("applicable_plans", "applicable_plan_types", "min_order_value"),
            "description": "Konsi plans par apply hoga? Empty = all plans."
        }),
    )

    readonly_fields = ("used_count", "created_at")
    filter_horizontal = ("applicable_plans",)
    inlines = [CouponUsageInline]

    actions = ["activate_coupons", "deactivate_coupons", "duplicate_coupon"]

    def discount_display(self, obj):
        if obj.discount_type == 'percentage':
            return format_html('<span style="color:#fbbf24;font-weight:600;">{}% OFF</span>', obj.discount_value)
        return format_html('<span style="color:#fbbf24;font-weight:600;">Rs.{} OFF</span>', obj.discount_value)
    discount_display.short_description = "Discount"

    def usage_stats(self, obj):
        if obj.max_uses > 0:
            return f"{obj.used_count} / {obj.max_uses}"
        return f"{obj.used_count} / infinity"
    usage_stats.short_description = "Used"

    def validity_status(self, obj):
        current = now()
        if current < obj.valid_from:
            return format_html('<span style="color:#fbbf24;">Upcoming</span>')
        if current > obj.valid_until:
            return format_html('<span style="color:#ef4444;">Expired</span>')
        return format_html('<span style="color:#22c55e;">Active</span>')
    validity_status.short_description = "Status"

    @admin.action(description="Activate selected coupons")
    def activate_coupons(self, request, queryset):
        queryset.update(is_active=True)
        messages.success(request, f"{queryset.count()} coupons activated.")

    @admin.action(description="Deactivate selected coupons")
    def deactivate_coupons(self, request, queryset):
        queryset.update(is_active=False)
        messages.success(request, f"{queryset.count()} coupons deactivated.")

    @admin.action(description="Duplicate selected coupons")
    def duplicate_coupon(self, request, queryset):
        for coupon in queryset:
            old_plans = list(coupon.applicable_plans.all())
            coupon.pk = None
            coupon.code = f"{coupon.code}_COPY"
            coupon.used_count = 0
            coupon.save()
            coupon.applicable_plans.set(old_plans)
        messages.success(request, f"{queryset.count()} coupons duplicated.")


# =============================================================================
# RAZORPAY ORDER ADMIN
# =============================================================================

@admin.register(RazorpayOrder)
class RazorpayOrderAdmin(admin.ModelAdmin):
    list_display = (
        "razorpay_order_id_short", "user", "plan", "amount_display",
        "coupon_applied", "billing_cycle", "status_badge", "created_at"
    )
    list_filter = ("status", "billing_cycle", "created_at")
    search_fields = ("razorpay_order_id", "user__username", "user__email", "plan__name")
    readonly_fields = (
        "razorpay_order_id", "razorpay_payment_id", "razorpay_signature",
        "original_amount", "discount_amount", "final_amount",
        "user", "plan", "coupon", "billing_cycle", "status",
        "subscription_start", "subscription_end", "notes", "created_at"
    )
    ordering = ("-created_at",)

    def razorpay_order_id_short(self, obj):
        return obj.razorpay_order_id[:20] + "..." if len(obj.razorpay_order_id) > 20 else obj.razorpay_order_id
    razorpay_order_id_short.short_description = "Order ID"

    def amount_display(self, obj):
        if obj.discount_amount > 0:
            return format_html(
                '<span style="text-decoration:line-through;color:#6b7280;">Rs.{}</span> <span style="color:#fbbf24;font-weight:600;">Rs.{}</span>',
                obj.original_amount, obj.final_amount
            )
        return format_html('<span style="color:#fbbf24;font-weight:600;">Rs.{}</span>', obj.final_amount)
    amount_display.short_description = "Amount"

    def coupon_applied(self, obj):
        if obj.coupon:
            return format_html(
                '<span style="background:#22c55e20;color:#22c55e;padding:2px 8px;border-radius:12px;font-size:12px;">{}</span>',
                obj.coupon.code
            )
        return "-"
    coupon_applied.short_description = "Coupon"

    def status_badge(self, obj):
        colors = {
            'created': '#6b7280',
            'attempted': '#fbbf24',
            'paid': '#22c55e',
            'failed': '#ef4444',
            'cancelled': '#6b7280'
        }
        return format_html(
            '<span style="background:{}20;color:{};padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            colors.get(obj.status, '#6b7280'),
            obj.status.upper()
        )
    status_badge.short_description = "Status"


# =============================================================================
# USER SUBSCRIPTION ADMIN (from core.models)
# =============================================================================

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "start_date", "end_date",
        "days_left", "is_active", "payment_status", "auto_renew"
    )
    list_filter = ("is_active", "payment_status", "plan")
    search_fields = ("user__username", "user__email", "plan__name")
    readonly_fields = ("created_at",)
    # RazorpayOrderInline removed - use user filter in RazorpayOrderAdmin instead

    def days_left(self, obj):
        days = obj.days_remaining()
        if days <= 0:
            return format_html('<span style="color:#ef4444;">Expired</span>')
        if days <= 7:
            return format_html('<span style="color:#fbbf24;">{} days</span>', days)
        return format_html('<span style="color:#22c55e;">{} days</span>', days)
    days_left.short_description = "Days Left"