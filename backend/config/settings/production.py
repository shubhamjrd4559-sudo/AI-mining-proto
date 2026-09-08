"""
CMPDI AI — Production Settings
Extends base.py. All secrets and host configuration are driven by
environment variables. No credentials are hard-coded here.

Required environment variables for Render deployment:
  SECRET_KEY            — Django secret key (required)
  ALLOWED_HOSTS         — comma-separated list of allowed host names (required)
  DATABASE_URL          — PostgreSQL connection string (required)
  CSRF_TRUSTED_ORIGINS  — comma-separated origins for CSRF (required when behind proxy)

Optional environment variables:
  CORS_ALLOWED_ORIGINS  — comma-separated allowed CORS origins (default: empty)
  STATIC_ROOT           — path for collectstatic output (default: backend/staticfiles)
  MEDIA_ROOT            — path for uploaded media files (default: backend/media)
  GEMINI_API_KEY        — Gemini LLM API key
"""

from .base import *  # noqa: F401, F403
from decouple import config, Csv  # noqa: F405 — already imported via base, re-import for clarity

# ============================================================
# Security
# ============================================================
DEBUG = False

# ALLOWED_HOSTS must be explicitly set in environment.
# base.py defaults to 127.0.0.1,localhost — production must override.
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# CSRF trusted origins — required when deployed behind a reverse proxy (Render).
# Set to the production app URL, e.g.: https://your-app.onrender.com
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='',
    cast=Csv(),
)

# ============================================================
# Database — PostgreSQL (production)
# Set DATABASE_URL in environment:
#   postgresql://user:password@host:5432/dbname
# ============================================================
import dj_database_url  # noqa: E402

_db_config = dj_database_url.config(
    env='DATABASE_URL',
    conn_max_age=600,
    ssl_require=True,
    default=None,
)
if _db_config:
    DATABASES = {'default': _db_config}
# If DATABASE_URL is not set (e.g. during CI import checks), DATABASES falls through
# to whatever base.py set — which is safe for import-time checks.

# ============================================================
# Static files — WhiteNoise for Render/Heroku-style deployment
# WhiteNoise serves compressed, cached static files directly from Django.
# Run `python manage.py collectstatic` before deployment.
# ============================================================
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# WhiteNoise middleware must be inserted immediately after SecurityMiddleware.
# Rebuild MIDDLEWARE list to ensure correct ordering.
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files efficiently
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# CORS — restricted in production
# Set CORS_ALLOWED_ORIGINS in environment to the actual frontend origin.
# Since the frontend is now Django-served (same-origin), CORS is only
# needed if external clients (e.g. mobile apps) need API access.
# ============================================================
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='',
    cast=Csv(),
)
