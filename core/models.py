from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib import admin
from cloudinary.models import CloudinaryField

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
    price = models.DecimalField(max_digits=12, decimal_places=2)

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
        related_name="agent_profile"   # 👈 add this
    )
    role = models.CharField(max_length=50, default='Agent')  # Admin / Agent
    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="builder_agents",  # 👈 add this
        null=True,
        blank=True
    ) # 🔥 IMPORTANT

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

    # ✅ THIS IS CORRECT (keep only this)
    properties = models.ManyToManyField(
        "Property",
        blank=True,
        related_name="interested_leads"
    )

    assigned_to = models.ForeignKey(
        "Agent",
        on_delete=models.CASCADE,
        related_name="leads",
        null=True,      # ✅ ADD THIS
        blank=True      # ✅ ADD THIS
)

    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    last_contacted = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    priority = models.CharField(
        max_length=10,
        choices=[('HOT','Hot'),('WARM','Warm'),('COLD','Cold')],
        default='WARM'
    )

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

    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    client_name = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW'
    )

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)

    # 🔥 IMPORTANT (builder visibility)
    builder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

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
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)

    date = models.DateField()
    time = models.TimeField()

    note = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=[("PENDING", "Pending"), ("DONE", "Done")],
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead} - {self.date}"
    
class LeadActivity(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)