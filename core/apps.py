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
        
        import time
        
        # Retry 3 times with delay
        for attempt in range(3):
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
                
                # 2. STRONG CLEANUP: Delete ALL Google apps using raw SQL
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM socialaccount_socialapp_sites WHERE socialapp_id IN (SELECT id FROM socialaccount_socialapp WHERE provider = 'google');")
                    cursor.execute("DELETE FROM socialaccount_socialapp WHERE provider = 'google';")
                    logger.info("[AUTO-SETUP] Deleted all Google SocialApps via raw SQL")
                
                # 3. Create FRESH
                client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
                secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
                
                if client_id and secret:
                    app = SocialApp.objects.create(
                        provider='google',
                        name='Google OAuth',
                        client_id=client_id,
                        secret=secret,
                    )
                    app.sites.add(site)
                    logger.info("[AUTO-SETUP] Google SocialApp created fresh")
                    return  # Success!
                else:
                    logger.warning("[AUTO-SETUP] Google credentials not set!")
                    return
                    
            except Exception as e:
                logger.error(f"[AUTO-SETUP] Attempt {attempt + 1} failed: {e}")
                time.sleep(2)  # Wait before retry
        
        logger.error("[AUTO-SETUP] All attempts failed")