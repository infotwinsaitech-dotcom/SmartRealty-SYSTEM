"""
core/seo_property.py

Property detail page ke liye SEO data ek jagah se banata hai:
  - <title>            (project name pehle, Housing/99acres jaisa)
  - meta description   (facts: BHK, sq.ft, status, possession, price, RERA)
  - og / twitter image (Cloudinary se 1200px crop)
  - JSON-LD            (Product + RealEstateListing, price range, rating, images)

Ye sab view se context me `seo` naam se template ko milta hai.
Rating sirf tab jaati hai jab approved reviews asli me maujood hon
(fake rating daalna Google ki policy ke khilaf hai).
"""
import json
import re
from decimal import Decimal, InvalidOperation

TITLE_MAX = 60
DESC_MAX = 158


# --------------------------------------------------------------------------
# price helpers  (price / starting_price / max_price me number + price_unit "L"/"Cr")
# --------------------------------------------------------------------------
def _num(value):
    """'85', '1,25.5', ' 1.5 ' -> Decimal. 'Price on Request' / blank -> None."""
    if value is None:
        return None
    text = str(value).replace(",", "").replace("₹", "").strip()
    if not text or not re.fullmatch(r"\d+(\.\d+)?", text):
        return None
    try:
        n = Decimal(text)
    except InvalidOperation:
        return None
    return n if n > 0 else None


def _to_rupees(n, unit):
    if n is None:
        return None
    return int(n * (Decimal("10000000") if unit == "Cr" else Decimal("100000")))


def _fmt_price(n, unit):
    """Decimal('85.50'), 'L' -> '₹85.5 Lakh'  /  Decimal('1.5'), 'Cr' -> '₹1.5 Cr'"""
    if n is None:
        return ""
    s = format(n.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"₹{s} {'Cr' if unit == 'Cr' else 'Lakh'}"


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _first_type(prop):
    raw = _clean(prop.property_type) or "Flat"
    return raw.split(",")[0].strip() or "Flat"


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------
def _cloud_url(public_id, **opts):
    from cloudinary.utils import cloudinary_url

    url, _ = cloudinary_url(
        public_id, secure=True, fetch_format="auto", quality="auto", crop="fill", **opts
    )
    return url


def _public_id(field):
    if not field:
        return None
    return getattr(field, "public_id", None) or (str(field) or None)


def _image_urls(prop):
    """Google ko 3 aspect ratio (16:9, 4:3, 1:1) chahiye thumbnail ke liye."""
    pid = _public_id(getattr(prop, "thumbnail", None))
    if not pid:
        try:
            first = prop.images.all()[0] if prop.images.all() else None
            pid = _public_id(first.image) if first else None
        except Exception:
            pid = None
    if not pid:
        return None, []
    try:
        og = _cloud_url(pid, width=1200, height=630)
        urls = [
            _cloud_url(pid, width=1200, height=675),  # 16:9
            _cloud_url(pid, width=1200, height=900),  # 4:3
            _cloud_url(pid, width=1200, height=1200),  # 1:1
        ]
        return og, urls
    except Exception:
        return None, []


# --------------------------------------------------------------------------
# title / description
# --------------------------------------------------------------------------
def _title(prop, name, loc, bhk):
    flats = f"{bhk} BHK {_first_type(prop)}s" if bhk else f"{_first_type(prop)}s"
    candidates = [
        f"{name} in {loc}, Ahmedabad – {flats} | RealShree",
        f"{name} in {loc}, Ahmedabad | RealShree",
        f"{name} in {loc}, Ahmedabad",
        f"{name} in {loc}",
    ]
    for c in candidates:
        if len(c) <= TITLE_MAX:
            return c
    # bahut lamba naam: word boundary par kaato (beech shabd me nahi)
    cut = candidates[-1][: TITLE_MAX - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,&-–") + "…"


def _description(prop, name, loc, bhk, price_low_txt, price_high_txt):
    first = f"{name} in {loc}, Ahmedabad"
    if bhk:
        first += f" offers {bhk} BHK {_first_type(prop)}s"
    if getattr(prop, "sqft", 0):
        first += f" of {prop.sqft} sq.ft"
    facts = [first + "."]

    status = _clean(getattr(prop, "project_status", ""))
    poss = _clean(getattr(prop, "possession_date", ""))
    if status and poss:
        facts.append(f"{status}, possession {poss}.")
    elif status:
        facts.append(f"{status}.")
    elif poss:
        facts.append(f"Possession {poss}.")

    if price_low_txt and price_high_txt and price_low_txt != price_high_txt:
        facts.append(f"{price_low_txt} to {price_high_txt}.")
    elif price_low_txt:
        facts.append(f"Starting {price_low_txt}.")

    if getattr(prop, "rera_number", None):
        facts.append("RERA registered.")
    facts.append("Zero brokerage, free site visit on RealShree.")

    out = ""
    for f in facts:  # priority order me jodo, limit par ruk jao
        nxt = (out + " " + f).strip()
        if len(nxt) > DESC_MAX:
            break
        out = nxt
    return out or facts[0][:DESC_MAX]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build_property_seo(prop, site_domain, rating_summary=None):
    site = site_domain.rstrip("/")
    name = _clean(prop.project_name) or _clean(prop.title)
    loc = _clean(prop.location)
    bhk = _clean(prop.beds)
    unit = prop.price_unit or "L"
    url = site + prop.get_absolute_url()

    low_n = _num(getattr(prop, "starting_price", None)) or _num(prop.price)
    high_n = _num(getattr(prop, "max_price", None))
    if low_n and high_n and high_n < low_n:
        low_n, high_n = high_n, low_n
    low_txt, high_txt = _fmt_price(low_n, unit), _fmt_price(high_n, unit)

    title = _title(prop, name, loc, bhk)
    description = _description(prop, name, loc, bhk, low_txt, high_txt)
    og_image, image_urls = _image_urls(prop)

    # ---------------- JSON-LD ----------------
    avail = "https://schema.org/InStock"
    if prop.status == "Sold Out":
        avail = "https://schema.org/SoldOut"
    elif prop.status == "Coming Soon":
        avail = "https://schema.org/PreOrder"

    seller = _clean(getattr(prop, "builder_name", "")) or "RealShree"
    data = {
        "@context": "https://schema.org",
        "@type": ["Product", "RealEstateListing"],
        "name": f"{name} in {loc}, Ahmedabad" + (f" – {bhk} BHK" if bhk else ""),
        "description": description,
        "url": url,
        "sku": f"RS-{prop.pk}",
        "category": "Real Estate",
        "datePosted": prop.created_at.strftime("%Y-%m-%d") if prop.created_at else None,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": loc,
            "addressRegion": "Gujarat",
            "addressCountry": "IN",
        },
    }
    if image_urls:
        data["image"] = image_urls
    if getattr(prop, "builder_name", None):
        data["brand"] = {"@type": "Brand", "name": _clean(prop.builder_name)}
    if bhk:
        data["numberOfRooms"] = bhk
    if getattr(prop, "baths", 0):
        data["numberOfBathroomsTotal"] = prop.baths
    if getattr(prop, "sqft", 0):
        data["floorSize"] = {
            "@type": "QuantitativeValue",
            "value": prop.sqft,
            "unitCode": "FTK",
        }
    if prop.latitude is not None and prop.longitude is not None:
        data["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(prop.latitude),
            "longitude": float(prop.longitude),
        }

    low_r, high_r = _to_rupees(low_n, unit), _to_rupees(high_n, unit)
    if low_r:
        if high_r and high_r != low_r:
            offer = {"@type": "AggregateOffer", "lowPrice": low_r, "highPrice": high_r}
        else:
            offer = {"@type": "Offer", "price": low_r}
        offer.update(
            {
                "priceCurrency": "INR",
                "availability": avail,
                "url": url,
                "seller": {"@type": "Organization", "name": seller},
            }
        )
        data["offers"] = offer

    if rating_summary and rating_summary.get("count"):
        data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": rating_summary["overall"],
            "reviewCount": rating_summary["count"],
            "bestRating": 5,
            "worstRating": 1,
        }

    data = {k: v for k, v in data.items() if v is not None}
    json_ld = (
        json.dumps(data, ensure_ascii=False, indent=2)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

    return {
        "title": title,
        "description": description,
        "og_title": f"{name} in {loc}, Ahmedabad",
        "og_image": og_image,
        "canonical": url,
        "json_ld": json_ld,
    }


def build_property_seo_safe(prop, site_domain, rating_summary=None):
    """SEO helper me kuch bhi fail ho to page 500 na de; basic fallback milta hai."""
    try:
        return build_property_seo(prop, site_domain, rating_summary)
    except Exception:  # pragma: no cover
        import logging

        logging.getLogger("core").exception("SEO build failed for property %s", getattr(prop, "pk", "?"))
        name = _clean(getattr(prop, "project_name", "")) or _clean(getattr(prop, "title", ""))
        loc = _clean(getattr(prop, "location", ""))
        return {
            "title": f"{name} in {loc}, Ahmedabad | RealShree"[:TITLE_MAX],
            "description": f"{name} in {loc}, Ahmedabad. View details, photos and book a free site visit on RealShree.",
            "og_title": f"{name} in {loc}, Ahmedabad",
            "og_image": None,
            "canonical": site_domain.rstrip("/") + prop.get_absolute_url(),
            "json_ld": "",
        }
