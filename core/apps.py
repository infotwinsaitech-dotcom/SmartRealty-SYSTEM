# core/apps.py — COMPLETE FIXED FILE

from django.apps import AppConfig
from django.db import connection, ProgrammingError, OperationalError
import logging
import sys

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # 1. Auto-create cache table if missing
        self._init_cache_table()
        
        # 2. PostgreSQL optimization
        self._optimize_postgres()
        
        # 3. Auto-create Google SocialApp
        self._init_social_app()
        
        logger.info("✅ Core app initialized")

    def _is_management_command(self):
        """Detect if running management command"""
        mgmt = ['migrate', 'makemigrations', 'collectstatic', 
                'createsuperuser', 'shell', 'dbshell', 'test', 'runserver']
        return any(cmd in sys.argv for cmd in mgmt)

    def _init_cache_table(self):
        """Auto-create cache table — works on every deploy"""
        if self._is_management_command():
            return
            
        try:
            from django.core.cache import cache
            cache.set('_health_check', 'ok', 10)
            if cache.get('_health_check') == 'ok':
                return
        except (ProgrammingError, OperationalError):
            pass
        
        try:
            from django.core.management import call_command
            call_command('createcachetable', verbosity=0)
            logger.info("✅ Cache table auto-created")
        except Exception as e:
            logger.warning(f"⚠️ Cache table: {e}")

    def _optimize_postgres(self):
        """PostgreSQL session-level optimizations"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION idle_in_transaction_session_timeout = '30s';")
                cursor.execute("SET SESSION statement_timeout = '30s';")
                cursor.execute("SET SESSION work_mem = '8MB';")
                logger.info("✅ PostgreSQL optimized")
        except Exception as e:
            logger.debug(f"PG optimize: {e}")

    def _init_social_app(self):
        if self._is_management_command():
            return

        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp
            import os

            # 1. Ensure Site exists
            site, _ = Site.objects.get_or_create(
                id=1,
                defaults={
                    'domain': 'smartrealty-system.onrender.com',
                    'name': 'SmartRealty'
                }
            )

            client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
            secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()

            if not (client_id and secret):
                logger.warning("[AUTO-SETUP] Google credentials not set!")
                return

            # BUG FIX: the old code did a raw-SQL DELETE of every Google
            # SocialApp followed by a fresh CREATE, every single time this
            # ready() hook ran. With multiple gunicorn workers all booting
            # at once on every deploy/restart, each worker raced to delete
            # and recreate the same row at the same time — this caused
            # intermittent "SocialApp matching query does not exist" / DB
            # lock errors on "Continue with Google" right after a deploy.
            # update_or_create is idempotent: if the row already has the
            # right credentials nothing changes; if it's missing or stale,
            # it's fixed in place without ever deleting it first.
            app, created = SocialApp.objects.update_or_create(
                provider='google',
                defaults={
                    'name': 'Google OAuth',
                    'client_id': client_id,
                    'secret': secret,
                }
            )
            if not app.sites.filter(pk=site.pk).exists():
                app.sites.add(site)

            logger.info(f"[AUTO-SETUP] Google SocialApp {'created' if created else 'verified'}")

        except Exception as e:
            logger.error(f"[AUTO-SETUP] SocialApp setup failed: {e}")