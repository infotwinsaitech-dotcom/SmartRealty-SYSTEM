#!/usr/bin/env python3
"""
SmartRealty / RealShree  -  property page SEO patch

Kaise chalana hai (project ke root folder me, jahan manage.py hai):
    python apply_seo_patch.py            # is file ke saath seo_property.py bhi rakho

Ye 4 kaam karta hai (har file ka .bak_seo backup banta hai, dobara chalane par kuch nahi badlta):
  1. core/seo_property.py          -> naya helper copy karta hai
  2. core/views.py                 -> property_detail me `seo` context jodta hai
  3. public/property_detail.html   -> title, description, og/twitter, canonical, JSON-LD badalta hai
  4. public/base.html              -> <title> ko page-wise override hone layak banata hai
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()

VIEWS = ROOT / "core" / "views.py"
DETAIL = ROOT / "frontend" / "templates" / "public" / "property_detail.html"
BASE = ROOT / "frontend" / "templates" / "public" / "base.html"
HELPER_SRC = HERE / "seo_property.py"
HELPER_DST = ROOT / "core" / "seo_property.py"


def die(msg):
    print(f"\n[ERROR] {msg}\nKuch bhi change nahi kiya gaya (ya sirf pehle wale steps hue; .bak_seo se restore kar sakte ho).")
    sys.exit(1)


def read(path):
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def write(path, text, crlf):
    backup = path.with_name(path.name + ".bak_seo")
    if not backup.exists():
        shutil.copy2(path, backup)
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


# ------------------------------------------------------------------ checks
if not (ROOT / "manage.py").exists():
    die("Ye script project root (jahan manage.py hai) se chalao.")
for p in (VIEWS, DETAIL, BASE, HELPER_SRC):
    if not p.exists():
        die(f"File nahi mili: {p}")

# ------------------------------------------------------------------ 1. helper
shutil.copy2(HELPER_SRC, HELPER_DST)
print("1/4  core/seo_property.py copy ho gaya")

# ------------------------------------------------------------------ 2. views.py
text, crlf = read(VIEWS)
if "build_property_seo" in text:
    print("2/4  views.py pehle se patched hai, skip")
else:
    m = re.search(r"\ndef property_detail\(request, id, slug=None\):.*?(?=\n(?:@\w|def )\w)", text, re.S)
    if not m:
        die("views.py me property_detail() nahi mila.")
    body = m.group(0)

    anchor_doc = '    """Property detail with inquiry form"""\n'
    anchor_ctx = '        "floor_plans": floor_plans,\n    })'
    if anchor_doc not in body or anchor_ctx not in body:
        die("views.py property_detail ka structure alag hai; patch manually lagana padega.")

    new_body = body.replace(
        anchor_doc, anchor_doc + "    from core.seo_property import build_property_seo_safe\n", 1
    ).replace(
        anchor_ctx,
        '        "floor_plans": floor_plans,\n'
        '        "seo": build_property_seo_safe(property, SITE_DOMAIN, rating_summary),\n    })',
        1,
    )
    write(VIEWS, text.replace(body, new_body, 1), crlf)
    print("2/4  views.py patched")

# ------------------------------------------------------------------ 3. property_detail.html
text, crlf = read(DETAIL)
if "seo.json_ld" in text:
    print("3/4  property_detail.html pehle se patched hai, skip")
else:
    # (a) title / description / og / canonical blocks
    pat_blocks = re.compile(
        r"\{% block title %\}.*?\{% block canonical_url %\}.*?\{% endblock %\}\n", re.S
    )
    new_blocks = (
        "{% block full_title %}{{ seo.title }}{% endblock %}\n"
        "{% block meta_description %}{{ seo.description }}{% endblock %}\n"
        "{% block og_title %}{{ seo.og_title }}{% endblock %}\n"
        "{% block og_description %}{{ seo.description }}{% endblock %}\n"
        "{% block og_image %}{% if seo.og_image %}{{ seo.og_image }}{% else %}"
        "https://www.realshree.com{% static 'images/logo.png' %}{% endif %}{% endblock %}\n"
        "{% block canonical_url %}{{ seo.canonical }}{% endblock %}\n"
    )
    text, n1 = pat_blocks.subn(lambda _: new_blocks, text, count=1)

    # (b) twitter tags
    text, n2 = re.subn(
        r'<meta name="twitter:title" content=".*?">',
        '<meta name="twitter:title" content="{{ seo.og_title }}">',
        text, count=1,
    )
    text, n3 = re.subn(
        r'<meta name="twitter:description" content=".*?">',
        '<meta name="twitter:description" content="{{ seo.description }}">',
        text, count=1,
    )
    text, n4 = re.subn(
        r'\{% if property\.thumbnail %\}<meta name="twitter:image".*?\{% endif %\}',
        '{% if seo.og_image %}<meta name="twitter:image" content="{{ seo.og_image }}">{% endif %}',
        text, count=1,
    )

    # (c) purana RealEstateListing JSON-LD  ->  naya (Product + RealEstateListing, sahi price, images, rating)
    text, n5 = re.subn(
        r"<!-- Structured data: this specific listing.*?</script>\n",
        '<!-- Structured data: listing (title/price/images/rating python helper se bante hain) -->\n'
        '{% if seo.json_ld %}<script type="application/ld+json">\n{{ seo.json_ld|safe }}\n</script>{% endif %}\n',
        text, count=1, flags=re.S,
    )
    if not all([n1, n2, n3, n4, n5]):
        die(f"property_detail.html me kuch hissa nahi mila (blocks={n1}, tw_title={n2}, tw_desc={n3}, tw_img={n4}, jsonld={n5}).")
    write(DETAIL, text, crlf)
    print("3/4  property_detail.html patched")

# ------------------------------------------------------------------ 4. base.html
text, crlf = read(BASE)
old = "<title>{% block title %}{% endblock %} | RealShree Ahmedabad</title>"
new = "<title>{% block full_title %}{% block title %}{% endblock %} | RealShree Ahmedabad{% endblock %}</title>"
if "block full_title" in text:
    print("4/4  base.html pehle se patched hai, skip")
elif old not in text:
    die("base.html me <title> line nahi mili.")
else:
    write(BASE, text.replace(old, new, 1), crlf)
    print("4/4  base.html patched")

print("\nDone. Ab server restart karo aur kisi property page ka 'View Source' dekho.")
