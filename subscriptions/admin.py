from django.contrib import admin

from core.models import SubscriptionPlan, UserSubscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name", "price_monthly", "price_yearly",
        "max_properties", "max_agents", "max_leads", "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("price_monthly",)

    # Reminder shown at the top of the admin change-list page
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["subtitle"] = (
            "Price/limits yaha se bhi edit ho sakte hain, lekin agar ye repo "
            "redeploy hota hai to subscriptions/plans_config.py hi source of "
            "truth hai — wahi file update karo aur 'python manage.py "
            "sync_plans' chalao."
        )
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "start_date", "end_date",
        "is_active", "payment_status", "auto_renew",
    )
    list_filter = ("is_active", "payment_status", "plan")
    search_fields = ("user__username", "user__email")
    
