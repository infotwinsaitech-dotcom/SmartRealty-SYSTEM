"""
Django settings for realestate_crm project.
Production-ready configuration.
"""

import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required!")

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "smartrealty-system.onrender.com",
    "*.onrender.com",
]

# Dynamic ALLOWED_HOSTS from env (for Render/custom domains)
_env_hosts = os.getenv("ALLOWED_HOSTS", "")
if _env_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in _env_hosts.split(",") if h.strip()])

CSRF_TRUSTED_ORIGINS = [
    "https://smartrealty-system.onrender.com",
]

# Security headers (conditional based on DEBUG)
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

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

    # Third party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "channels",
    "cloudinary",
    "cloudinary_storage",
    "django_celery_beat",
    "django_celery_results",

    # Local
    "core",
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Allauth settings
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_ADAPTER = "core.adapters.CustomSocialAccountAdapter"
SOCIALACCOUNT_FORMS = {
    "signup": "core.forms.CustomSocialSignupForm"
}

# Google OAuth settings
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_SECRET", ""),
            "key": ""
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# Login redirects
LOGIN_REDIRECT_URL = "/auth/redirect/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_URL = "/login/"

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
ASGI_APPLICATION = "realestate_crm.asgi.application"
WSGI_APPLICATION = "realestate_crm.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "frontend", "templates")],
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
# DATABASE
# =============================================================================

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"),
        conn_max_age=600,
    )
}

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
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
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
    os.path.join(BASE_DIR, "frontend", "assets"),
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Cloudinary
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

import cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# =============================================================================
# REDIS & CACHING (PRODUCTION-READY WITH FALLBACK)
# =============================================================================
# Priority:
#   1. Redis Cache (requires: pip install django-redis)
#   2. Database Cache (built-in, no extra packages)
#   3. LocMem Cache (in-memory, dev only)
# =============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Try Redis first, fallback to DatabaseCache if django-redis not installed
try:
    import django_redis
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "RETRY_ON_TIMEOUT": True,
                "CONNECTION_POOL_KWARGS": {"max_connections": 20},
            },
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
    _cache_backend = "redis"
except ImportError:
    # Fallback: Database Cache (no pip install needed)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache_table",
            "TIMEOUT": 300,
            "OPTIONS": {
                "MAX_ENTRIES": 10000,
                "CULL_FREQUENCY": 3,
            }
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
    _cache_backend = "database"

SESSION_COOKIE_AGE = 1209600
SESSION_SAVE_EVERY_REQUEST = True

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {
    "check-drip-sequences": {
        "task": "core.tasks.process_drip_sequences",
        "schedule": 21600.0,  # Every 6 hours
    },
    "check-missed-followups": {
        "task": "core.tasks.check_missed_followups_task",
        "schedule": 3600.0,  # Every 1 hour
    },
    "send-daily-summaries": {
        "task": "core.tasks.send_daily_summaries",
        "schedule": 86400.0,  # Every 24 hours (1 day)
    },
}

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "apikey"
EMAIL_HOST_PASSWORD = os.getenv("SENDGRID_API_KEY")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@smartrealty.com")

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# =============================================================================
# LOGGING (MERGED - SINGLE CONFIG)
# =============================================================================

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "django.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "task_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "tasks.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "core.tasks": {
            "handlers": ["task_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# =============================================================================
# RATE LIMITING
# =============================================================================

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"

# =============================================================================
# ADMINS
# =============================================================================

ADMINS = [("Admin", os.getenv("ADMIN_EMAIL", "admin@smartrealty.com"))]
MANAGERS = ADMINS

# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# AUTH USER MODEL
# =============================================================================

AUTH_USER_MODEL = "core.User"

# =============================================================================
# CACHALOT (DISABLED - optional caching layer)
# =============================================================================

CACHALOT_ENABLED = False

# =============================================================================
# DEBUG OUTPUT (ONLY IN DEBUG MODE)
# =============================================================================

if DEBUG:
    print("=" * 60)
    print("⚠️  DEBUG MODE IS ENABLED - NOT FOR PRODUCTION")
    print("=" * 60)
    print(f"SECRET_KEY loaded: {bool(SECRET_KEY)}")
    print(f"SENDGRID loaded: {bool(os.getenv('SENDGRID_API_KEY'))}")
    print(f"DB URL loaded: {bool(os.getenv('DATABASE_URL'))}")
    print(f"REDIS URL loaded: {bool(REDIS_URL)}")
    print(f"CACHE BACKEND: {_cache_backend}")
    print("=" * 60)