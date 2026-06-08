# core/automation_engine.py

from django.utils.timezone import now
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import Lead, FollowUp, AutomationLog, DripSequence, EscalationRule
import requests
import json

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
        self.send_message(lead, 'WHATSAPP', f"Hi {lead.name}, thanks for your interest! Our agent will contact you shortly.")
        
        lead.last_followup_date = now()
        lead.save()
    
    def check_missed_followups(self):
        """Har hour run karo - missed followups check"""
        today = now().date()
        current_time = now().time()
        
        # Find all pending followups that are past due
        missed = FollowUp.objects.filter(
            lead__builder=self.builder,
            status='PENDING',
            date__lte=today,
            time__lte=current_time
        ).exclude(
            date=today, 
            time__gt=current_time  # Aaj ka time abhi nahi aaya
        )
        
        for followup in missed:
            self.handle_missed_followup(followup)
    
    def handle_missed_followup(self, followup):
        """Missed followup ko handle karo"""
        lead = followup.lead
        agent = followup.agent
        
        # Mark as missed
        followup.status = 'MISSED'
        followup.save()
        
        # Log it
        AutomationLog.objects.create(
            lead=lead,
            action_type='MISSED_FOLLOWUP',
            channel='SYSTEM',
            message=f"Followup missed by {agent.name if agent else 'Unassigned'}"
        )
        
        # Check escalation rules
        missed_count = FollowUp.objects.filter(
            lead=lead, 
            status='MISSED'
        ).count()
        
        rule = EscalationRule.objects.filter(
            builder=self.builder,
            is_active=True
        ).first()
        
        if rule and missed_count >= rule.missed_followups:
            self.escalate_lead(lead, rule, missed_count)
        else:
            # Create urgent followup for next day
            FollowUp.objects.create(
                lead=lead,
                agent=agent,
                date=now().date() + timedelta(days=1),
                time=datetime.strptime("09:00", "%H:%M").time(),
                note=f"URGENT: Missed followup #{missed_count}. Please contact immediately!",
                is_auto_created=True,
                status='PENDING'
            )
            
            # Notify agent
            self.send_message(lead, 'WHATSAPP', 
                f"⚠️ URGENT: You missed a followup with {lead.name}. Next followup scheduled for tomorrow 9 AM.")
    
    def escalate_lead(self, lead, rule, missed_count):
        """Lead ko escalate karo builder/admin ko"""
        lead.escalation_level = 1
        lead.save()
        
        # Create escalation followup
        FollowUp.objects.create(
            lead=lead,
            agent=None,  # Builder will handle
            date=now().date(),
            time=now().time(),
            note=f"ESCALATED: {missed_count} missed followups. Auto-reassigned to {rule.escalate_to.username}",
            is_auto_created=True,
            status='ESCALATED'
        )
        
        # Auto reassign if enabled
        if rule.auto_reassign and lead.assigned_to:
            old_agent = lead.assigned_to
            lead.assigned_to = None  # Or assign to senior agent
            lead.save()
            
            # Notify old agent
            self.send_message(lead, 'WHATSAPP',
                f"Lead {lead.name} has been escalated to {rule.escalate_to.username} due to {missed_count} missed followups.")
        
        # Notify builder/admin
        self.send_message(lead, 'EMAIL',
            f"ESCALATION ALERT: Lead '{lead.name}' has {missed_count} missed followups. Immediate action required!")
        
        # Log escalation
        AutomationLog.objects.create(
            lead=lead,
            action_type='ESCALATION',
            channel='SYSTEM',
            message=f"Escalated to {rule.escalate_to.username} after {missed_count} missed followups"
        )
    
    def send_message(self, lead, channel, message):
        """Multi-channel message sender"""
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
        # Integrate with Twilio/SMS provider
        print(f"SMS to {phone}: {message}")
    
    def _send_email(self, email, message):
        send_mail(
            'Smart Realty - Follow-up',
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
    
    def _send_whatsapp(self, phone, message):
        # Twilio WhatsApp API
        from twilio.rest import Client
        client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
        client.messages.create(
            from_='whatsapp:+14155238886',
            body=message,
            to=f'whatsapp:+91{phone}'
        )