"""
CMPDI AI — Development Settings
Extends base.py with SQLite, DEBUG=True, and relaxed CORS.
"""

from .base import *  # noqa: F401, F403

# ============================================================
# Debug
# ============================================================
DEBUG = config('DEBUG', default=True, cast=bool)  # noqa: F405

# ============================================================
# Database — SQLite (development only)
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

# ============================================================
# CORS — allow all origins in development so index.html
# served from file:// or any local server can call the API
# ============================================================
CORS_ALLOW_ALL_ORIGINS = True

# ============================================================
# Email — console backend for development
# ============================================================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ============================================================
# Dev-only: show full exception detail in API responses
# ============================================================
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}
