# core/management/commands/init_cache.py
# =======================================

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection, ProgrammingError, OperationalError
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize cache table safely (idempotent)'

    def handle(self, *args, **options):
        try:
            # Try to use cache (table exists check)
            cache.set('_init_check', 'ok', 1)
            cache.get('_init_check')
            self.stdout.write(self.style.SUCCESS('✅ Cache table already exists'))
            return
            
        except (ProgrammingError, OperationalError):
            # Table doesn't exist — create it
            self.stdout.write(self.style.WARNING('⚠️ Cache table missing — creating...'))
            
        from django.core.management import call_command
        call_command('createcachetable')
        
        # Verify
        cache.set('_verify', 'ok', 10)
        if cache.get('_verify') == 'ok':
            self.stdout.write(self.style.SUCCESS('✅ Cache table created & verified'))
        else:
            self.stdout.write(self.style.ERROR('❌ Cache table creation failed'))


# =======================================
# Also create: core/management/__init__.py (empty)
# And: core/management/commands/__init__.py (empty)