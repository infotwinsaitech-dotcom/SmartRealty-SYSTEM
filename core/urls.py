from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.http import JsonResponse
from . import views
from . import views_automation

# BUG FIX: views_health se import karo — duplicate local def hataya
from core.views_health import health_check, cache_status

urlpatterns = [

    # ================= PUBLIC =================

    path("", views.home, name="user_home"),
    path("properties/", views.property_list, name="property_list"),
    path("properties/<int:id>/", views.property_detail, name="property_detail"),

    path("contact/", views.contact, name="contact"),
    path("about/", views.about, name="about"),

    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    path("forgot_password/", views.forgot_password, name="forgot_password"),
    path("otp_verification/", views.otp_verification, name="otp_verification"),
    path("reset_password/", views.reset_password, name="reset_password"),

    path("profile/", views.profile, name="profile"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),

    path("my-properties/", views.my_properties, name="my_property"),
    path("my-inquiries/", views.my_inquiries, name="my_inquiries"),

    path("add-property/", views.add_property, name="add_property"),

    path("privacy/", views.privacy, name="privacy"),

    # ================= HEALTH CHECK =================
    # BUG FIX: Sirf ek health path — pehle 2 jagah tha (line 73 aur 228)
    path("health/", health_check, name="health"),
    path("health/cache/", cache_status, name="cache_status"),

    # ================= CALCULATORS & WISHLIST =================

    path("emi-calculator/", views.emi_calculator, name="emi_calculator"),
    path("roi-calculator/", views.roi_calculator, name="roi_calculator"),

    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/count/", views.wishlist_count, name="wishlist_count"),
    path("wishlist/add/<int:property_id>/", views.wishlist_add, name="wishlist_add"),
    path("wishlist/remove/<int:property_id>/", views.wishlist_remove, name="wishlist_remove"),
    path("wishlist/compare/", views.wishlist_compare, name="wishlist_compare"),

    # ================= BUILDER =================

    path("builder/", views.builder_root),
    path("builder/dashboard/", views.builder_dashboard, name="builder_dashboard"),
    path("builder/properties/", views.property_management, name="property_management"),
    path("builder/properties/wishlist/", views.property_wishlist_list, name="property_wishlist_list"),
    path("builder/property/<int:id>/", views.builder_property_detail, name="builder_property_detail"),
    path("builder/property/delete/<int:id>/", views.delete_property, name="delete_property"),
    path("builder/leads/", views.lead_management, name="lead_management"),
    path("builder/leads/add/", views.add_lead, name="add_lead"),
    path("builder/leads/edit/<int:id>/", views.edit_lead, name="edit_lead"),
    path("builder/lead/<int:id>/", views.lead_detail_api, name="lead_detail_api"),
    path("builder/lead/delete/<int:id>/", views.delete_lead, name="delete_lead"),
    path("builder/export-leads/", views.export_leads_csv, name="export_leads_csv"),
    path("builder/pipeline/", views.builder_pipeline, name="builder_pipeline"),
    path("builder/update-lead-status/", views.update_lead_status, name="update_lead_status"),
    path("builder/analytics/", views.analytics, name="analytics"),
    path("builder/documents/", views.document_management, name="document_management"),
    path("delete-document/<int:doc_id>/", views.delete_document, name="delete_document"),
    path("builder/communication/", views.communication, name="communication"),
    path("builder/create-task/", views.create_task, name="create_task"),
    path("builder/task-done/<int:id>/", views.task_done, name="task_done"),
    path("builder/scheduler/", views.scheduler_overview, name="builder_scheduler"),
    path("builder/reorder-task/", views.reorder_task, name="reorder_task"),
    path("builder/check-reminders/", views.check_reminders, name="check_reminders"),
    path("builder/notifications/", views.notifications_page, name="notifications"),
    path("mark-notification/<int:id>/", views.mark_notification_read, name="mark_notification_read"),
    path("builder/create-agent/", views.create_agent, name="create_agent"),
    path("builder/users/", views.manage_users, name="manage_users"),
    path("builder/users/delete/<int:id>/", views.delete_agent, name="delete_agent"),
    path("builder/users/toggle/<int:id>/", views.toggle_agent, name="toggle_agent"),
    path("builder/agent/<int:id>/", views.agent_detail, name="agent_detail"),
    path("builder/export-agents/", views.export_agents, name="export_agents"),
    path("builder/agents-performance/", views.agent_performance, name="agent_performance"),
    path("builder/ai-insights/", views.ai_insights, name="ai_insights"),
    path("builder/marketing/", views.marketing_automation, name="marketing_automation"),
    path("builder/campaign/create/", views.create_campaign, name="create_campaign"),
    path("builder/campaign/run/<int:id>/", views.run_campaign, name="run_campaign"),
    path("builder/campaign/delete/<int:id>/", views.delete_campaign, name="delete_campaign"),
    path("builder/scale-launch-checklist/", views.scale_launch_checklist, name="scale_launch_checklist"),

    # ================= AGENT =================

    path("agent/dashboard/", views.agent_dashboard, name="agent_dashboard"),
    path("agent/leads/", views.agent_leads, name="agent_leads"),
    path("agent/properties/", views.agent_properties, name="agent_properties"),
    path("agent/profile/", views.agent_profile, name="agent_profile"),
    path("agent/scheduler/", views.scheduler, name="agent_scheduler"),
    path("agent/site-visits/", views.site_visits, name="site_visits"),
    path("add-followup/<int:lead_id>/", views.add_followup, name="add_followup"),
    path("followup/done/<int:id>/", views.mark_followup_done, name="mark_followup_done"),
    path("add-deal/", views.add_deal, name="add_deal"),
    path("update-deal/<int:deal_id>/", views.update_deal, name="update_deal"),

    # ================= CHAT =================

    path("send-message/", views.send_message, name="send_message"),
    path("client/send-message/", views.client_send_message, name="client_send_message"),
    path("agent/send-message/", views.agent_send_message, name="agent_send_message"),
    path("get-messages/", views.get_messages, name="get_messages"),
    path("chatbot/", lambda request: render(request, "chatbot.html"), name="chatbot"),

    # ================= OTHER =================

    path("assign-property/", views.assign_property, name="assign_property"),
    path("export-leads/", views.export_leads, name="export_leads"),
    path("add-to-cart/<int:id>/", views.add_to_cart, name="add_to_cart"),
    path("settings/", views.settings_view, name="settings"),
    path("agent/delete-lead/<int:lead_id>/", views.agent_delete_lead, name="agent_delete_lead"),

    # ================= AUTOMATION =================

    path("builder/automation/", views_automation.automation_settings, name="automation_settings"),
    path("builder/automation/drip/create/", views_automation.create_drip_sequence, name="create_drip"),
    path("builder/automation/escalation/create/", views_automation.create_escalation_rule, name="create_escalation"),
    path("builder/automation/logs/", views_automation.automation_logs, name="automation_logs"),
    path("builder/lead/<int:lead_id>/toggle-automation/", views_automation.toggle_lead_automation, name="toggle_automation"),

    path("properties-alt/", views.property_list, name="properties"),
    path("add-existing-agent/", views.add_existing_agent, name="add_existing_agent"),
    path("remove-agent/<int:agent_id>/", views.remove_agent_from_builder, name="remove_agent_from_builder"),
    path("export-dashboard-csv/", views.export_dashboard_csv, name="export_dashboard_csv"),
    path("agent/property-leads/<int:property_id>/", views.property_leads, name="property_leads"),
    path("accounts/", include("allauth.urls")),
    path("auth/redirect/", views.google_login_redirect, name="google_redirect"),
    path("api/check-username/", views.check_username, name="check_username"),
    path("get-messages-ajax/", views.get_messages_ajax, name="get_messages_ajax"),
    # urls.py
path("agent/toggle-scheduler/", views.toggle_scheduler, name="toggle_scheduler"),
path('pipeline/', views.builder_pipeline, name='builder_pipeline'),
path('accounts/', include('allauth.urls')),
    path("update-lead-status/", views.update_lead_status, name="update_lead_status"),
    path("add-note/", views.add_note, name="add_note"),
    path("update-priority/", views.update_priority, name="update_priority"),
    path("builder/property-map/", views.property_map, name="property_map"),
    # urls.py
    path("property-map/", views.property_map_public, name="property_map_public"),
    path('', views.home, name='home'),
    path('properties/', views.property_list, name='property_list'),
    path('property/<int:id>/', views.property_detail, name='property_detail'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('contact/', views.contact, name='contact'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('profile/', views.profile, name='profile'),
    
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
