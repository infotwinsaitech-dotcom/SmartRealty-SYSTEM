from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib import admin
from cloudinary.models import CloudinaryField

from django.conf import settings
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

    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    price = models.CharField(max_length=50, blank=True, null=True)
    project_name = models.CharField(max_length=200, blank=True, null=True)  # 🔥 NEW


    beds = models.IntegerField(null=True, blank=True)
    baths = models.FloatField()
    sqft = models.IntegerField()

    description = models.TextField(blank=True)
    status = models.CharField(max_length=50)

    builder = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name="properties",
        null=True,
        blank=True
    )

    property_type = models.CharField(
        max_length=50,
        choices=PROPERTY_TYPE_CHOICES,
        default="Flat",
    )

    thumbnail = CloudinaryField('image')
    video = models.FileField(upload_to='videos/', blank=True, null=True)

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
    brochure = models.FileField(upload_to='brochures/', null=True, blank=True)
    starting_price = models.CharField(max_length=50, blank=True, null=True)

    max_price = models.CharField(max_length=50, blank=True, null=True)

    project_logo = CloudinaryField(
    'image',
    blank=True,
    null=True
)

    project_video = models.FileField(
    upload_to='project_videos/',
    blank=True,
    null=True
)

    project_status = models.CharField(
    max_length=100,
    blank=True,
    null=True
)

    launch_date = models.CharField(
    max_length=100,
    blank=True,
    null=True
)

    total_units = models.CharField(
    max_length=100,
    blank=True,
    null=True
)

    total_towers = models.CharField(
    max_length=100,
    blank=True,
    null=True
)

    land_parcel = models.CharField(
    max_length=100,
    blank=True,
    null=True
)
    builder_name = models.CharField(
    max_length=255,
    blank=True,
    null=True
)
    nearby_places = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def has_bhk(self):
        return self.property_type in ["Flat", "Villa", "Bungalow", "Duplex", "Penthouse"]

    def __str__(self):
        return self.title

class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = CloudinaryField('image')
    def __str__(self):
        return self.property.title
    
class Amenity(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Inquiry(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    phone = models.CharField(max_length=15, blank=True, null=True)

    agent = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    

class SiteSettings(models.Model):
    company_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    location = models.CharField(max_length=255)
    about_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.company_name
    
# ✅ Custom User
class User(AbstractUser):
    ROLE_CHOICES = (
        ('builder', 'Builder'),
        ('agent', 'Agent'),
        ('user', 'User'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return self.full_name
    
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role')
    list_filter = ('role',)


class Agent(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, null=True, blank=True)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent_profile"
    )
    role = models.CharField(max_length=50, default='Agent')
    
    # ✅ MANYTOMANY: Ek agent multiple builders ke saath kaam kar sakta hai
    builders = models.ManyToManyField(
        User,
        related_name="builder_agents",
        blank=True
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

class Lead(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=[
        ('HOT', 'Hot'),
        ('WARM', 'Warm'),
        ('COLD', 'Cold'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20)
    interest = models.CharField(max_length=200, blank=True, null=True)
    properties = models.ManyToManyField("Property", blank=True, related_name="interested_leads")
    assigned_to = models.ForeignKey("Agent", on_delete=models.CASCADE, related_name="leads", null=True, blank=True)
    builder = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    last_contacted = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=[('HOT','Hot'),('WARM','Warm'),('COLD','Cold')], default='WARM')

    # ✅ NEW FIELDS (Add these)
    automation_enabled = models.BooleanField(default=True)
    last_followup_date = models.DateTimeField(null=True, blank=True)
    followup_count = models.IntegerField(default=0)
    escalation_level = models.IntegerField(default=0)  # 0=none, 1=builder, 2=admin

    def __str__(self):
        return self.name

class Deal(models.Model):

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('NEGOTIATION', 'Negotiation'),
        ('BOOKED', 'Booked'),
        ('CLOSED', 'Closed'),
        ('FAILED', 'Failed'),
    ]

    # 🔥 Lead connection (IMPORTANT)
    lead = models.ForeignKey(
        'Lead',
        on_delete=models.CASCADE,
        related_name="deals",
        null=True,
        blank=True
    )

    # Property linked
    property = models.ForeignKey(
        'Property',
        on_delete=models.CASCADE
    )

    client_name = models.CharField(max_length=100)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW'
    )

    # Agent (who closed deal)
    agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE
    )

    # Builder (for builder panel visibility)
    builder = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # ✅ FIXED
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )


    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client_name} - {self.status}"
class Task(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    order = models.IntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=[('PENDING','Pending'),('DONE','Done')],
        default='PENDING'
    )

    priority = models.CharField(
        max_length=20,
        choices=[('HIGH','High'),('MEDIUM','Medium'),('LOW','Low')],
        default='MEDIUM'
    )

class Activity(models.Model):
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


    
class LeadNote(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Document(models.Model):
    CATEGORY_CHOICES = [
        ('LEGAL', 'Legal'),
        ('SALES', 'Sales'),
        ('PROPERTY', 'Property'),
        ('PERSONAL', 'Personal'),
    ]

    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    size = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Conversation(models.Model):
    lead_name = models.CharField(max_length=255)
    lead_phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.lead_name


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    is_agent = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} - {self.text[:20]}"

class Notification(models.Model):

    TYPE_CHOICES = (
        ('lead', 'Lead'),
        ('message', 'Message'),
        ('task', 'Task'),
        ('document', 'Document'),
    )

    title = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    

class AIInsight(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=50)  # lead / revenue / risk
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class LeadScore(models.Model):
    lead = models.ForeignKey('Lead', on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    intent_level = models.CharField(max_length=50)  # High / Medium / Low
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.lead.name} - {self.score}"
    
class Campaign(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50)  # email / whatsapp / sms
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reach = models.IntegerField(default=0)
    
    sent = models.IntegerField(default=0)
    opened = models.IntegerField(default=0)
    clicked = models.IntegerField(default=0)
    conversion = models.IntegerField(default=0)
    image = models.ImageField(upload_to='campaigns/', null=True, blank=True)  # ✅ ADD THIS


    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class SiteVisit(models.Model):
    builder = models.ForeignKey(User, on_delete=models.CASCADE)

    agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        related_name='visits'
    )

    # 👉 better to use FK (recommended)
    property = models.ForeignKey(
        'Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # 👉 add these (IMPORTANT for scheduler)
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('SCHEDULED', 'Scheduled'),
            ('DONE', 'Done'),
            ('CANCELLED', 'Cancelled')
        ],
        default='SCHEDULED'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    lead = models.ForeignKey(
        'Lead',
        on_delete=models.CASCADE,
        null=True,
        blank=True
)

    def __str__(self):
        return f"{self.property} - {self.date} - {self.time}"
    

class FollowUp(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("DONE", "Done"),
        ("MISSED", "Missed"),
        ("ESCALATED", "Escalated"),  # ✅ NEW STATUS
    )

    lead = models.ForeignKey("Lead", on_delete=models.CASCADE)
    agent = models.ForeignKey("Agent", on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ NEW FIELDS (Add these)
    is_auto_created = models.BooleanField(default=False)
    sequence_step = models.IntegerField(default=0)  # 1,2,3,4 for drip sequence
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.lead.name} - {self.date}"

# ✅ NEW MODEL 1: Drip Sequence (Builder ke automation rules)
class DripSequence(models.Model):
    CHANNEL_CHOICES = [
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
    ]

    builder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='drip_sequences')
    name = models.CharField(max_length=100)
    step_number = models.IntegerField()
    delay_days = models.IntegerField()  # Day 1, Day 3, Day 7, Day 14
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    template_message = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['step_number']
        unique_together = ['builder', 'step_number']

    def __str__(self):
        return f"Step {self.step_number} - {self.channel} - {self.delay_days}days"


# ✅ NEW MODEL 2: Escalation Rule
class EscalationRule(models.Model):
    builder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='escalation_rules')
    name = models.CharField(max_length=100)
    missed_followups = models.IntegerField(default=2)  # Kitne missed pe escalate
    escalate_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='escalated_leads')
    auto_reassign = models.BooleanField(default=True)
    notify_channels = models.CharField(max_length=100, default='EMAIL,WHATSAPP')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.builder.username}"


# ✅ NEW MODEL 3: Automation Log (Audit trail)
class AutomationLog(models.Model):
    ACTION_CHOICES = [
        ('SMS_SENT', 'SMS Sent'),
        ('EMAIL_SENT', 'Email Sent'),
        ('WHATSAPP_SENT', 'WhatsApp Sent'),
        ('MISSED_FOLLOWUP', 'Missed Followup'),
        ('ESCALATION', 'Escalation'),
        ('AUTO_MESSAGE', 'Auto Message'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='automation_logs')
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    channel = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='SENT')  # SENT, FAILED, DELIVERED
    response = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.action_type} - {self.lead.name} - {self.sent_at}"
    
class LeadActivity(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
# models.py
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'property']