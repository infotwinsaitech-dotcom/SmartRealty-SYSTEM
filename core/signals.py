from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Agent

@receiver(post_save, sender=User)
def auto_create_agent(sender, instance, created, **kwargs):
    if created and instance.role == "agent":
        builder = User.objects.filter(role="builder").first()

        Agent.objects.create(
            user=instance,
            name=instance.username,
            email=instance.email,
            phone=instance.phone,
            builder=builder
        )