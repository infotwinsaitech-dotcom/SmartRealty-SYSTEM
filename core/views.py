from django.shortcuts import render, get_object_or_404, redirect
from .models import Property, User, Profile, Lead, Deal, Task, Activity, Agent, Document, Conversation, Message, Notification, Campaign, SiteVisit
import urllib.parse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
import random
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.db.models import Sum
from datetime import date, timedelta
from django.db.models.functions import ExtractMonth
import calendar, json, csv
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash
from .models import Property, PropertyImage
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import random
import os
from decimal import Decimal
from collections import defaultdict
from core.models import FollowUp
from datetime import datetime
from django.utils.timezone import now

def home(request):
    properties = Property.objects.all()[:6]
    return render(request, "public/index.html", {"properties": properties})

def properties_view(request):
    properties = Property.objects.all().order_by('-created_at')
    return render(request, "public/properties.html", {"properties": properties})

from .models import Inquiry

def property_detail(request, id):
    property = get_object_or_404(Property, id=id)
    highlights_list = []
    if property.highlights:
        highlights_list = property.highlights.split(",") if property.highlights else []
    
    similar_properties = Property.objects.filter(location=property.location).exclude(id=property.id)[:3]

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        message = request.POST.get("message")

        # ✅ ROUND ROBIN LOGIC (builders ManyToMany support)
        agents = list(Agent.objects.filter(builders=property.builder, is_active=True).order_by("id"))
        last_lead = Lead.objects.filter(builder=property.builder).order_by('-id').first()

        if last_lead and last_lead.assigned_to in agents:
            last_index = agents.index(last_lead.assigned_to)
            agent = agents[(last_index + 1) % len(agents)]
        else:
            agent = agents[0] if agents else None

        lead = Lead.objects.create(
            name=name,
            email=email,
            phone=phone,
            status='HOT',
            source='Website',
            interest=property.title,
            builder=property.builder,
            assigned_to=agent,
            notes=message
        )
        lead.properties.add(property)

        Inquiry.objects.create(
            property=property,
            name=name,
            email=email,
            phone=phone,
            message=message
        )
        messages.success(request, "Inquiry sent successfully!")
        return redirect('property_detail', id=property.id)

    return render(request, "public/property_detail.html", {
        "property": property,
        "highlights_list": highlights_list,
        "similar_properties": similar_properties
    })

def property_list(request):
    from django.db.models import Q, Value, IntegerField, Case, When
    properties = Property.objects.all().order_by('-created_at')
    
    location = request.GET.get('location', '').strip()
    property_type = request.GET.get('type', '').strip()
    possession = request.GET.get('possession', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    beds = request.GET.get('beds', '').strip()
    query = request.GET.get('q', '').strip()

    if query:
        properties = properties.filter(
            Q(title__icontains=query) | Q(location__icontains=query) |
            Q(project_name__icontains=query) | Q(builder__username__icontains=query) |
            Q(builder__first_name__icontains=query) | Q(builder__last_name__icontains=query) |
            Q(description__icontains=query)
        )

    if location:
        properties = properties.filter(
            Q(location__icontains=location) | Q(title__icontains=location) | Q(project_name__icontains=location)
        )

    if property_type:
        types = [t.strip() for t in property_type.split(',') if t.strip()]
        if types:
            type_query = Q()
            for t in types:
                type_query |= Q(property_type__iexact=t) | Q(property_type__icontains=t)
            properties = properties.filter(type_query)

    if possession:
        properties = properties.filter(Q(possession__iexact=possession) | Q(possession__icontains=possession))

    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass

    if beds:
        try:
            properties = properties.filter(beds__gte=int(beds))
        except ValueError:
            pass

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

    if not properties.exists():
        all_properties = Property.objects.all().order_by('-created_at')
        if location:
            nearest = all_properties.filter(location__icontains=location[:3])
            properties = nearest if nearest.exists() else all_properties[:10]
        elif query:
            nearest = all_properties.filter(
                Q(title__icontains=query[:3]) | Q(location__icontains=query[:3]) | Q(project_name__icontains=query[:3])
            )
            properties = nearest if nearest.exists() else all_properties[:10]
        else:
            properties = all_properties[:10]

    return render(request, "public/property.html", {
        "properties": properties,
        "search_query": query,
        "location_filter": location,
        "type_filter": property_type,
        "possession_filter": possession,
        "min_price_filter": min_price,
        "max_price_filter": max_price,
        "beds_filter": beds,
    })

def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "")
        phone = request.POST.get("phone", "")
        message = request.POST.get("message", "")
        text = f"New Inquiry:\nName: {name}\nPhone: {phone}\nMessage: {message}"
        whatsapp_url = f"https://wa.me/919876543210?text={urllib.parse.quote(text)}"
        return redirect(whatsapp_url)
    return render(request, "public/contact_us.html")

def about(request):
    return render(request, "public/about.html")

def login_view(request):
    if request.user.is_authenticated:
        if request.user.role == "builder":
            return redirect("builder_dashboard")
        elif request.user.role == "agent":
            return redirect("agent_dashboard")
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if user.role == "builder":
                return redirect("builder_dashboard")
            elif user.role == "agent":
                return redirect("agent_dashboard")
            return redirect("home")

        return render(request, "public/login.html", {"error": "Invalid credentials"})

    return render(request, "public/login.html")

def register_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            return render(request, "public/register.html", {"error": "Username and Password required"})

        if User.objects.filter(username=username).exists():
            return render(request, "public/register.html", {"error": "Username already exists"})

        if User.objects.filter(email=email).exists():
            return render(request, "public/register.html", {"error": "Email already exists"})

        user = User.objects.create_user(username=username, email=email, password=password, phone=phone, role="user")

        Profile.objects.update_or_create(
            user=user,
            defaults={"full_name": full_name, "email": email, "phone": phone}
        )

        messages.success(request, "Registration successful! Please login.")
        return redirect("login")

    return render(request, "public/register.html")

def user_login(request):
    if request.user.is_authenticated:
        if request.user.role == "builder":
            return redirect("builder_dashboard")
        elif request.user.role == "agent":
            return redirect("agent_dashboard")
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if user.role == "builder":
                return redirect("builder_dashboard")
            elif user.role == "agent":
                return redirect("agent_dashboard")
            return redirect("home")

        return render(request, "login.html", {"error": "Invalid username or password"})

    return render(request, "login.html")

@login_required
def agent_dashboard(request):
    if request.user.role != "agent":
        logout(request)
        return redirect("login")

    return render(request, "agent/agent_dashboard.html")

from django.utils.timezone import now
import random
import os

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            return render(request, "public/forgot_password.html", {"error": "Email is required"})

        try:
            user = User.objects.get(email=email)
            otp = random.randint(100000, 999999)
            request.session["reset_email"] = user.email
            request.session["otp"] = str(otp)
            request.session["otp_created"] = now().timestamp()
            request.session.save()

            try:
                message = Mail(
                    from_email=os.getenv("DEFAULT_FROM_EMAIL"),
                    to_emails=user.email,
                    subject="OTP Verification",
                    html_content=f"<h2>Password Reset OTP</h2><p>Your OTP is:</p><h1>{otp}</h1><p>This OTP will expire in 5 minutes.</p>"
                )
                sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
                sg.send(message)
            except Exception as e:
                return render(request, "public/forgot_password.html", {"error": f"Email sending failed: {str(e)}"})

            return redirect("otp_verification")

        except User.DoesNotExist:
            return render(request, "public/forgot_password.html", {"error": "Email not registered"})
        except Exception as e:
            return render(request, "public/forgot_password.html", {"error": str(e)})

    return render(request, "public/forgot_password.html")

def otp_verification(request):
    email = request.session.get("reset_email")
    session_otp = request.session.get("otp")
    otp_created = request.session.get("otp_created")

    if not email or not session_otp:
        return redirect("forgot_password")

    if otp_created:
        current_time = now().timestamp()
        if (current_time - otp_created) > 300:
            request.session.flush()
            return render(request, "public/otp_verification.html", {"error": "OTP expired. Please request a new OTP."})

    if request.method == "POST":
        user_otp = request.POST.get("otp", "").strip()
        if user_otp == session_otp:
            request.session["otp_verified"] = True
            return redirect("reset_password")
        return render(request, "public/otp_verification.html", {"error": "Invalid OTP"})

    return render(request, "public/otp_verification.html")

def reset_password(request):
    email = request.session.get("reset_email")
    otp_verified = request.session.get("otp_verified")

    if not email:
        return redirect("forgot_password")
    if not otp_verified:
        return redirect("otp_verification")

    if request.method == "POST":
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        if not password:
            return render(request, "public/reset_password.html", {"error": "Password is required"})
        if len(password) < 6:
            return render(request, "public/reset_password.html", {"error": "Password must be at least 6 characters"})
        if password != confirm_password:
            return render(request, "public/reset_password.html", {"error": "Passwords do not match"})

        try:
            user = User.objects.get(email=email)
            user.set_password(password)
            user.save()
            request.session.pop("otp", None)
            request.session.pop("otp_created", None)
            request.session.pop("otp_verified", None)
            request.session.pop("reset_email", None)
            return redirect("login")
        except User.DoesNotExist:
            request.session.flush()
            return redirect("forgot_password")
        except Exception as e:
            return render(request, "public/reset_password.html", {"error": str(e)})

    return render(request, "public/reset_password.html")

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults={"full_name": instance.username, "email": instance.email, "phone": instance.phone}
        )

@login_required
def profile(request):
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={"full_name": request.user.username, "email": request.user.email, "phone": request.user.phone}
    )
    return render(request, "public/profile.html", {"profile": profile})

def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={"full_name": request.user.username, "email": request.user.email, "phone": request.user.phone}
    )

    if request.method == "POST":
        profile.full_name = request.POST.get("full_name", "").strip()
        profile.email = request.POST.get("email", "").strip()
        profile.phone = request.POST.get("phone", "").strip()
        profile.save()
        request.user.email = profile.email
        request.user.phone = profile.phone
        request.user.save()
        return redirect("profile")

    return render(request, "user/edit_profile.html", {"profile": profile})

@login_required
def my_properties(request):
    if request.user.role != "builder":
        return redirect("login")
    properties = Property.objects.filter(builder=request.user)
    return render(request, "user/my_property.html", {"properties": properties})

@login_required
def my_inquiries(request):
    inquiries = Inquiry.objects.filter(email=request.user.email)
    return render(request, "user/my_inquiries.html", {"inquiries": inquiries})

from decimal import Decimal

def convert_price(price):
    price = price.lower().replace(",", "").strip()
    if "lakh" in price:
        return Decimal(price.replace("lakh", "").strip()) * 100000
    elif "cr" in price or "crore" in price:
        return Decimal(price.replace("crore", "").replace("cr", "").strip()) * 10000000
    else:
        return Decimal(price)

@login_required
def add_property(request):
    if request.user.role != "builder":
        return redirect("login")

    if request.method == "POST":
        title = request.POST.get("title")
        location = request.POST.get("location")
        project_name = request.POST.get("project_name")
        status = request.POST.get("status")
        property_type = request.POST.get("property_type")
        builder_name = request.POST.get("builder_name")
        price = request.POST.get("price")
        starting_price = request.POST.get("starting_price")
        max_price = request.POST.get("max_price")
        beds = request.POST.get("beds")
        baths = request.POST.get("baths")
        sqft = request.POST.get("sqft")
        description = request.POST.get("description")
        thumbnail = request.FILES.get("thumbnail")
        brochure = request.FILES.get("brochure")
        project_logo = request.FILES.get("project_logo")
        project_video = request.FILES.get("project_video")
        amenities = request.POST.getlist("amenities")
        highlights = request.POST.get("highlights")
        rera_number = request.POST.get("rera_number")
        possession_date = request.POST.get("possession_date")
        map_link = request.POST.get("map_link")
        configuration = request.POST.get("configuration")
        project_status = request.POST.get("project_status")
        launch_date = request.POST.get("launch_date")
        total_units = request.POST.get("total_units")
        total_towers = request.POST.get("total_towers")
        land_parcel = request.POST.get("land_parcel")

        nearby_names = request.POST.getlist("nearby_name")
        nearby_distances = request.POST.getlist("nearby_distance")
        nearby_icons = request.POST.getlist("nearby_icon")
        nearby_data = []
        for i in range(len(nearby_names)):
            nearby_data.append({"name": nearby_names[i], "distance": nearby_distances[i], "icon": nearby_icons[i]})

        property = Property.objects.create(
            title=title, location=location, project_name=project_name, price=price,
            beds=beds, baths=baths, sqft=sqft, description=description,
            property_type=property_type, status=status, thumbnail=thumbnail,
            brochure=brochure, amenities=amenities, highlights=highlights,
            rera_number=rera_number, possession_date=possession_date,
            map_link=map_link, configuration=configuration, builder_name=builder_name,
            starting_price=starting_price, max_price=max_price,
            project_logo=project_logo, project_video=project_video,
            project_status=project_status, launch_date=launch_date,
            total_units=total_units, total_towers=total_towers,
            land_parcel=land_parcel, nearby_places=nearby_data,
            builder=request.user
        )

        images = request.FILES.getlist("images")
        for img in images:
            PropertyImage.objects.create(property=property, image=img)

        return redirect("my_property")

    return render(request, "user/add_property.html")

@login_required
def property_management(request):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")
    properties = Property.objects.filter(builder=request.user).order_by("-id")
    return render(request, "builder/property_management.html", {"properties": properties})

@login_required
def lead_management(request):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

    inquiries = Inquiry.objects.filter(property__builder=request.user)
    leads = Lead.objects.filter(builder=request.user).order_by('-id')
    properties = Property.objects.filter(builder=request.user)

    query = request.GET.get('q')
    if query:
        leads = leads.filter(Q(name__icontains=query) | Q(email__icontains=query))

    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)

    sort = request.GET.get('sort')
    if sort == "old":
        leads = leads.order_by('id')
    else:
        leads = leads.order_by('-id')

    selected_lead = None
    lead_id = request.GET.get('lead')
    if lead_id:
        selected_lead = Lead.objects.filter(id=lead_id, builder=request.user).first()

    total_pipeline = Deal.objects.filter(builder=request.user).aggregate(total=Sum('amount'))['total'] or 0
    hot_leads = Lead.objects.filter(builder=request.user, status='HOT').count()
    
    # ✅ builders ManyToMany support
    agents = Agent.objects.filter(builders=request.user)

    return render(request, "builder/lead_management.html", {
        "inquiries": inquiries,
        "leads": leads,
        "selected_lead": selected_lead,
        "total_pipeline": total_pipeline,
        "hot_leads": hot_leads,
        "agents": agents,
        "properties": properties,
    })

@login_required
def builder_dashboard(request):
    if request.user.role != "builder":
        return redirect("login")

    # ✅ DATE RANGE FILTER
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Default: Today only
    today = date.today()
    
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
    else:
        # Default: Show only today's data
        start_date = today
        end_date = today

    # ✅ ALL FILTERS BASED ON DATE RANGE
    date_filter = {'created_at__date__range': [start_date, end_date]}
    
    # ===== TODAY FOLLOWUPS (Only for selected date range) =====
    today_followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date__range=[start_date, end_date],  # ✅ Date range filter
        status="PENDING"
    ).select_related('agent', 'lead')

    grouped_followups = defaultdict(list)
    for f in today_followups:
        agent_name = f.agent.name if f.agent else "Unassigned"
        grouped_followups[agent_name].append(f)

    # ===== UPCOMING FOLLOWUPS (Only for selected date range) =====
    upcoming_followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date__range=[start_date, end_date],
        time__lte=(now() + timedelta(hours=1)).time(),
        status="PENDING"
    )

    # ===== MISSED LEADS (Only for selected date range) =====
    missed_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date],  # ✅ Date range
        created_at__lt=now() - timedelta(hours=24),
        status="NEW"
    )

    # ===== MONTHLY REVENUE CHART (Only for selected date range) =====
    monthly_data = (
        Deal.objects.filter(
            builder=request.user, 
            status="CLOSED",
            created_at__date__range=[start_date, end_date]  # ✅ Date range
        )
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    chart_labels, chart_data = [], []
    for item in monthly_data:
        chart_labels.append(calendar.month_abbr[item['month']])
        chart_data.append(float(item['total'] or 0))

    # ===== BASIC STATS (Only for selected date range) =====
    total_leads = Lead.objects.filter(
        builder=request_user,
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
    ).aggregate(total=Sum('amount'))['total'] or 0

    closed_deals = Deal.objects.filter(
        builder=request.user,
        status="CLOSED",
        created_at__date__range=[start_date, end_date]
    ).count()

    conversion_rate = (closed_deals / total_leads * 100) if total_leads else 0

    # ===== ACTIVITY + TASK (Only for selected date range) =====
    activities = Activity.objects.filter(
        created_at__date__range=[start_date, end_date]
    ).order_by('-created_at')[:5]
    
    tasks = Task.objects.filter(
        user=request.user,
        date__range=[start_date, end_date]  # ✅ Date range
    ).order_by('-date', '-time')[:5]

    # ===== GROWTH CALCULATION (Compare with previous period) =====
    days_diff = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=days_diff)
    prev_end = start_date - timedelta(days=1)

    # Previous period leads
    prev_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[prev_start, prev_end]
    ).count()

    current_leads = total_leads  # Already calculated above

    # Previous period deals
    prev_deals = Deal.objects.filter(
        builder=request.user,
        created_at__date__range=[prev_start, prev_end]
    ).count()

    current_deals = Deal.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    ).count()

    # Previous period revenue
    prev_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED",
        created_at__date__range=[prev_start, prev_end]
    ).aggregate(total=Sum('amount'))['total'] or 0

    current_revenue = total_revenue  # Already calculated

    # Growth calculations
    lead_growth = ((current_leads - prev_leads) / prev_leads * 100) if prev_leads else 0
    deal_growth = ((current_deals - prev_deals) / prev_deals * 100) if prev_deals else 0
    revenue_growth = ((current_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0

    # ===== LEAD SOURCES (Only for selected date range) =====
    total = total_leads  # Already calculated
    builder_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    )
    
    search = builder_leads.filter(source='search').count()
    referral = builder_leads.filter(source='referral').count()
    social = builder_leads.filter(source='social').count()
    direct = builder_leads.filter(source='direct').count()

    lead_sources = {
        "search": (search / total * 100) if total else 0,
        "referrals": (referral / total * 100) if total else 0,
        "social": (social / total * 100) if total else 0,
        "direct": (direct / total * 100) if total else 0,
    }

    # ===== DEALS (Only for selected date range) =====
    deals = Deal.objects.filter(
        builder=request.user,
        created_at__date__range=[start_date, end_date]
    ).order_by('-created_at')

    return render(request, "builder/dashboard.html", {
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
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        "grouped_followups": dict(grouped_followups),
        "today_followups": today_followups,
        "missed_leads": missed_leads,
        "upcoming_followups": upcoming_followups,
        "deals": deals,
        # ✅ Date range for template
        "start_date": start_date,
        "end_date": end_date,
        "today": today,
    })

@login_required
@require_POST
def add_lead(request):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

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

    messages.success(request, f"Lead '{lead.name}' assigned to {agent.name if agent else 'No Agent'}")
    return redirect("lead_management")

@login_required
@require_POST
def edit_lead(request, id):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

    lead = get_object_or_404(Lead, id=id, builder=request.user)
    lead.name = request.POST.get("name")
    lead.email = request.POST.get("email")
    lead.phone = request.POST.get("phone")
    lead.source = request.POST.get("source")
    lead.status = request.POST.get("status")
    lead.interest = request.POST.get("interest")

    agent_id = request.POST.get("assigned_to")
    if agent_id:
        # ✅ builders ManyToMany support
        lead.assigned_to = Agent.objects.filter(id=agent_id, builders=request.user).first()

    lead.save()
    return redirect(f"/builder/leads/?lead={id}")

def export_leads(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Source', 'Status'])
    leads = Lead.objects.filter(builder=request.user)
    for lead in leads:
        writer.writerow([lead.name, lead.email, lead.phone, lead.source, lead.status])
    return response

@login_required
def add_to_cart(request, id):
    property = Property.objects.get(id=id)
    SavedProperty.objects.create(user=request.user, property=property)
    return redirect('property_list')

@login_required
def builder_property_detail(request, id):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

    property = get_object_or_404(Property, id=id, builder=request.user)
    leads = Lead.objects.filter(properties=property, builder=request.user)

    if request.method == "POST":
        property.title = request.POST.get('title')
        property.location = request.POST.get('location')
        property.price = request.POST.get('price')
        property.description = request.POST.get('description')
        property.status = request.POST.get('status')
        if request.FILES.get('thumbnail'):
            property.thumbnail = request.FILES.get('thumbnail')
        property.save()

    return render(request, "builder/property_detail.html", {"property": property, "leads": leads})

@login_required
def delete_property(request, id):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")
    property = get_object_or_404(Property, id=id, builder=request.user)
    property.delete()
    return redirect("property_management")

@login_required
def assign_property(request):
    if request.user.role != "builder":
        logout(request)
        return redirect("login")

    leads = Lead.objects.filter(builder=request.user)
    properties = Property.objects.filter(builder=request.user)
    
    # ✅ builders ManyToMany support
    agents = Agent.objects.filter(builders=request.user)

    selected_lead = None
    selected_lead_id = request.GET.get("lead")
    if selected_lead_id:
        selected_lead = Lead.objects.filter(id=selected_lead_id, builder=request.user).first()

    if request.method == "POST":
        lead = get_object_or_404(Lead, id=request.POST.get("lead_id"), builder=request.user)
        property_obj = get_object_or_404(Property, id=request.POST.get("property_id"), builder=request.user)
        
        # ✅ builders ManyToMany support
        agent = get_object_or_404(Agent, id=request.POST.get("agent_id"), builders=request.user)

        lead.properties.add(property_obj)
        lead.assigned_to = agent
        lead.save()
        return redirect(f"/builder/assign-property/?lead={lead.id}")

    return render(request, "builder/assign_property.html", {
        "leads": leads,
        "properties": properties,
        "agents": agents,
        "selected_lead": selected_lead
    })

@login_required
def builder_root(request):
    return redirect('builder_dashboard')

User = get_user_model()

@login_required
def create_agent(request):
    if request.method == "POST":
        name = request.POST.get("name")
        username = request.POST.get("username")
        password = request.POST.get("password")
        email = request.POST.get("email")
        phone = request.POST.get("phone")

        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(username=username, password=password, role="agent")

        # ✅ builders ManyToMany support
        agent, created = Agent.objects.get_or_create(
            user=user,
            defaults={"name": name, "email": email, "phone": phone}
        )

        # ✅ ADD CURRENT BUILDER TO MANYTOMANY
        agent.builders.add(request.user)

        if not created:
            agent.name = name
            agent.email = email
            agent.phone = phone
            agent.save()
            agent.builders.add(request.user)

        return redirect('create_agent')

    # ✅ FILTER: Sirf current builder ke agents dikhao
    agents = Agent.objects.filter(builders=request.user)

    return render(request, "builder/create_agent.html", {"agents": agents})

def pipeline(request):
    if request.method == "POST":
        lead_id = request.POST.get("lead_id")
        new_status = request.POST.get("status")
        if lead_id and new_status:
            lead = get_object_or_404(Lead, id=lead_id)
            lead.status = new_status
            lead.save()
        return redirect("pipeline")

    leads = Lead.objects.filter(builder=request.user).order_by('-created_at')

    return render(request, "builder/pipeline.html", {
        "columns": [
            ("NEW", leads.filter(status="NEW")),
            ("CONTACTED", leads.filter(status="CONTACTED")),
            ("VISIT", leads.filter(status="VISIT")),
            ("NEGOTIATION", leads.filter(status="NEGOTIATION")),
            ("CLOSED", leads.filter(status="CLOSED")),
        ]
    })

@login_required
@csrf_exempt
def update_lead_status(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    try:
        data = json.loads(request.body)
        lead_id = data.get("lead_id")
        status = data.get("status")

        if request.user.role == "builder":
            lead = get_object_or_404(Lead, id=lead_id, builder=request.user)

        elif request.user.role == "agent":
            agent = Agent.objects.get(user=request.user)
            # ✅ builders ManyToMany support - check if agent has access to this lead's builder
            lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)

        else:
            return JsonResponse({"success": False, "message": "Permission denied"})

        old_status = lead.status
        lead.status = status
        lead.save()

        LeadActivity.objects.create(
            lead=lead,
            message=f"{request.user.username} changed status from {old_status} to {status}"
        )

        return JsonResponse({"success": True, "status": status})

    except Agent.DoesNotExist:
        return JsonResponse({"success": False, "message": "Agent profile not found"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

def lead_detail_api(request, id):
    lead = get_object_or_404(Lead, id=id, builder=request.user)
    return JsonResponse({
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
        "priority": lead.priority,
    })

@csrf_exempt
def add_note(request):
    if request.method == "POST":
        data = json.loads(request.body)
        LeadNote.objects.create(lead_id=data['lead_id'], note=data['note'], created_at=timezone.now())
        return JsonResponse({"success": True})

@csrf_exempt
@login_required
def update_priority(request):
    if request.method == "POST":
        data = json.loads(request.body)
        lead = get_object_or_404(Lead, id=data["lead_id"], builder=request.user)
        lead.priority = data["priority"]
        lead.save()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})

def analytics(request):
    leads = Lead.objects.filter(builder=request.user)
    total_leads = leads.count()
    closed_leads = leads.filter(status="CLOSED").count()
    active_leads = leads.exclude(status="CLOSED").count()

    total_revenue = 0

    status_counts = {
        "NEW": leads.filter(status="NEW").count(),
        "CONTACTED": leads.filter(status="CONTACTED").count(),
        "SITE VISIT": leads.filter(status="SITE VISIT").count(),
        "NEGOTIATION": leads.filter(status="NEGOTIATION").count(),
        "CLOSED": leads.filter(status="CLOSED").count(),
    }

    sources = leads.values('source').annotate(count=Count('id'))
    source_labels = [s['source'] for s in sources]
    source_data = [s['count'] for s in sources]

    agents = []
    # ✅ builders ManyToMany support
    for agent in Agent.objects.filter(builders=request.user):
        total = leads.filter(assigned_to=agent).count()
        closed = leads.filter(assigned_to=agent, status="CLOSED").count()
        active = leads.filter(assigned_to=agent).exclude(status="CLOSED").count()
        agents.append({"name": agent.name, "total": total, "closed": closed, "active": active})

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

@login_required
def document_management(request):
    if request.method == "POST":
        file = request.FILES.get("file")
        category = request.POST.get("category")
        if file:
            doc = Document.objects.create(name=file.name, file=file, category=category, uploaded_by=request.user)
            Notification.objects.create(title="Document Uploaded", message=f"{doc.name} uploaded", type="document")
        return redirect("document_management")

    documents = Document.objects.all().order_by("-created_at")
    return render(request, "builder/document_management.html", {"documents": documents})

@login_required
def delete_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    doc.delete()
    return redirect('document_management')

@login_required
def communication(request):
    conversations = Conversation.objects.all().order_by('-created_at')
    first_chat = conversations.first()
    messages_list = []
    if first_chat:
        messages_list = first_chat.messages.all().order_by('created_at')

    return render(request, "builder/communication.html", {
        "conversations": conversations,
        "messages": messages_list,
        "active_chat": first_chat
    })

@csrf_exempt
def send_message(request):
    data = json.loads(request.body)
    name = data.get("name")
    phone = data.get("phone")
    text = data.get("message")

    convo, created = Conversation.objects.get_or_create(lead_phone=phone, defaults={"lead_name": name})
    Message.objects.create(conversation=convo, text=text, is_agent=False)
    Notification.objects.create(title="New Message", message=f"Message from {name}", type="message")

    return JsonResponse({"status": "sent", "conversation_id": convo.id})

@csrf_exempt
def client_send_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        name = data.get("name", "Guest")
        phone = data.get("phone", "unknown")
        text = data.get("message")

        convo, created = Conversation.objects.get_or_create(lead_phone=phone, defaults={"lead_name": name})
        Message.objects.create(conversation=convo, text=text, is_agent=False)
        return JsonResponse({"status": "ok"})

def get_messages(request):
    convo_id = request.GET.get("conversation_id")
    convo = Conversation.objects.filter(id=convo_id).first()
    if not convo:
        return JsonResponse({"messages": []})

    messages = convo.messages.all().order_by('created_at')
    data = [{"text": m.text, "is_agent": m.is_agent} for m in messages]
    return JsonResponse({"messages": data})

@csrf_exempt
def agent_send_message(request):
    data = json.loads(request.body)
    convo_id = data.get("conversation_id")
    text = data.get("message")
    convo = Conversation.objects.get(id=convo_id)
    Message.objects.create(conversation=convo, text=text, is_agent=True)
    return JsonResponse({"status": "sent"})

@csrf_exempt
@login_required
def create_task(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST request required"})

    data = json.loads(request.body)
    task = Task.objects.create(
        title=data["title"],
        lead_id=data["lead"],
        date=data["date"],
        time=data["time"],
        priority=data["priority"]
    )

    Notification.objects.create(title="Task Created", message=f"{task.title} scheduled", type="task")
    return JsonResponse({"status": "ok"})

def task_done(request, id):
    task = Task.objects.get(id=id)
    task.status = "DONE"
    task.save()
    return JsonResponse({"status": "done"})

def scheduler_overview(request):
    # ✅ Only builder ke tasks
    tasks = Task.objects.filter(user=request.user)
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

@csrf_exempt
@login_required
def reorder_task(request):
    if request.method != "POST":
        return JsonResponse({"status": "error"})

    data = json.loads(request.body)
    task = get_object_or_404(Task, id=data["task_id"])
    task.order = data["position"]
    task.save()
    return JsonResponse({"status": "ok"})

def check_reminders(request):
    today = date.today()
    count = Task.objects.filter(date=today, status='PENDING').count()
    return JsonResponse({"count": count})

@login_required
def notifications_page(request):
    notifications = Notification.objects.all().order_by('-created_at')
    return render(request, "builder/notifications.html", {"notifications": notifications})

@csrf_exempt
@login_required
def mark_notification_read(request, id):
    notification = get_object_or_404(Notification, id=id)
    notification.is_read = True
    notification.save()
    return JsonResponse({"status": "ok"})

import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from django.core.exceptions import FieldError

@login_required
def agent_performance(request):
    # ✅ builders ManyToMany support
    agents = Agent.objects.filter(builders=request.user)

    selected_agent = request.GET.get("agent")
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    data = []
    chart_labels = []
    chart_data = []
    total_revenue = 0
    total_deals = 0

    for agent in agents:
        leads = Lead.objects.filter(assigned_to=agent)
        deals = Deal.objects.filter(agent=agent, status="CLOSED")

        if start_date and end_date:
            leads = leads.filter(created_at__range=[start_date, end_date])
            deals = deals.filter(created_at__range=[start_date, end_date])

        if selected_agent:
            if str(agent.id) != selected_agent:
                continue

        total_leads = leads.count()
        closed_deals = deals.count()
        revenue = deals.aggregate(total=Sum('amount'))['total'] or 0

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

@login_required
def agent_detail(request, id):
    # ✅ builders ManyToMany support
    agent = get_object_or_404(Agent, id=id, builders=request.user)

    leads = Lead.objects.filter(assigned_to=agent)
    deals = Deal.objects.filter(agent=agent)
    revenue = deals.aggregate(total=Sum("amount"))["total"] or 0

    return render(request, "builder/agent_detail.html", {
        "agent": agent,
        "leads": leads.count(),
        "deals": deals.count(),
        "revenue": revenue
    })

def export_agents(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="agents.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Leads', 'Deals', 'Revenue'])

    # ✅ builders ManyToMany support
    for agent in Agent.objects.filter(builders=request.user):
        leads = Lead.objects.filter(assigned_to=agent).count()
        deals = Deal.objects.filter(agent=agent).count()
        revenue = Deal.objects.filter(agent=agent).aggregate(total=Sum('amount'))['total'] or 0
        writer.writerow([agent.name, leads, deals, revenue])

    return response

def ai_insights(request):
    leads = Lead.objects.filter(builder=request.user)

    scored_leads = []
    high_intent = 0
    closing = 0
    risk = 0

    for lead in leads:
        score = random.randint(40, 100)
        if score > 80:
            intent = "High"
            high_intent += 1
        elif score > 60:
            intent = "Medium"
            closing += 1
        else:
            intent = "Low"
            risk += 1

        scored_leads.append({"lead": lead, "score": score, "intent": intent})

    total_revenue = Deal.objects.aggregate(total=Sum('amount'))['total'] or 0
    forecast = int(total_revenue * 1.3)

    insights = [
        {"title": "Market Shift", "desc": "Luxury demand increased"},
        {"title": "Best Time", "desc": "Call leads at 2PM"},
    ]

    recommendations = []
    for item in scored_leads:
        if item["score"] > 85:
            recommendations.append(f"Follow up with {item['lead'].name}")

    return render(request, "builder/ai_insights.html", {
        "scored_leads": scored_leads[:5],
        "total_revenue": total_revenue,
        "forecast": forecast,
        "insights": insights,
        "recommendations": recommendations,
        "high_intent": high_intent,
        "closing": closing,
        "risk": risk
    })

def marketing_automation(request):
    campaigns = Campaign.objects.all()
    total_campaigns = campaigns.count()
    total_reach = sum(c.reach or 0 for c in campaigns)
    total_conversions = sum(c.conversion or 0 for c in campaigns)

    avg_ctr = 0
    if total_reach > 0:
        avg_ctr = round((sum(c.clicked or 0 for c in campaigns) / total_reach) * 100, 2)

    chart_labels = [c.name for c in campaigns]
    chart_data = [c.reach for c in campaigns]

    return render(request, 'builder/marketing_automation.html', {
        'campaigns': campaigns,
        'total_campaigns': total_campaigns,
        'total_reach': total_reach,
        'total_conversions': total_conversions,
        'avg_ctr': avg_ctr,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })

def create_campaign(request):
    if request.method == "POST":
        Campaign.objects.create(
            name=request.POST.get('name'),
            type=request.POST.get('type', ''),
            reach=request.POST.get('reach'),
            clicked=request.POST.get('clicked'),
            conversion=request.POST.get('conversion'),
            image=request.FILES.get('image')
        )
        return redirect('/builder/marketing/')

    return render(request, 'builder/create_campaign.html')

@login_required
def run_campaign(request, id):
    campaign = get_object_or_404(Campaign, id=id)
    campaign.sent = (campaign.sent or 0) + 100
    campaign.opened = (campaign.opened or 0) + 60
    campaign.clicked = (campaign.clicked or 0) + 20
    campaign.save()
    return redirect("marketing_automation")

def delete_campaign(request, id):
    campaign = get_object_or_404(Campaign, id=id)
    campaign.delete()
    return redirect('/builder/marketing/')

@login_required
def manage_users(request):
    query = request.GET.get('q')
    role_filter = request.GET.get('role')

    # ✅ builders ManyToMany support
    agents = Agent.objects.filter(builders=request.user).order_by('-id')

    if query:
        agents = agents.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))

    if role_filter and hasattr(Agent, "role"):
        agents = agents.filter(role=role_filter)

    return render(request, 'builder/manage_users.html', {'agents': agents})

# ❌ DELETE
@login_required
def delete_agent(request, id):
    # ✅ builders ManyToMany support
    agent = get_object_or_404(Agent, id=id, builders=request.user)
    agent.delete()
    return redirect('manage_users')

# 🔄 TOGGLE STATUS
@login_required
def toggle_agent(request, id):
    # ✅ builders ManyToMany support
    agent = get_object_or_404(Agent, id=id, builders=request.user)
    agent.is_active = not agent.is_active
    agent.save()
    return redirect('manage_users')

def register_user(request):
    if request.method == "POST":
        user = User.objects.create_user(username=request.POST["username"], password=request.POST["password"])
        Agent.objects.create(user=user, name=request.POST["username"], email="", phone="")
        return redirect("login")
    return render(request, "public/register.html")

@login_required
def agent_delete_lead(request, lead_id):
    agent = Agent.objects.get(user=request.user)
    lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)
    lead.delete()
    return redirect("agent_leads")

# ✅✅✅ AGENT VIEWS - FIXED FOR MULTIPLE BUILDERS ✅✅✅

@login_required
def agent_dashboard(request):
    # ===== GET OR CREATE AGENT =====
    agent, created = Agent.objects.get_or_create(
        user=request.user,
        defaults={
            "name": request.user.username,
            "email": request.user.email,
            "phone": getattr(request.user, "phone", "")
        }
    )

    # ✅ GET ALL BUILDERS FOR THIS AGENT
    agent_builders = agent.builders.all()

    # ✅ LEADS: Sirf un builders ke leads jo is agent ke hain
    leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    )

    total_leads = leads.count()
    hot = leads.filter(status="HOT").count()
    warm = leads.filter(status="WARM").count()
    cold = leads.filter(status="COLD").count()

    # ✅ VISITS: Sirf apne builders ke
    visits = SiteVisit.objects.filter(
        agent=agent,
        builder__in=agent_builders
    )
    today_visits = visits.filter(date=date.today()).count()

    # ✅ TASKS: Sirf apne builders ke
    tasks = Task.objects.filter(
        lead__assigned_to=agent,
        lead__builder__in=agent_builders,
        status="PENDING"
    )

    # ✅ TODAY FOLLOWUPS: Sirf apne builders ke
    today_followups = FollowUp.objects.filter(
        agent=agent,
        lead__builder__in=agent_builders,
        date=date.today(),
        status="PENDING"
    )

    # ✅ DEALS: Sirf apne builders ke
    deals = Deal.objects.filter(
        agent=agent,
        builder__in=agent_builders
    )
    total_deals = deals.count()

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
        "total_deals": total_deals,
    })

@login_required
def agent_leads(request):
    agent = get_object_or_404(Agent, user=request.user)
    
    # ✅ GET ALL BUILDERS FOR THIS AGENT
    agent_builders = agent.builders.all()

    # ✅ LEADS: Sirf un builders ke leads
    leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    ).order_by("-created_at")

    q = request.GET.get("q")
    if q:
        leads = leads.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))

    status = request.GET.get("status")
    if status:
        leads = leads.filter(status=status)

    sort = request.GET.get("sort")
    if sort == "old":
        leads = leads.order_by("created_at")
    else:
        leads = leads.order_by("-created_at")

    active_leads = leads.exclude(deals__status__in=["CLOSED", "FAILED"]).distinct()
    success_leads = leads.filter(deals__status__in=["CLOSED", "FAILED"]).distinct()

    return render(request, "agent/agent_leads.html", {
        "leads": active_leads,
        "success_leads": success_leads,
    })

def delete_lead(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, assigned_to__user=request.user)
    lead.delete()
    return redirect("agent_leads")

@login_required
def agent_properties(request):
    agent = get_object_or_404(Agent, user=request.user)
    
    # ✅ GET ALL BUILDERS FOR THIS AGENT
    agent_builders = agent.builders.all()

    properties = Property.objects.filter(
        interested_leads__assigned_to=agent,
        builder__in=agent_builders  # ✅ Privacy fix
    ).annotate(
        demand=Count("interested_leads")
    ).distinct().order_by("-demand")

    return render(request, "agent/agent_properties.html", {"properties": properties})

@login_required
def agent_profile(request):
    agent = get_object_or_404(Agent, user=request.user)
    
    # ✅ GET ALL BUILDERS FOR THIS AGENT
    agent_builders = agent.builders.all()

    total_leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    ).count()

    hot_leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders,
        status="HOT"
    ).count()

    visits = SiteVisit.objects.filter(
        agent=agent,
        builder__in=agent_builders
    )

    total_visits = visits.count()
    completed_visits = visits.filter(status="DONE").count()

    conversion_rate = 0
    if total_leads:
        conversion_rate = round((completed_visits / total_leads) * 100, 2)

    return render(request, "agent/agent_profile.html", {
        "agent": agent,
        "total_leads": total_leads,
        "hot_leads": hot_leads,
        "total_visits": total_visits,
        "completed_visits": completed_visits,
        "conversion_rate": conversion_rate,
    })

@login_required
def scheduler(request):
    agent = get_object_or_404(Agent, user=request.user)
    
    # ✅ GET ALL BUILDERS FOR THIS AGENT
    agent_builders = agent.builders.all()

    leads = Lead.objects.filter(
        assigned_to=agent,
        builder__in=agent_builders
    )

    visits = SiteVisit.objects.filter(
        agent=agent,
        builder__in=agent_builders
    ).order_by("-date")

    if request.method == "POST":
        lead_id = request.POST.get("lead")
        property_id = request.POST.get("property")
        visit_date = request.POST.get("date")
        visit_time = request.POST.get("time")

        # ✅ Security: Check lead belongs to agent's builders
        lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent, builder__in=agent_builders)

        SiteVisit.objects.create(
            property_id=property_id,
            lead=lead,
            agent=agent,
            date=visit_date,
            time=visit_time,
            builder=lead.builder  # ✅ Auto-set builder from lead
        )

        return redirect("scheduler")

    return render(request, "agent/scheduler.html", {"leads": leads, "visits": visits})

def property_leads(request, property_id):
    # ✅ Security: Only show leads for properties where agent has access
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = agent.builders.all()

    leads = Lead.objects.filter(
        properties__id=property_id,
        builder__in=agent_builders
    ).distinct()

    return render(request, "agent/property_leads.html", {"leads": leads})

@login_required
def site_visits(request):
    return render(request, "agent/scheduler.html")

@login_required
def settings_view(request):
    user = request.user

    if request.method == "POST":
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.phone = request.POST.get("phone")

        if request.FILES.get("profile_image"):
            user.profile_image = request.FILES.get("profile_image")

        user.save()

        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        if password:
            if password == confirm:
                user.set_password(password)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password updated successfully")
            else:
                messages.error(request, "Passwords do not match")

        messages.success(request, "Profile updated successfully")
        return redirect("settings")

    return render(request, "settings.html")

def privacy(request):
    property = Property.objects.first()
    return render(request, "public/privacy.html", {"property": property})

# ✅ builders ManyToMany support
def auto_assign_agent(builder):
    agents = list(Agent.objects.filter(builders=builder, is_active=True).order_by('id'))
    last_lead = Lead.objects.filter(builder=builder).order_by('-id').first()

    if last_lead and last_lead.assigned_to in agents:
        last_index = agents.index(last_lead.assigned_to)
        return agents[(last_index + 1) % len(agents)]
    return agents[0] if agents else None

@receiver(post_save, sender=User)
def create_agent_for_user(sender, instance, created, **kwargs):
    if created and instance.role == "agent":
        Agent.objects.get_or_create(
            user=instance,
            defaults={
                "name": instance.username,
                "email": instance.email,
                "phone": getattr(instance, "phone", ""),
            }
        )

import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Lead

@login_required
def export_leads_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Lead Name', 'Email', 'Phone', 'Source', 'Status', 'Assigned Agent', 'Properties'])

    leads = Lead.objects.filter(builder=request.user)

    search_query = request.GET.get('q')
    from django.db.models import Q

    if search_query:
        leads = leads.filter(Q(name__icontains=search_query) | Q(email__icontains=search_query))

    for lead in leads:
        agent_name = lead.assigned_to.name if lead.assigned_to else "Not Assigned"
        properties_list = ", ".join([p.title for p in lead.properties.all()]) if lead.properties.exists() else "-"

        writer.writerow([
            lead.name, lead.email, lead.phone, lead.source, lead.status,
            agent_name, properties_list
        ])

    return response

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from core.models import Property
from twilio.twiml.messaging_response import MessagingResponse

@csrf_exempt
def whatsapp_bot(request):
    if request.method == "POST":
        msg = request.POST.get("Body", "").lower()
        resp = MessagingResponse()
        reply = "Welcome to Smart Realty 🏠\n1 Residential\n2 Commercial" if "hi" in msg else "Type Hi"
        resp.message(reply)
        return HttpResponse(str(resp), content_type="application/xml")
    return HttpResponse("Method not allowed", status=405)

from decimal import Decimal

def add_deal(request):
    if request.method == "POST":
        property_id = request.POST.get('property_id')
        lead_id = request.POST.get('lead_id')
        client_name = request.POST.get('client_name') or "Unknown"
        amount = request.POST.get('amount')
        status = request.POST.get('status')

        property_obj = get_object_or_404(Property, id=property_id)
        agent = get_object_or_404(Agent, user=request.user)
        
        # ✅ Security: Check agent has access to this property's builder
        if property_obj.builder not in agent.builders.all():
            return redirect('agent_leads')

        lead = None
        if lead_id:
            lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent)

        if amount:
            amount = Decimal(str(amount).replace(",", "").strip())
        else:
            amount = Decimal("0")

        Deal.objects.create(
            lead=lead,
            property=property_obj,
            client_name=client_name,
            amount=amount,
            status=status,
            agent=agent,
            builder=property_obj.builder
        )

        return redirect('agent_leads')

def update_deal(request, deal_id):
    if request.method == "POST":
        deal = Deal.objects.get(id=deal_id)
        status = request.POST.get("status")
        deal.status = status
        deal.save()
    return redirect("agent_leads")

def add_followup(request, lead_id):
    agent = get_object_or_404(Agent, user=request.user)
    agent_builders = agent.builders.all()
    
    # ✅ Security: Check lead belongs to agent's builders
    lead = get_object_or_404(Lead, id=lead_id, assigned_to=agent, builder__in=agent_builders)

    if request.method == "POST":
        date = request.POST.get("date")
        time = request.POST.get("time")
        note = request.POST.get("note")

        FollowUp.objects.create(
            lead=lead,
            agent=agent,
            date=date,
            time=time,
            note=note
        )
        return redirect("agent_dashboard")

    return render(request, "agent/add_followup.html", {"lead": lead})

def update_missed_followups():
    followups = FollowUp.objects.filter(status="PENDING")
    for f in followups:
        followup_datetime = datetime.combine(f.date, f.time)
        if followup_datetime < now():
            f.status = "MISSED"
            f.save()

def mark_followup_done(request, id):
    f = FollowUp.objects.get(id=id)
    f.status = "DONE"
    f.save()
    return redirect(request.META.get('HTTP_REFERER'))