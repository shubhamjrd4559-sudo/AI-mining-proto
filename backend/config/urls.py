"""
CMPDI AI — Root URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/', include('apps.core.urls')),
    path('api/documents/', include('apps.documents.urls')),
    path('api/datasets/', include('apps.datasets.urls')),
    path('api/audit/', include('apps.audit.urls')),

    # DRF browsable API auth
    path('api-auth/', include('rest_framework.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
