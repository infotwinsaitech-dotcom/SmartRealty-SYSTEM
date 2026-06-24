from django.core.management.base import BaseCommand
from core.models import Lead

class Command(BaseCommand):
    help = 'Fix leads with HOT/WARM/COLD status to proper status+priority'

    def handle(self, *args, **options):
        # HOT -> NEW + HOT priority
        hot_count = Lead.objects.filter(status='HOT').update(status='NEW', priority='HOT')
        self.stdout.write(self.style.SUCCESS(f'Fixed {hot_count} HOT leads'))
        
        # WARM -> NEW + WARM priority
        warm_count = Lead.objects.filter(status='WARM').update(status='NEW', priority='WARM')
        self.stdout.write(self.style.SUCCESS(f'Fixed {warm_count} WARM leads'))
        
        # COLD -> NEW + COLD priority
        cold_count = Lead.objects.filter(status='COLD').update(status='NEW', priority='COLD')
        self.stdout.write(self.style.SUCCESS(f'Fixed {cold_count} COLD leads'))
        
        self.stdout.write(self.style.SUCCESS('All leads fixed!'))