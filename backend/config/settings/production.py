"""
CMPDI AI — Production Settings Stub
Extends base.py. Fill in real values via environment variables.

NOT used in Phase 1. Provided as a clean starting point for Phase 5.
"""

from .base import *  # noqa: F401, F403

# ============================================================
# Security
# ============================================================
DEBUG = False

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ============================================================
# Database — PostgreSQL (production)
# Fill DATABASE_URL in environment:
#   postgresql://user:password@host:5432/dbname
# ============================================================
import dj_database_url  # noqa: E402 — install in Phase 5

DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=600,
        ssl_require=True,
    )
}

# ============================================================
# Static files — WhiteNoise or S3 (Phase 5)
# ============================================================
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================================
# CORS — restrict to real frontend origin in production
# ============================================================
CORS_ALLOW_ALL_ORIGINS = False
