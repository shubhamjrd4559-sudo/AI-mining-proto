"""
SIH26023 — Root URL Configuration
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import path, include
from django.db import connection


def health_check(request):
    """
    Health check endpoint.
    Returns system status including database connectivity.
    """
    db_status = 'connected'
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception as e:
        db_status = f'error: {str(e)}'

    return JsonResponse({
        'status': 'healthy',
        'version': '1.0.0',
        'phase': '1',
        'database': db_status,
        'project': 'SIH26023',
        'description': 'AI-Powered Geological, Mining and Reporting Solution',
    })


urlpatterns = [
    path('admin/', admin.site.urls),

    # Health check
    path('api/health/', health_check, name='health-check'),

    # API endpoints
    path('api/documents/', include('backend.apps.documents.urls')),
    path('api/datasets/', include('backend.apps.structured_data.urls')),
    path('api/audit/', include('backend.apps.audit.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
