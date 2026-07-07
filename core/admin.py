from django.contrib import admin
from .models import (
    Property, PropertyImage, Inquiry, SiteSettings, User, Profile, 
    Lead, Deal, Task, Activity, Document, Notification, AIInsight, 
    LeadScore, Campaign, FollowUp, DripSequence, EscalationRule, 
    AutomationLog
)


# ========== PROPERTY ==========
class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 3


class PropertyAdmin(admin.ModelAdmin):
    inlines = [PropertyImageInline]


admin.site.register(Property, PropertyAdmin)


# ========== INQUIRY ==========
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'property', 'created_at']


# ========== SITE SETTINGS (ONLY ONCE!) ==========
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Company Info', {
            'fields': ('company_name', 'phone', 'email', 'location', 'about_text')
        }),
        ('Branding', {
            'fields': ('logo', 'favicon')
        }),
        ('Social Links', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url', 'whatsapp_number'),
            'classes': ('collapse',),
        }),
        ('Feature Flags', {
            'fields': ('enable_scheduler', 'enable_site_visits'),
            'classes': ('collapse',),
        }),
    )


# ========== USER & PROFILE ==========
admin.site.register(User)
admin.site.register(Profile)


# ========== LEAD & DEAL ==========
admin.site.register(Lead)
admin.site.register(Deal)


# ========== TASK & ACTIVITY ==========
admin.site.register(Task)
admin.site.register(Activity)


# ========== DOCUMENT ==========
admin.site.register(Document)


# ========== NOTIFICATION ==========
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read']
    search_fields = ['title', 'message']


# ========== AI & CAMPAIGN ==========
admin.site.register(AIInsight)
admin.site.register(LeadScore)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'status', 'sent']


# ========== FOLLOWUP & AUTOMATION ==========
admin.site.register(FollowUp)
admin.site.register(DripSequence)
admin.site.register(EscalationRule)
admin.site.register(AutomationLog)