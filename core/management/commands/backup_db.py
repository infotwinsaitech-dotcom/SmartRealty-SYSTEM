from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings
import os
import requests


class Command(BaseCommand):
    help = 'Backup database to free cloud storage'

    def handle(self, *args, **kwargs):
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.json'

        # Create backup
        with open(filename, 'w') as f:
            call_command('dumpdata',
                        '--exclude', 'contenttypes',
                        '--exclude', 'auth.permission',
                        '--exclude', 'sessions',
                        '--exclude', 'admin.logentry',
                        stdout=f)

        self.stdout.write(self.style.SUCCESS(f'✅ Backup created: {filename}'))

        # Upload to file.io (free, 14 days retention)
        try:
            with open(filename, 'rb') as f:
                response = requests.post('https://file.io', files={'file': f}, timeout=30)
                if response.status_code == 200:
                    link = response.json().get('link')
                    self.stdout.write(
                        self.style.SUCCESS(f'☁️  Upload: {link}')
                    )
                    # Save link to a file for reference
                    with open('latest_backup_link.txt', 'w') as link_file:
                        link_file.write(f"{link} | {timestamp}")
                else:
                    self.stdout.write(
                        self.style.WARNING('⚠️ Upload failed, keeping local')
                    )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Upload error: {e}')
            )

        # Clean old backups (keep last 5)
        self._cleanup_old_backups()

    def _cleanup_old_backups(self):
        import glob
        backups = sorted(glob.glob('backup_*.json'))
        for old in backups[:-5]:
            os.remove(old)
            self.stdout.write(f'🗑️  Removed: {old}')