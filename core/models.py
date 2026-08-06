"""
RealShree - Production Ready Models
FIXED VERSION:
  1. Activity.lead ForeignKey indentation fixed
  2. LeadNote.lead related_name fixed
  3. LeadActivity.lead related_name fixed
  4. All models verified for migration compatibility
"""

import os
import re
from decimal import Decimal

from django.db import models
from django.db.models import Index
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib import admin
from django.core.validators import (
    RegexValidator,
    MinValueValidator,
    MaxValueValidator,
    EmailValidator
)
from django.utils import timezone

from cloudinary.models import CloudinaryField
from django.utils import timezone
from django.utils.text import slugify

# =============================================================================
# VALIDATORS
# =============================================================================

phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
)

price_validator = RegexValidator(
    regex=r'^[\d\s.,a-zA-Z]+$',
    message="Price can contain numbers, spaces, dots, commas, and text like 'lakh', 'crore'"
)


# =============================================================================
# PROPERTY MODEL
# =============================================================================

class Property(models.Model):
    PROPERTY_TYPE_CHOICES = [
        ("Flat", "Flat"),
        ("Villa", "Villa"),
        ("Bungalow", "Bungalow"),
        ("Duplex", "Duplex"),
        ("Penthouse", "Penthouse"),
        ("Office", "Office"),
        ("Shop", "Shop"),
        ("Showroom", "Showroom"),
        ("Warehouse", "Warehouse"),
        ("Land", "Land"),
        ("Plot", "Plot"),
        ("Plots", "Plots"),
        ("Farmhouse", "Farmhouse"),
        ("Industrial", "Industrial"),
    ]

    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Sold Out', 'Sold Out'),
        ('Coming Soon', 'Coming Soon'),
        ('Under Construction', 'Under Construction'),
    ]

    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, blank=True, db_index=True)
    location = models.CharField(max_length=255, db_index=True)
    price = models.CharField(max_length=50, blank=True, null=True)
    PRICE_UNIT_CHOICES = [
        ('L', 'Lakh'),
        ('Cr', 'Crore'),
    ]
    price_unit = models.CharField(max_length=2, choices=PRICE_UNIT_CHOICES, default='L')
    project_name = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    beds = models.CharField(max_length=20, null=True, blank=True, help_text="e.g. 3 or 4/5")
    baths = models.FloatField(default=0, validators=[MinValueValidator(0)])
    sqft = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    description = models.TextField(blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Available', db_index=True)
    sales_head_number = models.CharField(max_length=20, blank=True, null=True)

    builder = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name="properties",
        null=True,
        blank=True,
        db_index=True
    )

    property_type = models.CharField(
        max_length=50,
        choices=PROPERTY_TYPE_CHOICES,
        default="Flat",
        db_index=True
    )

    thumbnail = CloudinaryField('image', blank=True, null=True)
    video = CloudinaryField('video', resource_type='video', blank=True, null=True, max_length=255)
    # Property class ke andar add karo:
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)

    agent_name = models.CharField(max_length=100, default="Agent")
    agent_role = models.CharField(max_length=100, default="Advisor")
    agent_image = models.ImageField(upload_to='agents/', blank=True, null=True)

    amenities = models.JSONField(default=list, blank=True)
    highlights = models.TextField(blank=True, null=True)
    rera_number = models.CharField(max_length=100, blank=True, null=True)

    possession_date = models.CharField(max_length=100, blank=True, null=True)
    possession = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default="Ready to Move"
    )

    map_link = models.TextField(blank=True, null=True)
    configuration = models.CharField(max_length=100, blank=True, null=True)
    brochure = CloudinaryField('raw', resource_type='raw', null=True, blank=True)
    starting_price = models.CharField(max_length=50, blank=True, null=True)
    max_price = models.CharField(max_length=50, blank=True, null=True)

    project_logo = CloudinaryField('image', blank=True, null=True)
    project_video = CloudinaryField('video', resource_type='video', blank=True, null=True, max_length=255)
    project_video_url = models.URLField(
        max_length=500, blank=True, null=True,
        help_text="YouTube (ya kisi bhi) video ka link - file upload ki jagah use kar sakte ho, especially bade/detailed videos ke liye"
    )

    project_status = models.CharField(max_length=100, blank=True, null=True)
    launch_date = models.CharField(max_length=100, blank=True, null=True)
    total_units = models.CharField(max_length=100, blank=True, null=True)
    total_towers = models.CharField(max_length=100, blank=True, null=True)
    land_parcel = models.CharField(max_length=100, blank=True, null=True)
    builder_name = models.CharField(max_length=255, blank=True, null=True)

    nearby_places = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['builder', 'status']),
            Index(fields=['location', 'property_type']),
            Index(fields=['project_name']),
            Index(fields=['status', 'created_at']),
            Index(fields=['property_type', 'status']),
            Index(fields=['latitude', 'longitude']),
        ]
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'

    def has_bhk(self):
        return self.property_type in ["Flat", "Villa", "Bungalow", "Duplex", "Penthouse"]

    def get_video_embed_url(self):
        """
        Kisi bhi YouTube link format (watch?v=, youtu.be/, shorts/) ya
        Google Drive share link ko embed-ready URL mein convert karta hai,
        taaki property detail page pe iframe se seedha play ho sake.

        NOTE: Google Drive wale video ke liye file ki sharing setting
        "Anyone with the link" (Viewer) honi chahiye, warna "You need
        access" wala error aayega chahe URL sahi ho ya nahi.
        """
        url = (self.project_video_url or '').strip()
        if not url:
            return None

        video_id = None
        try:
            if 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0]
            elif 'youtube.com/shorts/' in url:
                video_id = url.split('youtube.com/shorts/')[1].split('?')[0].split('&')[0]
            elif 'watch?v=' in url:
                video_id = url.split('watch?v=')[1].split('&')[0]
            elif 'youtube.com/embed/' in url:
                video_id = url.split('youtube.com/embed/')[1].split('?')[0].split('&')[0]
        except Exception:
            video_id = None

        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

        # Google Drive link ko preview/embed format mein convert karo
        if 'drive.google.com' in url:
            drive_id = None
            try:
                if '/file/d/' in url:
                    drive_id = url.split('/file/d/')[1].split('/')[0]
                elif 'id=' in url:
                    drive_id = url.split('id=')[1].split('&')[0]
            except Exception:
                drive_id = None

            if drive_id:
                return f"https://drive.google.com/file/d/{drive_id}/preview"

        # Koi aur video link ho to jaisa hai waisa hi use karo
        return url

    def get_price_numeric(self):
        """Price (number) + price_unit (L/Cr) ko actual rupee value mein convert karo, filtering ke liye"""
        if self.price is None or str(self.price).strip() == '':
            return Decimal('0')

        try:
            num = Decimal(str(self.price).replace(",", "").strip())
        except Exception:
            return Decimal('0')

        if self.price_unit == 'Cr':
            return num * Decimal("10000000")
        else:  # default: Lakh
            return num * Decimal("100000")

    def save(self, *args, **kwargs):
        if not self.slug:
            base_text = self.project_name or self.title
            self.slug = slugify(f"{base_text}-{self.location}")[:255]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        if self.slug:
            return reverse('property_detail', kwargs={'slug': self.slug, 'id': self.id})
        return reverse('property_detail', kwargs={'id': self.id})

    def __str__(self):
        return self.title
    def get_rating_summary(self):
        approved = self.reviews.filter(is_approved=True)
        count = approved.count()
        if count == 0:
            return None
        from django.db.models import Avg
        agg = approved.aggregate(
            connectivity=Avg('connectivity_rating'),
            neighbourhood=Avg('neighbourhood_rating'),
            safety=Avg('safety_rating'),
            livability=Avg('livability_rating'),
        )
        overall = sum(v for v in agg.values() if v is not None) / 4
        return {
            'overall': round(overall, 1),
            'connectivity': round(agg['connectivity'] or 0, 1),
            'neighbourhood': round(agg['neighbourhood'] or 0, 1),
            'safety': round(agg['safety'] or 0, 1),
            'livability': round(agg['livability'] or 0, 1),
            'count': count,
        }

    def get_rera_verify_url(self):
        if self.rera_number:
            return "https://gujrera.gujarat.gov.in/#/project-preview"
        return None


# =============================================================================
# PROPERTY IMAGE MODEL
# =============================================================================

class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
        db_index=True
    )
    image = CloudinaryField('image')
    caption = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.property.title} - Image {self.id}"

# =============================================================================
# FLOOR PLAN MODEL (unit-type wise floor plans - builder panel se add hote hain)
# =============================================================================

class FloorPlan(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="floor_plans", db_index=True
    )
    unit_type = models.CharField(max_length=100, help_text="e.g. 3 BHK, 4 BHK Penthouse")
    carpet_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Carpet area in sq.ft")
    super_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Super built-up area in sq.ft")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Price in Rupees for this unit type")
    image = CloudinaryField('image', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'created_at']
        verbose_name = "Floor Plan"
        verbose_name_plural = "Floor Plans"

    def __str__(self):
        return f"{self.property.title} - {self.unit_type}"
# =============================================================================
# AMENITY MODEL
# =============================================================================

class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, help_text="Font Awesome or Material Icon class name")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Amenities'

    def __str__(self):
        return self.name

# =============================================================================
# PROPERTY REVIEW MODEL (Ratings & Reviews - Housing.com jaisa feature)
# =============================================================================

class PropertyReview(models.Model):
    REVIEWER_TYPE_CHOICES = [
        ('Owner', 'Owner'),
        ('Tenant', 'Tenant'),
        ('Visitor', 'Visitor'),
        ('Others', 'Others'),
    ]

    property = models.ForeignKey(
        'Property', on_delete=models.CASCADE, related_name='reviews', db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='property_reviews'
    )
    reviewer_name = models.CharField(max_length=100)
    reviewer_type = models.CharField(max_length=20, choices=REVIEWER_TYPE_CHOICES, default='Owner')

    connectivity_rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    neighbourhood_rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    safety_rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    livability_rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])

    good_things = models.TextField(blank=True, help_text="Good things here")
    needs_improvement = models.TextField(blank=True, help_text="Things need improvement")

    is_approved = models.BooleanField(default=False, db_index=True, help_text="Sirf approved reviews public page par dikhengi")
    helpful_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['property', 'is_approved']),
        ]
        verbose_name = 'Property Review'
        verbose_name_plural = 'Property Reviews'

    def overall_rating(self):
        total = self.connectivity_rating + self.neighbourhood_rating + self.safety_rating + self.livability_rating
        return round(total / 4, 1)

    def __str__(self):
        return f"{self.reviewer_name} - {self.property.title} ({self.overall_rating}/5)"

# =============================================================================
# INQUIRY MODEL
# =============================================================================

class Inquiry(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="inquiries",
        db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='my_inquiries',
        help_text="Agar user login karke inquiry dala tha toh yaha link hota hai"
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(db_index=True)
    message = models.TextField()
    phone = models.CharField(max_length=15, blank=True, null=True, validators=[phone_validator])
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inquiries_handled'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['property', 'created_at']),
            Index(fields=['is_read', 'created_at']),
        ]

    def __str__(self):
        return f"{self.name} - {self.property.title}"


# =============================================================================
# SITE SETTINGS MODEL
# =============================================================================

class SiteSettings(models.Model):
    company_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField()
    location = models.CharField(max_length=255)
    about_text = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='site/', blank=True, null=True)
    favicon = models.ImageField(upload_to='site/', blank=True, null=True)
    facebook_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    enable_scheduler = models.BooleanField(default=True, help_text="Enable agent scheduler")
    enable_site_visits = models.BooleanField(default=True, help_text="Enable site visits page")
    

    class Meta:
        verbose_name = 'Site Setting'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.company_name

    @classmethod
    def get_settings(cls):
        """Get or create default settings"""
        settings_obj, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'company_name': 'RealShree',
                'phone': '+91-9876543210',
                'email': 'info@smartrealty.com',
                'location': 'India'
            }
        )
        return settings_obj


# =============================================================================
# CUSTOM USER MODEL
# =============================================================================

class User(AbstractUser):
    ROLE_CHOICES = (
        ('builder', 'Builder'),
        ('agent', 'Agent'),
        ('user', 'User'),
        ('admin', 'Admin'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='user',
        db_index=True
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[phone_validator]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    last_active = models.DateTimeField(auto_now=True)
    bio = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            Index(fields=['role', 'is_active']),
            Index(fields=['email']),
            Index(fields=['username']),
        ]

    def __str__(self):
        return self.username

    def get_full_name(self):
        if hasattr(self, 'profile') and self.profile.full_name:
            return self.profile.full_name
        return self.username


# =============================================================================
# PROFILE MODEL
# =============================================================================

class Profile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, null=True, blank=True, validators=[phone_validator])
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            Index(fields=['user']),
        ]

    def __str__(self):
        return self.full_name


# =============================================================================
# USER ADMIN
# =============================================================================

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_verified', 'created_at')
    list_filter = ('role', 'is_active', 'is_verified', 'created_at')
    search_fields = ('username', 'email', 'phone', 'first_name', 'last_name')
    list_per_page = 50
    ordering = ['-created_at']


# =============================================================================
# AGENT MODEL
# =============================================================================

class Agent(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, null=True, blank=True, validators=[phone_validator])
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent_profile"
    )
    role = models.CharField(max_length=50, default='Agent')
    builders = models.ManyToManyField(
        User,
        related_name="builder_agents",
        blank=True,
        limit_choices_to={'role': 'builder'}
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    total_sales = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    scheduler_enabled = models.BooleanField(
        default=True, 
        help_text="Agent can toggle their scheduler"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['is_active']),
            Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name

    def update_total_sales(self):
        """Recalculate total sales from closed deals"""
        total = self.deals.filter(status='CLOSED').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        self.total_sales = total
        self.save(update_fields=['total_sales'])


# =============================================================================
# LEAD MODEL
# =============================================================================

class Lead(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('VISIT', 'Site Visit'),
        ('NEGOTIATION', 'Negotiation'),
        ('CLOSED', 'Closed'),
        ('FAILED', 'Failed'),
    ]

    PRIORITY_CHOICES = [
        ('HOT', 'Hot'),
        ('WARM', 'Warm'),
        ('COLD', 'Cold'),
    ]

    name = models.CharField(max_length=100, db_index=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=15, validators=[phone_validator])
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    source = models.CharField(max_length=50, db_index=True, default='Website')
    interest = models.CharField(max_length=200, blank=True, null=True)

    properties = models.ManyToManyField(
        "Property",
        blank=True,
        related_name="interested_leads"
    )
    assigned_to = models.ForeignKey(
        "Agent",
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
        db_index=True
    )
    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='builder_leads'
    )
    last_contacted = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='WARM',
        db_index=True
    )

    # Automation fields
    automation_enabled = models.BooleanField(default=True)
    last_followup_date = models.DateTimeField(null=True, blank=True)
    followup_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    escalation_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(2)]
    )

    # Budget info
    budget_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    budget_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    preferred_location = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['builder', 'status']),
            Index(fields=['builder', 'created_at']),
            Index(fields=['assigned_to', 'status']),
            Index(fields=['priority', 'status']),
            Index(fields=['source']),
            Index(fields=['status', 'created_at']),
            Index(fields=['email']),
            Index(fields=['phone']),
        ]
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'

    def __str__(self):
        return self.name

    @classmethod
    def from_db(cls, db, field_names, values):
        # BUG FIX: cache the status this instance was loaded with, so save()
        # below doesn't need an extra Lead.objects.get() query just to detect
        # a status change. Removes the N+1 query that ran on every single
        # lead.save() call (including bulk loops in automation_engine.py).
        instance = super().from_db(db, field_names, values)
        instance._loaded_status = instance.status
        return instance

    def save(self, *args, **kwargs):
        old_status = getattr(self, "_loaded_status", None)
        # self.pk check keeps old behaviour: skip on first-ever create
        if self.pk and old_status is not None and old_status != self.status:
            self.last_contacted = timezone.now()
            super().save(*args, **kwargs)
            # Use activity_logs (LeadActivity related_name)
            LeadActivity.objects.create(
                lead=self,
                message=f"Status changed from {old_status} to {self.status}"
            )
        else:
            super().save(*args, **kwargs)
        self._loaded_status = self.status

    def get_next_followup(self):
        """Get next scheduled followup"""
        return self.followups.filter(
            status='PENDING',
            date__gte=timezone.now().date()
        ).order_by('date', 'time').first()

    def get_deal_value(self):
        """Get total deal value"""
        return self.deals.filter(status='CLOSED').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')


# =============================================================================
# DEAL MODEL
# =============================================================================

class Deal(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('NEGOTIATION', 'Negotiation'),
        ('BOOKED', 'Booked'),
        ('CLOSED', 'Closed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    lead = models.ForeignKey(
        'Lead',
        on_delete=models.CASCADE,
        related_name="deals",
        null=True,
        blank=True,
        db_index=True
    )
    property = models.ForeignKey(
        'Property',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='property_deals'
    )
    client_name = models.CharField(max_length=100)
    client_email = models.EmailField(blank=True, null=True)
    client_phone = models.CharField(max_length=15, blank=True, null=True, validators=[phone_validator])
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    AMOUNT_UNIT_CHOICES = [
        ('L', 'Lakh'),
        ('Cr', 'Crore'),
    ]
    amount_unit = models.CharField(max_length=2, choices=AMOUNT_UNIT_CHOICES, default='L')
    AMOUNT_UNIT_CHOICES = [
        ('L', 'Lakh'),
        ('Cr', 'Crore'),
    ]
    # Stores which unit the agent originally picked, purely for display.
    # `amount` itself always stores the full rupee value so Sum('amount')
    # on the builder dashboard stays mathematically correct.
    amount_unit = models.CharField(max_length=2, choices=AMOUNT_UNIT_CHOICES, default='L')
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        db_index=True
    )
    agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='deals'
    )
    builder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='builder_deals'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    expected_close_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['builder', 'status']),
            Index(fields=['agent', 'status']),
            Index(fields=['status', 'created_at']),
            Index(fields=['lead']),
        ]

    def __str__(self):
        return f"{self.client_name} - {self.status} - Rs. {self.amount}"

    def save(self, *args, **kwargs):
        if self.status == 'CLOSED' and not self.closed_at:
            self.closed_at = timezone.now()
            if self.agent and self.agent.commission_rate:
                self.commission_amount = self.amount * (self.agent.commission_rate / 100)
                self.agent.update_total_sales()
        super().save(*args, **kwargs)

    def get_profit(self):
        return self.amount - self.commission_amount


# =============================================================================
# TASK MODEL
# =============================================================================

class Task(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('DONE', 'Done'),
        ('CANCELLED', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='tasks'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='tasks'
    )
    assigned_to = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    date = models.DateField(null=True, blank=True, db_index=True)
    time = models.TimeField(null=True, blank=True)
    order = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM'
    )
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order', 'date', 'time', 'priority']
        indexes = [
            Index(fields=['user', 'status']),
            Index(fields=['date', 'status']),
            Index(fields=['assigned_to', 'status']),
            Index(fields=['lead', 'status']),
        ]

    def __str__(self):
        return self.title

    def mark_done(self):
        self.status = 'DONE'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])


# =============================================================================
# ACTIVITY MODEL
# FIX: lead ForeignKey indentation was broken — now properly indented
# =============================================================================

class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('LEAD_CREATED', 'Lead Created'),
        ('LEAD_UPDATED', 'Lead Updated'),
        ('DEAL_CREATED', 'Deal Created'),
        ('DEAL_CLOSED', 'Deal Closed'),
        ('FOLLOWUP_DONE', 'Follow-up Done'),
        ('TASK_CREATED', 'Task Created'),
        ('TASK_COMPLETED', 'Task Completed'),
        ('PROPERTY_ADDED', 'Property Added'),
        ('AGENT_ASSIGNED', 'Agent Assigned'),
        ('NOTE_ADDED', 'Note Added'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('OTHER', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities'
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES,
        default='OTHER'
    )
    message = models.TextField()
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        related_name='lead_activities',
        null=True,
        blank=True,
        db_index=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activities'
        indexes = [
            Index(fields=['user', 'created_at']),
            Index(fields=['activity_type']),
            Index(fields=['lead']),
        ]

    def __str__(self):
        return f"{self.activity_type} - {self.message[:50]}"


# =============================================================================
# LEAD NOTE MODEL
# FIX: related_name changed to 'lead_notes' to avoid clash
# =============================================================================

class LeadNote(models.Model):
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='lead_notes',
        db_index=True
    )
    note = models.TextField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes_created'
    )
    is_important = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['lead', 'created_at']),
        ]

    def __str__(self):
        return f"Note for {self.lead.name}"


# =============================================================================
# DOCUMENT MODEL
# =============================================================================

class Document(models.Model):
    CATEGORY_CHOICES = [
        ('LEGAL', 'Legal'),
        ('SALES', 'Sales'),
        ('PROPERTY', 'Property'),
        ('PERSONAL', 'Personal'),
        ('FINANCIAL', 'Financial'),
        ('MARKETING', 'Marketing'),
    ]

    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/')
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='PERSONAL',
        db_index=True
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='documents'
    )
    related_property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    related_lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    size = models.CharField(max_length=50, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    is_public = models.BooleanField(default=False)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['uploaded_by', 'category']),
            Index(fields=['category', 'created_at']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.file:
            size_bytes = self.file.size
            if size_bytes < 1024:
                self.size = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                self.size = f"{size_bytes / 1024:.1f} KB"
            else:
                self.size = f"{size_bytes / (1024 * 1024):.1f} MB"

            import mimetypes
            self.mime_type = mimetypes.guess_type(self.file.name)[0] or 'application/octet-stream'

        super().save(*args, **kwargs)

    def increment_download(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])


# =============================================================================
# CONVERSATION & MESSAGE MODELS
# =============================================================================

class Conversation(models.Model):
    lead_name = models.CharField(max_length=255, db_index=True)
    lead_email = models.EmailField(blank=True, null=True)
    lead_phone = models.CharField(max_length=20, db_index=True)
    source = models.CharField(max_length=50, default='Website')
    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            Index(fields=['lead_phone']),
            Index(fields=['is_active', 'updated_at']),
        ]

    def __str__(self):
        return self.lead_name

    def update_last_message(self):
        self.last_message_at = timezone.now()
        self.save(update_fields=['last_message_at', 'updated_at'])


class Message(models.Model):
    MESSAGE_TYPES = [
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('FILE', 'File'),
        ('SYSTEM', 'System'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='messages_sent'
    )
    text = models.TextField(blank=True, null=True)
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPES,
        default='TEXT'
    )
    file_attachment = models.FileField(upload_to='chat_files/', blank=True, null=True)
    is_agent = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            Index(fields=['conversation', 'created_at']),
            Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.sender.username} - {self.text[:20] if self.text else 'Attachment'}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.conversation.update_last_message()


# =============================================================================
# NOTIFICATION MODEL
# =============================================================================

class Notification(models.Model):
    TYPE_CHOICES = (
        ('lead', 'Lead'),
        ('message', 'Message'),
        ('task', 'Task'),
        ('document', 'Document'),
        ('system', 'System'),
        ('deal', 'Deal'),
        ('followup', 'Follow-up'),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        db_index=True
    )
    is_read = models.BooleanField(default=False, db_index=True)
    action_url = models.URLField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['recipient', 'is_read']),
            Index(fields=['type', 'created_at']),
        ]

    def __str__(self):
        return self.title

    def mark_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])


# =============================================================================
# AI INSIGHT MODEL
# =============================================================================

class AIInsight(models.Model):
    INSIGHT_TYPES = [
        ('lead', 'Lead'),
        ('revenue', 'Revenue'),
        ('risk', 'Risk'),
        ('market', 'Market'),
        ('performance', 'Performance'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=INSIGHT_TYPES,
        db_index=True
    )
    score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    recommendations = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['type', 'is_active']),
        ]

    def __str__(self):
        return self.title

    def is_expired(self):
        from datetime import date
        return self.end_date < date.today()
    
    def days_remaining(self):
        from datetime import date
        if self.end_date < date.today():
            return 0
        return (self.end_date - date.today()).days


# =============================================================================
# LEAD SCORE MODEL
# =============================================================================

class LeadScore(models.Model):
    INTENT_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]

    lead = models.OneToOneField(
        'Lead',
        on_delete=models.CASCADE,
        related_name='score'
    )
    score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    intent_level = models.CharField(
        max_length=50,
        choices=INTENT_CHOICES,
        default='MEDIUM'
    )
    factors = models.JSONField(default=dict, blank=True)
    predicted_conversion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            Index(fields=['score']),
            Index(fields=['intent_level']),
        ]

    def __str__(self):
        return f"{self.lead.name} - Score: {self.score} ({self.intent_level})"


# =============================================================================
# CAMPAIGN MODEL
# =============================================================================

class Campaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('scheduled', 'Scheduled'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    CAMPAIGN_TYPES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('social', 'Social Media'),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20,
        choices=CAMPAIGN_TYPES,
        default='email'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )
    subject = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    target_audience = models.JSONField(default=dict, blank=True)
    reach = models.PositiveIntegerField(default=0)
    sent = models.PositiveIntegerField(default=0)
    opened = models.PositiveIntegerField(default=0)
    clicked = models.PositiveIntegerField(default=0)
    bounced = models.PositiveIntegerField(default=0)
    unsubscribed = models.PositiveIntegerField(default=0)
    conversion = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='campaigns/', null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='campaigns',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['created_by', 'status']),
            Index(fields=['status', 'scheduled_at']),
            Index(fields=['type', 'status']),
        ]

    def __str__(self):
        return self.name

    @property
    def ctr(self):
        return round((self.clicked / self.sent * 100), 2) if self.sent else 0

    @property
    def open_rate(self):
        return round((self.opened / self.sent * 100), 2) if self.sent else 0

    @property
    def conversion_rate(self):
        return round((self.conversion / self.sent * 100), 2) if self.sent else 0

    @property
    def bounce_rate(self):
        return round((self.bounced / self.sent * 100), 2) if self.sent else 0


# =============================================================================
# SITE VISIT MODEL
# =============================================================================

class SiteVisit(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('CONFIRMED', 'Confirmed'),
        ('DONE', 'Done'),
        ('CANCELLED', 'Cancelled'),
        ('RESCHEDULED', 'Rescheduled'),
        ('NO_SHOW', 'No Show'),
    ]

    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='site_visits'
    )
    agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        related_name='visits',
        db_index=True
    )
    property = models.ForeignKey(
        'Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        related_name='site_visits'
    )
    lead = models.ForeignKey(
        'Lead',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='site_visits'
    )
    date = models.DateField(null=True, blank=True, db_index=True)
    time = models.TimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SCHEDULED',
        db_index=True
    )
    notes = models.TextField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']
        indexes = [
            Index(fields=['agent', 'date', 'status']),
            Index(fields=['builder', 'status']),
            Index(fields=['lead']),
            Index(fields=['date', 'status']),
        ]

    def __str__(self):
        return f"{self.property} - {self.date} - {self.time}"


# =============================================================================
# FOLLOW-UP MODEL
# =============================================================================

class FollowUp(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("DONE", "Done"),
        ("MISSED", "Missed"),
        ("ESCALATED", "Escalated"),
        ("CANCELLED", "Cancelled"),
    )

    FOLLOWUP_TYPES = [
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('SMS', 'SMS'),
        ('MEETING', 'Meeting'),
        ('SITE_VISIT', 'Site Visit'),
    ]

    lead = models.ForeignKey(
        "Lead",
        on_delete=models.CASCADE,
        related_name='followups',
        db_index=True
    )
    agent = models.ForeignKey(
        "Agent",
        on_delete=models.CASCADE,
        db_index=True,
        related_name='followups'
    )
    followup_type = models.CharField(
        max_length=20,
        choices=FOLLOWUP_TYPES,
        default='CALL'
    )
    date = models.DateField(db_index=True)
    time = models.TimeField()
    note = models.TextField(blank=True, null=True)
    outcome = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_auto_created = models.BooleanField(default=False)
    sequence_step = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    next_followup_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['date', 'time']
        indexes = [
            Index(fields=['agent', 'date', 'status']),
            Index(fields=['lead', 'status']),
            Index(fields=['status', 'date']),
        ]

    def __str__(self):
        return f"{self.lead.name} - {self.date} {self.time}"

    def mark_done(self, outcome=None):
        self.status = "DONE"
        self.completed_at = timezone.now()
        if outcome:
            self.outcome = outcome
        self.save(update_fields=['status', 'completed_at', 'outcome'])

        self.lead.last_contacted = timezone.now()
        self.lead.followup_count += 1
        self.lead.save(update_fields=['last_contacted', 'followup_count'])


# =============================================================================
# DRIP SEQUENCE MODEL
# =============================================================================

class DripSequence(models.Model):
    CHANNEL_CHOICES = [
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('PUSH', 'Push Notification'),
    ]

    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='drip_sequences',
        db_index=True
    )
    name = models.CharField(max_length=100)
    step_number = models.IntegerField(validators=[MinValueValidator(1)])
    delay_days = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Days after lead creation"
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    template_message = models.TextField()
    template_subject = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['step_number']
        unique_together = ['builder', 'step_number']
        indexes = [
            Index(fields=['builder', 'is_active']),
        ]

    def __str__(self):
        return f"Step {self.step_number} - {self.channel} - {self.delay_days} days"


# =============================================================================
# ESCALATION RULE MODEL
# =============================================================================

class EscalationRule(models.Model):
    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='escalation_rules',
        db_index=True
    )
    name = models.CharField(max_length=100)
    missed_followups = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Number of missed followups before escalation"
    )
    escalate_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='escalated_leads',
        limit_choices_to={'role__in': ['builder', 'admin']}
    )
    auto_reassign = models.BooleanField(default=True)
    notify_channels = models.CharField(max_length=100, default='EMAIL,WHATSAPP')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            Index(fields=['builder', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} - {self.builder.username}"


# =============================================================================
# AUTOMATION LOG MODEL
# =============================================================================

class AutomationLog(models.Model):
    ACTION_CHOICES = [
        ('SMS_SENT', 'SMS Sent'),
        ('EMAIL_SENT', 'Email Sent'),
        ('WHATSAPP_SENT', 'WhatsApp Sent'),
        ('PUSH_SENT', 'Push Notification Sent'),
        ('MISSED_FOLLOWUP', 'Missed Followup'),
        ('ESCALATION', 'Escalation'),
        ('AUTO_MESSAGE', 'Auto Message'),
        ('FOLLOWUP_CREATED', 'Followup Created'),
        ('TASK_CREATED', 'Task Created'),
        ('LEAD_ASSIGNED', 'Lead Assigned'),
    ]

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='automation_logs',
        db_index=True
    )
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        db_index=True
    )
    channel = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=20, default='SENT')
    response = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            Index(fields=['lead', 'action_type']),
            Index(fields=['status', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.action_type} - {self.lead.name}"


# =============================================================================
# LEAD ACTIVITY MODEL
# FIX: related_name changed to 'activity_logs', null=True added, on_delete=SET_NULL
# =============================================================================

class LeadActivity(models.Model):
    ACTIVITY_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('FOLLOWUP', 'Follow-up'),
        ('DEAL', 'Deal'),
        ('NOTE', 'Note'),
        ('STATUS', 'Status Change'),
        ('ASSIGNED', 'Assigned'),
        ('CALL', 'Call'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('MEETING', 'Meeting'),
    ]

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        related_name='activity_logs',
        null=True,
        blank=True,
        db_index=True
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES,
        default='UPDATED'
    )
    message = models.TextField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_activities'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['lead', 'created_at']),
            Index(fields=['activity_type']),
        ]

    def __str__(self):
        lead_name = self.lead.name if self.lead else "Deleted Lead"
        return f"{self.activity_type} - {lead_name}"


# =============================================================================
# WISHLIST MODEL
# =============================================================================

class Wishlist(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist',
        db_index=True
    )
    property = models.ForeignKey(
        'Property',
        on_delete=models.CASCADE,
        related_name='wishlisted_by',
        db_index=True
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'property']
        ordering = ['-created_at']
        indexes = [
            Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.property.title}"


# =============================================================================
# SAVED PROPERTY MODEL
# =============================================================================

class SavedProperty(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_properties'
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='saved_by'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'property']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.property.title}"


# =============================================================================
# PROPERTY INQUIRY TRACKING
# =============================================================================

class PropertyInquiry(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='property_inquiries',
        db_index=True
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='property_inquiries',
        db_index=True
    )
    inquiry_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('INTERESTED', 'Interested'),
            ('VISITED', 'Visited'),
            ('NEGOTIATING', 'Negotiating'),
            ('BOOKED', 'Booked'),
            ('NOT_INTERESTED', 'Not Interested'),
        ],
        default='INTERESTED'
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['property', 'lead']
        ordering = ['-inquiry_date']

    def __str__(self):
        return f"{self.lead.name} - {self.property.title}"


# =============================================================================
# SUBSCRIPTION / PLAN MODEL
# =============================================================================

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_properties = models.PositiveIntegerField(default=10)
    max_agents = models.PositiveIntegerField(default=5)
    max_leads = models.PositiveIntegerField(default=100)
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price_monthly']

    def __str__(self):
        return self.name


class UserSubscription(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
    'subscriptions.SubscriptionPlan',  # <-- YEH CHANGE KARO (was 'SubscriptionPlan' only)
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)
    current_order = models.ForeignKey(
    'subscriptions.RazorpayOrder',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='active_subscription'
)
    razorpay_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('FAILED', 'Failed'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            Index(fields=['user', 'is_active']),
        ]
    def is_expired(self):
        from datetime import date
        return self.end_date < date.today()
    def days_remaining(self):
            from datetime import date
            if self.end_date < date.today():
                return 0
            return (self.end_date - date.today()).days

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'No Plan'}"


# =============================================================================
# AUDIT LOG MODEL
# =============================================================================

class AuditLog(models.Model):
    ACTION_TYPES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('VIEW', 'View'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=255)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            Index(fields=['user', 'timestamp']),
            Index(fields=['action', 'timestamp']),
            Index(fields=['model_name', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.action} {self.model_name} by {self.user}"
    
# =============================================================================
# HOME PAGE ADVERTISEMENT BANNER
# =============================================================================
class Advertisement(models.Model):
    """Home page banner ads that link to a property"""
    title = models.CharField(max_length=200, blank=True, help_text="Internal name, not shown on site")
    image = CloudinaryField('image')
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='advertisements',
        help_text="Clicking the banner will open this property's detail page"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Lower number shows first")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Advertisement"
        verbose_name_plural = "Advertisements"

    def __str__(self):
        return self.title or f"Ad for {self.property}"
