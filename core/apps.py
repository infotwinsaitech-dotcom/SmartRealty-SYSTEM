from django.apps import AppConfig
from django.db import connection, ProgrammingError, OperationalError
import logging
import sys

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals
        self._init_cache_table()
        self._optimize_postgres()
        logger.info("✅ Core app initialized")

    def _init_cache_table(self):
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
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION idle_in_transaction_session_timeout = '30s';")
                cursor.execute("SET SESSION statement_timeout = '30s';")
                cursor.execute("SET SESSION work_mem = '8MB';")
        except Exception as e:
            logger.debug(f"PG optimize: {e}")

    def _is_management_command(self):
        mgmt = ['migrate', 'makemigrations', 'collectstatic', 'createsuperuser', 'shell', 'test', 'runserver']
        return any(cmd in sys.argv for cmd in mgmt)