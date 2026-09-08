"""
CMPDI AI — Root URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.authtoken.views import obtain_auth_token

from apps.frontend.views import index as frontend_index

urlpatterns = [
    # -------------------------------------------------------
    # Frontend SPA — serves the CMPDI AI shell at site root
    # Must be listed last so it does not shadow any API routes.
    # -------------------------------------------------------

    # Django admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/', include('apps.core.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/documents/', include('apps.documents.urls')),
    path('api/datasets/', include('apps.datasets.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/audit/', include('apps.audit.urls')),
    path('api/', include('apps.pipeline.urls')),
    path('api/maintainer/', include('apps.maintainer.urls')),
    path('api/intelligence/', include('apps.intelligence.urls')),
    path('api/phase8/', include('apps.phase8.urls')),




    # Auth — obtain token via POST username/password
    path('api/auth/token/', obtain_auth_token, name='api-token-auth'),

    # DRF browsable API auth
    path('api-auth/', include('rest_framework.urls')),

    # Root — frontend SPA (must come after all /api/ routes)
    path('', frontend_index, name='frontend-index'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

