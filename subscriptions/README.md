# Subscriptions App — Setup Guide

Ye poora folder ek **standalone Django app** hai. Isse tumhare `SmartRealty-SYSTEM`
project me daalna hai aur 4 chhoti jagah wire karna hai. Uske baad, **future me
price/limit/feature change karne ke liye tumhe SIRF `plans_config.py` edit
karna padega** — baaki kahin touch nahi karna.

---

## Step 1 — Folder copy karo

Is `subscriptions/` folder ko apne project ke root me daalo, `core/` ke
bagal me (jaha `manage.py` hai wahi level par):

```
SmartRealty-SYSTEM/
├── core/
├── subscriptions/     <-- yaha
├── manage.py
└── realestate_crm/
```

## Step 2 — `settings.py` me app add karo

`realestate_crm/settings.py` me `INSTALLED_APPS` list me `"core"` ke neeche
ek line add karo:

```python
INSTALLED_APPS = [
    ...
    "core",
    "subscriptions",   # <-- ye line add karo
]
```

## Step 3 — `urls.py` me route add karo

`realestate_crm/urls.py` me:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('plans/', include('subscriptions.urls')),   # <-- ye line add karo
    ...
]
```

Isse `/plans/pricing/` aur `/plans/my-subscription/` pages live ho jayenge.

## Step 4 — Plans database me daalo

```bash
python manage.py sync_plans
```

Ye command `plans_config.py` ko padh kar `SubscriptionPlan` table me
Builder Starter/Growth/Business/Enterprise aur Agent Free/Pro/Elite — sab
create kar dega. Admin panel (`/admin/`) me bhi ab ye plans dikhengi
(Step 2 ke baad `admin.py` auto-register kar deta hai).

## Step 5 (optional, recommended) — Limit enforcement jodo

Abhi `core/views.py` ka `add_property` view kisi limit ko check nahi karta.
Isme sirf 3 lines add karni hain — ye ek-baar ka kaam hai, baad me limit
badalne par isse dobara touch nahi karna padega (wo config file se hoga):

```python
# core/views.py — top me import add karo
from subscriptions.utils import check_property_limit, LimitExceeded

# add_property view ke andar, POST block ke sabse upar:
def add_property(request):
    if request.method == "POST":
        try:
            check_property_limit(request.user)
        except LimitExceeded as e:
            messages.error(request, str(e))
            return redirect('add_property')   # apne actual url-name se badlo
        ...
```

Isi tarah agent add karne wale view me `check_agent_limit(request.user)`
aur lead create karne wale view me `check_lead_limit(request.user)` daal
sakte ho — dono functions `subscriptions/utils.py` me already bane hue hain.

---

## Roz-marra ka kaam: price/limit/feature badalna

1. `subscriptions/plans_config.py` kholo
2. Jo plan change karna hai uske dictionary me number/list edit karo
3. Terminal me: `python manage.py sync_plans`
4. Done — DB, admin panel, aur pricing page sab automatically update ho
   jayenge. Koi aur file touch nahi karni.

Naya plan add karna ho to bas `BUILDER_PLANS` ya `AGENT_PLANS` list me ek
naya dictionary daal do, same command chalao.

---

## Abhi is app me kya NAHI hai (agla step jab chaho)

- Payment gateway (Razorpay) integration — abhi "Choose Plan" button sirf
  UI hai, actual payment/subscribe flow connect nahi hai.
- Subscription expiry ke liye daily Celery task (project me Celery already
  hai, `core/celery.py` — usme ek task add karna hoga jo expire ho chuki
  `UserSubscription` rows ko `is_active=False` kare).
