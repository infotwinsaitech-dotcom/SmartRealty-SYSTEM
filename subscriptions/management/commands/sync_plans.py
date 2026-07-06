"""
Usage:
    python manage.py sync_plans

Ye command subscriptions/plans_config.py ko padhta hai aur
core.models.SubscriptionPlan table ko usi ke hisaab se update karta hai.

- Plan naya hai       -> create
- Plan already hai    -> price/limits/features update (name se match hota hai)
- Plan config se hata diya -> DB row ko is_active=False (delete nahi)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import SubscriptionPlan
from subscriptions.plans_config import ALL_PLANS


class Command(BaseCommand):
    help = "Sync subscriptions/plans_config.py into the SubscriptionPlan table"

    @transaction.atomic
    def handle(self, *args, **options):
        configured_names = set()
        created_count = 0
        updated_count = 0

        for plan_data in ALL_PLANS:
            name = plan_data["name"]
            configured_names.add(name)

            defaults = {
                "description": plan_data.get("description", ""),
                "price_monthly": plan_data["price_monthly"],
                "price_yearly": plan_data["price_yearly"],
                "max_properties": plan_data["max_properties"],
                "max_agents": plan_data["max_agents"],
                "max_leads": plan_data["max_leads"],
                "features": plan_data.get("features", []),
                "is_active": plan_data.get("is_active", True),
            }

            plan, created = SubscriptionPlan.objects.update_or_create(
                name=name, defaults=defaults
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  + Created: {name}"))
            else:
                updated_count += 1
                self.stdout.write(f"  ~ Updated: {name}")

        # Plans config se hata diye gaye but DB me maujood -> deactivate
        stale_plans = SubscriptionPlan.objects.exclude(name__in=configured_names)
        stale_count = stale_plans.update(is_active=False)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created={created_count}, Updated={updated_count}, "
            f"Deactivated(removed from config)={stale_count}"
        ))
