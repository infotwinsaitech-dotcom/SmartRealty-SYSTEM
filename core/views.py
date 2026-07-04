"""
SmartRealty CRM - Production Ready Views
All features preserved with security & performance fixes
"""

import os
import re
import uuid
import json
import csv
import secrets
import calendar
import urllib.parse
import logging
from decimal import Decimal
from datetime import date, datetime, timedelta
from collections import defaultdict

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.db.models import Sum, Count, Q, Value, IntegerField, Case, When
from django.db import transaction
from django.db.models.functions import ExtractMonth
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.core.cache import cache
from django.views.decorators.cache import cache_page

# BUG FIX: Hard import band karo — agar package nahi to server crash hoga
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    HAS_SENDGRID = True
except ImportError:
    HAS_SENDGRID = False

try:
    from twilio.twiml.messaging_response import MessagingResponse
    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False

from .models import (
    Property, PropertyImage, User, Profile, Lead, Deal, Task, 
    Activity, Agent, Document, Conversation, Message, 
    Notification, Campaign, SiteVisit, FollowUp, Wishlist,
    Inquiry, LeadNote, LeadActivity, SavedProperty
)

logger = logging.getLogger('core')

User = get_user_model()

# =============================================================================
# CONSTANTS
# =============================================================================
PAGE_SIZE = 20
CACHE_TTL = 300
OTP_EXPIRY_SECONDS = 300
MAX_LOGIN_ATTEMPTS = 5
MAX_OTP_ATTEMPTS = 3
RATE_LIMIT_WINDOW = 300  # 5 minutes
OTP_WINDOW = 600  # 10 minutes

# =============================================================================
# SECURITY HELPERS
# =============================================================================
# =============================================================================
# AUTO-SETUP: Site + SocialApp (Immediate fix, no deploy wait)
# =============================================================================

# core/views.py — TOP OF FILE, after imports
def sanitize_input(text):
    """Remove potentially dangerous HTML/JS from user input"""
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<iframe.*?>.*?</iframe>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<object.*?>.*?</object>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<embed.*?>', '', text, flags=re.IGNORECASE)
    return text.strip()


def validate_file_upload(file, allowed_extensions=None, max_size_mb=10):
    """Validate uploaded file for security with MIME type check"""
    if not file:
        return False, "No file provided"
    
    if allowed_extensions is None:
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.pdf', '.mp4', '.mov']
    
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        return False, f"Allowed types: {', '.join(allowed_extensions)}"
    
    # MIME type validation
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file.name)
    allowed_mimes = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.webp': 'image/webp', '.avif': 'image/avif',
        '.pdf': 'application/pdf',
        '.mp4': 'video/mp4', '.mov': 'video/quicktime',
        '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    if mime_type and ext in allowed_mimes:
        if not mime_type.startswith(allowed_mimes[ext].split('/')[0]):
            return False, "File content does not match extension"
    
    if file.size > max_size_mb * 1024 * 1024:
        return False, f"Max size: {max_size_mb}MB"
    
    return True, "Valid"


def generate_secure_otp():
    """Generate cryptographically secure OTP"""
    return secrets.randbelow(900000) + 100000


def check_rate_limit(request, prefix, max_attempts=5, window=300):
    """Redis-based rate limiting"""
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f"ratelimit:{prefix}:{client_ip}"
    
    try:
        from django.core.cache import cache
        attempts = cache.get(key, [])
        current_time = now().timestamp()
        
        # Clean old attempts
        attempts = [t for t in attempts if current_time - t < window]
        
        if len(attempts) >= max_attempts:
            logger.warning(f"Rate limit exceeded for {prefix} from {client_ip}")
            return False
        
        attempts.append(current_time)
        cache.set(key, attempts, window)
        return True
    except Exception:
        # Fallback if cache unavailable
        return True


def clear_rate_limit(request, prefix):
    """Clear rate limit on successful auth"""
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f"ratelimit:{prefix}:{client_ip}"
    cache.delete(key)

from django.core.cache import cache

def get_cached_stats(builder, start_date, end_date):
    """5 minute cache ke saath stats lao"""
    cache_key = f"stats:{builder.id}:{start_date}:{end_date}"
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = {
            'total_leads': Lead.objects.filter(
                builder=builder, 
                created_at__date__range=[start_date, end_date]
            ).count(),
            'active_deals': Deal.objects.filter(
                builder=builder,
                status__in=["NEW", "NEGOTIATION", "BOOKED"],
                created_at__date__range=[start_date, end_date]
            ).count(),
            'total_revenue': Deal.objects.filter(
                builder=builder,
                status="CLOSED",
                created_at__date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }
        cache.set(cache_key, stats, 300)  # 5 minutes cache
    
    return stats

def get_paginated_queryset(queryset, request, page_size=PAGE_SIZE):
    """Helper for consistent pagination"""
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page', 1)
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1
    return paginator.get_page(page_number)


def log_activity(user, action, details=""):
    """Log user activity"""
    Activity.objects.create(
        message=f"{user.username} {action}: {details}" if details else f"{user.username} {action}"
    )


def builder_required(view_func):
    """Decorator to ensure user is builder"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if request.user.role != "builder":
            messages.error(request, "Builder access required")
            return redirect("login")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def agent_required(view_func):
    """Decorator to ensure user is agent"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if request.user.role != "agent":
            messages.error(request, "Agent access required")
            return redirect("login")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# =============================================================================
# PUBLIC VIEWS
# =============================================================================

def home(request):
    """Home page with featured properties"""
    cache_key = 'home_properties'
    properties = cache.get(cache_key)
    
    if properties is None:
        properties = list(Property.objects.select_related('builder').all()[:6])
        cache.set(cache_key, properties, CACHE_TTL)
    
    return render(request, "public/index.html", {"properties": properties})


def convert_price(price):
    """Convert price string to Decimal"""
    if isinstance(price, (int, float, Decimal)):
        return Decimal(str(price))
    
    price = str(price).lower().replace(",", "").strip()
    
    if not price or price in ['', 'none', 'null', 'nan']:
        return Decimal("0")
    
    if "crore" in price or "cr" in price:
        num_part = re.sub(r'[^\d.]', '', price)
        try:
            return Decimal(num_part) * Decimal("10000000")
        except Exception:
            return Decimal("0")
    
    elif "lakh" in price or "lac" in price or "l" in price:
        num_part = re.sub(r'[^\d.]', '', price)
        try:
            return Decimal(num_part) * Decimal("100000")
        except Exception:
            return Decimal("0")
    
    else:
        try:
            return Decimal(re.sub(r'[^\d.]', '', price))
        except Exception:
            return Decimal("0")


def properties_view(request):
    """Public properties listing"""
    properties = Property.objects.select_related('builder').all().order_by('-created_at')
    page_obj = get_paginated_queryset(properties, request)
    
    return render(request, "public/properties.html", {
        "properties": page_obj,
        "page_obj": page_obj
    })


def property_detail(request, id):
    """Property detail with inquiry form"""
    property = get_object_or_404(
        Property.objects.select_related('builder').prefetch_related('images'), 
        id=id
    )
    
    highlights_list = []
    if property.highlights:
        highlights_list = [h.strip() for h in property.highlights.split(",") if h.strip()]
    
    similar_properties = Property.objects.filter(
        location=property.location
    ).exclude(id=property.id).select_related('builder')[:3]

    if request.method == "POST":
        name = sanitize_input(request.POST.get("name"))
        email = sanitize_input(request.POST.get("email"))
        phone = sanitize_input(request.POST.get("phone"))
        message = sanitize_input(request.POST.get("message"))

        if not all([name, email, phone]):
            messages.error(request, "Name, email and phone are required")
            return redirect('property_detail', id=property.id)

        # Round-robin agent assignment
        agents = list(Agent.objects.filter(
            builders=property.builder, 
            is_active=True
        ).order_by("id"))
        
        last_lead = Lead.objects.filter(
            builder=property.builder
        ).select_related('assigned_to').order_by('-id').first()

        if last_lead and last_lead.assigned_to in agents:
            last_index = agents.index(last_lead.assigned_to)
            agent = agents[(last_index + 1) % len(agents)]
        else:
            agent = agents[0] if agents else None

        try:
            lead = Lead.objects.create(
                name=name,
                email=email,
                phone=phone,
                status='NEW',
                priority='HOT', 
                source='Website',
                interest=property.title,
                builder=property.builder,
                assigned_to=agent,
                notes=message
            )
            lead.properties.add(property)

            Inquiry.objects.create(
                property=property,
                user=request.user if request.user.is_authenticated else None,
                name=name,
                email=email,
                phone=phone,
                message=message,
                agent=agent.user if agent else None
            )
            
            # Create follow-up
            if agent:
                FollowUp.objects.create(
                    lead=lead,
                    agent=agent,
                    date=now().date() + timedelta(days=1),
                    time=datetime.strptime("10:00", "%H:%M").time(),
                    note="First followup - auto created",
                    status='PENDING',
                    is_auto_created=True
                )
            
            messages.success(request, "Inquiry sent successfully! Our team will contact you soon.")
            logger.info(f"New lead created: {lead.name} for property {property.title}")
            
        except Exception as e:
            logger.error(f"Error creating lead: {str(e)}")
            messages.error(request, "Something went wrong. Please try again.")

        return redirect('property_detail', id=property.id)

    user_wishlist_ids = []
    if request.user.is_authenticated:
        user_wishlist_ids = list(
            Wishlist.objects.filter(user=request.user)
            .values_list('property_id', flat=True)
        )

    brochure_pdf_url = None
    if property.brochure:
        try:
            brochure_pdf_url = property.brochure.url
        except Exception:
            brochure_pdf_url = None

    return render(request, "public/property_detail.html", {
        "property": property,
        "highlights_list": highlights_list,
        "similar_properties": similar_properties,
        "user_wishlist_ids": user_wishlist_ids,
        "brochure_pdf_url": brochure_pdf_url,
    })


def property_list(request):
    """Advanced property search with filters"""
    from django.db.models import Q, Value, IntegerField, Case, When

    # Ahmedabad ke popular areas - Add Property form (builder side) mein bhi yehi list hai,
    # taaki dono jagah options match karein.
    AHMEDABAD_AREAS = [
        "Satellite", "Vastrapur", "Bodakdev", "Thaltej", "SG Highway", "Prahlad Nagar",
        "Navrangpura", "Ellisbridge", "Paldi", "Vasna", "Maninagar", "Isanpur",
        "Ghatlodia", "Naranpura", "Ranip", "Chandkheda", "Motera", "Sabarmati",
        "Gota", "Chandlodia", "Vejalpur", "Jodhpur", "Ambawadi", "Shahibaug",
        "Naroda", "Nikol", "Vastral", "Bapunagar", "Odhav", "Kubernagar",
        "Rakhial", "Amraiwadi", "Gomtipur", "Khokhra", "Kankaria", "Danilimda",
        "Vatva", "Lambha", "Narol", "Sarkhej", "Juhapura", "Makarba",
        "Ghuma", "South Bopal", "Bopal", "Shela", "Shilaj", "Science City",
        "Chharodi", "Nava Vadaj", "Vadaj", "Usmanpura", "Memnagar", "Gulbai Tekra",
        "Panjrapole", "C.G. Road", "Law Garden", "Navjivan", "Income Tax", "Stadium",
        "Nehru Nagar", "Judges Bungalow Road", "Iscon", "Anand Nagar", "Manekbaug",
        "Jivraj Park", "Vishala", "Nirnaynagar", "Chenpur", "Sughad", "Zundal",
        "Gandhinagar Road", "Adalaj", "Koba", "Randesan", "Kudasan", "New CG Road",
        "Bhat", "Sarangpur", "Kalupur", "Raikhad", "Dariapur", "Jamalpur",
        "Khadia", "Shahpur", "Dudheshwar", "Saraspur", "Rajpur", "Meghaninagar",
    ]

    # Property type groups — must match the checkbox groups in public/property.html
    CATEGORY_TYPES = {
        'residential': ['Flat', 'Villa', 'Bungalow', 'Duplex', 'Penthouse'],
        'commercial': ['Office', 'Shop', 'Showroom', 'Warehouse', 'Industrial'],
        'land': ['Land', 'Plot', 'Plots', 'Farmhouse'],
    }

    properties = Property.objects.select_related('builder').all().order_by('-created_at')

    location = sanitize_input(request.GET.get('location', '')).strip()
    areas = [sanitize_input(a).strip() for a in request.GET.getlist('areas') if a.strip()]
    property_type = sanitize_input(request.GET.get('type', '')).strip()
    category = sanitize_input(request.GET.get('category', '')).strip().lower()
    possession = sanitize_input(request.GET.get('possession', '')).strip()
    min_price = sanitize_input(request.GET.get('min_price', '')).strip()
    max_price = sanitize_input(request.GET.get('max_price', '')).strip()
    min_price_unit = sanitize_input(request.GET.get('min_price_unit', 'L')).strip()
    max_price_unit = sanitize_input(request.GET.get('max_price_unit', 'L')).strip()
    beds = sanitize_input(request.GET.get('beds', '')).strip()
    query = sanitize_input(request.GET.get('q', '')).strip()

    # Build query filters
    filters = Q()

    if query:
        filters &= (
            Q(title__icontains=query) | 
            Q(location__icontains=query) |
            Q(project_name__icontains=query) | 
            Q(builder__username__icontains=query) |
            Q(builder__first_name__icontains=query) | 
            Q(builder__last_name__icontains=query) |
            Q(description__icontains=query)
        )

    if location:
        filters &= (
            Q(location__icontains=location) | 
            Q(title__icontains=location) | 
            Q(project_name__icontains=location)
        )

    # Multiple areas select ki ho (jaise Satellite + Bodakdev) to unme se kisi bhi ek se match ho to dikhao
    if areas:
        area_query = Q()
        for a in areas:
            area_query |= Q(location__icontains=a)
        filters &= area_query

    # HARD FILTER: Category (Residential / Commercial / Land tab).
    # This never falls back to other categories — Commercial tab must never show Residential, and vice versa.
    if category in CATEGORY_TYPES:
        filters &= Q(property_type__in=CATEGORY_TYPES[category])

    # HARD FILTER: specific type checkboxes (Flat, Office, Plot, etc.)
    if property_type:
        types = [t.strip() for t in property_type.split(',') if t.strip()]
        if types:
            type_query = Q()
            for t in types:
                type_query |= Q(property_type__iexact=t) | Q(property_type__icontains=t)
            filters &= type_query

    if possession:
        filters &= Q(possession__icontains=possession)

    properties = properties.filter(filters)

    # Relevance scoring for search
    if query:
        properties = properties.annotate(
            relevance_score=Case(
                When(title__iexact=query, then=Value(100)),
                When(location__iexact=query, then=Value(90)),
                When(project_name__iexact=query, then=Value(80)),
                When(builder__username__iexact=query, then=Value(70)),
                When(title__istartswith=query, then=Value(60)),
                When(location__istartswith=query, then=Value(50)),
                When(title__icontains=query, then=Value(40)),
                When(location__icontains=query, then=Value(30)),
                When(project_name__icontains=query, then=Value(20)),
                When(builder__username__icontains=query, then=Value(10)),
                default=Value(1), output_field=IntegerField(),
            )
        ).order_by('-relevance_score', '-created_at')

    properties = list(properties)

    # Fallback ONLY broadens location/query matching — category & type stay hard filters.
    # If a category genuinely has zero properties, we show zero (never leak another category's listings).
    if not properties and (location or query):
        base_qs = Property.objects.select_related('builder').all()
        if category in CATEGORY_TYPES:
            base_qs = base_qs.filter(property_type__in=CATEGORY_TYPES[category])
        if property_type:
            types = [t.strip() for t in property_type.split(',') if t.strip()]
            if types:
                type_query = Q()
                for t in types:
                    type_query |= Q(property_type__iexact=t) | Q(property_type__icontains=t)
                base_qs = base_qs.filter(type_query)
        if possession:
            base_qs = base_qs.filter(possession__icontains=possession)

        term = (location or query)[:3]
        nearest = base_qs.filter(
            Q(title__icontains=term) |
            Q(location__icontains=term) |
            Q(project_name__icontains=term)
        ).order_by('-created_at')
        properties = list(nearest)

    # PRICE (price is stored as text like "50 Lakh", "1.2 Cr" — compare using get_price_numeric()):
    #  - Both min & max given  -> hard range filter (a real "between X and Y" search)
    #  - Only ONE of them given -> treated as a target price: nothing gets excluded, results are
    #    just sorted by closeness to that price (so "50L" also surfaces 45L/55L etc., nearest first)
    min_val = None
    max_val = None
    if min_price:
        try:
            min_val = float(min_price) * (10000000 if min_price_unit == 'Cr' else 100000)
        except ValueError:
            pass
    if max_price:
        try:
            max_val = float(max_price) * (10000000 if max_price_unit == 'Cr' else 100000)
        except ValueError:
            pass

    price_target = None
    if min_val is not None and max_val is not None:
        properties = [p for p in properties if min_val <= float(p.get_price_numeric()) <= max_val]
    elif min_val is not None:
        price_target = min_val
    elif max_val is not None:
        price_target = max_val

    # BEDS (BHK): no longer a hard "beds >= N" cutoff. Selecting "2 BHK" keeps every property
    # visible, just sorted so 2 BHK comes first, then the next-closest (1 BHK / 3 BHK), etc.
    beds_target = None
    if beds:
        try:
            beds_target = int(beds)
        except ValueError:
            pass

    if beds_target is not None or price_target is not None:
        def sort_key(p):
            bed_distance = 0
            if beds_target is not None:
                bed_distance = abs(p.beds - beds_target) if p.beds is not None else 999
            price_distance = 0
            if price_target is not None:
                price_distance = abs(float(p.get_price_numeric()) - price_target)
            return (bed_distance, price_distance)
        properties = sorted(properties, key=sort_key)

    page_obj = get_paginated_queryset(properties, request)

    user_wishlist_ids = []
    if request.user.is_authenticated:
        user_wishlist_ids = list(
            Wishlist.objects.filter(user=request.user)
            .values_list('property_id', flat=True)
        )

    return render(request, "public/property.html", {
        "properties": page_obj,
        "page_obj": page_obj,
        "search_query": query,
        "location_filter": location,
        "areas_filter": areas,
        "ahmedabad_areas": AHMEDABAD_AREAS,
        "type_filter": property_type,
        "type_filter_list": [t.strip() for t in property_type.split(',') if t.strip()],
        "category_filter": category if category in CATEGORY_TYPES else "residential",
        "possession_filter": possession,
        "min_price_filter": min_price,
        "max_price_filter": max_price,
        "min_price_unit": min_price_unit,
        "max_price_unit": max_price_unit,
        "beds_filter": beds,
        'user_wishlist_ids': user_wishlist_ids,
    })


def contact(request):
    """Contact form with WhatsApp redirect"""
    if request.method == "POST":
        name = sanitize_input(request.POST.get("name", ""))
        phone = sanitize_input(request.POST.get("phone", ""))
        message = sanitize_input(request.POST.get("message", ""))
        
        if not all([name, phone]):
            messages.error(request, "Name and phone are required")
            return redirect('contact')
            
        text = f"New Inquiry:\nName: {name}\nPhone: {phone}\nMessage: {message}"
        whatsapp_url = f"https://wa.me/919876543210?text={urllib.parse.quote(text)}"
        return redirect(whatsapp_url)
    
    return render(request, "public/contact_us.html")


def about(request):
    """About page"""
    return render(request, "public/about.html")


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

def redirect_by_role(user):
    """Redirect user based on role"""
    if user.role == "builder":
        return redirect("builder_dashboard")
    elif user.role == "agent":
        return redirect("agent_dashboard")
    return redirect("/")


def login_view(request):
    """Login view with rate limiting"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == "POST":
        username = sanitize_input(request.POST.get("username", "")).strip()
        password = request.POST.get("password", "")

        if not username or not password:
            return render(request, "public/login.html", {
                "error": "Username and password are required"
            })

        # Rate limiting
        if not check_rate_limit(request, "login", MAX_LOGIN_ATTEMPTS, RATE_LIMIT_WINDOW):
            return render(request, "public/login.html", {
                "error": "Too many attempts. Please try again after 5 minutes."
            })

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            clear_rate_limit(request, "login")
            logger.info(f"User logged in: {user.username}")
            return redirect_by_role(user)

        logger.warning(f"Failed login attempt for: {username}")
        return render(request, "public/login.html", {
            "error": "Invalid credentials"
        })

    return render(request, "public/login.html")


def register_view(request):
    """User registration"""
    if request.method == "POST":
        full_name = sanitize_input(request.POST.get("full_name", "")).strip()
        username = sanitize_input(request.POST.get("username", "")).strip()
        email = sanitize_input(request.POST.get("email", "")).strip()
        phone = sanitize_input(request.POST.get("phone", "")).strip()
        password = request.POST.get("password", "")

        # Validation
        errors = []
        if not username or not password:
            errors.append("Username and Password required")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password):
            errors.append("Password must contain uppercase, lowercase, and number")
        if User.objects.filter(username=username).exists():
            errors.append("Username already exists")
        if email and User.objects.filter(email=email).exists():
            errors.append("Email already exists")

        if errors:
            return render(request, "public/register.html", {"error": " | ".join(errors)})

        try:
            # BUG FIX: wrap User + Profile creation in transaction.atomic().
            # Without this, if Profile creation fails after User is created,
            # you get a User account with no Profile (broken/half-created
            # account) instead of nothing at all.
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, 
                    email=email, 
                    password=password, 
                    phone=phone, 
                    role="user"
                )

                Profile.objects.update_or_create(
                    user=user,
                    defaults={"full_name": full_name, "email": email, "phone": phone}
                )

            messages.success(request, "Registration successful! Please login.")
            logger.info(f"New user registered: {username}")
            return redirect("login")
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return render(request, "public/register.html", {
                "error": "Registration failed. Please try again."
            })

    return render(request, "public/register.html")


def user_login(request):
    """Alternative login view"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == "POST":
        username = sanitize_input(request.POST.get("username", "")).strip()
        password = request.POST.get("password", "")

        if not username or not password:
            return render(request, "login.html", {
                "error": "Username and password are required"
            })

        if not check_rate_limit(request, "login", MAX_LOGIN_ATTEMPTS, RATE_LIMIT_WINDOW):
            return render(request, "login.html", {
                "error": "Too many attempts. Please try again later."
            })

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            clear_rate_limit(request, "login")
            return redirect_by_role(user)

        return render(request, "login.html", {"error": "Invalid username or password"})

    return render(request, "login.html")


@login_required
def agent_dashboard(request):
    """Agent dashboard redirect"""
    if request.user.role != "agent":
        logout(request)
        return redirect("login")
    return render(request, "agent/agent_dashboard.html")


# =============================================================================
# PASSWORD RESET
# =============================================================================

def forgot_password(request):
    """Password reset with OTP"""
    if request.method == "POST":
        email = sanitize_input(request.POST.get("email", "")).strip().lower()
        if not email:
            return render(request, "public/forgot_password.html", {
                "error": "Email is required"
            })

        if not check_rate_limit(request, "otp", MAX_OTP_ATTEMPTS, OTP_WINDOW):
            return render(request, "public/forgot_password.html", {
                "error": "Too many OTP requests. Please try again after 10 minutes."
            })

        try:
            user = User.objects.get(email=email)
            otp = generate_secure_otp()
            
            # Store OTP in cache instead of session
            cache_key = f"password_reset:{email}"
            cache.set(cache_key, {
                "otp": str(otp),
                "created_at": now().timestamp()
            }, OTP_EXPIRY_SECONDS)

            # Send email via Celery (async)
            try:
                from .tasks import send_password_reset_email
                send_password_reset_email.delay(email, otp)
            except Exception as e:
                logger.error(f"Failed to queue password reset email: {str(e)}")
                # Fallback to synchronous
                message = Mail(
                    from_email=os.getenv("DEFAULT_FROM_EMAIL"),
                    to_emails=user.email,
                    subject="Password Reset OTP",
                    html_content=f"""
                    <h2>Password Reset OTP</h2>
                    <p>Your OTP is:</p>
                    <h1>{otp}</h1>
                    <p>This OTP will expire in 5 minutes.</p>
                    <p>If you didn't request this, please ignore.</p>
                    """
                )
                sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
                sg.send(message)

            request.session["reset_email"] = email
            return redirect("otp_verification")

        except User.DoesNotExist:
            # Same message to prevent user enumeration
            logger.info(f"Password reset requested for non-existent email: {email}")
            return render(request, "public/forgot_password.html", {
                "error": "If this email is registered, you will receive an OTP."
            })
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return render(request, "public/forgot_password.html", {
                "error": "Something went wrong. Please try again."
            })

    return render(request, "public/forgot_password.html")


def otp_verification(request):
    """Verify OTP"""
    email = request.session.get("reset_email")
    
    if not email:
        return redirect("forgot_password")

    cache_key = f"password_reset:{email}"
    cached_data = cache.get(cache_key)

    if not cached_data:
        return render(request, "public/otp_verification.html", {
            "error": "OTP expired. Please request a new OTP."
        })

    if request.method == "POST":
        user_otp = sanitize_input(request.POST.get("otp", "")).strip()
        
        if user_otp == cached_data.get("otp"):
            request.session["otp_verified"] = True
            return redirect("reset_password")
        
        return render(request, "public/otp_verification.html", {
            "error": "Invalid OTP"
        })

    return render(request, "public/otp_verification.html")


def reset_password(request):
    """Reset password after OTP verification"""
    email = request.session.get("reset_email")
    otp_verified = request.session.get("otp_verified")

    if not email:
        return redirect("forgot_password")
    if not otp_verified:
        return redirect("otp_verification")

    if request.method == "POST":
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        errors = []
        if not password:
            errors.append("Password is required")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password):
            errors.append("Password must contain uppercase, lowercase, and number")
        if password != confirm_password:
            errors.append("Passwords do not match")

        if errors:
            return render(request, "public/reset_password.html", {
                "error": " | ".join(errors)
            })

        try:
            user = User.objects.get(email=email)
            user.set_password(password)
            user.save()
            
            # Clear all session data
            cache.delete(f"password_reset:{email}")
            for key in ["otp", "otp_created", "otp_verified", "reset_email"]:
                request.session.pop(key, None)
            
            messages.success(request, "Password reset successful! Please login.")
            logger.info(f"Password reset for: {email}")
            return redirect("login")
            
        except User.DoesNotExist:
            request.session.flush()
            return redirect("forgot_password")
        except Exception as e:
            logger.error(f"Password reset save error: {str(e)}")
            return render(request, "public/reset_password.html", {
                "error": "Password reset failed. Please try again."
            })

    return render(request, "public/reset_password.html")


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create profile on user creation"""
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults={
                "full_name": instance.username, 
                "email": instance.email, 
                "phone": instance.phone
            }
        )


@login_required
def profile(request):
    """User profile"""
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.username, 
            "email": request.user.email, 
            "phone": request.user.phone
        }
    )
    return render(request, "public/profile.html", {"profile": profile})


def logout_view(request):
    """Logout user"""
    logger.info(f"User logged out: {request.user.username}")
    logout(request)
    return redirect("login")


@login_required
def edit_profile(request):
    """Edit user profile"""
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.username, 
            "email": request.user.email, 
            "phone": request.user.phone
        }
    )

    if request.method == "POST":
        profile.full_name = sanitize_input(request.POST.get("full_name", "")).strip()
        profile.email = sanitize_input(request.POST.get("email", "")).strip()
        profile.phone = sanitize_input(request.POST.get("phone", "")).strip()
        profile.save()
        
        request.user.email = profile.email
        request.user.phone = profile.phone
        request.user.save()
        
        messages.success(request, "Profile updated successfully")
        return redirect("profile")

    return render(request, "user/edit_profile.html", {"profile": profile})


@login_required
def my_properties(request):
    """Builder's properties"""
    if request.user.role != "builder":
        return redirect("login")
    
    properties = Property.objects.filter(builder=request.user).select_related('builder').order_by('-created_at')
    page_obj = get_paginated_queryset(properties, request)
    return render(request, "user/my_property.html", {"properties": page_obj, "page_obj": page_obj})


@login_required
def my_inquiries(request):
    """User inquiries - sirf isi logged-in user ki, chahe purani email-based ho ya nayi user-linked"""
    inquiries = Inquiry.objects.filter(
        Q(user=request.user) | Q(email=request.user.email)
    ).select_related('property', 'agent', 'agent__agent_profile').order_by('-created_at')
    page_obj = get_paginated_queryset(inquiries, request)
    return render(request, "user/my_inquiries.html", {"inquiries": page_obj, "page_obj": page_obj})


# =============================================================================
# PROPERTY MANAGEMENT (BUILDER)
# =============================================================================

logger = logging.getLogger(__name__)

from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.contrib import messages
from django.shortcuts import redirect, render
import logging

logger = logging.getLogger(__name__)


@builder_required
def add_property(request):
    """Add new property with proper validation and error handling"""
    if request.method == "POST":
        # Collect data
        data = {
            'title': sanitize_input(request.POST.get("title", "")),
            'location': sanitize_input(request.POST.get("location", "")),
            'project_name': sanitize_input(request.POST.get("project_name", "")),
            'status': sanitize_input(request.POST.get("status", "Available")),
            'property_type': sanitize_input(request.POST.get("property_type", "")),
            'builder_name': sanitize_input(request.POST.get("builder_name", "")),
            'price': request.POST.get("price", ""),
            'price_unit': sanitize_input(request.POST.get("price_unit", "L")),
            'starting_price': sanitize_input(request.POST.get("starting_price", "")),
            'max_price': sanitize_input(request.POST.get("max_price", "")),
            'beds': request.POST.get("beds", ""),
            'baths': request.POST.get("baths", ""),
            'sqft': request.POST.get("sqft", ""),
            'description': sanitize_input(request.POST.get("description", "")),
            'highlights': sanitize_input(request.POST.get("highlights", "")),
            'rera_number': sanitize_input(request.POST.get("rera_number", "")),
            'possession': sanitize_input(request.POST.get("possession", "")),
            'map_link': sanitize_input(request.POST.get("map_link", "")),
            'configuration': sanitize_input(request.POST.get("configuration", "")),
            'project_status': sanitize_input(request.POST.get("project_status", "")),
            'launch_date': sanitize_input(request.POST.get("launch_date", "")),
            'total_units': sanitize_input(request.POST.get("total_units", "")),
            'total_towers': sanitize_input(request.POST.get("total_towers", "")),
            'land_parcel': sanitize_input(request.POST.get("land_parcel", "")),
            'sales_head_number': sanitize_input(request.POST.get("sales_head_number", "")),
            'project_video_url': sanitize_input(request.POST.get("project_video_url", "")).strip(),
        }

        # ===== VALIDATION =====
        errors = []
        
        if not data['title'].strip():
            errors.append("Title is required")
        if not data['location'].strip():
            errors.append("Location is required")
        if not data['price'].strip():
            errors.append("Price is required")
        else:
            try:
                float(data['price'])
                data['price'] = str(data['price']).strip()
            except (ValueError, TypeError):
                errors.append("Price must be a valid number")
        
        if not data['property_type']:
            errors.append("Property type is required")

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("add_property")

        # File validations
        files = {}
        file_fields = {
            'thumbnail': (['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'], 10),
            'brochure': (['.pdf'], 10),
            'project_logo': (['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'], 10),
            'project_video': (['.mp4', '.mov', '.avi', '.mkv'], 20),
        }

        for field, (exts, max_size) in file_fields.items():
            uploaded = request.FILES.get(field)
            if uploaded:
                valid, msg = validate_file_upload(uploaded, exts, max_size)
                if not valid:
                    messages.error(request, f"{field.title()}: {msg}")
                    return redirect("add_property")
                files[field] = uploaded

        # Parse numeric fields
        try:
            beds_val = int(data['beds']) if data['beds'] else None
            baths_val = float(data['baths']) if data['baths'] else 0.0
            sqft_val = int(data['sqft']) if data['sqft'] else 0
        except ValueError:
            messages.error(request, "Invalid numeric values for beds, baths, or sqft")
            return redirect("add_property")

        # Parse map coordinates (used by the public Property Map page)
        lat_raw = request.POST.get("latitude", "").strip()
        lng_raw = request.POST.get("longitude", "").strip()
        try:
            latitude_val = float(lat_raw) if lat_raw else None
            longitude_val = float(lng_raw) if lng_raw else None
        except ValueError:
            latitude_val = None
            longitude_val = None

        # Parse amenities
        amenities = request.POST.getlist("amenities")

        # Parse nearby places
        nearby_names = request.POST.getlist("nearby_name")
        nearby_distances = request.POST.getlist("nearby_distance")
        nearby_icons = request.POST.getlist("nearby_icon")
        nearby_data = []
        for i in range(len(nearby_names)):
            name = nearby_names[i].strip()
            if name:
                nearby_data.append({
                    "name": sanitize_input(name),
                    "distance": sanitize_input(nearby_distances[i]) if i < len(nearby_distances) else "",
                    "icon": sanitize_input(nearby_icons[i]) if i < len(nearby_icons) else ""
                })

        # ===== DUPLICATE SUBMIT GUARD (server-side, token-based) =====
        # Builder jaan-boojh kar similar/same-title properties dobara add kar sakta hai
        # (jaise same project ke multiple units) — isliye title/location se block nahi karte.
        # Iske bajaye har form-load ko ek unique token milta hai; agar wahi EXACT
        # submission dobara aaye (double-click / resubmit), tabhi usse duplicate maana jaata hai.
        form_token = request.POST.get('form_token', '')
        used_tokens = request.session.get('used_property_tokens', [])

        if form_token and form_token in used_tokens:
            messages.info(request, "Ye submission already process ho chuki hai (duplicate click rok diya gaya).")
            return redirect("my_property")

        if form_token:
            used_tokens.append(form_token)
            request.session['used_property_tokens'] = used_tokens[-20:]  # sirf recent 20 yaad rakho
            request.session.modified = True

        try:
            with transaction.atomic():
                # FIXED: 'prop' instead of 'property' (reserved keyword)
                # FIXED: Both possession and possession_date fields
                prop = Property.objects.create(
                    title=data['title'],
                    location=data['location'],
                    project_name=data['project_name'],
                    price=data['price'],
                    price_unit=data['price_unit'],
                    beds=beds_val,
                    baths=baths_val,
                    sqft=sqft_val,
                    description=data['description'],
                    property_type=data['property_type'],
                    status=data['status'],
                    amenities=amenities,
                    highlights=data['highlights'],
                    rera_number=data['rera_number'],
                    possession=data['possession'],
                    possession_date=data['possession'],  # FIXED
                    map_link=data['map_link'],
                    configuration=data['configuration'],
                    builder_name=data['builder_name'],
                    starting_price=data['starting_price'],
                    max_price=data['max_price'],
                    project_status=data['project_status'],
                    launch_date=data['launch_date'],
                    total_units=data['total_units'],
                    total_towers=data['total_towers'],
                    land_parcel=data['land_parcel'],
                    nearby_places=nearby_data,
                    sales_head_number=data['sales_head_number'],
                    project_video_url=data['project_video_url'] or None,
                    latitude=latitude_val,
                    longitude=longitude_val,
                    builder=request.user,
                    **files
                )

            # Gallery images ko atomic transaction ke BAHAR upload karte hain (performance fix):
            # Cloudinary upload calls slow network operations hain, DB transaction ko itni der
            # tak khula rakhna DB connection ko block karta hai. Har image apne aap mein
            # ek independent save hai, isliye alag rakhna safe hai.
            images = request.FILES.getlist("images")
            logger.info(f"DEBUG: Received {len(images)} gallery image(s) in request.FILES for property '{prop.title}'")
            saved_count = 0
            for img in images:
                logger.info(f"DEBUG: Processing gallery file: name={img.name}, size={img.size} bytes")
                valid, msg = validate_file_upload(img, ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'], 10)
                if valid:
                    try:
                        pi = PropertyImage.objects.create(property=prop, image=img)
                        saved_count += 1
                        logger.info(f"DEBUG: Gallery image saved successfully -> id={pi.id}, url={pi.image.url}")
                    except Exception as img_err:
                        logger.error(f"DEBUG: Gallery image FAILED to save (likely Cloudinary upload error): {img_err}")
                else:
                    logger.warning(f"Gallery image skipped: {msg}")
            logger.info(f"DEBUG: Gallery upload complete -> {saved_count}/{len(images)} images saved for property '{prop.title}'")

            messages.success(request, f"Property '{prop.title}' added successfully!")
            logger.info(f"Property created: {prop.title} by {request.user.username}")
            return redirect("my_property")

        except Exception as e:
            logger.error(f"Property creation error: {str(e)}")
            messages.error(request, f"Failed to create property: {str(e)}")
            return redirect("add_property")

    return render(request, "builder/property_management.html", {"form_token": str(uuid.uuid4())})
@builder_required
def property_management(request):
    """Show builder's properties with gallery - N+1 FIXED"""
    
    # FIX: prefetch_related('images') se saari images ek hi query mein aa jayengi
    properties = Property.objects.filter(
        builder=request.user
    ).prefetch_related(
        'images'  # N+1 FIX: Gallery images ek saath load hongi
    ).annotate(
        wishlist_count=Count('wishlisted_by', distinct=True)
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(properties, 12)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    return render(request, "builder/property_management.html", {
        "properties": page_obj,
        "page_obj": page_obj,
        "form_token": str(uuid.uuid4()),
    })

@builder_required
def property_wishlist_list(request):
    """Builder ko dikhao ki kaunse users ne kaunsi property wishlist ki hai"""

    wishlist_items = Wishlist.objects.filter(
        property__builder=request.user
    ).select_related('user', 'property').order_by('-created_at')

    # Optional filter by property
    property_id = request.GET.get('property')
    if property_id and property_id.isdigit():
        wishlist_items = wishlist_items.filter(property_id=int(property_id))

    # Pagination
    paginator = Paginator(wishlist_items, 20)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    properties = Property.objects.filter(builder=request.user).only('id', 'title')

    return render(request, "builder/property_wishlist.html", {
        "wishlist_items": page_obj,
        "page_obj": page_obj,
        "properties": properties,
        "selected_property": property_id,
    })

@builder_required
def lead_management(request):
    """Builder lead management with search, filter, pagination"""
    
    inquiries = Inquiry.objects.filter(
        property__builder=request.user
    ).select_related('property').order_by('-created_at')
    
    # FIX: 'notes' hatao - TextField hai, prefetch nahi hota
    leads = Lead.objects.filter(
        builder=request.user
    ).select_related('assigned_to').prefetch_related('properties').order_by('-id')
    
    properties = Property.objects.filter(builder=request.user)

    # Search
    query = sanitize_input(request.GET.get('q', ''))
    if query:
        leads = leads.filter(
            Q(name__icontains=query) | 
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )

    # Status filter
    status = sanitize_input(request.GET.get('status', ''))
    if status:
        leads = leads.filter(status=status)

    # Sort
    sort = sanitize_input(request.GET.get('sort', ''))
    if sort == "old":
        leads = leads.order_by('id')
    else:
        leads = leads.order_by('-id')

    # Pagination
    page_obj = get_paginated_queryset(leads, request)

    # Selected lead detail - FIX: 'notes' hatao
    selected_lead = None
    lead_id = request.GET.get('lead')
    if lead_id and lead_id.isdigit():
        selected_lead = Lead.objects.filter(
            id=int(lead_id), 
            builder=request.user
        ).select_related('assigned_to').prefetch_related('properties').first()  # FIXED

    # Stats
    total_pipeline = Deal.objects.filter(
        builder=request.user
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    hot_leads = Lead.objects.filter(
        builder=request.user, 
        status='HOT'
    ).count()

    agents = Agent.objects.filter(builders=request.user, is_active=True)

    return render(request, "builder/lead_management.html", {
        "inquiries": inquiries,
        "leads": page_obj,
        "page_obj": page_obj,
        "selected_lead": selected_lead,
        "total_pipeline": total_pipeline,
        "hot_leads": hot_leads,
        "agents": agents,
        "properties": properties,
    })


# =============================================================================
# BUILDER DASHBOARD
# =============================================================================


@builder_required
def builder_dashboard(request):
    """Builder dashboard - OPTIMIZED for production"""
    today = date.today()

    # Date range filter
    start_date_str = sanitize_input(request.GET.get('start_date', ''))
    end_date_str = sanitize_input(request.GET.get('end_date', ''))

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
    else:
        start_date = today
        end_date = today

    # Cache key
    cache_key = f"dashboard_v2:{request.user.id}:{start_date}:{end_date}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return render(request, "builder/dashboard.html", cached_data)

    # =================================================================
    # FIX 1: Single base queryset for leads - REUSE
    # =================================================================
    base_leads_qs = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    )

    # =================================================================
    # FIX 2: Single base queryset for deals - REUSE
    # =================================================================
    base_deals_qs = Deal.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    )

    # =================================================================
    # FIX 3: Source counts in ONE query using annotation
    # =================================================================
    from django.db.models import Count, Case, When, Value, IntegerField

    source_counts = base_leads_qs.aggregate(
        search_count=Count(Case(When(source='search', then=1), output_field=IntegerField())),
        referral_count=Count(Case(When(source='referral', then=1), output_field=IntegerField())),
        social_count=Count(Case(When(source='social', then=1), output_field=IntegerField())),
        direct_count=Count(Case(When(source='direct', then=1), output_field=IntegerField())),
    )

    total_leads = base_leads_qs.count()
    total = total_leads or 1

    lead_sources = {
        "search": round((source_counts['search_count'] or 0) / total * 100, 2),
        "referrals": round((source_counts['referral_count'] or 0) / total * 100, 2),
        "social": round((source_counts['social_count'] or 0) / total * 100, 2),
        "direct": round((source_counts['direct_count'] or 0) / total * 100, 2),
    }

    # =================================================================
    # FIX 4: Followups with only() - lightweight fields
    # =================================================================
    today_followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date__range=[start_date, end_date],
        status="PENDING"
    ).select_related('agent', 'lead').only(
        'id', 'date', 'time', 'status', 'note',
        'agent__name', 'agent__id',
        'lead__id', 'lead__name'
    )

    grouped_followups = defaultdict(list)
    for f in today_followups:
        agent_name = f.agent.name if f.agent else "Unassigned"
        grouped_followups[agent_name].append(f)

    # =================================================================
    # FIX 5: Upcoming followups - only needed fields
    # =================================================================
    upcoming_time = (now() + timedelta(hours=1)).time()
    upcoming_followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date__range=[start_date, end_date],
        time__lte=upcoming_time,
        status="PENDING"
    ).select_related('lead').only(
        'id', 'date', 'time', 'note',
        'lead__id', 'lead__name'
    )

    # =================================================================
    # FIX 6: Missed leads - only needed fields
    # =================================================================
    missed_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date],
        created_at__lt=now() - timedelta(hours=24),
        status="NEW"
    ).only('id', 'name', 'phone', 'created_at')

    # =================================================================
    # FIX 7: Monthly revenue - single query
    # =================================================================
    monthly_data = (
        base_deals_qs.filter(status="CLOSED")
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    chart_labels = [calendar.month_abbr[item['month']] for item in monthly_data]
    chart_data = [float(item['total'] or 0) for item in monthly_data]

    # =================================================================
    # FIX 8: Stats - reuse base querysets
    # =================================================================
    active_deals = base_deals_qs.filter(
        status__in=["NEW", "NEGOTIATION", "BOOKED"]
    ).count()

    total_revenue = base_deals_qs.filter(
        status="CLOSED"
    ).aggregate(total=Sum('amount'))['total'] or 0

    closed_deals = base_deals_qs.filter(status="CLOSED").count()
    conversion_rate = (closed_deals / total_leads * 100) if total_leads else 0

    # =================================================================
    # FIX 9: Activities - only needed fields
    # =================================================================
    activities = Activity.objects.filter(
        created_at__date__range=[start_date, end_date]
    ).select_related('user').only(
        'message', 'created_at', 'user__username'
    ).order_by('-created_at')[:5]

    # =================================================================
    # FIX 10: Tasks - only needed fields
    # =================================================================
    tasks = Task.objects.filter(
        user=request.user,
        date__range=[start_date, end_date]
    ).only(
        'title', 'date', 'time', 'priority', 'status'
    ).order_by('-date', '-time')[:5]

    # =================================================================
    # FIX 11: Growth calculation - cached
    # =================================================================
    days_diff = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=days_diff)
    prev_end = start_date - timedelta(days=1)

    growth_cache_key = f"growth:{request.user.id}:{prev_start}:{prev_end}"
    growth_data = cache.get(growth_cache_key)

    if growth_data is None:
        prev_leads = Lead.objects.filter(
            builder=request.user,
            created_at__date__range=[prev_start, prev_end]
        ).count()

        prev_deals = Deal.objects.filter(
            builder=request.user,
            created_at__date__range=[prev_start, prev_end]
        ).count()

        prev_revenue = Deal.objects.filter(
            builder=request.user,
            status="CLOSED",
            created_at__date__range=[prev_start, prev_end]
        ).aggregate(total=Sum('amount'))['total'] or 0

        growth_data = {
            'prev_leads': prev_leads,
            'prev_deals': prev_deals,
            'prev_revenue': prev_revenue
        }
        cache.set(growth_cache_key, growth_data, 3600)

    prev_leads = growth_data['prev_leads']
    prev_deals = growth_data['prev_deals']
    prev_revenue = growth_data['prev_revenue']

    lead_growth = ((total_leads - prev_leads) / prev_leads * 100) if prev_leads else 0
    deal_growth = ((active_deals - prev_deals) / prev_deals * 100) if prev_deals else 0

    try:
        revenue_growth = ((float(total_revenue) - float(prev_revenue)) / float(prev_revenue) * 100) if prev_revenue else 0
    except (TypeError, ValueError, ZeroDivisionError):
        revenue_growth = 0

    # =================================================================
    # FIX 12: Deals list - only needed fields
    # =================================================================
    deals = base_deals_qs.select_related('property', 'agent').only(
        'id', 'client_name', 'amount', 'status', 'created_at',
        'property__title', 'property__id',
        'agent__name', 'agent__id'
    ).order_by('-created_at')

    # =================================================================
    # Build context - FIX 13: json.dumps hatao
    # =================================================================
    context = {
        "total_leads": total_leads,
        "active_deals": active_deals,
        "total_revenue": total_revenue,
        "conversion_rate": round(conversion_rate, 2),
        "activities": activities,
        "tasks": tasks,
        "lead_growth": round(lead_growth, 2),
        "deal_growth": round(deal_growth, 2),
        "revenue_growth": round(revenue_growth, 2),
        "lead_sources": lead_sources,
        "chart_labels": chart_labels,  # List bhejo
        "chart_data": chart_data,      # List bhejo
        "grouped_followups": dict(grouped_followups),
        "today_followups": today_followups,
        "missed_leads": missed_leads,
        "upcoming_followups": upcoming_followups,
        "deals": deals,
        "start_date": start_date,
        "end_date": end_date,
        "today": today,
    }

    # Cache dashboard data
    cache.set(cache_key, context, 300)

    return render(request, "builder/dashboard.html", context)# =============================================================================
# SCALE LAUNCH CHECKLIST
# =============================================================================

@builder_required
def scale_launch_checklist(request):
    """
    Scale Launch Checklist - Production Ready
    Shows checklist items with progress tracking + Leads sidebar
    """
    builder = request.user

    # ---- LEADS SIDEBAR DATA ----
    leads = Lead.objects.filter(
        builder=builder
    ).select_related('assigned_to').prefetch_related('properties').order_by('-created_at')[:20]

    # Lead stats for sidebar
    lead_stats = {
        'total': Lead.objects.filter(builder=builder).count(),
        'hot': Lead.objects.filter(builder=builder, status='HOT').count(),
        'warm': Lead.objects.filter(builder=builder, status='WARM').count(),
        'cold': Lead.objects.filter(builder=builder, status='COLD').count(),
        'new': Lead.objects.filter(builder=builder, status='NEW').count(),
        'contacted': Lead.objects.filter(builder=builder, status='CONTACTED').count(),
        'closed': Lead.objects.filter(builder=builder, status='CLOSED').count(),
    }

    # Recent activities for sidebar (with fallback)
    try:
        recent_activities = LeadActivity.objects.filter(
            lead__builder=builder
        ).select_related('lead', 'created_by').order_by('-created_at')[:10]
    except Exception:
        recent_activities = []

    # ---- CHECKLIST DATA ----
    # Pre-launch checklist items
    checklist_items = [
        {
            'id': 'property_setup',
            'title': 'Property Setup & Configuration',
            'description': 'Add all properties with complete details, images, and pricing',
            'icon': 'apartment',
            'category': 'pre_launch',
            'weight': 15,
            'tasks': [
                {'text': 'Add minimum 5 properties', 'check': Property.objects.filter(builder=builder).count() >= 5},
                {'text': 'Upload property images for all listings', 'check': PropertyImage.objects.filter(property__builder=builder).exists()},
                {'text': 'Set pricing and possession dates', 'check': Property.objects.filter(builder=builder, price__isnull=False).exclude(price='').exists()},
                {'text': 'Add amenities and highlights', 'check': Property.objects.filter(builder=builder).exclude(amenities=[]).exists()},
                {'text': 'Configure RERA numbers', 'check': Property.objects.filter(builder=builder).exclude(rera_number__isnull=True).exclude(rera_number='').exists()},
            ]
        },
        {
            'id': 'agent_setup',
            'title': 'Agent Team Setup',
            'description': 'Configure your sales team with proper assignments',
            'icon': 'group',
            'category': 'pre_launch',
            'weight': 15,
            'tasks': [
                {'text': 'Add at least 2 agents', 'check': Agent.objects.filter(builders=builder).count() >= 2},
                {'text': 'Assign agents to properties', 'check': Lead.objects.filter(builder=builder, assigned_to__isnull=False).exists()},
                {'text': 'Set agent commission rates', 'check': Agent.objects.filter(builders=builder).exclude(commission_rate=2.00).exists()},
                {'text': 'Configure agent profiles', 'check': Agent.objects.filter(builders=builder, user__profile__isnull=False).exists()},
            ]
        },
        {
            'id': 'lead_system',
            'title': 'Lead Management System',
            'description': 'Set up lead capture, assignment, and follow-up workflows',
            'icon': 'person_add',
            'category': 'pre_launch',
            'weight': 20,
            'tasks': [
                {'text': 'Configure lead capture forms', 'check': True},
                {'text': 'Set up auto-assignment rules', 'check': Agent.objects.filter(builders=builder).exists()},
                {'text': 'Create follow-up sequences', 'check': _safe_model_check('DripSequence', builder)},
                {'text': 'Configure escalation rules', 'check': _safe_model_check('EscalationRule', builder)},
                {'text': 'Test lead pipeline workflow', 'check': Lead.objects.filter(builder=builder).exclude(status='NEW').exists()},
            ]
        },
        {
            'id': 'automation',
            'title': 'Automation & Drip Campaigns',
            'description': 'Configure automated follow-ups and marketing sequences',
            'icon': 'smart_toy',
            'category': 'pre_launch',
            'weight': 10,
            'tasks': [
                {'text': 'Create welcome email sequence', 'check': _safe_model_check('DripSequence', builder, step_number=1)},
                {'text': 'Set up SMS/WhatsApp templates', 'check': _safe_model_check('DripSequence', builder, channel__in=['SMS', 'WHATSAPP'])},
                {'text': 'Configure missed follow-up alerts', 'check': _safe_model_check('EscalationRule', builder, is_active=True)},
                {'text': 'Test automation triggers', 'check': _safe_model_check('AutomationLog', builder)},
            ]
        },
        {
            'id': 'analytics',
            'title': 'Analytics & Reporting',
            'description': 'Set up dashboards and reporting for performance tracking',
            'icon': 'analytics',
            'category': 'pre_launch',
            'weight': 10,
            'tasks': [
                {'text': 'Review analytics dashboard', 'check': True},
                {'text': 'Configure revenue tracking', 'check': Deal.objects.filter(builder=builder).exists()},
                {'text': 'Set up agent performance metrics', 'check': Agent.objects.filter(builders=builder).exists()},
                {'text': 'Configure AI insights', 'check': True},
            ]
        },
        {
            'id': 'communication',
            'title': 'Communication Channels',
            'description': 'Set up chat, email, and notification systems',
            'icon': 'chat',
            'category': 'pre_launch',
            'weight': 10,
            'tasks': [
                {'text': 'Configure email settings', 'check': True},
                {'text': 'Set up WhatsApp integration', 'check': True},
                {'text': 'Test notification system', 'check': Notification.objects.filter(recipient=builder).exists()},
                {'text': 'Configure chatbot responses', 'check': True},
            ]
        },
        {
            'id': 'security',
            'title': 'Security & Compliance',
            'description': 'Ensure data security and regulatory compliance',
            'icon': 'shield',
            'category': 'pre_launch',
            'weight': 10,
            'tasks': [
                {'text': 'Review user permissions', 'check': Agent.objects.filter(builders=builder).exists()},
                {'text': 'Configure data backup', 'check': True},
                {'text': 'Set up privacy policy', 'check': True},
                {'text': 'Enable audit logging', 'check': True},
            ]
        },
        {
            'id': 'launch_prep',
            'title': 'Launch Preparation',
            'description': 'Final checks before going live',
            'icon': 'rocket_launch',
            'category': 'launch',
            'weight': 10,
            'tasks': [
                {'text': 'Test all user flows', 'check': Lead.objects.filter(builder=builder).count() > 0},
                {'text': 'Verify mobile responsiveness', 'check': True},
                {'text': 'Check site performance', 'check': True},
                {'text': 'Create launch announcement', 'check': Campaign.objects.filter(created_by=builder).exists()},
                {'text': 'Set up monitoring alerts', 'check': True},
            ]
        },
    ]

    # Calculate progress for each category
    total_progress = 0
    total_weight = 0

    for item in checklist_items:
        completed = sum(1 for task in item['tasks'] if task['check'])
        total = len(item['tasks'])
        item['progress'] = round((completed / total) * 100) if total > 0 else 0
        item['completed_tasks'] = completed
        item['total_tasks'] = total
        item['is_complete'] = completed == total

        total_progress += item['progress'] * item['weight']
        total_weight += item['weight']

    overall_progress = round(total_progress / total_weight) if total_weight > 0 else 0

    # Categorize items
    pre_launch_items = [item for item in checklist_items if item['category'] == 'pre_launch']
    launch_items = [item for item in checklist_items if item['category'] == 'launch']

    # Calculate category progress
    pre_launch_progress = round(sum(item['progress'] * item['weight'] for item in pre_launch_items) / sum(item['weight'] for item in pre_launch_items)) if pre_launch_items else 0
    launch_progress = round(sum(item['progress'] * item['weight'] for item in launch_items) / sum(item['weight'] for item in launch_items)) if launch_items else 0

    context = {
        'checklist_items': checklist_items,
        'pre_launch_items': pre_launch_items,
        'launch_items': launch_items,
        'overall_progress': overall_progress,
        'pre_launch_progress': pre_launch_progress,
        'launch_progress': launch_progress,
        'leads': leads,
        'lead_stats': lead_stats,
        'recent_activities': recent_activities,
        'total_leads': lead_stats['total'],
        'is_ready_to_launch': overall_progress >= 80,
    }

    return render(request, "builder/scale_launch_checklist.html", context)


def _safe_model_check(model_name, builder, **filters):
    """
    Safely check if model exists and has records for builder.
    Returns False if model doesn't exist (not migrated yet).
    """
    try:
        from django.apps import apps
        model = apps.get_model('core', model_name)
        queryset = model.objects.filter(builder=builder)
        if filters:
            queryset = queryset.filter(**filters)
        return queryset.exists()
    except LookupError:
        # Model doesn't exist (not migrated)
        return False
    except Exception:
        return False

@login_required
@require_POST
def add_lead(request):
    """Add new lead with auto-assignment"""
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

    try:
        agent = auto_assign_agent(request.user)
        
        lead = Lead.objects.create(
            name=sanitize_input(request.POST.get("name")),
            email=sanitize_input(request.POST.get("email")),
            phone=sanitize_input(request.POST.get("phone")),
            source=sanitize_input(request.POST.get("source", "Manual")),
            status=sanitize_input(request.POST.get("status", "NEW")),
            assigned_to=agent,
            interest=sanitize_input(request.POST.get("interest")),
            builder=request.user,
            notes=sanitize_input(request.POST.get("message", ""))
        )

        LeadActivity.objects.create(
            lead=lead, 
            message="Lead created",
            created_by=request.user
        )

        property_id = request.POST.get("property_id")
        if property_id and property_id.isdigit():
            property_obj = get_object_or_404(
                Property, 
                id=int(property_id), 
                builder=request.user
            )
            lead.properties.add(property_obj)

        if agent:
            FollowUp.objects.create(
                lead=lead,
                agent=agent,
                date=now().date() + timedelta(days=1),
                time=datetime.strptime("10:00", "%H:%M").time(),
                note="First followup - auto created",
                status='PENDING',
                is_auto_created=True
            )
        
        messages.success(request, f"Lead '{lead.name}' assigned + followup scheduled!")
        logger.info(f"Lead created: {lead.name} by {request.user.username}")
        
    except Exception as e:
        logger.error(f"Lead creation error: {str(e)}")
        messages.error(request, "Failed to create lead. Please try again.")

    return redirect("lead_management")


@login_required
@require_POST
def edit_lead(request, id):
    """Edit lead"""
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

    lead = get_object_or_404(Lead, id=id, builder=request.user)
    
    lead.name = sanitize_input(request.POST.get("name"))
    lead.email = sanitize_input(request.POST.get("email"))
    lead.phone = sanitize_input(request.POST.get("phone"))
    lead.source = sanitize_input(request.POST.get("source"))
    lead.status = sanitize_input(request.POST.get("status"))
    lead.interest = sanitize_input(request.POST.get("interest"))

    agent_id = request.POST.get("assigned_to")
    if agent_id and agent_id.isdigit():
        lead.assigned_to = Agent.objects.filter(
            id=int(agent_id), 
            builders=request.user
        ).first()

    lead.save()
    
    LeadActivity.objects.create(
        lead=lead,
        message=f"Lead updated by {request.user.username}",
        created_by=request.user
    )
    
    messages.success(request, "Lead updated successfully")
    return redirect(f"/builder/leads/?lead={id}")


@login_required
def export_leads(request):
    """Export leads to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Source', 'Status', 'Assigned Agent', 'Created At'])
    
    leads = Lead.objects.filter(
        builder=request.user
    ).select_related('assigned_to')
    
    for lead in leads:
        writer.writerow([
            lead.name, 
            lead.email, 
            lead.phone, 
            lead.source, 
            lead.status,
            lead.assigned_to.name if lead.assigned_to else "Unassigned",
            lead.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    return response


# =============================================================================
# PROPERTY DETAIL & EDIT (BUILDER)
# =============================================================================

logger = logging.getLogger(__name__)

@builder_required
def builder_property_detail(request, id):
    """Builder property detail with edit/delete - N+1 FIXED"""
    
    # FIX: prefetch_related already hai, but select_related builder bhi add karo
    property_obj = get_object_or_404(
        Property.objects.select_related('builder').prefetch_related(
            'images',           # Gallery images
            'interested_leads',  # Leads
            'inquiries',         # Inquiries
        ), 
        id=id, 
        builder=request.user
    )
    
    # FIX: Leads ko bhi prefetch_related ke saath lao
    leads = Lead.objects.filter(
        properties=property_obj, 
        builder=request.user
    ).select_related('assigned_to').prefetch_related('followups')

    # Delete handling
    if request.method == "POST" and request.POST.get("action") == "delete":
        property_title = property_obj.title
        property_obj.delete()
        messages.success(request, f"Property '{property_title}' deleted successfully!")
        logger.info(f"Property deleted: {property_title}")
        return redirect("property_management")

    # Update handling
    if request.method == "POST":
        return _update_property(request, property_obj)

    # FIX: Gallery images ko list mein convert karke bhejo - template mein baar-baar query nahi hogi
    gallery_images = list(property_obj.images.all())
    
    return render(request, "builder/property_detail.html", {
        "property": property_obj,
        "leads": leads,
        "gallery_images": gallery_images,  # N+1 FIX: Pre-loaded list
        "gallery_count": len(gallery_images),
    })

def _update_property(request, property):
    """Helper to update property"""
    fields = {
        'title': 'title',
        'location': 'location',
        'project_name': 'project_name',
        'price': 'price',
        'property_type': 'property_type',
        'description': 'description',
        'status': 'status',
        'configuration': 'configuration',
        'builder_name': 'builder_name',
        'starting_price': 'starting_price',
        'max_price': 'max_price',
        'project_status': 'project_status',
        'launch_date': 'launch_date',
        'total_units': 'total_units',
        'total_towers': 'total_towers',
        'land_parcel': 'land_parcel',
        'rera_number': 'rera_number',
        'possession': 'possession',
        'highlights': 'highlights',
        'map_link': 'map_link',
        'sales_head_number': 'sales_head_number',
        'project_video_url': 'project_video_url',
    }

    for field, post_key in fields.items():
        value = sanitize_input(request.POST.get(post_key, getattr(property, field)))
        setattr(property, field, value)

    # Numeric fields
    try:
        property.beds = int(sanitize_input(request.POST.get('beds'))) or None
        property.baths = float(sanitize_input(request.POST.get('baths'))) or None
        property.sqft = int(sanitize_input(request.POST.get('sqft'))) or None
    except (ValueError, TypeError):
        pass

    # Map coordinates (used by the public Property Map page)
    lat_raw = (request.POST.get('latitude') or '').strip()
    lng_raw = (request.POST.get('longitude') or '').strip()
    try:
        property.latitude = float(lat_raw) if lat_raw else None
    except (ValueError, TypeError):
        pass
    try:
        property.longitude = float(lng_raw) if lng_raw else None
    except (ValueError, TypeError):
        pass

    # Amenities
    property.amenities = request.POST.getlist("amenities")

    # Nearby places
    nearby_names = request.POST.getlist("nearby_name")
    nearby_distances = request.POST.getlist("nearby_distance")
    nearby_icons = request.POST.getlist("nearby_icon")
    nearby_data = []
    for i in range(len(nearby_names)):
        if nearby_names[i].strip():
            nearby_data.append({
                "name": sanitize_input(nearby_names[i]),
                "distance": sanitize_input(nearby_distances[i]) if i < len(nearby_distances) else "",
                "icon": sanitize_input(nearby_icons[i]) if i < len(nearby_icons) else ""
            })
    property.nearby_places = nearby_data

    # File uploads
    file_fields = {
        'thumbnail': (['.jpg', '.jpeg', '.png', '.gif', '.avif'], 10),
        'project_logo': (['.jpg', '.jpeg', '.png', '.gif', '.avif'], 10),
        'project_video': (['.mp4', '.mov', '.avi'], 20),
        'brochure': (['.pdf'], 10),
    }

    for field, (exts, max_size) in file_fields.items():
        if request.FILES.get(field):
            valid, msg = validate_file_upload(request.FILES.get(field), exts, max_size)
            if valid:
                setattr(property, field, request.FILES.get(field))
            else:
                messages.error(request, f"{field.title()}: {msg}")

    property.save()

    # New gallery images
    images = request.FILES.getlist("images")
    for img in images:
        valid, msg = validate_file_upload(img, ['.jpg', '.jpeg', '.png', '.gif', '.avif'])
        if valid:
            PropertyImage.objects.create(property=property, image=img)

    messages.success(request, "Property updated successfully!")
    return redirect('builder_property_detail', id=property.id)

@builder_required
def delete_property(request, id):
    """Delete property"""
    property = get_object_or_404(Property, id=id, builder=request.user)
    property_title = property.title
    property.delete()
    messages.success(request, f"Property '{property_title}' deleted successfully!")
    logger.info(f"Property deleted: {property_title}")
    return redirect("property_management")


@builder_required
def assign_property(request):
    """Assign property to lead"""
    leads = Lead.objects.filter(builder=request.user).select_related('assigned_to')
    properties = Property.objects.filter(builder=request.user)
    agents = Agent.objects.filter(builders=request.user, is_active=True)

    selected_lead = None
    selected_lead_id = request.GET.get("lead")
    if selected_lead_id and selected_lead_id.isdigit():
        selected_lead = Lead.objects.filter(
            id=int(selected_lead_id), 
            builder=request.user
        ).first()

    if request.method == "POST":
        lead_id = request.POST.get("lead_id")
        property_id = request.POST.get("property_id")
        agent_id = request.POST.get("agent_id")

        if not all([lead_id, property_id, agent_id]):
            messages.error(request, "All fields are required")
            return redirect("assign_property")

        lead = get_object_or_404(Lead, id=lead_id, builder=request.user)
        property_obj = get_object_or_404(Property, id=property_id, builder=request.user)
        agent = get_object_or_404(Agent, id=agent_id, builders=request.user)

        lead.properties.add(property_obj)
        lead.assigned_to = agent
        lead.save()
        
        LeadActivity.objects.create(
            lead=lead,
            message=f"Property assigned by {request.user.username}",
            created_by=request.user
        )
        
        messages.success(request, "Property assigned successfully!")
        return redirect(f"/builder/assign-property/?lead={lead.id}")

    return render(request, "builder/assign_property.html", {
        "leads": leads,
        "properties": properties,
        "agents": agents,
        "selected_lead": selected_lead
    })


@login_required
def builder_root(request):
    """Builder root redirect"""
    return redirect('builder_dashboard')


# =============================================================================
# AGENT MANAGEMENT
# =============================================================================

@builder_required
def create_agent(request):
    """Create new agent"""
    if request.method == "POST" and not request.POST.get("search_query") and not request.POST.get("agent_id"):
        name = sanitize_input(request.POST.get("name"))
        username = sanitize_input(request.POST.get("username"))
        password = request.POST.get("password")
        email = sanitize_input(request.POST.get("email"))
        phone = sanitize_input(request.POST.get("phone"))

        if not all([name, username, password]):
            messages.error(request, "Name, username and password are required")
            return redirect('create_agent')

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters")
            return redirect('create_agent')

        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'role': 'agent'
                }
            )
            
            if created:
                user.set_password(password)
                user.save()

            agent, created = Agent.objects.get_or_create(
                user=user,
                defaults={"name": name, "email": email, "phone": phone}
            )

            agent.builders.add(request.user)

            if not created:
                agent.name = name
                agent.email = email
                agent.phone = phone
                agent.save()
                agent.builders.add(request.user)

            messages.success(request, f"Agent '{name}' created and added to your team!")
            logger.info(f"Agent created: {name} by {request.user.username}")

        except Exception as e:
            logger.error(f"Agent creation error: {str(e)}")
            messages.error(request, "Failed to create agent. Please try again.")

        return redirect('create_agent')

    agents = Agent.objects.filter(builders=request.user).select_related('user')
    return render(request, "builder/create_agent.html", {"agents": agents})


@builder_required
def add_existing_agent(request):
    """Add existing agent to builder's team"""
    if request.method == "POST":
        search_query = sanitize_input(request.POST.get("search_query"))
        
        if search_query:
            results = Agent.objects.filter(
                Q(user__username__iexact=search_query) |
                Q(phone__icontains=search_query)
            ).exclude(builders=request.user).select_related('user')

            agents = Agent.objects.filter(builders=request.user)
            return render(request, "builder/create_agent.html", {
                "agents": agents,
                "search_results": results
            })

        agent_id = request.POST.get("agent_id")
        if agent_id and agent_id.isdigit():
            try:
                agent = Agent.objects.get(id=int(agent_id))
                if request.user in agent.builders.all():
                    messages.warning(request, "This agent is already in your team!")
                else:
                    agent.builders.add(request.user)
                    messages.success(request, f"Agent '{agent.name}' added to your team!")
                    logger.info(f"Agent {agent.name} added to builder {request.user.username}")
            except Agent.DoesNotExist:
                messages.error(request, "Agent not found!")

    return redirect('create_agent')


@builder_required
def remove_agent_from_builder(request, agent_id):
    """Remove agent from builder's team"""
    if request.method == "POST":
        try:
            agent = Agent.objects.get(id=agent_id)
            agent.builders.remove(request.user)
            messages.success(request, f"Agent '{agent.name}' removed from your team.")
            logger.info(f"Agent {agent.name} removed from builder {request.user.username}")
        except Agent.DoesNotExist:
            messages.error(request, "Agent not found!")

    return redirect('create_agent')


# =============================================================================
# PIPELINE & LEAD STATUS
# =============================================================================
@builder_required
def builder_pipeline(request):
    builder = request.user

    # ===== DATE FILTERING =====
    filter_type = request.GET.get('filter', 'all')  # all, today, week, month, custom
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    today = date.today()

    # Calculate date range based on filter
    if filter_type == 'today':
        start_date = today
        end_date = today
    elif filter_type == 'week':
        # This week (Monday to Sunday)
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif filter_type == 'month':
        # This month
        start_date = today.replace(day=1)
        # Last day of month
        if today.month == 12:
            end_date = today.replace(day=31)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    elif filter_type == 'custom' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = None
            end_date = None
    else:
        start_date = None
        end_date = None

    # Base queryset for agents
    agents = Agent.objects.filter(
        builders=builder,
        is_active=True
    ).select_related('user').order_by('name')

    agent_pipeline = {}

    for agent in agents:
        # Apply date filter to leads
        agent_leads_qs = Lead.objects.filter(
            assigned_to=agent,
            builder=builder
        ).select_related('assigned_to').prefetch_related('properties').order_by('-updated_at')

        # Apply date range filter if specified
        if start_date and end_date:
            agent_leads_qs = agent_leads_qs.filter(
                created_at__date__range=[start_date, end_date]
            )

        stages = {
            'NEW': list(agent_leads_qs.filter(status='NEW')),
            'CONTACTED': list(agent_leads_qs.filter(status='CONTACTED')),
            'VISIT': list(agent_leads_qs.filter(status='VISIT')),
            'NEGOTIATION': list(agent_leads_qs.filter(status='NEGOTIATION')),
            'CLOSED': list(agent_leads_qs.filter(status='CLOSED')),
            'FAILED': list(agent_leads_qs.filter(status='FAILED')),
            'OTHER': list(agent_leads_qs.exclude(
                status__in=['NEW', 'CONTACTED', 'VISIT', 'NEGOTIATION', 'CLOSED', 'FAILED']
            )),
        }

        agent_pipeline[agent.id] = {
            'agent': agent,
            'total': agent_leads_qs.count(),
            'hot': agent_leads_qs.filter(priority='HOT').count(),
            'stages': stages,
        }

    # Unassigned leads with date filter
    unassigned_qs = Lead.objects.filter(
        builder=builder,
        assigned_to__isnull=True
    ).select_related('assigned_to').prefetch_related('properties').order_by('-updated_at')

    if start_date and end_date:
        unassigned_qs = unassigned_qs.filter(
            created_at__date__range=[start_date, end_date]
        )

    unassigned_stages = {
        'NEW': list(unassigned_qs.filter(status='NEW')),
        'CONTACTED': list(unassigned_qs.filter(status='CONTACTED')),
        'VISIT': list(unassigned_qs.filter(status='VISIT')),
        'NEGOTIATION': list(unassigned_qs.filter(status='NEGOTIATION')),
        'CLOSED': list(unassigned_qs.filter(status='CLOSED')),
        'FAILED': list(unassigned_qs.filter(status='FAILED')),
        'OTHER': list(unassigned_qs.exclude(
            status__in=['NEW', 'CONTACTED', 'VISIT', 'NEGOTIATION', 'CLOSED', 'FAILED']
        )),
    }

    # Stats with date filter
    all_leads_qs = Lead.objects.filter(builder=builder)
    if start_date and end_date:
        all_leads_qs = all_leads_qs.filter(
            created_at__date__range=[start_date, end_date]
        )

    context = {
        'agent_pipeline': agent_pipeline,
        'unassigned': {
            'total': unassigned_qs.count(),
            'stages': unassigned_stages,
        },
        'agents': agents,
        'total_leads': all_leads_qs.count(),
        'hot_leads': all_leads_qs.filter(priority='HOT').count(),
        'total_closed': all_leads_qs.filter(status='CLOSED').count(),
        'conversion_rate': round(
            (all_leads_qs.filter(status='CLOSED').count() / all_leads_qs.count() * 100), 1
        ) if all_leads_qs.count() else 0,
        # Date filter context for template
        'filter_type': filter_type,
        'start_date': start_date_str if start_date_str else '',
        'end_date': end_date_str if end_date_str else '',
        'filter_label': {
            'all': 'All Time',
            'today': 'Today',
            'week': 'This Week',
            'month': 'This Month',
            'custom': 'Custom Range'
        }.get(filter_type, 'All Time'),
    }

    return render(request, "builder/pipeline.html", context)
@login_required
@require_POST
def update_lead_status(request):
    """AJAX: Update lead status"""
    try:
        data = json.loads(request.body)
        lead_id = data.get("lead_id")
        status = sanitize_input(data.get("status"))

        if request.user.role == "builder":
            lead = get_object_or_404(Lead, id=lead_id, builder=request.user)
        elif request.user.role == "agent":
            agent = get_object_or_404(Agent, user=request.user)
            lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)
        else:
            return JsonResponse({"success": False, "message": "Permission denied"})

        old_status = lead.status
        lead.status = status
        lead.save()

        LeadActivity.objects.create(
            lead=lead,
            message=f"{request.user.username} changed status from {old_status} to {status}",
            created_by=request.user
        )

        return JsonResponse({"success": True, "status": status})

    except Agent.DoesNotExist:
        return JsonResponse({"success": False, "message": "Agent profile not found"})
    except Exception as e:
        logger.error(f"Update lead status error: {str(e)}")
        return JsonResponse({"success": False, "message": "An error occurred"})


@login_required
def lead_detail_api(request, id):
    """API: Lead detail"""
    if request.user.role == "builder":
        lead = get_object_or_404(Lead, id=id, builder=request.user)
    elif request.user.role == "agent":
        agent = get_object_or_404(Agent, user=request.user)
        lead = get_object_or_404(Lead, id=id, assigned_to=agent)
    else:
        return JsonResponse({"error": "Permission denied"}, status=403)

    return JsonResponse({
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
        "priority": lead.priority,
    })


@login_required
@require_POST
def add_note(request):
    """AJAX: Add note to lead"""
    try:
        data = json.loads(request.body)
        lead_id = data.get('lead_id')
        note_text = sanitize_input(data.get('note'))

        if request.user.role == "builder":
            lead = get_object_or_404(Lead, id=lead_id, builder=request.user)
        elif request.user.role == "agent":
            agent = get_object_or_404(Agent, user=request.user)
            lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)
        else:
            return JsonResponse({"success": False, "message": "Permission denied"})

        LeadNote.objects.create(
            lead=lead, 
            note=note_text,
            created_by=request.user
        )
        
        LeadActivity.objects.create(
            lead=lead,
            message=f"Note added by {request.user.username}",
            created_by=request.user
        )
        
        return JsonResponse({"success": True})
        
    except Exception as e:
        logger.error(f"Add note error: {str(e)}")
        return JsonResponse({"success": False, "message": "An error occurred"})


@login_required
@require_POST
def update_priority(request):
    """AJAX: Update lead priority"""
    try:
        data = json.loads(request.body)
        lead_id = data.get("lead_id")
        priority = sanitize_input(data.get("priority"))
        
        lead = get_object_or_404(Lead, id=lead_id, builder=request.user)
        lead.priority = priority
        lead.save()
        
        return JsonResponse({"success": True})
        
    except Exception as e:
        logger.error(f"Update priority error: {str(e)}")
        return JsonResponse({"success": False, "message": "An error occurred"})


# =============================================================================
# ANALYTICS
# =============================================================================

@builder_required
def analytics(request):
    """Builder analytics dashboard"""
    leads = Lead.objects.filter(builder=request.user)
    total_leads = leads.count()
    closed_leads = leads.filter(status="CLOSED").count()
    active_leads = leads.exclude(status="CLOSED").count()

    total_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED"
    ).aggregate(total=Sum('amount'))['total'] or 0

    status_counts = {
        "NEW": leads.filter(status="NEW").count(),
        "CONTACTED": leads.filter(status="CONTACTED").count(),
        "SITE VISIT": leads.filter(status="SITE VISIT").count(),
        "NEGOTIATION": leads.filter(status="NEGOTIATION").count(),
        "CLOSED": leads.filter(status="CLOSED").count(),
    }

    sources = leads.values('source').annotate(count=Count('id')).order_by('-count')
    source_labels = [s['source'] for s in sources]
    source_data = [s['count'] for s in sources]

    agents = []
    for agent in Agent.objects.filter(builders=request.user):
        agent_leads = leads.filter(assigned_to=agent)
        total = agent_leads.count()
        closed = agent_leads.filter(status="CLOSED").count()
        active = agent_leads.exclude(status="CLOSED").count()
        agents.append({
            "name": agent.name, 
            "total": total, 
            "closed": closed, 
            "active": active
        })

    return render(request, "builder/analytics.html", {
        "total_leads": total_leads,
        "closed_leads": closed_leads,
        "active_leads": active_leads,
        "total_revenue": total_revenue,
        "status_data": list(status_counts.values()),
        "source_labels": source_labels,
        "source_data": source_data,
        "agents": agents
    })


# =============================================================================
# DOCUMENT MANAGEMENT
# =============================================================================

@login_required
def document_management(request):
    """Document upload and management"""
    if request.method == "POST":
        file = request.FILES.get("file")
        category = sanitize_input(request.POST.get("category", "PERSONAL"))

        if file:
            valid, msg = validate_file_upload(
                file, 
                ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.png'],
                10
            )
            if valid:
                try:
                    doc = Document.objects.create(
                        name=file.name,
                        file=file,
                        category=category,
                        uploaded_by=request.user
                    )
                    Notification.objects.create(
                        recipient=request.user,
                        title="Document Uploaded",
                        message=f"{doc.name} uploaded",
                        type="document"
                    )
                    messages.success(request, "Document uploaded successfully!")
                except Exception as e:
                    logger.error(f"Document upload error: {str(e)}")
                    messages.error(request, "Upload failed. Please try again.")
            else:
                messages.error(request, f"File upload failed: {msg}")
        
        return redirect("document_management")

    documents = Document.objects.filter(
        uploaded_by=request.user
    ).order_by("-created_at")
    
    return render(request, "builder/document_management.html", {"documents": documents})


@login_required
def delete_document(request, doc_id):
    """Delete document"""
    doc = get_object_or_404(Document, id=doc_id, uploaded_by=request.user)
    doc.delete()
    messages.success(request, "Document deleted successfully!")
    return redirect('document_management')


# =============================================================================
# COMMUNICATION
# =============================================================================

@login_required
def communication(request):
    """Chat/messaging interface"""
    if request.user.role == "builder":
        conversations = Conversation.objects.filter(
            messages__is_agent=True
        ).distinct().select_related().order_by('-updated_at')
    else:
        agent = get_object_or_404(Agent, user=request.user)
        conversations = Conversation.objects.filter(
            messages__conversation__in=Conversation.objects.filter(
                messages__is_agent=False
            )
        ).distinct().order_by('-updated_at')

    first_chat = conversations.first()
    messages_list = []
    if first_chat:
        messages_list = first_chat.messages.select_related('sender').all().order_by('created_at')

    return render(request, "builder/communication.html", {
        "conversations": conversations,
        "messages": messages_list,
        "active_chat": first_chat
    })


@login_required
@require_POST
def send_message(request):
    """Send message"""
    try:
        data = json.loads(request.body)
        name = sanitize_input(data.get("name"))
        phone = sanitize_input(data.get("phone"))
        text = sanitize_input(data.get("message"))

        if not phone or not text:
            return JsonResponse({
                "status": "error", 
                "message": "Phone and message required"
            })

        convo, created = Conversation.objects.get_or_create(
            lead_phone=phone,
            defaults={"lead_name": name or "Unknown"}
        )
        
        Message.objects.create(
            conversation=convo,
            sender=request.user,
            text=text,
            is_agent=False
        )
        
        Notification.objects.create(
            recipient=request.user,
            title="New Message",
            message=f"Message from {name}",
            type="message"
        )

        return JsonResponse({"status": "sent", "conversation_id": convo.id})
        
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"})


@login_required
@require_POST
def client_send_message(request):
    """Client send message"""
    try:
        data = json.loads(request.body)
        name = sanitize_input(data.get("name", "Guest"))
        phone = sanitize_input(data.get("phone", "unknown"))
        text = sanitize_input(data.get("message"))

        if not text:
            return JsonResponse({"status": "error", "message": "Message required"})

        convo, created = Conversation.objects.get_or_create(
            lead_phone=phone,
            defaults={"lead_name": name}
        )
        
        Message.objects.create(
            conversation=convo,
            sender=request.user,
            text=text,
            is_agent=False
        )
        
        return JsonResponse({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Client message error: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"})


@login_required
@require_GET
def get_messages(request):
    """Get messages for conversation"""
    convo_id = request.GET.get("conversation_id")
    if not convo_id or not convo_id.isdigit():
        return JsonResponse({"messages": []})

    convo = Conversation.objects.filter(id=int(convo_id)).first()
    if not convo:
        return JsonResponse({"messages": []})

    msgs = convo.messages.select_related('sender').all().order_by('created_at')
    data = [{"text": m.text, "is_agent": m.is_agent, "sender": m.sender.username} for m in msgs]
    
    return JsonResponse({"messages": data})


@login_required
@require_POST
def agent_send_message(request):
    """Agent send message"""
    try:
        data = json.loads(request.body)
        convo_id = data.get("conversation_id")
        text = sanitize_input(data.get("message"))

        if not convo_id or not text:
            return JsonResponse({
                "status": "error", 
                "message": "Conversation ID and message required"
            })

        convo = get_object_or_404(Conversation, id=convo_id)
        Message.objects.create(
            conversation=convo,
            sender=request.user,
            text=text,
            is_agent=True
        )
        
        return JsonResponse({"status": "sent"})
        
    except Exception as e:
        logger.error(f"Agent send message error: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"})


# =============================================================================
# TASKS
# =============================================================================

@login_required
@require_POST
def create_task(request):
    """Create new task"""
    try:
        data = json.loads(request.body)
        title = sanitize_input(data.get("title"))
        lead_id = data.get("lead")
        date_str = sanitize_input(data.get("date"))
        time_str = sanitize_input(data.get("time"))
        priority = sanitize_input(data.get("priority", "MEDIUM"))

        # Validate lead access
        if request.user.role == "builder":
            get_object_or_404(Lead, id=lead_id, builder=request.user)
        elif request.user.role == "agent":
            agent = get_object_or_404(Agent, user=request.user)
            get_object_or_404(Lead, id=lead_id, assigned_to=agent)

        task = Task.objects.create(
            title=title,
            lead_id=lead_id,
            date=date_str,
            time=time_str,
            priority=priority,
            user=request.user
        )

        Notification.objects.create(
            recipient=request.user,
            title="Task Created",
            message=f"{task.title} scheduled",
            type="task"
        )
        
        return JsonResponse({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Create task error: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"})


@login_required
@require_POST
def task_done(request, id):
    """Mark task as done"""
    try:
        task = Task.objects.get(id=id, user=request.user)
        task.status = "DONE"
        task.save()
        
        Notification.objects.create(
            recipient=request.user,
            title="Task Completed",
            message=f"{task.title} marked as done",
            type="task"
        )
        
        return JsonResponse({"status": "done"})
        
    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Task not found"})


@builder_required
def scheduler_overview(request):
    """Task scheduler overview"""
    tasks = Task.objects.filter(user=request.user).select_related('lead')
    leads = Lead.objects.filter(builder=request.user)
    today = date.today()

    tasks = tasks.filter(date__year=today.year, date__month=today.month)

    cal = calendar.monthcalendar(today.year, today.month)
    calendar_days = []

    for week in cal:
        for d in week:
            if d == 0:
                calendar_days.append({"date": "", "tasks": []})
            else:
                day_tasks = tasks.filter(date__day=d)
                calendar_days.append({"date": d, "tasks": day_tasks})

    return render(request, "builder/scheduler_overview.html", {
        "tasks": tasks,
        "leads": leads,
        "calendar_days": calendar_days,
        "today": today
    })
@require_POST
def reorder_task(request):
    """Reorder tasks"""
    try:
        data = json.loads(request.body)
        task_id = data.get("task_id")
        position = data.get("position")

        if not task_id:
            return JsonResponse({"status": "error", "message": "Task ID required"})
        task = get_object_or_404(Task, id=int(task_id), user=request.user)
        task.order = position
        task.save()
        return JsonResponse({"status": "ok"})
    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Task not found"})
    except Exception as e:
        logger.error(f"Reorder task error: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"})
       

@login_required
@require_GET
def check_reminders(request):
    """Check pending task reminders"""
    today = date.today()
    count = Task.objects.filter(
        date=today,
        status='PENDING',
        user=request.user
    ).count()
    return JsonResponse({"count": count})


@login_required
def notifications_page(request):
    """User notifications page"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    
    # Mark as read when viewed
    notifications.filter(is_read=False).update(is_read=True)
    
    return render(request, "builder/notifications.html", {
        "notifications": notifications
    })


@login_required
@require_POST
def mark_notification_read(request, id):
    """Mark single notification as read"""
    notification = get_object_or_404(Notification, id=id, recipient=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({"status": "ok"})


# =============================================================================
# AGENT PERFORMANCE
# =============================================================================

@builder_required
def agent_performance(request):
    """Agent performance analytics"""
    agents = Agent.objects.filter(
        builders=request.user,
        is_active=True
    ).select_related('user')

    selected_agent = request.GET.get("agent")
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    data = []
    chart_labels = []
    chart_data = []
    total_revenue = Decimal('0')
    total_deals = 0

    for agent in agents:
        leads = Lead.objects.filter(assigned_to=agent)
        deals = Deal.objects.filter(agent=agent, status="CLOSED")

        if start_date and end_date:
            leads = leads.filter(created_at__date__range=[start_date, end_date])
            deals = deals.filter(created_at__date__range=[start_date, end_date])

        if selected_agent and str(agent.id) != selected_agent:
            continue

        total_leads = leads.count()
        closed_deals = deals.count()
        revenue = deals.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        total_revenue += revenue
        total_deals += closed_deals

        conversion = (closed_deals / total_leads * 100) if total_leads else 0

        data.append({
            "id": agent.id,
            "name": agent.name,
            "total_leads": total_leads,
            "closed_deals": closed_deals,
            "revenue": revenue,
            "conversion": round(conversion, 1)
        })

        chart_labels.append(agent.name)
        chart_data.append(float(revenue))

    data = sorted(data, key=lambda x: x['revenue'], reverse=True)

    return render(request, "builder/agent_performance.html", {
        "agents": data,
        "all_agents": agents,
        "total_agents": agents.count(),
        "total_deals": total_deals,
        "total_revenue": total_revenue,
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data)
    })


@builder_required
def agent_detail(request, id):
    """Individual agent detail"""
    agent = get_object_or_404(
        Agent.objects.select_related('user'),
        id=id,
        builders=request.user
    )

    leads = Lead.objects.filter(assigned_to=agent).select_related('builder')
    deals = Deal.objects.filter(agent=agent).select_related('property')
    revenue = deals.filter(status="CLOSED").aggregate(total=Sum("amount"))["total"] or Decimal('0')

    return render(request, "builder/agent_detail.html", {
        "agent": agent,
        "total_leads": leads.count(),
        "total_deals": deals.count(),
        "revenue": revenue
    })


@builder_required
def export_agents(request):
    """Export agents performance to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="agents_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Total Leads', 'Closed Deals', 'Revenue', 'Conversion %'])

    for agent in Agent.objects.filter(builders=request.user).select_related('user'):
        leads = Lead.objects.filter(assigned_to=agent)
        deals = Deal.objects.filter(agent=agent, status="CLOSED")
        total_leads = leads.count()
        closed_deals = deals.count()
        revenue = deals.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        conversion = round((closed_deals / total_leads * 100), 2) if total_leads else 0

        writer.writerow([
            agent.name,
            agent.email,
            agent.phone or '-',
            total_leads,
            closed_deals,
            float(revenue),
            conversion
        ])

    return response


# =============================================================================
# AI INSIGHTS
# =============================================================================

@builder_required
def ai_insights(request):
    """AI-powered insights dashboard"""
    leads = Lead.objects.filter(builder=request.user).select_related('assigned_to')

    scored_leads = []
    high_intent = 0
    closing = 0
    risk = 0

    for lead in leads:
        # Simple scoring algorithm (replace with ML model in production)
        score = 0
        factors = []
        
        # Base score
        score += 50
        
        # Status-based scoring
        status_scores = {
            'HOT': 30, 'NEGOTIATION': 25, 'VISIT': 20,
            'CONTACTED': 10, 'WARM': 15, 'COLD': -10,
            'NEW': 5, 'CLOSED': 0, 'FAILED': -20
        }
        status_score = status_scores.get(lead.status, 0)
        score += status_score
        if status_score > 0:
            factors.append(f"Status: +{status_score}")

        # Follow-up frequency
        followup_count = lead.followups.count()
        if followup_count >= 3:
            score += 10
            factors.append("Multiple followups: +10")

        # Response time
        if lead.last_contacted:
            days_since = (now() - lead.last_contacted).days
            if days_since <= 2:
                score += 10
                factors.append("Recent contact: +10")
            elif days_since > 7:
                score -= 10
                factors.append("Stale lead: -10")

        # Cap score
        score = max(0, min(100, score))

        if score > 80:
            intent = "High"
            high_intent += 1
        elif score > 60:
            intent = "Medium"
            closing += 1
        else:
            intent = "Low"
            risk += 1

        scored_leads.append({
            "lead": lead,
            "score": score,
            "intent": intent,
            "factors": factors
        })

    # Sort by score
    scored_leads.sort(key=lambda x: x['score'], reverse=True)

    total_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED"
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    try:
        forecast = int(float(total_revenue) * 1.3)
    except (TypeError, ValueError):
        forecast = 0

    insights = [
        {"title": "Market Shift", "desc": "Luxury demand increased by 15% this quarter"},
        {"title": "Best Time", "desc": "Call leads between 2PM-4PM for highest conversion"},
        {"title": "Hot Location", "desc": "Properties in downtown showing 20% more inquiries"},
    ]

    recommendations = []
    for item in scored_leads[:5]:
        if item["score"] > 85:
            recommendations.append(f"Priority follow-up with {item['lead'].name} (Score: {item['score']})")
        elif item["score"] < 40:
            recommendations.append(f"Consider re-engagement strategy for {item['lead'].name}")

    return render(request, "builder/ai_insights.html", {
        "scored_leads": scored_leads[:10],
        "total_revenue": total_revenue,
        "forecast": forecast,
        "insights": insights,
        "recommendations": recommendations,
        "high_intent": high_intent,
        "closing": closing,
        "risk": risk
    })


# =============================================================================
# MARKETING AUTOMATION
# =============================================================================

@builder_required
def marketing_automation(request):
    """Marketing campaigns dashboard"""
    campaigns = Campaign.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    total_campaigns = campaigns.count()
    total_reach = sum(c.reach or 0 for c in campaigns)
    total_conversions = sum(c.conversion or 0 for c in campaigns)

    avg_ctr = 0
    if total_reach > 0:
        total_clicked = sum(c.clicked or 0 for c in campaigns)
        avg_ctr = round((total_clicked / total_reach) * 100, 2)

    chart_labels = [c.name for c in campaigns[:10]]
    chart_data = [c.reach for c in campaigns[:10]]

    return render(request, 'builder/marketing_automation.html', {
        'campaigns': campaigns,
        'total_campaigns': total_campaigns,
        'total_reach': total_reach,
        'total_conversions': total_conversions,
        'avg_ctr': avg_ctr,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })


@builder_required
def create_campaign(request):
    """Create new marketing campaign"""
    if request.method == "POST":
        try:
            campaign = Campaign.objects.create(
                name=sanitize_input(request.POST.get('name')),
                type=sanitize_input(request.POST.get('type', 'email')),
                status='scheduled',
                reach=int(request.POST.get('reach', 0) or 0),
                clicked=int(request.POST.get('clicked', 0) or 0),
                conversion=int(request.POST.get('conversion', 0) or 0),
                image=request.FILES.get('image'),
                created_by=request.user
            )
            
            messages.success(request, f"Campaign '{campaign.name}' created successfully!")
            logger.info(f"Campaign created: {campaign.name}")
            return redirect('marketing_automation')
            
        except Exception as e:
            logger.error(f"Campaign creation error: {str(e)}")
            messages.error(request, "Failed to create campaign")

    return render(request, 'builder/create_campaign.html')


@builder_required
def run_campaign(request, id):
    """Execute campaign (simulated)"""
    campaign = get_object_or_404(Campaign, id=id, created_by=request.user)
    
    # Simulate campaign execution
    campaign.sent = (campaign.sent or 0) + 100
    campaign.opened = (campaign.opened or 0) + 60
    campaign.clicked = (campaign.clicked or 0) + 20
    campaign.conversion = (campaign.conversion or 0) + 5
    campaign.status = 'active'
    campaign.save()
    
    messages.success(request, f"Campaign '{campaign.name}' executed successfully!")
    return redirect("marketing_automation")


@builder_required
def delete_campaign(request, id):
    """Delete campaign"""
    campaign = get_object_or_404(Campaign, id=id, created_by=request.user)
    campaign.delete()
    messages.success(request, "Campaign deleted successfully!")
    return redirect('marketing_automation')


# =============================================================================
# USER MANAGEMENT
# =============================================================================

@builder_required
def manage_users(request):
    """Manage builder's agents"""
    query = sanitize_input(request.GET.get('q', ''))
    role_filter = sanitize_input(request.GET.get('role', ''))

    agents = Agent.objects.filter(
        builders=request.user
    ).select_related('user').order_by('-id')

    if query:
        agents = agents.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )

    if role_filter:
        agents = agents.filter(role=role_filter)

    return render(request, 'builder/manage_users.html', {'agents': agents})


@builder_required
def delete_agent(request, id):
    """Delete agent completely"""
    agent = get_object_or_404(Agent, id=id, builders=request.user)
    agent_name = agent.name
    
    # Remove builder association first
    agent.builders.remove(request.user)
    
    # If no builders left, delete agent and user
    if not agent.builders.exists():
        user = agent.user
        agent.delete()
        user.delete()
        messages.success(request, f"Agent '{agent_name}' and associated user deleted completely!")
    else:
        messages.success(request, f"Agent '{agent_name}' removed from your team.")
    
    logger.info(f"Agent deleted: {agent_name} by {request.user.username}")
    return redirect('manage_users')


@builder_required
def toggle_agent(request, id):
    """Toggle agent active status"""
    agent = get_object_or_404(Agent, id=id, builders=request.user)
    agent.is_active = not agent.is_active
    agent.save()
    
    status = "activated" if agent.is_active else "deactivated"
    messages.success(request, f"Agent '{agent.name}' {status}!")
    return redirect('manage_users')


# =============================================================================
# AGENT VIEWS
# =============================================================================

@agent_required
def agent_dashboard(request):
    """Agent dashboard with all metrics"""
    agent = get_object_or_404(
        Agent.objects.select_related('user'),
        user=request.user
    )

    agent_builders = list(agent.builders.all())

    # Leads
    leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    ).select_related('builder').order_by("-created_at")

    total_leads = leads.count()
    hot = leads.filter(status="HOT").count()
    warm = leads.filter(status="WARM").count()
    cold = leads.filter(status="COLD").count()

    # Visits
    visits = SiteVisit.objects.filter(
        agent=agent,
        builder__in=agent_builders
    ).select_related('property', 'lead').order_by("-date", "-time")
    
    today_visits = visits.filter(date=date.today()).count()

    # Tasks
    tasks = Task.objects.filter(
        lead__assigned_to=agent,
        lead__builder__in=agent_builders,
        status="PENDING"
    ).select_related('lead').order_by("date", "time")

    # Follow-ups
    today_followups = FollowUp.objects.filter(
        agent=agent,
        lead__builder__in=agent_builders,
        date=date.today(),
        status="PENDING"
    ).select_related('lead').order_by("time")

    upcoming_followups = FollowUp.objects.filter(
        agent=agent,
        lead__builder__in=agent_builders,
        date=date.today(),
        time__lte=(now() + timedelta(hours=1)).time(),
        status="PENDING"
    ).select_related('lead')

    missed_followups = FollowUp.objects.filter(
        agent=agent,
        lead__builder__in=agent_builders,
        status="PENDING"
    ).exclude(
        date__gt=date.today()
    ).exclude(
        date=date.today(),
        time__gt=now().time()
    ).select_related('lead')

    today_auto_followups = FollowUp.objects.filter(
        agent=agent,
        lead__builder__in=agent_builders,
        date=date.today(),
        status="PENDING",
        is_auto_created=True
    ).select_related('lead')

    # Upcoming visits
    upcoming_visits = SiteVisit.objects.filter(
        agent=agent,
        builder__in=agent_builders,
        date__gte=date.today(),
        status="SCHEDULED"
    ).select_related('property', 'lead').order_by("date", "time")[:5]

    # Deals
    deals = Deal.objects.filter(
        agent=agent,
        builder__in=agent_builders
    ).select_related('property')
    
    total_deals = deals.count()

    # Performance chart
    monthly_deals = deals.filter(
        status="CLOSED",
        created_at__year=date.today().year
    ).annotate(
        month=ExtractMonth("created_at")
    ).values("month").annotate(count=Count("id")).order_by("month")

    chart_labels = [calendar.month_abbr[m["month"]] for m in monthly_deals]
    chart_data = [m["count"] for m in monthly_deals]

    return render(request, "agent/agent_dashboard.html", {
        "leads": leads[:5],
        "total_leads": total_leads,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "visits": visits[:5],
        "today_visits": today_visits,
        "tasks": tasks[:5],
        "today_followups": today_followups,
        "upcoming_followups": upcoming_followups,
        "missed_followups": missed_followups,
        "today_auto_followups": today_auto_followups,
        "upcoming_visits": upcoming_visits,
        "total_deals": total_deals,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    })


@agent_required
def agent_leads(request):
    """Agent leads management"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    ).select_related('builder').prefetch_related('properties').order_by("-created_at")

    q = sanitize_input(request.GET.get("q", ""))
    if q:
        leads = leads.filter(
            Q(name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )

    status = sanitize_input(request.GET.get("status", ""))
    if status:
        leads = leads.filter(status=status)

    sort = sanitize_input(request.GET.get("sort", ""))
    if sort == "old":
        leads = leads.order_by("created_at")
    else:
        leads = leads.order_by("-created_at")

    active_leads = leads.exclude(
        deals__status__in=["CLOSED", "FAILED"]
    ).distinct()
    
    success_leads = leads.filter(
        deals__status__in=["CLOSED", "FAILED"]
    ).distinct()

    return render(request, "agent/agent_leads.html", {
        "leads": active_leads,
        "success_leads": success_leads,
    })


@agent_required
def delete_lead(request, lead_id):
    """Agent delete lead"""
    agent = get_object_or_404(Agent, user=request.user)
    lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)
    lead_name = lead.name
    lead.delete()
    
    messages.success(request, f"Lead '{lead_name}' deleted successfully!")
    logger.info(f"Lead deleted: {lead_name} by agent {request.user.username}")
    return redirect("agent_leads")


@agent_required
def agent_properties(request):
    """Agent's properties with lead counts"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    properties = Property.objects.filter(
        interested_leads__assigned_to=agent,
        builder__in=agent_builders
    ).annotate(
        demand=Count("interested_leads", distinct=True)
    ).distinct().select_related('builder').order_by("-demand")

    page_obj = get_paginated_queryset(properties, request)

    return render(request, "agent/agent_properties.html", {
        "properties": page_obj,
        "page_obj": page_obj
    })


@agent_required
def agent_profile(request):
    """Agent profile page"""
    agent = get_object_or_404(Agent, user=request.user)
    
    # Stats
    total_leads = Lead.objects.filter(assigned_to=agent).count()
    hot_leads = Lead.objects.filter(assigned_to=agent, status='HOT').count()
    total_visits = SiteVisit.objects.filter(agent=agent).count()
    
    # Conversion rate
    total_deals = Deal.objects.filter(agent=agent).count()
    closed_deals = Deal.objects.filter(agent=agent, status='CLOSED').count()
    conversion_rate = round((closed_deals / total_deals * 100), 1) if total_deals else 0
    
    return render(request, "agent/profile.html", {
        "agent": agent,
        "total_leads": total_leads,
        "hot_leads": hot_leads,
        "total_visits": total_visits,
        "conversion_rate": conversion_rate,
    })
# ==================== SCHEDULER ====================

@agent_required
def scheduler(request):
    """Agent visit scheduler with edit/reschedule support"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    ).exclude(
        status__in=["CLOSED", "FAILED"]
    ).exclude(
        deals__status__in=["CLOSED", "FAILED"]
    ).select_related('builder').distinct()

    visits = SiteVisit.objects.filter(
        agent=agent,
        builder__in=agent_builders
    ).select_related('property', 'lead').order_by("-date", "-time")

    # EDIT MODE CHECK
    edit_visit = None
    edit_id = request.GET.get('edit')
    if edit_id and edit_id.isdigit():
        edit_visit = get_object_or_404(
            SiteVisit, 
            id=int(edit_id), 
            agent=agent,
            builder__in=agent_builders
        )

    if request.method == "POST":
        action = request.POST.get("action", "create")
        
        # UPDATE EXISTING VISIT
        if action == "update":
            visit_id = request.POST.get("visit_id")
            visit = get_object_or_404(
                SiteVisit, 
                id=visit_id, 
                agent=agent,
                builder__in=agent_builders
            )
            
            visit_date = request.POST.get("date")
            visit_time = request.POST.get("time")
            
            if visit_date and visit_time:
                visit.date = visit_date
                visit.time = visit_time
                visit.status = "RESCHEDULED"
                visit.save()
                messages.success(
                    request, 
                    f"Visit rescheduled to {visit_date} at {visit.time}!"
                )
                logger.info(f"Visit {visit.id} rescheduled by {agent.name}")
            else:
                messages.error(request, "Date and time required!")
            
            # FIX: Correct URL name
            return redirect("agent_scheduler")
        
        # CREATE NEW VISIT
        else:
            lead_id = request.POST.get("lead")
            property_id = request.POST.get("property")
            visit_date = request.POST.get("date")
            visit_time = request.POST.get("time")

            lead = get_object_or_404(
                Lead,
                id=lead_id,
                assigned_to=agent,
                builder__in=agent_builders
            )

            if lead.status in ["CLOSED", "FAILED"]:
                messages.error(request, "Cannot schedule visit for closed/failed lead!")
                return redirect("agent_scheduler")  # FIX

            if lead.deals.filter(status__in=["CLOSED", "FAILED"]).exists():
                messages.error(request, "Lead already has closed deal!")
                return redirect("agent_scheduler")  # FIX

            try:
                SiteVisit.objects.create(
                    property_id=property_id,
                    lead=lead,
                    agent=agent,
                    date=visit_date,
                    time=visit_time,
                    builder=lead.builder
                )
                messages.success(request, "Visit scheduled successfully!")
                logger.info(f"Visit scheduled for lead {lead.name}")
                
            except Exception as e:
                logger.error(f"Schedule error: {str(e)}")
                messages.error(request, "Failed to schedule visit")

            # FIX: Correct URL name
            return redirect("agent_scheduler")

    return render(request, "agent/scheduler.html", {
        "leads": leads,
        "visits": visits,
        "edit_visit": edit_visit,
    })

@agent_required
def toggle_scheduler(request):
    """Agent toggles their own scheduler on/off"""
    agent = get_object_or_404(Agent, user=request.user)
    
    # Toggle the flag
    agent.scheduler_enabled = not agent.scheduler_enabled
    agent.save(update_fields=['scheduler_enabled'])
    
    status = "enabled" if agent.scheduler_enabled else "disabled"
    messages.success(request, f"Your scheduler has been {status}!")
    
    return redirect("agent_profile")

@agent_required
def property_leads(request, property_id):
    """Leads for specific property"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    property_obj = get_object_or_404(
        Property,
        id=property_id,
        builder__in=agent_builders
    )

    leads = Lead.objects.filter(
        properties__id=property_id,
        builder__in=agent_builders
    ).exclude(
        status__in=["CLOSED", "FAILED"]
    ).exclude(
        deals__status__in=["CLOSED", "FAILED"]
    ).select_related('builder').distinct().order_by("-created_at")

    return render(request, "agent/property_leads.html", {
        "property": property_obj,
        "leads": leads,
    })

@agent_required
def site_visits(request):
    """Site visits page - redirect to scheduler (same template)"""
    # FIX: Same template use karo, ya redirect kar do
    return redirect("agent_scheduler")

@login_required
def settings_view(request):
    """User settings"""
    user = request.user

    if request.method == "POST":
        user.username = sanitize_input(request.POST.get("username", user.username))
        user.email = sanitize_input(request.POST.get("email", user.email))
        user.phone = sanitize_input(request.POST.get("phone", user.phone or ""))

        if request.FILES.get("profile_image"):
            valid, msg = validate_file_upload(
                request.FILES.get("profile_image"),
                ['.jpg', '.jpeg', '.png', '.gif', '.avif'],
                5
            )
            if valid:
                user.profile_image = request.FILES.get("profile_image")
            else:
                messages.error(request, f"Profile image: {msg}")

        user.save()

        # Password change
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        if password:
            if password != confirm:
                messages.error(request, "Passwords do not match")
            elif len(password) < 8:
                messages.error(request, "Password must be at least 8 characters")
            elif not (re.search(r'[A-Z]', password) and re.search(r'[a-z]', password) and re.search(r'[0-9]', password)):
                messages.error(request, "Password must contain uppercase, lowercase, and number")
            else:
                user.set_password(password)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password updated successfully")

        messages.success(request, "Profile updated successfully")
        return redirect("settings")

    return render(request, "settings.html", {"user": user})


def privacy(request):
    """Privacy policy page"""
    property = Property.objects.select_related('builder').first()
    return render(request, "public/privacy.html", {"property": property})


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def auto_assign_agent(builder):
    """Round-robin agent assignment"""
    agents = list(Agent.objects.filter(
        builders=builder,
        is_active=True
    ).order_by('id'))

    if not agents:
        return None

    last_lead = Lead.objects.filter(
        builder=builder
    ).select_related('assigned_to').order_by('-id').first()

    if last_lead and last_lead.assigned_to in agents:
        last_index = agents.index(last_lead.assigned_to)
        return agents[(last_index + 1) % len(agents)]
    
    return agents[0]


@receiver(post_save, sender=User)
def create_agent_for_user(sender, instance, created, **kwargs):
    """Auto-create agent profile for agent users"""
    if created and instance.role == "agent":
        Agent.objects.get_or_create(
            user=instance,
            defaults={
                "name": instance.username,
                "email": instance.email,
                "phone": getattr(instance, "phone", ""),
            }
        )


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

@builder_required
def export_leads_csv(request):
    """Export leads to CSV with all details"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_report.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Lead Name', 'Email', 'Phone', 'Source', 'Status',
        'Priority', 'Assigned Agent', 'Properties', 'Created Date'
    ])

    leads = Lead.objects.filter(
        builder=request.user
    ).select_related('assigned_to').prefetch_related('properties')

    search_query = sanitize_input(request.GET.get('q', ''))
    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    for lead in leads:
        agent_name = lead.assigned_to.name if lead.assigned_to else "Not Assigned"
        properties_list = ", ".join([p.title for p in lead.properties.all()]) if lead.properties.exists() else "-"

        writer.writerow([
            lead.name,
            lead.email,
            lead.phone,
            lead.source,
            lead.status,
            lead.priority,
            agent_name,
            properties_list,
            lead.created_at.strftime('%Y-%m-%d %H:%M')
        ])

    return response


# =============================================================================
# WHATSAPP BOT
# =============================================================================

def whatsapp_bot(request):
    """Twilio WhatsApp webhook"""
    if request.method == "POST":
        msg = sanitize_input(request.POST.get("Body", "")).lower()
        resp = MessagingResponse()
        
        if "hi" in msg or "hello" in msg:
            reply = "Welcome to Smart Realty 🏠\n\n1️⃣ Residential Properties\n2️⃣ Commercial Properties\n3️⃣ Talk to Agent\n\nReply with number:"
        elif msg in ["1", "residential"]:
            reply = "Great! Please tell us your preferred location:"
        elif msg in ["2", "commercial"]:
            reply = "Commercial properties available! Budget range?"
        elif msg in ["3", "agent"]:
            reply = "Connecting you to our agent... Please share your name and phone number."
        else:
            reply = "Welcome to Smart Realty 🏠\nType 'Hi' to get started!"
        
        resp.message(reply)
        return HttpResponse(str(resp), content_type="application/xml")
    
    return HttpResponse("Method not allowed", status=405)


# =============================================================================
# DEAL MANAGEMENT
# =============================================================================

@agent_required
def add_deal(request):
    """Add new deal"""
    if request.method == "POST":
        property_id = request.POST.get('property_id')
        lead_id = request.POST.get('lead_id')
        client_name = sanitize_input(request.POST.get('client_name')) or "Unknown"
        amount = request.POST.get('amount')
        amount_unit = sanitize_input(request.POST.get('amount_unit')) or 'L'
        status = sanitize_input(request.POST.get('status', 'NEW'))

        property_obj = get_object_or_404(Property, id=property_id)
        agent = get_object_or_404(Agent, user=request.user)

        if property_obj.builder not in agent.builders.all():
            messages.error(request, "Access denied!")
            return redirect('agent_leads')

        lead = None
        if lead_id:
            lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)

        # FIX: use the explicit L/Cr dropdown instead of guessing the unit
        # from free text (convert_price's "l" in price check was ambiguous).
        # amount is always stored as the full rupee value so Sum('amount')
        # on the builder dashboard stays accurate regardless of unit chosen.
        try:
            amount_value = Decimal(amount) if amount else Decimal("0")
            multiplier = Decimal("10000000") if amount_unit == "Cr" else Decimal("100000")
            amount = amount_value * multiplier
        except Exception:
            amount = Decimal("0")

        try:
            Deal.objects.create(
                lead=lead,
                property=property_obj,
                client_name=client_name,
                amount=amount,
                amount_unit=amount_unit,
                status=status,
                agent=agent,
                builder=property_obj.builder
            )
            # FIX: keep Lead.status in sync with Deal.status. Without this,
            # a deal marked CLOSED/FAILED here never reflects on the Lead's
            # own status field, so the Pipeline page (which buckets leads
            # by Lead.status) keeps showing the lead under "OTHER" forever.
            if lead and status in ("CLOSED", "FAILED", "NEGOTIATION"):
                lead.status = status
                lead.save()
            messages.success(request, "Deal created successfully!")
            
        except Exception as e:
            logger.error(f"Deal creation error: {str(e)}")
            messages.error(request, "Failed to create deal")

        return redirect('agent_leads')

    return redirect('agent_leads')


@agent_required
def update_deal(request, deal_id):
    """Update deal status"""
    if request.method == "POST":
        deal = get_object_or_404(Deal, id=deal_id, agent__user=request.user)
        status = sanitize_input(request.POST.get("status"))
        
        old_status = deal.status
        deal.status = status
        deal.save()

        # FIX: same sync as add_deal above — otherwise updating an existing
        # deal to CLOSED/FAILED still leaves the Lead stuck in its old
        # status on the Pipeline board.
        if deal.lead and status in ("CLOSED", "FAILED", "NEGOTIATION"):
            deal.lead.status = status
            deal.lead.save()
        
        LeadActivity.objects.create(
            lead=deal.lead,
            message=f"Deal status changed from {old_status} to {status}",
            created_by=request.user
        )
        
        messages.success(request, "Deal updated successfully!")
    
    return redirect("agent_leads")


# =============================================================================
# FOLLOW-UP MANAGEMENT
# =============================================================================

@agent_required
def add_followup(request, lead_id):
    """Add follow-up for lead"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    lead = get_object_or_404(
        Lead,
        id=lead_id,
        assigned_to=agent,
        builder__in=agent_builders
    )

    if request.method == "POST":
        try:
            followup = FollowUp.objects.create(
                lead=lead,
                agent=agent,
                date=request.POST.get("date"),
                time=request.POST.get("time"),
                note=sanitize_input(request.POST.get("note", ""))
            )
            
            messages.success(request, "Follow-up scheduled successfully!")
            logger.info(f"Follow-up created for lead {lead.name}")
            
        except Exception as e:
            logger.error(f"Follow-up creation error: {str(e)}")
            messages.error(request, "Failed to schedule follow-up")

        return redirect("agent_dashboard")

    return render(request, "agent/add_followup.html", {"lead": lead})


def update_missed_followups():
    """Background task: Mark overdue followups as missed"""
    followups = FollowUp.objects.filter(status="PENDING")
    current_time = now()
    
    for f in followups:
        try:
            followup_datetime = datetime.combine(f.date, f.time)
            if followup_datetime < current_time:
                f.status = "MISSED"
                f.save()
                
                # Create escalation if needed
                missed_count = FollowUp.objects.filter(
                    lead=f.lead,
                    status="MISSED"
                ).count()
                
                if missed_count >= 2:
                    f.lead.escalation_level = min(2, f.lead.escalation_level + 1)
                    f.lead.save()
                    
        except Exception as e:
            logger.error(f"Update missed followup error: {str(e)}")


@login_required
def mark_followup_done(request, id):
    """Mark followup as completed"""
    followup = get_object_or_404(FollowUp, id=id)
    
    # Security check
    if request.user.role == "agent":
        agent = get_object_or_404(Agent, user=request.user)
        if followup.agent != agent:
            messages.error(request, "Access denied!")
            return redirect('agent_dashboard')
    elif request.user.role == "builder":
        if followup.lead.builder != request.user:
            messages.error(request, "Access denied!")
            return redirect('builder_dashboard')

    followup.status = "DONE"
    followup.completed_at = now()
    followup.save()
    
    # Update lead
    followup.lead.last_contacted = now()
    followup.lead.followup_count += 1
    followup.lead.save()
    
    messages.success(request, "Follow-up marked as done!")
    return redirect(request.META.get('HTTP_REFERER', 'agent_dashboard'))


# =============================================================================
# WISHLIST
# =============================================================================

@login_required
def wishlist(request):
    """User wishlist"""
    wishlist_items = Wishlist.objects.filter(
        user=request.user
    ).select_related('property').order_by('-created_at')
    
    return render(request, 'public/wishlist.html', {
        'wishlist_properties': [item.property for item in wishlist_items]
    })


@login_required
def wishlist_remove(request, id):
    """Remove from wishlist"""
    Wishlist.objects.filter(user=request.user, property_id=id).delete()
    return JsonResponse({'success': True})


@login_required
def wishlist_compare(request):
    """Compare wishlist properties"""
    ids = request.GET.get('ids', '').split(',')
    ids = [int(i) for i in ids if i.isdigit()]

    properties = Property.objects.filter(id__in=ids).select_related('builder')

    data = []
    for p in properties:
        data.append({
            'id': p.id,
            'project_name': p.project_name or p.title,
            'price': p.price,
            'location': p.location,
            'configuration': p.configuration,
            'beds': p.beds,
            'baths': p.baths,
            'sqft': p.sqft,
            'possession': p.possession,
            'property_type': p.property_type
        })

    return JsonResponse({'properties': data})


def wishlist_count(request):
    """Get wishlist count for navbar"""
    if request.user.is_authenticated:
        count = Wishlist.objects.filter(user=request.user).count()
    else:
        count = 0
    return JsonResponse({'count': count})


@login_required
def wishlist_add(request, property_id):
    """Add to wishlist"""
    property_obj = get_object_or_404(Property, id=property_id)

    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        property=property_obj
    )

    # Builder ko notification bhejo jab naya wishlist add ho (duplicate par nahi)
    if created and property_obj.builder:
        Notification.objects.create(
            recipient=property_obj.builder,
            title="Property Wishlisted",
            message=f"{request.user.username} ne aapki property '{property_obj.title}' wishlist mein add ki hai.",
            type='system',
            action_url=reverse('property_wishlist_list'),
            icon='favorite'
        )

    count = Wishlist.objects.filter(user=request.user).count()
    # Builder ko notification bhejo jab naya wishlist add ho (duplicate par nahi)
    if created and property_obj.builder:
        Notification.objects.create(
            recipient=property_obj.builder,
            title="Property Wishlisted",
            message=f"{request.user.username} ne aapki property '{property_obj.title}' wishlist mein add ki hai.",
            type='system',
            action_url=reverse('property_wishlist_list'),
            icon='favorite'
        )

    count = Wishlist.objects.filter(user=request.user).count()

    # Pehli baar wishlist mein add hua to builder ko notify karo
    if created and property_obj.builder:
        Notification.objects.create(
            recipient=property_obj.builder,
            title="❤️ Property Wishlist mein Add Hui",
            message=f"{request.user.get_full_name() or request.user.username} ne aapki property '{property_obj.project_name or property_obj.title}' apni wishlist mein add ki hai.",
            type="lead"
        )
        logger.info(f"Wishlist notification sent to builder {property_obj.builder.username} for property {property_obj.title}")

    count = Wishlist.objects.filter(user=request.user).count()

    return JsonResponse({
        'success': True,
        'wishlist_count': count,
        'created': created,
        'wishlist_item':wishlist_item,
        'message': 'Added to wishlist!' if created else 'Already in wishlist!'
    })


@login_required
def wishlist_remove_by_id(request, property_id):
    """Remove from wishlist by property ID"""
    Wishlist.objects.filter(
        user=request.user,
        property_id=property_id
    ).delete()

    count = Wishlist.objects.filter(user=request.user).count()

    return JsonResponse({
        'success': True,
        'wishlist_count': count,
        'message': 'Removed from wishlist!'
    })


# =============================================================================
# CALCULATORS
# =============================================================================

def emi_calculator(request):
    """EMI calculator page"""
    emi_result = None
    if request.method == "POST":
        try:
            principal = float(request.POST.get('principal', 0))
            rate = float(request.POST.get('rate', 0))
            years = int(request.POST.get('years', 0))

            if principal > 0 and rate > 0 and years > 0:
                monthly_rate = rate / (12 * 100)
                months = years * 12
                emi = (principal * monthly_rate * (1 + monthly_rate)**months) / ((1 + monthly_rate)**months - 1)
                emi_result = round(emi, 2)
        except (ValueError, ZeroDivisionError):
            emi_result = None

    return render(request, 'public/emi_calculator.html', {
        'emi_result': emi_result
    })


def roi_calculator(request):
    """ROI calculator page"""
    roi_result = None
    if request.method == "POST":
        try:
            investment = float(request.POST.get('investment', 0))
            returns = float(request.POST.get('returns', 0))
            years = int(request.POST.get('years', 1))

            if investment > 0:
                roi = ((returns - investment) / investment) * 100
                annualized = ((returns / investment) ** (1/years) - 1) * 100 if years > 0 else roi
                roi_result = {
                    'roi': round(roi, 2),
                    'annualized': round(annualized, 2),
                    'profit': round(returns - investment, 2)
                }
        except (ValueError, ZeroDivisionError):
            roi_result = None

    return render(request, 'public/roi_calculator.html', {
        'roi_result': roi_result
    })


# =============================================================================
# EXPORT DASHBOARD CSV
# =============================================================================

@builder_required
def export_dashboard_csv(request):
    """Export comprehensive dashboard report"""
    start_date_str = sanitize_input(request.GET.get('start_date', ''))
    end_date_str = sanitize_input(request.GET.get('end_date', ''))
    today = date.today()

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
    else:
        start_date = today
        end_date = today

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="dashboard_report_{start_date}_to_{end_date}.csv"'
    writer = csv.writer(response)

    # Summary
    writer.writerow(['SMART REALTY - DASHBOARD REPORT'])
    writer.writerow(['Date Range', f'{start_date} to {end_date}'])
    writer.writerow(['Generated By', request.user.username])
    writer.writerow(['Generated At', now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])

    total_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    ).count()

    active_deals = Deal.objects.filter(
        builder=request.user,
        status__in=["NEW", "NEGOTIATION", "BOOKED"],
        created_at__date__range=[start_date, end_date]
    ).count()

    total_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED",
        created_at__date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    closed_deals = Deal.objects.filter(
        builder=request.user,
        status="CLOSED",
        created_at__date__range=[start_date, end_date]
    ).count()

    conversion_rate = round((closed_deals / total_leads * 100), 2) if total_leads else 0

    writer.writerow(['SUMMARY STATS'])
    writer.writerow(['Total Leads', total_leads])
    writer.writerow(['Active Deals', active_deals])
    writer.writerow(['Closed Deals', closed_deals])
    writer.writerow(['Total Revenue', f'Rs. {total_revenue}'])
    writer.writerow(['Conversion Rate', f'{conversion_rate}%'])
    writer.writerow([])

    # Leads Detail
    writer.writerow(['LEADS DETAILS'])
    writer.writerow(['Name', 'Email', 'Phone', 'Source', 'Status', 'Priority', 'Assigned Agent', 'Created Date'])

    leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    ).select_related('assigned_to')

    for lead in leads:
        writer.writerow([
            lead.name,
            lead.email,
            lead.phone,
            lead.source,
            lead.status,
            lead.priority,
            lead.assigned_to.name if lead.assigned_to else "Unassigned",
            lead.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    writer.writerow([])

    # Deals Detail
    writer.writerow(['DEALS DETAILS'])
    writer.writerow(['Client Name', 'Property', 'Amount', 'Status', 'Agent', 'Created Date'])

    deals = Deal.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    ).select_related('property', 'agent')

    for deal in deals:
        writer.writerow([
            deal.client_name,
            deal.property.title if deal.property else "N/A",
            f'Rs. {deal.amount}',
            deal.status,
            deal.agent.name if deal.agent else "N/A",
            deal.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    writer.writerow([])

    # Follow-ups
    writer.writerow(['FOLLOW-UPS'])
    writer.writerow(['Lead Name', 'Agent', 'Date', 'Time', 'Status', 'Note'])

    followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date__range=[start_date, end_date]
    ).select_related('lead', 'agent')

    for f in followups:
        writer.writerow([
            f.lead.name if f.lead else "N/A",
            f.agent.name if f.agent else "Unassigned",
            f.date,
            f.time,
            f.status,
            f.note or ""
        ])
    writer.writerow([])

    # Tasks
    writer.writerow(['TASKS'])
    writer.writerow(['Title', 'Date', 'Time', 'Priority', 'Status'])

    tasks = Task.objects.filter(
        user=request.user,
        date__range=[start_date, end_date]
    )

    for task in tasks:
        writer.writerow([
            task.title,
            task.date,
            task.time,
            task.priority,
            task.status
        ])
    writer.writerow([])

    # Agent Performance
    writer.writerow(['AGENT PERFORMANCE'])
    writer.writerow(['Agent Name', 'Total Leads', 'Closed Deals', 'Revenue', 'Conversion %'])

    agents = Agent.objects.filter(builders=request.user)
    for agent in agents:
        agent_leads = Lead.objects.filter(
            assigned_to=agent,
            builder=request.user,
            created_at__date__range=[start_date, end_date]
        ).count()

        agent_deals = Deal.objects.filter(
            agent=agent,
            builder=request.user,
            status="CLOSED",
            created_at__date__range=[start_date, end_date]
        )

        closed_count = agent_deals.count()
        revenue = agent_deals.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        conversion = round((closed_count / agent_leads * 100), 2) if agent_leads else 0

        writer.writerow([
            agent.name,
            agent_leads,
            closed_count,
            f'Rs. {revenue}',
            f'{conversion}%'
        ])

    return response


# =============================================================================
# PROPERTY LEADS (AGENT)
# =============================================================================

@agent_required
def property_leads_page(request, property_id):
    """Agent property leads with sidebar"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    property_obj = get_object_or_404(
        Property,
        id=property_id,
        builder__in=agent_builders
    )

    leads = Lead.objects.filter(
        properties__id=property_id,
        builder__in=agent_builders
    ).exclude(
        status__in=["CLOSED", "FAILED"]
    ).exclude(
        deals__status__in=["CLOSED", "FAILED"]
    ).select_related('builder').distinct().order_by("-created_at")

    return render(request, "agent/agent_propertieswithleads.html", {
        "property": property_obj,
        "leads": leads,
    })


# =============================================================================
# GOOGLE LOGIN REDIRECT
# =============================================================================


# =============================================================================
# GOOGLE LOGIN REDIRECT — WITH SUCCESS MESSAGE
# =============================================================================



@login_required
def google_login_redirect(request):
    """Redirect after Google OAuth login with success message."""

    messages.success(request, "🎉 Registration completed successfully! Welcome to SmartRealty.")

    # Use direct paths instead of URL names to avoid NoReverseMatch
    if request.user.role == 'builder':
        return redirect('/builder/dashboard/')
    elif request.user.role == 'agent':
        return redirect('/agent/dashboard/')
    else:
        # Default: regular user -> home page
        return redirect('/')
# =============================================================================
# USERNAME CHECK API
# =============================================================================

@require_GET
def check_username(request):
    """Check username availability"""
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({
            'available': False,
            'message': 'Username required'
        })

    exists = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({
        'available': not exists,
        'message': 'Username already taken' if exists else 'Username available'
    })


# =============================================================================
# ADD TO CART / SAVED PROPERTIES
# =============================================================================

@login_required
def add_to_cart(request, id):
    """Add property to saved/cart"""
    property = get_object_or_404(Property, id=id)
    
    SavedProperty.objects.get_or_create(
        user=request.user,
        property=property
    )
    
    messages.success(request, "Property saved!")
    return redirect('property_list')


# =============================================================================
# REGISTER USER (LEGACY)
# =============================================================================

@login_required
def register_user(request):
    """Legacy user registration"""
    if request.method == "POST":
        user = User.objects.create_user(
            username=sanitize_input(request.POST["username"]),
            password=request.POST["password"]
        )
        Agent.objects.create(
            user=user,
            name=sanitize_input(request.POST["username"]),
            email="",
            phone=""
        )
        return redirect("login")
    return render(request, "public/register.html")


# =============================================================================
# AGENT DELETE LEAD
# =============================================================================

@agent_required
def agent_delete_lead(request, lead_id):
    """Agent delete their lead"""
    agent = get_object_or_404(Agent, user=request.user)
    lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)
    lead.delete()
    messages.success(request, "Lead deleted successfully!")
    return redirect("agent_leads")


# =============================================================================
# LOGGING END
# =============================================================================

logger.info("views.py loaded successfully")
@login_required
def get_messages_ajax(request):
    """AJAX polling for chat — WebSocket ke jagah"""
    convo_id = request.GET.get("conversation_id")
    last_id = request.GET.get("last_id", 0)
    
    if not convo_id:
        return JsonResponse({"messages": []})
    
    convo = Conversation.objects.filter(id=int(convo_id)).first()
    if not convo:
        return JsonResponse({"messages": []})
    
    msgs = convo.messages.filter(id__gt=int(last_id)).select_related('sender').order_by('created_at')
    data = [{
        "id": m.id,
        "text": m.text, 
        "is_agent": m.is_agent, 
        "sender": m.sender.username,
        "created_at": m.created_at.strftime('%H:%M')
    } for m in msgs]
    
    return JsonResponse({
        "messages": data, 
        "last_id": msgs.last().id if msgs else last_id
    })
@agent_required
def property_leads(request, property_id):
    """Leads for specific property - FIXED with formatted prices"""
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = list(agent.builders.all())

    property_obj = get_object_or_404(
        Property,
        id=property_id,
        builder__in=agent_builders
    )

    # ===== FIX: Format property price =====
    if property_obj.price:
        try:
            price_val = float(property_obj.price)
            if price_val >= 10000000:
                property_obj.display_price = f"₹{price_val/10000000:.1f} Cr"
            elif price_val >= 100000:
                property_obj.display_price = f"₹{price_val/100000:.0f} Lakh"
            else:
                property_obj.display_price = f"₹{price_val:.0f}"
        except (ValueError, TypeError):
            property_obj.display_price = f"₹{property_obj.price}"
    else:
        property_obj.display_price = None

    leads = Lead.objects.filter(
        properties__id=property_id,
        builder__in=agent_builders
    ).select_related('builder').distinct().order_by("-created_at")

    # ===== FIX: Format deal amounts =====
    for lead in leads:
        for deal in lead.deals.all():
            if deal.amount:
                try:
                    amt = float(deal.amount)
                    if amt >= 10000000:
                        deal.display_amount = f"₹{amt/10000000:.1f} Cr"
                    elif amt >= 100000:
                        deal.display_amount = f"₹{amt/100000:.0f} Lakh"
                    else:
                        deal.display_amount = f"₹{amt:.0f}"
                except (ValueError, TypeError):
                    deal.display_amount = f"₹{deal.amount}"
            else:
                deal.display_amount = None

    return render(request, "agent/property_leads.html", {
        "property": property_obj,
        "leads": leads,
    })

@builder_required
def property_map(request):
    properties = Property.objects.filter(
        builder=request.user
    ).select_related('builder').prefetch_related('images').annotate(
        wishlist_count=Count('wishlisted_by', distinct=True)
    ).order_by('-created_at')
    
    return render(request, "builder/property_map.html", {
        'properties': properties,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
        'builder_name': request.user.get_full_name() or request.user.username,
    })
# views.py mein add karo (NO login_required - public hai!)

def property_map_public(request):
    """
    PUBLIC Property Map - Sab users dekh sakte hain bina login ke.
    Sab builders ki properties map pe dikhengi.
    """
    properties = Property.objects.filter(
        status='Available'
    ).select_related('builder').prefetch_related('images').annotate(
        wishlist_count=Count('wishlisted_by', distinct=True)
    ).order_by('-created_at')
    
    google_maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    
    return render(request, "public/public_property_map.html", {
        'properties': properties,
        'google_maps_api_key': google_maps_api_key,
    })
