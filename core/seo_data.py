from django.utils.text import slugify

# Sirf Ahmedabad city/AMC-AUDA belt ki areas — Gandhinagar side ki koi bhi
# locality (Sargasan, Kudasan, Adalaj, Koba, Randesan, Raysan, Sughad, Bhat,
# Gandhinagar Road, New CG Road, GIFT City corridor) is list me NAHI hai.
# Wo sab GANDHINAGAR_AREAS list me alag rakhi hain (neeche).
AHMEDABAD_AREAS = [
    "Satellite", "Vastrapur", "Bodakdev", "Thaltej", "SG Highway", "Prahlad Nagar",
    "Navrangpura", "Ellisbridge", "Paldi", "Vasna", "Maninagar", "Isanpur", "Bhadaj",
    "Ghatlodia", "Naranpura", "Ranip", "Chandkheda", "Motera", "Sabarmati",
    "Gota", "Vaishnodevi", "Chandlodia", "Vejalpur", "Jodhpur", "Ambawadi", "Shahibaug",
    "Naroda", "Nikol", "Vastral", "Bapunagar", "Odhav", "Kubernagar",
    "Rakhial", "Amraiwadi", "Gomtipur", "Khokhra", "Kankaria", "Danilimda",
    "Vatva", "Lambha", "Narol", "Sarkhej", "Juhapura", "Makarba",
    "Ghuma", "South Bopal", "Bopal", "Shela", "Shilaj", "Science City", "Science Park",
    "Chharodi", "Nava Vadaj", "Vadaj", "Usmanpura", "Memnagar", "Gulbai Tekra",
    "Panjrapole", "C.G. Road", "Law Garden", "Navjivan", "Income Tax", "Stadium",
    "Nehru Nagar", "Judges Bungalow Road", "Iscon", "Iskon Ambli", "Anand Nagar", "Manekbaug",
    "Jivraj Park", "Vishala", "Nirnaynagar", "Chenpur", "Zundal", "Jagatpur", "Tragad",
    "Sindhubhavan Road", "Vaishnodevi Circle",
    "Sarangpur", "Kalupur", "Raikhad", "Dariapur", "Jamalpur",
    "Khadia", "Shahpur", "Dudheshwar", "Saraspur", "Rajpur", "Meghaninagar",
]

# Gandhinagar side ki localities — inhe kabhi bhi "...in Ahmedabad" wale
# section (Trending Localities, Most Searched Projects) me nahi dikhana.


BHK_OPTIONS = ["1", "2", "3", "4", "5"]


def get_area_by_slug(location_slug):
    """URL slug (e.g. 'sg-highway') se actual area name (e.g. 'SG Highway') dhoondta hai."""
    for area in AHMEDABAD_AREAS:
        if slugify(area) == location_slug:
            return area
    return None


def get_area_slug(area_name):
    return slugify(area_name)

# =============================================================================
# SEO INTERNAL-LINK SECTIONS (homepage + listing page "explore" blocks)
# Used by core/views.py -> get_seo_explore_context() and rendered by
# frontend/templates/components/seo_explore_links.html
# =============================================================================

# "Popular Apartment Configurations" — BHK links use ?beds=, others use ?type=
CONFIG_LINKS = [
    {"label": "1 BHK Flats in Ahmedabad", "params": "beds=1"},
    {"label": "2 BHK Flats in Ahmedabad", "params": "beds=2"},
    {"label": "3 BHK Flats in Ahmedabad", "params": "beds=3"},
    {"label": "4 BHK Flats in Ahmedabad", "params": "beds=4"},
    {"label": "5 BHK Flats in Ahmedabad", "params": "beds=5"},
    {"label": "Bungalows in Ahmedabad", "params": "type=Bungalow"},
    {"label": "Duplex in Ahmedabad", "params": "type=Duplex"},
    {"label": "Penthouse in Ahmedabad", "params": "type=Penthouse"},
    {"label": "Villa in Ahmedabad", "params": "type=Villa"},
    {"label": "Plots in Ahmedabad", "params": "type=Plot"},
    {"label": "Farmhouse in Ahmedabad", "params": "type=Farmhouse"},
]

# "Budget Collections" — min/max price use the same unit ('L' or 'Cr') the
# property_list filter already understands (min_price_unit / max_price_unit)
BUDGET_LINKS = [
    {
        "label": "Properties Under ₹50 Lakh",
        "params": "max_price=50&max_price_unit=L",
    },
    {
        "label": "₹50 Lakh - ₹1 Cr",
        "params": "min_price=50&min_price_unit=L&max_price=1&max_price_unit=Cr",
    },
    {
        "label": "₹1 Cr - ₹2 Cr",
        "params": "min_price=1&min_price_unit=Cr&max_price=2&max_price_unit=Cr",
    },
    {
        "label": "₹2 Cr - ₹5 Cr",
        "params": "min_price=2&min_price_unit=Cr&max_price=5&max_price_unit=Cr",
    },
    {
        "label": "Luxury Properties Above ₹5 Cr",
        "params": "min_price=5&min_price_unit=Cr",
    },
]

# Areas to feature first under "Trending Localities" when they exist in the
# database — falls back to the front of AHMEDABAD_AREAS if none match yet.
TRENDING_LOCALITY_SEED = [
    "Shela", "Zundal", "South Bopal", "Iskon Ambli", "Vaishnodevi",
    "Shilaj", "Gota", "Jagatpur", "Tragad", "Thaltej", "Chharodi",
]


def _ahmedabad_only(properties_qs):
    """Property queryset ko sirf Ahmedabad ki listings tak filter karta hai.
    Location text me Gandhinagar ka naam ho, ya GANDHINAGAR_AREAS me se
    koi bhi area ka naam ho, aisi properties ko explicitly bahar rakha jaata hai —
    isliye Gandhinagar ki property "Ahmedabad" section me kabhi nahi aayegi,
    chahe uska location text kuch bhi likha ho."""
    from django.db.models import Q

    include_q = Q()
    for area in AHMEDABAD_AREAS:
        include_q |= Q(location__icontains=area)

    exclude_q = Q(location__icontains="Gandhinagar")
    for area in GANDHINAGAR_AREAS:
        exclude_q |= Q(location__icontains=area)

    return properties_qs.filter(include_q).exclude(exclude_q)


def get_seo_explore_context(properties_qs=None, limit_projects=None, limit_localities=None):
    """
    Builds the link data for the homepage / listing-page 'explore' section
    (Popular Apartment Configurations, Budget Collections, Trending
    Localities, Most Searched Projects) seen across the site's SEO pages.

    Default behaviour (limit_projects / limit_localities = None) is to
    return EVERY Ahmedabad project and EVERY Ahmedabad locality — the
    template decides how many to show up-front and reveals the rest via a
    "show more" toggle, so nothing is hidden from Google or from the user,
    it's just visually collapsed.

    Pass the already-filtered Property queryset for the current page when
    available so 'Most Searched Projects' reflects real, live listings
    instead of only the static seed list.
    """
    trending_localities = list(TRENDING_LOCALITY_SEED)
    popular_projects = []

    if properties_qs is not None:
        try:
            from django.db.models import Count

            from django.db.models import Value, CharField
            from django.db.models.functions import Coalesce

            ahmedabad_qs = _ahmedabad_only(properties_qs).annotate(
                display_name=Coalesce(
                    "project_name", "title", Value(""), output_field=CharField()
                )
            )
            popular_projects_qs = (
                ahmedabad_qs.exclude(display_name__exact="")
                .values("display_name")
                .annotate(total=Count("id"))
                .order_by("-total")
            )
            if limit_projects:
                popular_projects_qs = popular_projects_qs[:limit_projects]
            popular_projects = [p["display_name"] for p in popular_projects_qs]
        except Exception:
            popular_projects = []

    # Ahmedabad ki har area trending-localities me aa jaaye — seed wali areas
    # sabse upar, baaki AHMEDABAD_AREAS list se bharta hai (koi bhi Gandhinagar
    # area is list me hai hi nahi, isliye yahan alag se filter nahi karna padta).
    for area in AHMEDABAD_AREAS:
        if area not in trending_localities:
            trending_localities.append(area)

    if limit_localities:
        trending_localities = trending_localities[:limit_localities]

    return {
        "seo_config_links": CONFIG_LINKS,
        "seo_budget_links": BUDGET_LINKS,
        "seo_trending_localities": [
            {"name": a, "slug": get_area_slug(a)}
            for a in trending_localities
        ],
        "seo_popular_projects": popular_projects,
    }