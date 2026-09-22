from django.utils.text import slugify

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
    "Nehru Nagar", "Judges Bungalow Road", "Iscon", "Anand Nagar", "Manekbaug",
    "Jivraj Park", "Vishala", "Nirnaynagar", "Chenpur", "Sughad", "Zundal",
    "Gandhinagar Road", "Adalaj", "Koba", "Randesan", "Kudasan", "New CG Road",
    "Bhat", "Sarangpur", "Kalupur", "Raikhad", "Dariapur", "Jamalpur",
    "Khadia", "Shahpur", "Dudheshwar", "Saraspur", "Rajpur", "Meghaninagar",
]

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
    "Shela", "Zundal", "Sargasan", "South Bopal", "Iskon Ambli", "Vaishnodevi",
    "Shilaj", "Gota", "Jagatpur", "Tragad", "Thaltej", "Chharodi",
]


def get_seo_explore_context(properties_qs=None, limit_projects=12, limit_localities=12):
    """
    Builds the link data for the homepage / listing-page 'explore' section
    (Popular Apartment Configurations, Budget Collections, Trending
    Localities, Most Searched Projects) seen across the site's SEO pages.

    Pass the already-filtered Property queryset for the current page when
    available so 'Most Searched Projects' and 'Trending Localities' reflect
    real, live listings instead of only the static seed list.
    """
    trending_localities = list(TRENDING_LOCALITY_SEED)
    popular_projects = []

    if properties_qs is not None:
        try:
            from django.db.models import Count

            popular_projects = list(
                properties_qs.exclude(project_name__isnull=True)
                .exclude(project_name__exact="")
                .values("project_name")
                .annotate(total=Count("id"))
                .order_by("-total")[:limit_projects]
            )
            popular_projects = [p["project_name"] for p in popular_projects]
        except Exception:
            popular_projects = []

    for area in AHMEDABAD_AREAS:
        if len(trending_localities) >= limit_localities:
            break
        if area not in trending_localities:
            trending_localities.append(area)

    return {
        "seo_config_links": CONFIG_LINKS,
        "seo_budget_links": BUDGET_LINKS,
        "seo_trending_localities": [
            {"name": a, "slug": get_area_slug(a)}
            for a in trending_localities[:limit_localities]
        ],
        "seo_popular_projects": popular_projects,
    }