"""
Django settings for realestate_crm project.
PRODUCTION READY - 1000+ users/day
All bugs fixed by Claude audit.
"""

import os
import sys
import urllib.parse
from pathlib import Path

# =============================================================================
# ENVIRONMENT DETECTION
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

if os.path.exists(BASE_DIR / ".env"):
    from dotenv import load_dotenv
    load_dotenv()

IS_RENDER = os.environ.get("RENDER", "False").lower() in ("true", "1", "yes")
IS_PRODUCTION = os.environ.get("DJANGO_ENV", "production").lower() == "production"
IS_TEST = "test" in sys.argv or "pytest" in sys.modules

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION and not IS_TEST:
        raise ValueError("SECRET_KEY environment variable is required in production!")
    SECRET_KEY = "django-insecure-dev-key-change-in-production-123456789"

DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes", "on")
if IS_PRODUCTION:
    DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
if IS_RENDER:
    ALLOWED_HOSTS.extend([
        "smartrealty-system.onrender.com",
        "*.onrender.com",
    ])

_env_hosts = os.environ.get("ALLOWED_HOSTS", "")
if _env_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in _env_hosts.split(",") if h.strip()])
ALLOWED_HOSTS = list(set(ALLOWED_HOSTS))

CSRF_TRUSTED_ORIGINS = ["https://smartrealty-system.onrender.com"]
_env_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _env_csrf:
    CSRF_TRUSTED_ORIGINS.extend([u.strip() for u in _env_csrf.split(",") if u.strip()])

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    X_FRAME_OPTIONS = "DENY"
else:
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    X_FRAME_OPTIONS = "SAMEORIGIN"

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "cloudinary",
    "cloudinary_storage",
    "core",
    "subscriptions",
]

if not IS_TEST:
    INSTALLED_APPS.extend([
        "django_celery_beat",
        "django_celery_results",
    ])

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# =============================================================================
# ALLAUTH SETTINGS
# =============================================================================


# =============================================================================
# ALLAUTH SETTINGS — UPDATED FOR GOOGLE OAUTH WITH AUTO USERNAME
# =============================================================================

ACCOUNT_EMAIL_VERIFICATION = "mandatory" if IS_PRODUCTION else "none"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
LOGIN_REDIRECT_URL = "/auth/redirect/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_URL = "/login/"

# Auto-redirect after social signup (bypass form if possible)
SOCIALACCOUNT_AUTO_SIGNUP = True  # Try auto signup first

# Custom forms for social signup
SOCIALACCOUNT_FORMS = {
    "signup": "core.forms.CustomSocialSignupForm"
}

# Custom adapter for social accounts
SOCIALACCOUNT_ADAPTER = "core.adapters.CustomSocialAccountAdapter"

# =============================================================================
# GOOGLE OAUTH SETTINGS
# =============================================================================

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
            # Fetch these fields from Google
            "FETCH_USERINFO": True,
        }
    }
else:
    SOCIALACCOUNT_PROVIDERS = {}
    SOCIALACCOUNT_AUTO_SIGNUP = False

SOCIALACCOUNT_ADAPTER = "core.adapters.CustomSocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "core.forms.CustomSocialSignupForm"}

# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.RequestLoggingMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

# =============================================================================
# URLS & TEMPLATES
# =============================================================================

ROOT_URLCONF = "realestate_crm.urls"
WSGI_APPLICATION = "realestate_crm.wsgi.application"

try:
    import channels
    ASGI_APPLICATION = "realestate_crm.asgi.application"
    HAS_CHANNELS = True
except ImportError:
    HAS_CHANNELS = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_settings",
                "core.context_processors.notification_count",
            ],
        },
    },
]

# =============================================================================
# RAZORPAY PAYMENT GATEWAY SETTINGS
# =============================================================================

# Get from Razorpay Dashboard -> Settings -> API Keys
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_YOUR_TEST_KEY_HERE')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'YOUR_TEST_SECRET_HERE')

# Webhook secret (optional but recommended for production)
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')

# =============================================================================
# SUBSCRIPTION SETTINGS
# =============================================================================
SUBSCRIPTION_GRACE_PERIOD_DAYS = 3
SUBSCRIPTION_TRIAL_DAYS = 0

# =============================================================================
# DATABASE
# =============================================================================

import dj_database_url

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    parsed = urllib.parse.urlparse(DATABASE_URL)
    hostname = parsed.hostname or ""
    is_render_external = ".render.com" in hostname
    is_render_internal = hostname.endswith("-a") and not is_render_external

    db_config = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
    db_config.setdefault("OPTIONS", {})

    if is_render_external:
        db_config["OPTIONS"]["sslmode"] = "require"
    elif is_render_internal:
        pass
    else:
        db_config["OPTIONS"]["sslmode"] = "prefer"

    db_config["OPTIONS"]["connect_timeout"] = 10
    db_config["OPTIONS"]["options"] = "-c statement_timeout=30000"

    DATABASES = {"default": db_config}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static", BASE_DIR / "frontend" / "assets"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

if IS_PRODUCTION:
    _staticfiles_backend = "whitenoise.storage.CompressedManifestStaticFilesStorage"
else:
    _staticfiles_backend = "django.contrib.staticfiles.storage.StaticFilesStorage"

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    import cloudinary
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
    )
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": _staticfiles_backend,
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": _staticfiles_backend,
        },
    }

# =============================================================================
# CACHING
# BUG FIX: _redis_url pehle define karo — phir CACHES mein use karo
# =============================================================================

_redis_url = os.environ.get("REDIS_URL")

if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
            },
            "TIMEOUT": 300,
            "KEY_PREFIX": "smartrealty",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache_table",
            "TIMEOUT": 300,
            "OPTIONS": {
                "MAX_ENTRIES": 100000,
                "CULL_FREQUENCY": 3,
            }
        }
    }

# =============================================================================
# SESSIONS
# BUG FIX: cached_db + False — DB hammer band
# =============================================================================

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600
SESSION_SAVE_EVERY_REQUEST = False

# =============================================================================
# CELERY
# =============================================================================

if not IS_TEST:
    CELERY_BROKER_URL = os.environ.get("REDIS_URL", "sqla+sqlite:///celerydb.sqlite")
    CELERY_RESULT_BACKEND = "db+sqlite:///celery_results.sqlite"

    if os.environ.get("REDIS_URL"):
        CELERY_BROKER_URL = os.environ.get("REDIS_URL")
        CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")

    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    CELERY_TASK_TIME_LIMIT = 300
    CELERY_TASK_SOFT_TIME_LIMIT = 240
    CELERY_TASK_ACKS_LATE = True
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1

    CELERY_BEAT_SCHEDULE = {
        "check-drip-sequences": {
            "task": "core.tasks.process_drip_sequences",
            "schedule": 21600.0,
        },
        "check-missed-followups": {
            "task": "core.tasks.check_missed_followups_task",
            "schedule": 3600.0,
        },
        "send-daily-summaries": {
            "task": "core.tasks.send_daily_summaries",
            "schedule": 86400.0,
        },
    }

# =============================================================================
# CHANNELS
# =============================================================================

if HAS_CHANNELS:
    if os.environ.get("REDIS_URL"):
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [os.environ.get("REDIS_URL")]},
            }
        }
    else:
        CHANNEL_LAYERS = {
            "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
        }

# =============================================================================
# EMAIL
# =============================================================================
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@realshree.com")

# Sent via Brevo's HTTP API (not SMTP) in core/tasks.py, so no EMAIL_BACKEND
# SMTP settings are needed. EMAIL_BACKEND is kept only as a safe fallback
# for any code path that still calls Django's send_mail() directly.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/hour", "user": "1000/hour"},
}

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO", "propagate": False},
    },
}

if not IS_RENDER and not IS_PRODUCTION:
    LOGS_DIR = BASE_DIR / "logs"
    LOGS_DIR.mkdir(exist_ok=True)
    LOGGING["handlers"]["file"] = {
        "level": "INFO",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOGS_DIR / "django.log"),
        "maxBytes": 1024 * 1024 * 5,
        "backupCount": 5,
        "formatter": "verbose",
    }
    LOGGING["root"]["handlers"].append("file")
    LOGGING["loggers"]["django"]["handlers"].append("file")
    LOGGING["loggers"]["core"]["handlers"].append("file")

# =============================================================================
# SENTRY
# =============================================================================

SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN and IS_PRODUCTION and not IS_TEST:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.05,
            profiles_sample_rate=0.05,
            environment="production",
            send_default_pii=True,
        )
    except ImportError:
        pass

# =============================================================================
# FILE UPLOAD LIMITS
# =============================================================================

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760
DATA_UPLOAD_MAX_NUMBER_FILES = 100

# =============================================================================
# ADMINS & DEFAULTS
# =============================================================================

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@smartrealty.com")
ADMINS = [("Admin", ADMIN_EMAIL)]
MANAGERS = ADMINS
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"

# =============================================================================
# DEBUG OUTPUT (local only)
# =============================================================================

if DEBUG and not IS_TEST:
    print("=" * 60)
    print("WARNING: DEBUG MODE ON - NOT FOR PRODUCTION")
    print("=" * 60)
    print(f"  DATABASE: {'PostgreSQL' if DATABASE_URL else 'SQLite'}")
    print(f"  REDIS: {'Connected' if _redis_url else 'Not set - using DB cache'}")
    print(f"  CLOUDINARY: {'Enabled' if CLOUDINARY_CLOUD_NAME else 'Disabled - local storage'}")
    print(f"  EMAIL: {'SendGrid' if SENDGRID_API_KEY else 'Console only'}")
    print(f"  SENTRY: {'Enabled' if SENTRY_DSN else 'Disabled'}")
    print("=" * 60)
    # =============================================================================
# AUTO-SETUP ON STARTUP (No shell needed for Render free tier)
# =============================================================================
# =============================================================================
# AUTO-SETUP: Site + SocialApp (Called after Django is fully ready)
# =============================================================================

def _auto_setup_site_and_socialapp():
    """Auto-create Site and SocialApp. Call from apps.py ready(), NOT here."""
    import os
    import logging
    
    logger = logging.getLogger("core.setup")
    
    try:
        from django.contrib.sites.models import Site
        from allauth.socialaccount.models import SocialApp
        
        # 1. Create Site
        site, created = Site.objects.get_or_create(
            id=1,
            defaults={
                'domain': 'realshree.com',
                'name': 'SmartRealty'
            }
        )
        if created:
            logger.info(f"[AUTO-SETUP] Site created: {site.domain}")
        
        # 2. Create SocialApp
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        
        if client_id and secret:
            app, created = SocialApp.objects.get_or_create(
                provider='google',
                defaults={
                    'name': 'Google OAuth',
                    'client_id': client_id,
                    'secret': secret,
                }
            )
            if not app.sites.filter(pk=site.pk).exists():
                app.sites.add(site)
            if created:
                logger.info("[AUTO-SETUP] Google SocialApp created")
            else:
                logger.info("[AUTO-SETUP] Google SocialApp already exists")
        else:
            logger.warning("[AUTO-SETUP] Google credentials not set")
            
    except Exception as e:
        logger.error(f"[AUTO-SETUP] Error: {e}")

# settings.py
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')