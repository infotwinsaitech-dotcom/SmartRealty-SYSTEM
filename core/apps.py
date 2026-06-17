from django.apps import AppConfig
from django.db import connection


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Signals import karo — isse cache auto-invalidate hoga
        import core.signals
        
        # PostgreSQL session optimize
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION idle_in_transaction_session_timeout = '30s';")
                print("✅ PostgreSQL session optimized")
        except Exception as e:
            print(f"⚠️ DB optimization skipped: {e}")