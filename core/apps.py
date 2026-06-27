# core/apps.py — COMPLETE FILE

from django.apps import AppConfig
from django.db import connection, ProgrammingError, OperationalError
import logging
import sys

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # ❌ signals import mat karo agar wahan se create_social_app call hota hai
        # import core.signals  # COMMENT KAR DO YA HATA DO
        
        # 1. Auto-create cache table if missing
        self._init_cache_table()
        
        # 2. PostgreSQL optimization
        self._optimize_postgres()
        
        # 3. Auto-create Google SocialApp (EK HI JAGAH SE)
        self._init_social_app()
        
        logger.info("✅ Core app initialized")

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

    # core/apps.py — _init_social_app() method

def _init_social_app(self):
    """Auto-create Site + SocialApp after DB is ready — delayed to avoid warning"""
    if self._is_management_command():
        return
    
    import threading
    def delayed_setup():
        import time
        time.sleep(3)  # Thoda zyada wait for Django to fully initialize
        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp
            import os
            
            # 1. Ensure Site exists
            site, created = Site.objects.get_or_create(
                id=1,
                defaults={
                    'domain': 'smartrealty-system.onrender.com',
                    'name': 'SmartRealty'
                }
            )
            if created:
                logger.info(f"[AUTO-SETUP] Site created: {site.domain}")
            
            # 2. STRONG DUPLICATE CLEANUP: Delete ALL existing Google apps, then create fresh
            google_apps = list(SocialApp.objects.filter(provider='google'))
            if len(google_apps) > 1:
                logger.warning(f"[AUTO-SETUP] Found {len(google_apps)} Google SocialApps — deleting ALL")
                for app in google_apps:
                    app.delete()
                logger.info("[AUTO-SETUP] All duplicates deleted")
            elif len(google_apps) == 1:
                # Even single one — delete and recreate to ensure clean state
                google_apps[0].delete()
                logger.info("[AUTO-SETUP] Old SocialApp deleted for clean recreate")
            
            # 3. Create FRESH SocialApp
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
                logger.info("[AUTO-SETUP] Google SocialApp FRESH created")
            else:
                logger.warning("[AUTO-SETUP] GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set!")
                    
        except Exception as e:
            logger.error(f"[AUTO-SETUP] Error: {e}")
    
    thread = threading.Thread(target=delayed_setup, daemon=True)
    thread.start()
    def _is_management_command(self):
        """Detect if running management command"""
        mgmt = ['migrate', 'makemigrations', 'collectstatic', 
                'createsuperuser', 'shell', 'dbshell', 'test', 'runserver']
        return any(cmd in sys.argv for cmd in mgmt)