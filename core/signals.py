from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Agent, Builder  # अगर builder भी है

User = get_user_model()

@receiver(post_save, sender=User)
def create_profiles(sender, instance, created, **kwargs):
    if created:
        if instance.role == "agent":
            Agent.objects.create(user=instance)

        elif instance.role == "builder":
            Builder.objects.create(user=instance)