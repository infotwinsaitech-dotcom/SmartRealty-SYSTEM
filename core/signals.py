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