"""
Django management command to run background tasks
Usage: python manage.py run_tasks --task drip --builder 1
"""

import argparse
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.tasks import (
    process_drip_sequences,
    check_missed_followups_task,
    trigger_new_lead_automation,
    process_scheduled_campaigns,
    send_daily_summaries,
    cleanup_old_data,
    health_check
)


class Command(BaseCommand):
    help = 'Run background tasks for SmartRealty CRM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            required=True,
            choices=[
                'drip',
                'missed',
                'new_lead',
                'campaigns',
                'summary',
                'cleanup',
                'health',
                'all'
            ],
            help='Task to run'
        )
        parser.add_argument(
            '--builder',
            type=int,
            default=None,
            help='Builder ID (optional)'
        )
        parser.add_argument(
            '--lead',
            type=int,
            default=None,
            help='Lead ID (for new_lead task)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Days for cleanup task'
        )

    def handle(self, *args, **options):
        task = options['task']
        builder_id = options['builder']
        lead_id = options['lead']
        dry_run = options['dry_run']
        days = options['days']

        self.stdout.write(
            self.style.SUCCESS(f"Running task: {task} at {timezone.now()}")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        result = None

        try:
            if task == 'drip':
                result = process_drip_sequences(builder_id=builder_id, dry_run=dry_run)
                
            elif task == 'missed':
                result = check_missed_followups_task(builder_id=builder_id, dry_run=dry_run)
                
            elif task == 'new_lead':
                if not lead_id:
                    self.stdout.write(self.style.ERROR("Lead ID required for new_lead task"))
                    return
                result = trigger_new_lead_automation(lead_id, dry_run=dry_run)
                
            elif task == 'campaigns':
                result = process_scheduled_campaigns(dry_run=dry_run)
                
            elif task == 'summary':
                result = send_daily_summaries(builder_id=builder_id, dry_run=dry_run)
                
            elif task == 'cleanup':
                result = cleanup_old_data(days=days, dry_run=dry_run)
                
            elif task == 'health':
                result = health_check()
                
            elif task == 'all':
                self.stdout.write("Running all maintenance tasks...")
                results = {
                    'drip': process_drip_sequences(builder_id=builder_id, dry_run=dry_run),
                    'missed': check_missed_followups_task(builder_id=builder_id, dry_run=dry_run),
                    'campaigns': process_scheduled_campaigns(dry_run=dry_run),
                }
                result = results

            self.stdout.write(
                self.style.SUCCESS(f"Task completed successfully: {result}")
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Task failed: {str(e)}")
            )
            raise