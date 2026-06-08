# core/tasks.py

from celery import shared_task
from django.utils.timezone import now
from .models import Lead, FollowUp, DripSequence
from .automation_engine import SmartAutomationEngine

@shared_task
def process_drip_sequences():
    """Har 6 hours mein run - drip sequences check"""
    today = now().date()
    current_time = now().time()
    
    # Find followups scheduled for today
    todays_followups = FollowUp.objects.filter(
        date=today,
        time__hour=current_time.hour,
        status='PENDING',
        is_auto_created=True
    ).select_related('lead', 'agent')
    
    for followup in todays_followups:
        lead = followup.lead
        builder = lead.builder
        
        # Get drip sequence for this step
        sequence = DripSequence.objects.filter(
            builder=builder,
            step_number=followup.sequence_step,
            is_active=True
        ).first()
        
        if sequence:
            engine = SmartAutomationEngine(builder)
            
            # Personalize message
            message = sequence.template_message.format(
                name=lead.name,
                agent=followup.agent.name if followup.agent else 'Our Team',
                property=lead.interest or 'this property'
            )
            
            engine.send_message(lead, sequence.channel, message)
            
            # Mark followup done
            followup.status = 'DONE'
            followup.completed_at = now()
            followup.save()
            
            lead.last_followup_date = now()
            lead.followup_count += 1
            lead.save()

@shared_task
def check_missed_followups_task():
    """Har hour mein run - missed followups check"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    builders = User.objects.filter(role='builder')
    
    for builder in builders:
        engine = SmartAutomationEngine(builder)
        engine.check_missed_followups()

@shared_task
def trigger_new_lead_automation(lead_id):
    """Jab naya lead create ho → Ye task run karo"""
    from .models import Lead
    lead = Lead.objects.get(id=lead_id)
    engine = SmartAutomationEngine(lead.builder)
    engine.process_new_lead(lead)