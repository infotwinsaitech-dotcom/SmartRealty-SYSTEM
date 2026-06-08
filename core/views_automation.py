# core/views_automation.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from .models import Lead, FollowUp, DripSequence, EscalationRule, AutomationLog
from .automation_engine import SmartAutomationEngine
# ❌ from .tasks import trigger_new_lead_automation  # HATAO
import json

User = get_user_model()

@login_required
def automation_settings(request):
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
    if request.user.role != 'builder':
        return redirect('login')
    
    logs = AutomationLog.objects.filter(
        lead__builder=request.user
    ).order_by('-sent_at')[:100]
    
    return render(request, 'builder/automation_logs.html', {'logs': logs})

@login_required
def toggle_lead_automation(request, lead_id):
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

    agent = auto_assign_agent(request.user)

    lead = Lead.objects.create(
        name=request.POST.get("name"),
        email=request.POST.get("email"),
        phone=request.POST.get("phone"),
        source=request.POST.get("source"),
        status=request.POST.get("status"),
        assigned_to=agent,
        interest=request.POST.get("interest"),
        builder=request.user,
        notes=request.POST.get("message")
    )

    LeadActivity.objects.create(lead=lead, message="Lead created")

    property_id = request.POST.get("property_id")
    if property_id:
        property_obj = get_object_or_404(Property, id=property_id, builder=request.user)
        lead.properties.add(property_obj)

    # ✅ DIRECT CALL — NO CELERY
    engine = SmartAutomationEngine(lead.builder)
    engine.process_new_lead(lead)

    messages.success(request, f"Lead '{lead.name}' assigned to {agent.name if agent else 'No Agent'}")
    return redirect("lead_management")