from django.shortcuts import render,get_object_or_404 ,redirect
from .models import Property,User,Profile,Lead, Deal, Task,Activity,Agent,Document,Conversation, Message,Notification,Campaign,SiteVisit
import urllib.parse
from django.contrib import messages
from django.contrib.auth import authenticate, login,logout,get_user_model
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
import calendar, json,csv
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
from django.utils.timezone import now
def home(request):
    properties = Property.objects.all()[:6]

    return render(request, "public/index.html", {
        "properties": properties
    })

def properties_view(request):
    properties = Property.objects.all().order_by('-created_at')
    return render(request, "public/properties.html", {
        "properties": properties
    })

from .models import Inquiry


def property_detail(request, id):
    property = get_object_or_404(Property, id=id)
    # ✅ highlights split fix
    highlights_list = []
    if property.highlights:
        highlights_list = property.highlights.split(",") if property.highlights else []
    
    similar_properties = Property.objects.filter(
    location=property.location
).exclude(id=property.id)[:3]

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        message = request.POST.get("message")

        # ✅ ROUND ROBIN LOGIC
        agents = list(Agent.objects.filter(builder=property.builder).order_by('id'))

        last_lead = Lead.objects.filter(builder=property.builder).order_by('-id').first()

        if last_lead and last_lead.assigned_to in agents:
            last_index = agents.index(last_lead.assigned_to)
            agent = agents[(last_index + 1) % len(agents)]
        else:
            agent = agents[0] if agents else None

        # ✅ CREATE LEAD
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
    properties = Property.objects.all().order_by('-created_at')

    location = request.GET.get('location')
    property_type = request.GET.get('type')
    possession = request.GET.get('possession')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    beds = request.GET.get('beds')
    query = request.GET.get('q')   # 🔥 NEW SEARCH

    # 🔍 GLOBAL SEARCH (AREA / PROJECT / BUILDER / TITLE)
    if query:
        properties = properties.filter(
            Q(title__icontains=query) |
            Q(location__icontains=query) |
            Q(project_name__icontains=query) |
            Q(builder__username__icontains=query)
        )

    # LOCATION (smart match)
    if location:
        properties = properties.filter(location__icontains=location)

    # TYPE (exact + similar)
    if property_type:
        properties = properties.filter(
            Q(property_type__iexact=property_type) |
            Q(property_type__icontains=property_type)
        )

    # POSSESSION (important fix)
    if possession:
        properties = properties.filter(
            Q(possession__iexact=possession) |
            Q(possession__icontains=possession)
        )

    # PRICE RANGE
    if min_price:
        properties = properties.filter(price__gte=min_price)

    if max_price:
        properties = properties.filter(price__lte=max_price)

    # BEDS
    if beds:
        properties = properties.filter(beds__gte=beds)

    return render(request, "public/property.html", {
        "properties": properties
    })
def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        message = request.POST.get("message")
        messages.success(request, "Redirecting to WhatsApp...")

        text = f"New Inquiry:%0AName: {name}%0APhone: {phone}%0AMessage: {message}"

        whatsapp_url = f"https://wa.me/919876543210?text={text}"

        return redirect(whatsapp_url)
    

    return render(request, "public/contact_us.html")

def about(request):
    return render(request, "public/about.html")

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            if user.role == "builder":
                return redirect("builder_dashboard")
            elif user.role == "agent":
                return redirect("agent_dashboard")
            else:
                return redirect("home")

        else:
            return render(request, "public/login.html", {"error": "Invalid credentials"})

    return render(request, "public/login.html")



def register_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")

        if not username or not password:
            return render(request, "public/register.html", {
                "error": "Username and Password required"
            })

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            phone=phone,
            role="user"
        )

        profile, created = Profile.objects.get_or_create(user=user)
        profile.full_name = full_name
        profile.email = email
        profile.phone = phone
        profile.save()

        # ✅ SUCCESS MESSAGE
        messages.success(request, "🎉 Registration successful! Please login.")

        return redirect("login")

    return render(request, "public/register.html")

def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # 🔥 ROLE CHECK
            if hasattr(user, 'agent'):
                return redirect('agent_dashboard')

            else:
                return redirect('builder_dashboard')

    return render(request, "login.html")
    
@login_required
def agent_dashboard(request):
    if request.user.role != "agent":
        return redirect("login")

    return render(request, "agent/agent_dashboard.html")

def forgot_password(request):
    print("METHOD:", request.method)

    if request.method == "POST":
        print("POST HIT")

        email = request.POST.get("email")
        print("EMAIL:", email)

        try:
            user = User.objects.get(email=email)

            # 🔥 OTP generate
            otp = random.randint(100000, 999999)

            # 🔥 session set (safe way)
            request.session['reset_email'] = email
            request.session['otp'] = str(otp)
            request.session.save()

            print("OTP:", otp)
            print("SESSION AFTER SET:", request.session.items())

            # 🔥 EMAIL SEND (SendGrid API - NO TIMEOUT)
            try:
                message = Mail(
                   from_email=os.getenv("DEFAULT_FROM_EMAIL"),
                   to_emails=email,
                   subject="OTP Verification",
                   html_content=f"<strong>Your OTP is {otp}</strong>"
)

                sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
                response = sg.send(message)
                print("MAIL SENT")

            except Exception as e:
                print("MAIL FAILED:", e)
                return render(request, "public/forgot_password.html", {
                    "error": f"Email failed: {str(e)}"
                })

            return redirect("otp_verification")

        except User.DoesNotExist:
            return render(request, "public/forgot_password.html", {
                "error": "Email not registered"
            })

        except Exception as e:
            print("ERROR:", str(e))
            return render(request, "public/forgot_password.html", {
                "error": str(e)
            })

    return render(request, "public/forgot_password.html")
def otp_verification(request):
    email = request.session.get("reset_email")
    session_otp = request.session.get("otp")

    print("OTP PAGE SESSION:", request.session.items())

    # 🔒 direct access block
    if not email or not session_otp:
        return redirect("forgot_password")

    if request.method == "POST":
        user_otp = request.POST.get("otp")

        if user_otp == session_otp:
            return redirect("reset_password")
        else:
            return render(request, "public/otp_verification.html", {
                "error": "Invalid OTP"
            })

    return render(request, "public/otp_verification.html")
def reset_password(request):
    email = request.session.get("reset_email")

    if not email:
        return redirect("forgot_password")  # direct access block

    if request.method == "POST":
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            return render(request, "public/reset_password.html", {
                "error": "Passwords do not match"
            })

        try:
            user = User.objects.get(email=email)
            user.password = make_password(password)
            user.save()

            # session clear
            request.session.flush()

            return redirect("login")

        except User.DoesNotExist:
            return redirect("forgot_password")

    return render(request, "public/reset_password.html")


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(
            user=instance,
            full_name=instance.username,  # fallback
            email=instance.email,
            phone=instance.phone
        )

@login_required
def profile(request):
    profile = Profile.objects.get(user=request.user)

    return render(request, "public/profile.html", {
        "profile": profile
    })

def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def edit_profile(request):
    profile = Profile.objects.get(user=request.user)

    if request.method == "POST":
        profile.full_name = request.POST.get("full_name")
        profile.email = request.POST.get("email")
        profile.phone = request.POST.get("phone")
        profile.save()

        return redirect("profile")

    return render(request, "user/edit_profile.html", {"profile": profile})


@login_required
def my_properties(request):
    properties = Property.objects.filter(builder=request.user) 
    return render(request, "user/my_property.html", {
        "properties": properties
    })

@login_required
def my_inquiries(request):
    inquiries = Inquiry.objects.filter(email=request.user.email)

    return render(request, "user/my_inquiries.html", {
        "inquiries": inquiries
    })


from decimal import Decimal

def convert_price(price):
    price = price.lower().replace(",", "").strip()

    if "lakh" in price:
        num = price.replace("lakh", "").strip()
        return Decimal(num) * 100000

    elif "cr" in price or "crore" in price:
        num = price.replace("crore", "").replace("cr", "").strip()
        return Decimal(num) * 10000000

    else:
        return Decimal(price)


@login_required
def add_property(request):

    if request.method == "POST":

        title = request.POST.get("title")
        location = request.POST.get("location")
        project_name = request.POST.get('project_name')
        status = request.POST.get("status")

        # ✅ PRICE FIX (IMPORTANT)
        price_input = request.POST.get("price", "").strip()
        price = Decimal(0)

        if price_input:
            try:
                if "Lakh" in price_input:
                    price = Decimal(price_input.replace("Lakh", "").strip()) * 100000
                elif "Cr" in price_input:
                    price = Decimal(price_input.replace("Cr", "").strip()) * 10000000
                else:
                    price = Decimal(price_input)
            except:
                price = Decimal(0)

        beds = request.POST.get("beds")
        baths = request.POST.get("baths")
        sqft = request.POST.get("sqft")
        description = request.POST.get("description")

        property_type = request.POST.get("property_type")  # ✅ FIXED

        thumbnail = request.FILES.get("thumbnail")
        brochure = request.FILES.get("brochure")

        amenities = request.POST.getlist("amenities")

        highlights = request.POST.get("highlights")
        rera_number = request.POST.get("rera_number")
        possession_date = request.POST.get("possession_date")
        map_link = request.POST.get("map_link")
        configuration = request.POST.get("configuration")

        import json

        nearby_names = request.POST.getlist("nearby_name")
        nearby_distances = request.POST.getlist("nearby_distance")
        nearby_icons = request.POST.getlist("nearby_icon")

        nearby_data = []

        for i in range(len(nearby_names)):
            nearby_data.append({
                "name": nearby_names[i],
                "distance": nearby_distances[i],
                "icon": nearby_icons[i]
            })

        property = Property.objects.create(
            title=title,
            location=location,
            project_name=project_name,
            price=price,  # ✅ cleaned price
            beds=beds,
            baths=baths,
            sqft=sqft,
            description=description,
            property_type=property_type,
            status=status,
            thumbnail=thumbnail,
            brochure=brochure,
            amenities=amenities,
            highlights=highlights,
            rera_number=rera_number,
            possession_date=possession_date,
            map_link=map_link,
            configuration=configuration,
            nearby_places=nearby_data,
            builder=request.user
        )

        images = request.FILES.getlist("images")
        for img in images:
            PropertyImage.objects.create(property=property, image=img)

        return redirect("my_property")

    return render(request, "user/add_property.html")
@login_required
def property_management(request):
    properties = Property.objects.filter(builder=request.user)
    return render(request, "builder/property_management.html", {
        "properties": properties
    })



@login_required
def lead_management(request):

    inquiries = Inquiry.objects.all()

    # ✅ FINAL QUERY (DON'T OVERRIDE LATER)
    leads = Lead.objects.filter(builder=request.user).order_by('-id')

    properties = Property.objects.filter(builder=request.user)

    # 🔍 search
    query = request.GET.get('q')
    if query:
        leads = leads.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query)
        )

    # 🎯 status filter
    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)

    # 🔄 sorting
    sort = request.GET.get('sort')
    if sort == "old":
        leads = leads.order_by('id')
    else:
        leads = leads.order_by('-id')

    # ✅ SELECTED LEAD
    selected_lead = None
    lead_id = request.GET.get('lead')

    if lead_id:
        selected_lead = Lead.objects.filter(id=lead_id).first()

    # 📊 stats
    total_pipeline = Deal.objects.aggregate(total=Sum('amount'))['total'] or 0

    hot_leads = Lead.objects.filter(
        Q(builder=request.user) | Q(builder__isnull=True),
        status='HOT'
    ).count()

    # 👥 agents
    agents = Agent.objects.filter(builder=request.user)

    # ✅ PAGINATION (same queryset use karo)
    #paginator = Paginator(leads, 10)
    #page = request.GET.get('page', 1)
    #leads = paginator.get_page(page)

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

    # 🔐 SECURITY (FINAL FIX)
    if request.user.role != "builder":
        return redirect("login")

    agent = getattr(request.user, 'agent', None)

    # ===== TODAY FOLLOWUPS =====
    today_followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date=date.today(),
        status="PENDING"
    ).select_related('agent', 'lead')

    grouped_followups = defaultdict(list)

    for f in today_followups:
        agent_name = f.agent.name if f.agent else "Unassigned"
        grouped_followups[agent_name].append(f)

    # ===== UPCOMING FOLLOWUPS (NEXT 1 HOUR) =====
    upcoming_followups = FollowUp.objects.filter(
        lead__builder=request.user,
        date=date.today(),
        time__lte=(now() + timedelta(hours=1)).time(),
        status="PENDING"
    )

    # ===== MISSED LEADS =====
    missed_leads = Lead.objects.filter(
        builder=request.user,
        created_at__lt=now() - timedelta(hours=24),
        status="NEW"
    )

    # ===== MONTHLY REVENUE CHART =====
    monthly_data = (
        Deal.objects.filter(builder=request.user, status="CLOSED")
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    chart_labels = []
    chart_data = []

    for item in monthly_data:
        chart_labels.append(calendar.month_abbr[item['month']])
        chart_data.append(float(item['total'] or 0))

    # ===== BASIC STATS =====
    total_leads = Lead.objects.filter(builder=request.user).count()

    active_deals = Deal.objects.filter(
        builder=request.user,
        status__in=["NEW", "NEGOTIATION", "BOOKED"]
    ).count()

    total_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED"
    ).aggregate(total=Sum('amount'))['total'] or 0

    closed_deals = Deal.objects.filter(
        builder=request.user,
        status="CLOSED"
    ).count()

    # ===== CONVERSION =====
    conversion_rate = (closed_deals / total_leads * 100) if total_leads else 0

    # ===== ACTIVITY + TASK =====
    activities = Activity.objects.order_by('-created_at')[:5]
    tasks = Task.objects.order_by('-date', '-time')[:5]

    # ===== DATE CALC =====
    today = date.today()
    start_of_month = today.replace(day=1)

    last_month_end = start_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # ===== LEADS GROWTH =====
    current_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__gte=start_of_month
    ).count()

    last_leads = Lead.objects.filter(
        builder=request.user,
        created_at__date__range=[last_month_start, last_month_end]
    ).count()

    lead_growth = ((current_leads - last_leads) / last_leads * 100) if last_leads else 0

    # ===== DEALS GROWTH =====
    current_deals = Deal.objects.filter(
        builder=request.user,
        created_at__date__gte=start_of_month
    ).count()

    last_deals = Deal.objects.filter(
        builder=request.user,
        created_at__date__range=[last_month_start, last_month_end]
    ).count()

    deal_growth = ((current_deals - last_deals) / last_deals * 100) if last_deals else 0

    # ===== REVENUE GROWTH =====
    current_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED",
        created_at__date__gte=start_of_month
    ).aggregate(total=Sum('amount'))['total'] or 0

    last_revenue = Deal.objects.filter(
        builder=request.user,
        status="CLOSED",
        created_at__date__range=[last_month_start, last_month_end]
    ).aggregate(total=Sum('amount'))['total'] or 0

    revenue_growth = ((current_revenue - last_revenue) / last_revenue * 100) if last_revenue else 0

    # ===== LEAD SOURCES =====
    total = Lead.objects.filter(builder=request.user).count()

    search = Lead.objects.filter(builder=request.user, source='search').count()
    referral = Lead.objects.filter(builder=request.user, source='referral').count()
    social = Lead.objects.filter(builder=request.user, source='social').count()
    direct = Lead.objects.filter(builder=request.user, source='direct').count()

    lead_sources = {
        "search": (search / total * 100) if total else 0,
        "referrals": (referral / total * 100) if total else 0,
        "social": (social / total * 100) if total else 0,
        "direct": (direct / total * 100) if total else 0,
    }

    # ===== DEAL LIST =====
    deals = Deal.objects.filter(builder=request.user).order_by('-created_at')

    # ===== CONTEXT =====
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

        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),

        "grouped_followups": dict(grouped_followups),
        "today_followups": today_followups,
        "missed_leads": missed_leads,
        "upcoming_followups": upcoming_followups,

        "deals": deals,
    }

    return render(request, "builder/dashboard.html", context)

@require_POST
def add_lead(request):

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
    # 🔥 activity log
    LeadActivity.objects.create(
        lead=lead,
        message="Lead created"
)


    property_id = request.POST.get("property_id")
    if property_id:
        property = Property.objects.get(id=property_id)
        lead.properties.add(property)

    messages.success(
        request,
        f"Lead '{lead.name}' assigned to {agent.name if agent else 'No Agent'}"
    )

    return redirect("lead_management")

@require_POST
def edit_lead(request, id):
    lead = get_object_or_404(Lead, id=id)

    lead.name = request.POST.get("name")
    lead.email = request.POST.get("email")
    lead.phone = request.POST.get("phone")
    lead.source = request.POST.get("source")
    lead.status = request.POST.get("status")
    lead.assigned_to = request.POST.get("assigned_to")
    lead.interest = request.POST.get("interest")

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

    SavedProperty.objects.create(
        user=request.user,
        property=property
    )

    return redirect('property_list')

@login_required
def builder_property_detail(request, id):
    property = Property.objects.get(id=id)
    amenities_list = ["Parking", "Lift", "Gym", "Pool", "Security", "Garden"]
    leads = Lead.objects.filter(properties=property)

    if request.method == "POST":
        property.title = request.POST.get('title')
        property.location = request.POST.get('location')
        property.price = request.POST.get('price')
        property.description = request.POST.get('description')
        property.status = request.POST.get('status'),
        

        if request.FILES.get('thumbnail'):
            property.thumbnail = request.FILES.get('thumbnail')

        property.save()

    return render(request, "builder/property_detail.html", {
        "property": property,
        "leads": leads
    })
@login_required
def delete_property(request, id):
    property = Property.objects.get(id=id)
    property.delete()
    return redirect('property_management')
@login_required
def assign_property(request):
    leads = Lead.objects.filter(builder=request.user)
    properties = Property.objects.all()
    agents = Agent.objects.filter(builder=request.user)
    print(agents)

    selected_lead_id = request.GET.get('lead')
    selected_lead = None

    if selected_lead_id:
        selected_lead = Lead.objects.get(id=selected_lead_id)

    if request.method == "POST":
        lead_id = request.POST.get("lead_id")
        property_id = request.POST.get("property_id")
        agent_id = request.POST.get("agent_id")

        lead = Lead.objects.get(id=lead_id)
        property_obj = Property.objects.get(id=property_id)
        agent = Agent.objects.get(id=agent_id)

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

        # ✅ Check user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                role="agent"
            )

        # ✅ Prevent duplicate agent (IMPORTANT)
        agent, created = Agent.objects.get_or_create(
            user=user,
            defaults={
                "name": name,
                "email": email,
                "phone": phone,
                "builder": request.user
            }
        )

        # optional: update if already exists
        if not created:
            agent.name = name
            agent.email = email
            agent.phone = phone
            agent.builder = request.user
            agent.save()

        return redirect('create_agent')

    agents = Agent.objects.filter(builder=request.user)

    return render(request, "builder/create_agent.html", {
        "agents": agents
    })

def pipeline(request):

    # POST: update status
    if request.method == "POST":
        lead_id = request.POST.get("lead_id")
        new_status = request.POST.get("status")

        if lead_id and new_status:
            lead = get_object_or_404(Lead, id=lead_id)
            lead.status = new_status
            lead.save()

        return redirect("pipeline")

    # GET: show pipeline
    leads = Lead.objects.filter(builder=request.user).order_by('-created_at')

    context = {
        "columns": [
            ("NEW", leads.filter(status="NEW")),
            ("CONTACTED", leads.filter(status="CONTACTED")),
            ("VISIT", leads.filter(status="VISIT")),
            ("NEGOTIATION", leads.filter(status="NEGOTIATION")),
            ("CLOSED", leads.filter(status="CLOSED")),
        ]
    }

    return render(request, "builder/pipeline.html", context)

@csrf_exempt
def update_lead_status(request):
    if request.method == "POST":
        data = json.loads(request.body)

        lead_id = data.get("lead_id")
        status = data.get("status")

        try:
            lead = Lead.objects.get(id=lead_id)

            lead.status = status
            lead.save()
            LeadActivity.objects.create(
                lead=lead,
                message=f"{request.user.username} changed status to {lead.status}"
            )

            # 🔥 ADD THIS (IMPORTANT)
            LeadActivity.objects.create(
                lead=lead,
                message=f"Status changed to {lead.status}"
            )

            return JsonResponse({"success": True})

        except Lead.DoesNotExist:
            return JsonResponse({"success": False})

    return JsonResponse({"error": "Invalid request"})
def lead_detail_api(request, id):
    lead = Lead.objects.get(id=id)

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
        LeadNote.objects.create(
            lead_id=data['lead_id'],
            note=data['note'],
            created_at=timezone.now()
)         


        return JsonResponse({"success": True})


@csrf_exempt
def update_priority(request):
    if request.method == "POST":
        data = json.loads(request.body)

        lead = Lead.objects.get(id=data['lead_id'])
        lead.priority = data['priority']
        lead.save()

        return JsonResponse({"success": True})
    
def analytics(request):

    leads = Lead.objects.filter(builder=request.user)

    total_leads = leads.count()
    closed_leads = leads.filter(status="CLOSED").count()
    active_leads = leads.exclude(status="CLOSED").count()

    # 🔥 IMPORTANT: price issue fix
    total_revenue = 0  # अगर price नहीं है तो 0 रखो

    # STATUS DATA
    status_counts = {
        "NEW": leads.filter(status="NEW").count(),
        "CONTACTED": leads.filter(status="CONTACTED").count(),
        "SITE VISIT": leads.filter(status="SITE VISIT").count(),
        "NEGOTIATION": leads.filter(status="NEGOTIATION").count(),
        "CLOSED": leads.filter(status="CLOSED").count(),
    }

    # SOURCE DATA
    sources = leads.values('source').annotate(count=Count('id'))
    source_labels = [s['source'] for s in sources]
    source_data = [s['count'] for s in sources]

    # AGENT PERFORMANCE
    agents = []
    for agent in Agent.objects.filter(builder=request.user):
        total = leads.filter(assigned_to=agent).count()

        closed = leads.filter(assigned_to=agent, status="CLOSED").count()

        active = leads.filter(assigned_to=agent).exclude(status="CLOSED").count()

        agents.append({
            "name": agent.name,
            "total": total,
            "closed": closed,
            "active":active
        })

    context = {
        "total_leads": total_leads,
        "closed_leads": closed_leads,
        "active_leads": active_leads,
        "total_revenue": total_revenue,
        "status_data": list(status_counts.values()),
        "source_labels": source_labels,
        "source_data": source_data,
        "agents": agents
    }

    return render(request, "builder/analytics.html", context)



@login_required
def document_management(request):

    if request.method == "POST":
        file = request.FILES.get("file")
        category = request.POST.get("category")

        if file:
            Document.objects.create(
                name=file.name,
                file=file,
                category=category,
                uploaded_by=request.user
            )
            doc = Document.objects.create(
        Notification.objects.create(
            title="Document Uploaded",
            message=f"{doc.name} uploaded",
            type="document"
         )     
            )   
            # 🔥 notification
          
        return redirect('document_management')

    documents = Document.objects.all().order_by('-created_at')

    return render(request, "builder/document_management.html", {
        "documents": documents
    })

@login_required
def delete_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    doc.delete()
    return redirect('document_management')

@login_required
def communication(request):

    conversations = Conversation.objects.all().order_by('-created_at')
    first_chat = conversations.first()

    messages = []
    if first_chat:
        messages = first_chat.messages.all().order_by('created_at')

    return render(request, "builder/communication.html", {
        "conversations": conversations,
        "messages": messages,
        "active_chat": first_chat
    })


@csrf_exempt
def send_message(request):

    data = json.loads(request.body)

    name = data.get("name")
    phone = data.get("phone")
    text = data.get("message")

    # ✅ SAME CONVERSATION ALWAYS
    convo, created = Conversation.objects.get_or_create(
        lead_phone=phone,
        defaults={"lead_name": name}
    )

    Message.objects.create(
        conversation=convo,
        text=text,
        is_agent=False
    )
            # 🔥 ADD THIS
    Notification.objects.create(
        title="New Message",
        message=f"Message from {name}",
        type="message"
        )

    
    return JsonResponse({
        "status": "sent",
        "conversation_id": convo.id   # 🔥 IMPORTANT
    })
@csrf_exempt
def client_send_message(request):

    if request.method == "POST":
        data = json.loads(request.body)

        name = data.get("name", "Guest")
        phone = data.get("phone", "unknown")
        text = data.get("message")

        # conversation create / get
        convo, created = Conversation.objects.get_or_create(
            lead_phone=phone,
            defaults={"lead_name": name}
        )

        # save message
        Message.objects.create(
            conversation=convo,
            text=text,
            is_agent=False
        )

        return JsonResponse({"status": "ok"})

def get_messages(request):

    convo_id = request.GET.get("conversation_id")

    convo = Conversation.objects.filter(id=convo_id).first()

    if not convo:
        return JsonResponse({"messages": []})

    messages = convo.messages.all().order_by('created_at')

    data = []

    for m in messages:
        data.append({
            "text": m.text,
            "is_agent": m.is_agent
        })

    return JsonResponse({"messages": data})

@csrf_exempt
def agent_send_message(request):

    data = json.loads(request.body)

    convo_id = data.get("conversation_id")
    text = data.get("message")

    convo = Conversation.objects.get(id=convo_id)

    Message.objects.create(
        conversation=convo,
        text=text,
        is_agent=True
    )

    return JsonResponse({"status": "sent"})

@csrf_exempt
def create_task(request):

    data = json.loads(request.body)

    Task.objects.create(
        title=data['title'],
        lead_id=data['lead'],
        date=data['date'],
        time=data['time'],
        priority=data['priority']
    )
        # 🔥 notification
    Notification.objects.create(
        title="Task Created",
        message=f"{task.title} scheduled",
        type="task"
    )


    return JsonResponse({"status": "ok"})


def task_done(request, id):

    task = Task.objects.get(id=id)
    task.status = "DONE"
    task.save()

    return JsonResponse({"status": "done"})

def scheduler_overview(request):

    # ✅ Only builder ke tasks
    tasks = Task.objects.filter(user=request.user)

    # ✅ Leads for builder
    leads = Lead.objects.filter(builder=request.user)

    today = date.today()

    # ✅ Current month ke tasks
    tasks = tasks.filter(
        date__year=today.year,
        date__month=today.month
    )

    cal = calendar.monthcalendar(today.year, today.month)

    calendar_days = []

    for week in cal:
        for d in week:
            if d == 0:
                calendar_days.append({"date": "", "tasks": []})
            else:
                day_tasks = tasks.filter(date__day=d)

                calendar_days.append({
                    "date": d,
                    "tasks": day_tasks
                })

    return render(request, "builder/scheduler_overview.html", {
        "tasks": tasks,
        "leads": leads,
        "calendar_days": calendar_days,
        "today": today
    })
@csrf_exempt
def reorder_task(request):

    data = json.loads(request.body)
    task = Task.objects.get(id=data['task_id'])
    task.order = data['position']
    task.save()
    

    return JsonResponse({"status": "ok"})


def check_reminders(request):

    today = date.today()   # ✅ ADD THIS
    count = Task.objects.filter(date=today, status='PENDING').count()

    return JsonResponse({"count": count})


def notifications_page(request):
    Notification.objects.create(
    title="New Lead Assigned",
    message=f"{lead.name} assigned to {agent.name}",
    type="lead"
)

    notifications = Notification.objects.all().order_by('-created_at')

    return render(request, "builder/notifications.html", {
        "notifications": notifications
    })
@csrf_exempt
def mark_notification_read(request, id):
    n = Notification.objects.get(id=id)
    n.is_read = True
    n.save()

    return JsonResponse({"status": "ok"})
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from django.core.exceptions import FieldError
# अपने मॉडल्स को यहाँ सही से इम्पोर्ट रखें (उदा. from .models import Agent, Lead, Deal)

@login_required
def agent_performance(request):

    agents = Agent.objects.filter(builder=request.user)

    selected_agent = request.GET.get("agent")
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    data = []
    chart_labels = []
    chart_data = []

    total_revenue = 0
    total_deals = 0

    for agent in agents:

        # LEADS
        leads = Lead.objects.filter(assigned_to=agent)

        # DEALS (FIX: CLOSED)
        deals = Deal.objects.filter(agent=agent, status="CLOSED")

        # FILTER APPLY
        if start_date and end_date:
            leads = leads.filter(created_at__range=[start_date, end_date])
            deals = deals.filter(created_at__range=[start_date, end_date])

        # SINGLE AGENT FILTER
        if selected_agent:
            if str(agent.id) != selected_agent:
                continue

        total_leads = leads.count()
        closed_deals = deals.count()

        revenue = deals.aggregate(total=Sum('amount'))['total'] or 0

        total_revenue += revenue
        total_deals += closed_deals

        # CONVERSION SAFE
        conversion = (closed_deals / total_leads * 100) if total_leads else 0

        data.append({
            "id": agent.id,
            "name": agent.name,
            "total_leads": total_leads,
            "closed_deals": closed_deals,
            "revenue": revenue,
            "conversion": round(conversion, 1)
        })

        # CHART (ONLY FILTERED AGENTS)
        chart_labels.append(agent.name)
        chart_data.append(float(revenue))

    # SORT BY REVENUE
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

    agent = Agent.objects.get(id=id)

    leads = Lead.objects.filter(agent=agent)
    deals = Deal.objects.filter(agent=agent)

    revenue = deals.aggregate(total=Sum('amount'))['total'] or 0

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

    for agent in Agent.objects.filter(builder=request.user):
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

        scored_leads.append({
            "lead": lead,
            "score": score,
            "intent": intent
        })

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

    # ✅ CHART DATA (यही तुम पूछ रहे थे)
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
            type=request.POST.get('type', ''),  # ✅ FIX
            reach=request.POST.get('reach'),
            clicked=request.POST.get('clicked'),
            conversion=request.POST.get('conversion'),
            image=request.FILES.get('image')
        )
        return redirect('/builder/marketing/')

    return render(request, 'builder/create_campaign.html')


def run_campaign(request, id):
    campaign = Campaign.objects.get(id=id)

    # dummy automation logic
    campaign.sent += 100
    campaign.opened += 60
    campaign.clicked += 20
    campaign.save()

    return redirect('marketing_automation')


def delete_campaign(request, id):
    campaign = get_object_or_404(Campaign, id=id)
    campaign.delete()
    return redirect('/builder/marketing/')

@login_required
def manage_users(request):
    query = request.GET.get('q')
    role_filter = request.GET.get('role')

    # 🔒 SAFE FILTER
    agents = Agent.objects.filter(builder=request.user).order_by('-id')

    # 🔍 SEARCH
    if query:
        agents = agents.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )

    # 🎯 FILTER
    if role_filter:
        agents = agents.filter(role=role_filter)

    return render(request, 'builder/manage_users.html', {
        'agents': agents
    })


# ❌ DELETE
@login_required
def delete_agent(request, id):
    agent = get_object_or_404(Agent, id=id, builder=request.user)
    agent.delete()
    return redirect('manage_users')


# 🔄 TOGGLE STATUS
@login_required
def toggle_agent(request, id):
    agent = get_object_or_404(Agent, id=id, builder=request.user)
    agent.is_active = not agent.is_active
    agent.save()
    return redirect('manage_users')

def register_user(request):
    if request.method == "POST":
        user = User.objects.create_user(
            username=request.POST['username'],
            password=request.POST['password']
        )

        Agent.objects.create(
            user=user,
            name=request.POST['username'],
            email="",
            phone="",
            role="Agent"
        )

        return redirect('/login/')
    

def delete_lead(request, id):
    lead = get_object_or_404(Lead, id=id)

    if request.method == "POST":
        if lead.builder == request.user:
            lead.delete()
            messages.success(request, "Lead deleted successfully")
        else:
            messages.error(request, "Permission denied")

    return redirect('lead_management')

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

    # ===== LEADS =====
    leads = Lead.objects.filter(
        assigned_to=agent,
        builder=agent.builder
    )

    # ===== LEAD STATS =====
    total_leads = leads.count()
    hot = leads.filter(status="HOT").count()
    warm = leads.filter(status="WARM").count()
    cold = leads.filter(status="COLD").count()

    # ===== VISITS =====
    visits = SiteVisit.objects.filter(agent=agent)
    today_visits = visits.filter(date=date.today()).count()

    # ===== TASKS =====
    tasks = Task.objects.filter(
        lead__assigned_to=agent,
        status="PENDING"
    )

    # ===== TODAY FOLLOWUPS =====
    today_followups = FollowUp.objects.filter(
        agent=agent,
        date=date.today(),
        status="PENDING"
    )

    # ===== DEALS =====
    deals = Deal.objects.filter(agent=agent)
    total_deals = deals.count()

    # ===== CONTEXT =====
    context = {
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
    }

    return render(request, "agent/agent_dashboard.html", context)

@login_required
def agent_leads(request):
   
    # 🔐 SECURITY (FINAL CLEAN FIX)
    if not hasattr(request.user, 'agent_profile'):
        return redirect("login")

    agent = request.user.agent_profile

    leads = Lead.objects.filter(assigned_to=agent).order_by('-created_at')

    # 🔍 Search
    q = request.GET.get('q')
    if q:
        leads = leads.filter(
            Q(name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )

    # 🎯 Status filter
    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)

    # 📊 Sorting
    sort = request.GET.get('sort')
    if sort == "old":
        leads = leads.order_by('created_at')
    else:
        leads = leads.order_by('-created_at')

    # ✅ ACTIVE
    active_leads = leads.exclude(deals__status__in=["CLOSED", "FAILED"]).distinct()

    # ✅ SUCCESS
    success_leads = leads.filter(deals__status__in=["CLOSED", "FAILED"]).distinct()

    return render(request, "agent/agent_leads.html", {
        "leads": active_leads,
        "success_leads": success_leads,
    })
def delete_lead(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, agent=request.user)
    lead.delete()
    return redirect("agent_leads")

@login_required
def agent_properties(request):
    agent = request.user.agent_profile

    # 🔥 Step 1: agent ki leads
    leads = Lead.objects.filter(assigned_to=agent)

    # 🔥 Step 2: un leads ki properties ONLY
    properties = Property.objects.filter(
        interested_leads__in=leads
    ).annotate(
        demand=Count('interested_leads')
    ).order_by('-demand').distinct()

    properties = Property.objects.filter(
    interested_leads__assigned_to=agent,
    interested_leads__builder=request.user
    ).distinct()

    return render(request, "agent/agent_properties.html", {
        "properties": properties
    })

@login_required
def agent_profile(request):
    agent = request.user.agent_profile  # OneToOne relation assumed

    # 📊 stats
    total_leads = Lead.objects.filter(assigned_to=agent).count()
    hot_leads = Lead.objects.filter(assigned_to=agent, status='HOT').count()

    visits = SiteVisit.objects.filter(agent=agent)
    total_visits = visits.count()
    completed_visits = visits.filter(status='DONE').count()

    # 💰 conversion rate
    conversion_rate = 0
    if total_leads > 0:
        conversion_rate = round((completed_visits / total_leads) * 100, 2)

    context = {
        "agent": agent,
        "total_leads": total_leads,
        "hot_leads": hot_leads,
        "total_visits": total_visits,
        "completed_visits": completed_visits,
        "conversion_rate": conversion_rate,
    }

    return render(request, "agent/agent_profile.html", context)


@login_required
def scheduler(request):
    agent = request.user.agent_profile

    leads = Lead.objects.filter(assigned_to=agent)

    visits = SiteVisit.objects.filter(agent=agent).order_by('-date')
    property_id = request.POST.get('property')

    if request.method == "POST":
        lead_id = request.POST.get("lead")
        date = request.POST.get("date")
        time = request.POST.get("time")

        SiteVisit.objects.create(
            property_id=property_id,
            lead_id=lead_id,
            agent=agent,
            date=date,
            time=time
        )

        return redirect("scheduler")

    return render(request, "agent/scheduler.html", {
        "leads": leads,
        "visits": visits
    })

def property_leads(request, property_id):
    leads = Lead.objects.filter(property_id=property_id)

    return render(request, "agent/property_leads.html", {
        "leads": leads
    })
@login_required
def site_visits(request):
    return render(request, "agent/scheduler.html")

@login_required
def settings_view(request):
    user = request.user

    if request.method == "POST":

        # PROFILE UPDATE
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.phone = request.POST.get("phone")

        # IMAGE
        if request.FILES.get("profile_image"):
            user.profile_image = request.FILES.get("profile_image")

        user.save()

        # PASSWORD CHANGE
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
    property = Property.objects.first()  # या कोई logic
    return render(request, "public/privacy.html", {
        "property": property
    })

def auto_assign_agent(builder):
    agents = list(Agent.objects.filter(builder=builder).order_by('id'))
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
                "phone": instance.phone or "",
                "builder": None  # ya default builder
            }
        )

import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Lead  # अपने सही मॉडल इम्पोर्ट का उपयोग करें

@login_required
def export_leads_csv(request):
    # HTTP Response को CSV Content-Type के साथ सेट करें
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_report.csv"'

    writer = csv.writer(response)
    # CSV के कॉलम हेडर (Headers)
    writer.writerow(['Lead Name', 'Email', 'Phone', 'Source', 'Status', 'Assigned Agent', 'Properties'])

    # केवल इस बिल्डर से जुड़े लीड्स प्राप्त करें
    leads = Lead.objects.filter(builder=request.user)

    # अगर यूज़र ने कोई सर्च क्वेरी डाली हुई है, तो उसी हिसाब से फ़िल्टर करें
    search_query = request.GET.get('q')
    if search_query:
        leads = leads.filter(name__icontains=search_query) | leads.filter(email__icontains=search_query)

    for lead in leads:
        # एजेंट का नाम निकालें
        agent_name = lead.assigned_to.name if lead.assigned_to else "Not Assigned"
        
        # प्रॉपर्टीज़ के नाम कॉमा (,) से अलग करके एक लाइन में लाएं
        properties_list = ", ".join([p.title for p in lead.properties.all()]) if lead.properties.exists() else "-"

        # CSV में रो (Row) राइट करें
        writer.writerow([
            lead.name,
            lead.email,
            lead.phone,
            lead.source,
            lead.status,
            agent_name,
            properties_list
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
        reply = ""

        if "hi" in msg:
            reply = "Welcome to Smart Realty 🏠\n1 Residential\n2 Commercial"

        else:
            reply = "Type Hi"

        resp.message(reply)
        return HttpResponse(str(resp), content_type="application/xml")
    
from decimal import Decimal

from decimal import Decimal

def add_deal(request):
    if request.method == "POST":
        property_id = request.POST.get('property_id')
        lead_id = request.POST.get('lead_id')   # 🔥 IMPORTANT
        client_name = request.POST.get('client_name') or "Unknown"
        amount = request.POST.get('amount')
        status = request.POST.get('status')

        property_obj = get_object_or_404(Property, id=property_id)

        # 🔥 GET LEAD (IMPORTANT FIX)
        lead = None
        if lead_id:
            lead = get_object_or_404(Lead, id=lead_id)

        # 💰 amount fix
        if amount:
            amount = amount.lower().replace("lakh", "00000").replace(",", "")
            amount = Decimal(amount)
        else:
            amount = Decimal(0)

        # 👤 agent
        agent = get_object_or_404(Agent, user=request.user)

        # 🔥 FINAL DEAL CREATE (MOST IMPORTANT)
        Deal.objects.create(
            lead=lead,                      # ✅ LINK WITH LEAD (CRITICAL)
            property=property_obj,
            client_name=client_name,
            amount=amount,
            status=status,
            agent=agent,
            builder=property_obj.builder   # ✅ BUILDER LINK (CRITICAL)
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
    lead = Lead.objects.get(id=lead_id)

    if request.method == "POST":
        date = request.POST.get("date")
        time = request.POST.get("time")
        note = request.POST.get("note")

        FollowUp.objects.create(
            lead=lead,
            agent=request.user.agent,
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