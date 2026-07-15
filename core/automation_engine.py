# core/automation_engine.py

from django.utils.timezone import now
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import Lead, FollowUp, AutomationLog, DripSequence, EscalationRule
import os

class SmartAutomationEngine:
    
    def __init__(self, builder):
        self.builder = builder
    
    def process_new_lead(self, lead):
        """Jab naya lead aaye → Drip sequence start"""
        if not lead.automation_enabled:
            return
        
        # Get builder's drip sequence
        sequences = DripSequence.objects.filter(
            builder=self.builder, 
            is_active=True
        ).order_by('step_number')
        
        for seq in sequences:
            scheduled_date = now() + timedelta(days=seq.delay_days)
            scheduled_time = datetime.strptime("10:00", "%H:%M").time()
            
            FollowUp.objects.create(
                lead=lead,
                agent=lead.assigned_to,
                date=scheduled_date.date(),
                time=scheduled_time,
                note=f"Auto: {seq.channel} - {seq.template_message[:50]}...",
                is_auto_created=True,
                sequence_step=seq.step_number,
                status='PENDING'
            )
        
        # Day 0 - Immediate welcome
        self.send_message(lead, 'WHATSAPP', 
            f"Hi {lead.name}, thanks for your interest! Our agent will contact you shortly.")
        
        lead.last_followup_date = now()
        lead.save()
    
    def check_missed_followups(self):
        """Missed followups check"""
        today = now().date()
        current_time = now().time()
        
        missed = FollowUp.objects.filter(
            lead__builder=self.builder,
            status='PENDING',
            date__lte=today,
            time__lte=current_time
        ).exclude(
            date=today, 
            time__gt=current_time
        )
        
        for followup in missed:
            self.handle_missed_followup(followup)
    
    def handle_missed_followup(self, followup):
        """Missed followup handle"""
        lead = followup.lead
        agent = followup.agent
        
        followup.status = 'MISSED'
        followup.save()
        
        AutomationLog.objects.create(
            lead=lead,
            action_type='MISSED_FOLLOWUP',
            channel='SYSTEM',
            message=f"Followup missed by {agent.name if agent else 'Unassigned'}"
        )
        
        missed_count = FollowUp.objects.filter(lead=lead, status='MISSED').count()
        
        rule = EscalationRule.objects.filter(
            builder=self.builder,
            is_active=True
        ).first()
        
        if rule and missed_count >= rule.missed_followups:
            self.escalate_lead(lead, rule, missed_count)
        else:
            FollowUp.objects.create(
                lead=lead,
                agent=agent,
                date=now().date() + timedelta(days=1),
                time=datetime.strptime("09:00", "%H:%M").time(),
                note=f"URGENT: Missed followup #{missed_count}. Contact immediately!",
                is_auto_created=True,
                status='PENDING'
            )
            
            self.send_message(lead, 'WHATSAPP', 
                f"⚠️ URGENT: You missed followup with {lead.name}. Next: tomorrow 9 AM.")
    
    def escalate_lead(self, lead, rule, missed_count):
        """Lead escalate"""
        lead.escalation_level = 1
        lead.save()
        
        FollowUp.objects.create(
            lead=lead,
            agent=None,
            date=now().date(),
            time=now().time(),
            note=f"ESCALATED: {missed_count} missed. Reassigned to {rule.escalate_to.username}",
            is_auto_created=True,
            status='ESCALATED'
        )
        
        if rule.auto_reassign and lead.assigned_to:
            lead.assigned_to = None
            lead.save()
        
        self.send_message(lead, 'EMAIL',
            f"ESCALATION: Lead '{lead.name}' has {missed_count} missed followups!")
        
        AutomationLog.objects.create(
            lead=lead,
            action_type='ESCALATION',
            channel='SYSTEM',
            message=f"Escalated to {rule.escalate_to.username}"
        )
    
    def send_message(self, lead, channel, message):
        """Multi-channel sender"""
        log = AutomationLog.objects.create(
            lead=lead,
            action_type='AUTO_MESSAGE',
            channel=channel,
            message=message
        )
        
        try:
            if channel == 'SMS':
                self._send_sms(lead.phone, message)
            elif channel == 'EMAIL':
                self._send_email(lead.email, message)
            elif channel == 'WHATSAPP':
                self._send_whatsapp(lead.phone, message)
            
            log.status = 'SENT'
            log.save()
            
        except Exception as e:
            log.status = 'FAILED'
            log.response = str(e)
            log.save()
    
    def _send_sms(self, phone, message):
        print(f"SMS to {phone}: {message}")
    
    def _send_email(self, email, message):
        if email:
            send_mail(
                'RealShree - Follow-up',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False
            )
    
    def _send_whatsapp(self, phone, message):
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
            client.messages.create(
                from_='whatsapp:+14155238886',
                body=message,
                to=f'whatsapp:+91{phone}'
            )
        except Exception as e:
            print(f"WhatsApp failed: {e}")