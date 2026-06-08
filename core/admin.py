from django.contrib import admin
from .models import Property, PropertyImage, Inquiry, SiteSettings, User, Profile, Lead, Deal, Task, Activity, Document, Notification, AIInsight, LeadScore, Campaign
from .models import FollowUp

class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 3

class PropertyAdmin(admin.ModelAdmin):
    inlines = [PropertyImageInline]

admin.site.register(Property, PropertyAdmin)

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'property', 'created_at']

admin.site.register(SiteSettings)
admin.site.register(User)
admin.site.register(Profile)
admin.site.register(Lead)
admin.site.register(Deal)
admin.site.register(Task)
admin.site.register(Activity)
admin.site.register(Document)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read']
    search_fields = ['title', 'message']

admin.site.register(AIInsight)
admin.site.register(LeadScore)

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'status', 'sent']

admin.site.register(FollowUp)
from .models import DripSequence, EscalationRule, AutomationLog

admin.site.register(DripSequence)
admin.site.register(EscalationRule)
admin.site.register(AutomationLog)