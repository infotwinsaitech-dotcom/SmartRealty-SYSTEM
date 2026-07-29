from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Property, PropertyImage, Inquiry, SiteSettings, User, Profile, 
    Lead, Deal, Task, Activity, Document, Notification, AIInsight, 
    LeadScore, Campaign, FollowUp, DripSequence, EscalationRule, 
    AutomationLog, Advertisement, PropertyReview, FloorPlan
)

# ========== PROPERTY ==========
class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 3


class FloorPlanInline(admin.TabularInline):
    model = FloorPlan
    extra = 1
    fields = ['unit_type', 'carpet_area', 'super_area', 'price', 'image', 'display_order']


class PropertyAdmin(admin.ModelAdmin):
    inlines = [PropertyImageInline, FloorPlanInline]
    search_fields = ['title', 'project_name', 'location']


admin.site.register(Property, PropertyAdmin)


# ========== INQUIRY ==========
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'property', 'created_at']

# ========== PROPERTY REVIEW (Ratings & Reviews moderation) ==========
@admin.register(PropertyReview)
class PropertyReviewAdmin(admin.ModelAdmin):
    list_display = ['reviewer_name', 'property', 'overall_rating', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'reviewer_type']
    list_editable = ['is_approved']
    search_fields = ['reviewer_name', 'property__title', 'property__project_name']
    autocomplete_fields = ['property']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Reviewer', {'fields': ('property', 'user', 'reviewer_name', 'reviewer_type')}),
        ('Ratings (1-5)', {'fields': ('connectivity_rating', 'neighbourhood_rating', 'safety_rating', 'livability_rating')}),
        ('Review Text', {'fields': ('good_things', 'needs_improvement')}),
        ('Moderation', {'fields': ('is_approved', 'helpful_count', 'created_at')}),
    )

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

# ========== ADVERTISEMENT (HOME PAGE BANNER) ==========
@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ['title', 'property', 'is_active', 'order', 'created_at']
    list_filter = ['is_active']
    list_editable = ['is_active', 'order']
    search_fields = ['title', 'property__title', 'property__project_name']
    autocomplete_fields = ['property']

# ========== FOLLOWUP & AUTOMATION ==========
admin.site.register(FollowUp)
admin.site.register(DripSequence)
admin.site.register(EscalationRule)
admin.site.register(AutomationLog)