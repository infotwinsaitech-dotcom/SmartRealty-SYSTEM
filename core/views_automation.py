# core/views_automation.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Lead, FollowUp, DripSequence, EscalationRule, AutomationLog
from .tasks import trigger_new_lead_automation
import json

@login_required
def automation_settings(request):
    """Builder ka automation settings page"""
    if request.user.role != 'builder':
        return redirect('login')
    
    drip_sequences = DripSequence.objects.filter(builder=request.user)
    escalation_rules = EscalationRule.objects.filter(builder=request.user)
    
    return render(request, 'builder/automation_settings.html', {
        'drip_sequences': drip_sequences,
        'escalation_rules': escalation_rules,
    })

@login_required
@require_POST
def create_drip_sequence(request):
    """Builder drip sequence create kare"""
    if request.user.role != 'builder':
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    data = json.loads(request.body)
    
    DripSequence.objects.create(
        builder=request.user,
        name=data.get('name'),
        step_number=data.get('step_number'),
        delay_days=data.get('delay_days'),
        channel=data.get('channel'),
        template_message=data.get('template_message')
    )
    
    return JsonResponse({'success': True, 'message': 'Drip sequence created'})

@login_required
@require_POST
def create_escalation_rule(request):
    """Builder escalation rule create kare"""
    if request.user.role != 'builder':
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    data = json.loads(request.body)
    
    escalate_to_id = data.get('escalate_to')
    escalate_to = get_object_or_404(User, id=escalate_to_id) if escalate_to_id else request.user
    
    EscalationRule.objects.create(
        builder=request.user,
        name=data.get('name'),
        missed_followups=data.get('missed_followups', 2),
        escalate_to=escalate_to,
        auto_reassign=data.get('auto_reassign', True),
        notify_channels=data.get('notify_channels', 'EMAIL,WHATSAPP')
    )
    
    return JsonResponse({'success': True, 'message': 'Escalation rule created'})

@login_required
def automation_logs(request):
    """Builder automation logs dekhe"""
    if request.user.role != 'builder':
        return redirect('login')
    
    logs = AutomationLog.objects.filter(
        lead__builder=request.user
    ).order_by('-sent_at')[:100]
    
    return render(request, 'builder/automation_logs.html', {'logs': logs})

@login_required
def toggle_lead_automation(request, lead_id):
    """Lead ka automation on/off kare"""
    lead = get_object_or_404(Lead, id=lead_id, builder=request.user)
    lead.automation_enabled = not lead.automation_enabled
    lead.save()
    
    return JsonResponse({
        'success': True, 
        'automation_enabled': lead.automation_enabled
    })

# Modify existing add_lead to trigger automation
@login_required
@require_POST
def add_lead(request):
    if request.user.role != 'builder':
        return redirect('login')
    
    # ... existing lead creation code ...
    
    # Trigger automation
    trigger_new_lead_automation.delay(lead.id)
    
    return redirect('lead_management')