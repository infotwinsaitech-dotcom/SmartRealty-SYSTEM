"""
RealShree - Subscription Models with Razorpay & Coupons
NOTE: UserSubscription is in core/models.py, NOT here. We reference it via imports.
"""

from django.db import models
from django.db.models import Index
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class SubscriptionPlan(models.Model):
    """Admin-customizable subscription plans"""
    PLAN_TYPE_CHOICES = [
        ('builder', 'Builder'),
        ('agent', 'Agent'),
    ]

    name = models.CharField(max_length=100, unique=True)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES, default='builder')
    description = models.TextField(blank=True)

    # Pricing - Admin can customize
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Limits - Admin can customize
    max_properties = models.PositiveIntegerField(default=10)
    max_agents = models.PositiveIntegerField(default=5)
    max_leads = models.PositiveIntegerField(default=100)

    # Features stored as JSON for flexibility
    features = models.JSONField(default=list, blank=True, help_text="List of feature flags")

    # Razorpay Plan IDs (auto-created or manually entered)
    razorpay_plan_id_monthly = models.CharField(max_length=100, blank=True, null=True, 
                                               help_text="Auto-generated Razorpay plan ID for monthly")
    razorpay_plan_id_yearly = models.CharField(max_length=100, blank=True, null=True,
                                               help_text="Auto-generated Razorpay plan ID for yearly")

    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, help_text="Highlight this plan as popular")
    display_order = models.PositiveIntegerField(default=0, help_text="Order in which plans are displayed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'price_monthly']
        indexes = [
            Index(fields=['plan_type', 'is_active']),
            Index(fields=['is_active', 'display_order']),
        ]

    def __str__(self):
        return f"{self.name} (Rs.{self.price_monthly}/mo)"

    def get_discounted_price(self, coupon=None, billing_cycle='monthly'):
        """Get price after coupon discount"""
        base_price = self.price_monthly if billing_cycle == 'monthly' else self.price_yearly
        if coupon and coupon.is_valid():
            return coupon.apply_discount(base_price)
        return base_price


class CouponCode(models.Model):
    """Admin-customizable coupon codes"""
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount (Rs.)'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True, 
                            help_text="Uppercase, no spaces. E.g., BUILDER50")
    description = models.TextField(blank=True, help_text="Internal note about this coupon")

    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, 
                                         validators=[MinValueValidator(0)],
                                         help_text="Percentage (e.g., 20 for 20%) or Fixed amount (e.g., 500 for Rs.500)")

    # Usage limits
    max_uses = models.PositiveIntegerField(default=0, 
                                            help_text="0 = unlimited uses")
    used_count = models.PositiveIntegerField(default=0)
    max_uses_per_user = models.PositiveIntegerField(default=1,
                                                      help_text="How many times one user can use this coupon")

    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    # Applicability
    applicable_plans = models.ManyToManyField(SubscriptionPlan, blank=True, 
                                               related_name='coupons',
                                               help_text="Leave empty to apply to all plans")
    applicable_plan_types = models.CharField(max_length=20, blank=True,
                                              help_text="Comma-separated: builder,agent. Leave empty for all")

    # Minimum order value
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                    null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['code', 'is_active']),
            Index(fields=['valid_from', 'valid_until']),
        ]

    def __str__(self):
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'percentage' else 'Rs.'}"

    def is_valid(self, user=None, plan=None, amount=None):
        """Check if coupon is valid for given context"""
        from django.utils import timezone
        now = timezone.now()

        if not self.is_active:
            return False, "Coupon is inactive"

        if now < self.valid_from:
            return False, "Coupon not yet valid"

        if now > self.valid_until:
            return False, "Coupon expired"

        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False, "Coupon usage limit reached"

        if user and self.max_uses_per_user > 0:
            user_usage = CouponUsage.objects.filter(coupon=self, user=user).count()
            if user_usage >= self.max_uses_per_user:
                return False, f"You can use this coupon max {self.max_uses_per_user} time(s)"

        if plan and self.applicable_plans.exists() and plan not in self.applicable_plans.all():
            return False, "Coupon not applicable for this plan"

        if amount and amount < self.min_order_value:
            return False, f"Minimum order value Rs.{self.min_order_value} required"

        return True, "Valid"

    def apply_discount(self, amount):
        """Calculate discounted amount"""
        if self.discount_type == 'percentage':
            discount = (amount * self.discount_value) / 100
        else:
            discount = self.discount_value
        return max(Decimal('0'), amount - discount)

    def calculate_discount_amount(self, amount):
        """Calculate how much discount is given"""
        if self.discount_type == 'percentage':
            return (amount * self.discount_value) / 100
        return self.discount_value


class CouponUsage(models.Model):
    """Track coupon usage per user"""
    coupon = models.ForeignKey(CouponCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey('RazorpayOrder', on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['coupon', 'user', 'order']


class RazorpayOrder(models.Model):
    """Track Razorpay payment orders"""
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('attempted', 'Attempted'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='razorpay_orders')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)

    # Order details
    razorpay_order_id = models.CharField(max_length=100, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.TextField(blank=True, null=True)

    # Amount details
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Coupon applied
    coupon = models.ForeignKey(CouponCode, on_delete=models.SET_NULL, null=True, blank=True)

    # Billing cycle
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='monthly')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')

    # Subscription details (filled after payment)
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)

    # Metadata
    notes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['user', 'status']),
            Index(fields=['razorpay_order_id']),
        ]

    def __str__(self):
        return f"Order {self.razorpay_order_id} - {self.status}"


# NOTE: UserSubscription is defined in core/models.py to avoid duplication.
# The subscriptions app only adds RazorpayOrder, CouponCode, and SubscriptionPlan.
# The core.UserSubscription model already has: user (OneToOne), plan (FK), start_date, end_date, etc.
# We extend functionality by linking RazorpayOrder to the user, not to UserSubscription directly.