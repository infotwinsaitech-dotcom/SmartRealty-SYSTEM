"""
Django settings for realestate_crm project.
Production-ready — Render FREE TIER OPTIMIZED.
"""

import os
import sys
from pathlib import Path

# =============================================================================
# ENVIRONMENT DETECTION
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env only in local development
if os.path.exists(BASE_DIR / ".env"):
    from dotenv import load_dotenv
    load_dotenv()

# Environment flags
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

# ALLOWED_HOSTS — dynamic from env + defaults
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

# CSRF — dynamic from env
CSRF_TRUSTED_ORIGINS = ["https://smartrealty-system.onrender.com"]
_env_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _env_csrf:
    CSRF_TRUSTED_ORIGINS.extend([u.strip() for u in _env_csrf.split(",") if u.strip()])

# Security headers — only in production
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
    CSRF_COOKIE_HTTPONLY = True
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
]

# Only add Celery if not in test mode
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

ACCOUNT_EMAIL_VERIFICATION = "mandatory" if IS_PRODUCTION else "none"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
LOGIN_REDIRECT_URL = "/auth/redirect/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_URL = "/login/"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_SECRET = os.environ.get("GOOGLE_SECRET", "")

if GOOGLE_CLIENT_ID and GOOGLE_SECRET:
    SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APP": {
                "client_id": GOOGLE_CLIENT_ID,
                "secret": GOOGLE_SECRET,
                "key": ""
            },
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
        }
    }
    SOCIALACCOUNT_AUTO_SIGNUP = True
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
# DATABASE — POSTGRESQL (Render Free Tier)
# =============================================================================

import dj_database_url

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=IS_PRODUCTION,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Merge query timeout options (don't overwrite)
if "default" in DATABASES and DATABASES["default"].get("ENGINE") == "django.db.backends.postgresql":
    existing_options = DATABASES["default"].get("OPTIONS", {})
    existing_options["connect_timeout"] = 10
    existing_options["options"] = "-c statement_timeout=30000"
    DATABASES["default"]["OPTIONS"] = existing_options

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

if IS_PRODUCTION:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
else:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary — only if credentials exist
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
    import cloudinary
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
    )
else:
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# =============================================================================
# CACHING — BULLETPROOF (DatabaseCache + Auto-Create)
# =============================================================================

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
# SESSIONS — DATABASE BACKED
# =============================================================================

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600
SESSION_SAVE_EVERY_REQUEST = True

# =============================================================================
# CELERY — FREE TIER OPTIMIZED
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
    
    # ✅ FIXED: String task names only — NO import at module level
    # Celery resolves these at runtime when apps are fully loaded
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
# CHANNELS — CONDITIONAL
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
# EMAIL — FALLBACK CHAIN
# =============================================================================

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@smartrealty.com")

if SENDGRID_API_KEY and IS_PRODUCTION:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.sendgrid.net"
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "apikey"
    EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
else:
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
# LOGGING — RENDER OPTIMIZED
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
# SENTRY — CONDITIONAL
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
# DEBUG OUTPUT
# =============================================================================

if DEBUG and not IS_TEST:
    print("=" * 60)
    print("⚠️  DEBUG MODE ENABLED — NOT FOR PRODUCTION")
    print("=" * 60)
    print(f"  BASE_DIR: {BASE_DIR}")
    print(f"  IS_RENDER: {IS_RENDER}")
    print(f"  DATABASE: {'PostgreSQL' if DATABASE_URL else 'SQLite'}")
    print(f"  CLOUDINARY: {'Enabled' if CLOUDINARY_CLOUD_NAME else 'Disabled'}")
    print(f"  EMAIL: {'SendGrid' if SENDGRID_API_KEY else 'Console'}")
    print(f"  SENTRY: {'Enabled' if SENTRY_DSN else 'Disabled'}")
    print("=" * 60)