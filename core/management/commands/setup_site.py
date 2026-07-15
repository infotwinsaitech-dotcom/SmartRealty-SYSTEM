# core/management/commands/setup_site.py
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
import os


class Command(BaseCommand):
    help = 'Auto-create Site and SocialApp for allauth'

    def handle(self, *args, **options):
        # 1. Create/update Site
        site, created = Site.objects.update_or_create(
            id=1,
            defaults={
                'domain': 'smartrealty-system.onrender.com',
                'name': 'RealShree'
            }
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} Site: {site.domain}'))

        # 2. Create/update SocialApp for Google
        client_id = os.getenv('GOOGLE_CLIENT_ID', '')
        secret = os.getenv('GOOGLE_CLIENT_SECRET', '')

        if client_id and secret:
            app, created = SocialApp.objects.update_or_create(
                provider='google',
                name='Google OAuth',
                defaults={
                    'client_id': client_id,
                    'secret': secret,
                }
            )
            app.sites.add(site)
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'{action} SocialApp: Google OAuth'))
        else:
            self.stdout.write(self.style.WARNING('GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set!'))

        self.stdout.write(self.style.SUCCESS('Setup complete!'))