"""
CMPDI AI — Base Django Settings
Shared across all environments.
Environment-specific settings extend this file.

DO NOT put environment secrets here.
Use python-decouple to read from .env file.
"""

import os
from pathlib import Path
from decouple import config, Csv

# ============================================================
# Paths
# ============================================================
# backend/config/settings/base.py  →  backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ============================================================
# Security
# ============================================================
SECRET_KEY = config('SECRET_KEY', default='insecure-dev-key-change-in-production-!!!')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

# ============================================================
# Application definition
# ============================================================
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
]

LOCAL_APPS = [
    'apps.core',
    'apps.documents',
    'apps.datasets',
    'apps.audit',
    'apps.storage',
    'apps.pipeline',
    'apps.maintainer',
    'apps.intelligence',
    'apps.analytics',
    'apps.reports',
    'apps.frontend',
    'apps.phase8',
]


INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ============================================================
# Middleware
# ============================================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # Must be first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# URLs
# ============================================================
ROOT_URLCONF = 'config.urls'

# ============================================================
# Templates
# ============================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ============================================================
# Password validation
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================
# Internationalisation
# ============================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ============================================================
# Static files
# ============================================================
STATIC_URL = '/static/'
STATIC_ROOT = config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
# Extra directories that collectstatic will include.
# backend/static/ holds the frontend assets (logo, future JS/CSS bundles).
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# ============================================================
# Media files (uploaded documents)
# ============================================================
MEDIA_URL = '/media/'
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

# ============================================================
# Default primary key
# ============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# ============================================================
# Django REST Framework
# ============================================================
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# ============================================================
# CORS (Cross-Origin Resource Sharing)
# ============================================================
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080',
    cast=Csv(),
)
# Allow the static index.html served from file:// during dev
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ============================================================
# Storage & Document Upload Configuration
# ============================================================
STORAGE_BACKEND = config('STORAGE_BACKEND', default='local')

# Maximum file size allowed for a single upload (default 50 MB)
MAX_UPLOAD_SIZE = config('MAX_UPLOAD_SIZE', default=50 * 1024 * 1024, cast=int)

# Maximum files permitted in a single batch upload request
MAX_BATCH_FILE_COUNT = config('MAX_BATCH_FILE_COUNT', default=10, cast=int)

# Maximum aggregate size allowed for a batch upload request (default 100 MB)
MAX_BATCH_TOTAL_SIZE = config('MAX_BATCH_TOTAL_SIZE', default=100 * 1024 * 1024, cast=int)

# Supported document extensions (case-insensitive)
ALLOWED_DOCUMENT_EXTENSIONS = {
    '.pdf',
    '.docx',
    '.xlsx',
    '.csv',
    '.txt',
    '.png',
    '.jpg',
    '.jpeg',
}

# Mapping of extensions to standard MIME types
ALLOWED_DOCUMENT_MIMETYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'text/csv',
    'text/plain',
    'image/png',
    'image/jpeg',
    'application/octet-stream', # common fallback for multipart clients
}

# ============================================================
# Development / Demo User Seed Configuration
# Used ONLY by the seed_dev_user management command.
# NEVER commit real credentials. Set via .env.
# DEV_USER_USERNAME and DEV_USER_PASSWORD default to None —
# seed_dev_user will abort if either is not set, preventing
# accidental creation of predictable default credentials.
# ============================================================
DEV_USER_USERNAME = config('DEV_USER_USERNAME', default=None)
DEV_USER_PASSWORD = config('DEV_USER_PASSWORD', default=None)
DEV_USER_EMAIL = config('DEV_USER_EMAIL', default='admin@cmpdi.local')
# Show seed credentials hint on the login form only in DEBUG mode.
SHOW_DEV_LOGIN_HINT = config('DEBUG', default=True, cast=bool)

# ============================================================
# Phase 5: RAG Mining Intelligence & LLM Configuration
# ============================================================
GEMINI_API_KEY = config('GEMINI_API_KEY', default=config('GOOGLE_API_KEY', default=None))
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-2.5-flash')
AI_QUERY_MAX_LENGTH = config('AI_QUERY_MAX_LENGTH', default=1000, cast=int)
AI_RETRIEVAL_TOP_K = config('AI_RETRIEVAL_TOP_K', default=5, cast=int)
AI_RETRIEVAL_MIN_SCORE = config('AI_RETRIEVAL_MIN_SCORE', default=0.05, cast=float)
