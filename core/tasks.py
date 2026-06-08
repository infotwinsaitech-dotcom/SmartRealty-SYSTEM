# core/tasks.py — NO CELERY VERSION

from django.utils.timezone import now
from .models import Lead, FollowUp, DripSequence
from .automation_engine import SmartAutomationEngine

def process_drip_sequences():
    """Drip sequences check — call from management command or cron"""
    today = now().date()
    current_time = now().time()
    
    todays_followups = FollowUp.objects.filter(
        date=today,
        time__hour=current_time.hour,
        status='PENDING',
        is_auto_created=True
    ).select_related('lead', 'agent')
    
    for followup in todays_followups:
        lead = followup.lead
        builder = lead.builder
        
        sequence = DripSequence.objects.filter(
            builder=builder,
            step_number=followup.sequence_step,
            is_active=True
        ).first()
        
        if sequence:
            engine = SmartAutomationEngine(builder)
            message = sequence.template_message.format(
                name=lead.name,
                agent=followup.agent.name if followup.agent else 'Our Team',
                property=lead.interest or 'this property'
            )
            engine.send_message(lead, sequence.channel, message)
            
            followup.status = 'DONE'
            followup.completed_at = now()
            followup.save()
            
            lead.last_followup_date = now()
            lead.followup_count += 1
            lead.save()


def check_missed_followups_task():
    """Missed followups check"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    builders = User.objects.filter(role='builder')
    
    for builder in builders:
        engine = SmartAutomationEngine(builder)
        engine.check_missed_followups()


def trigger_new_lead_automation(lead_id):
    """New lead automation trigger"""
    from .models import Lead
    lead = Lead.objects.get(id=lead_id)
    engine = SmartAutomationEngine(lead.builder)
    engine.process_new_lead(lead)