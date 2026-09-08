"""
apps.frontend.views — Root frontend view

GET /
    Renders the CMPDI AI frontend SPA template.
    All API calls within the template use same-origin relative URLs.
    No authentication is required to load the shell HTML; individual
    API endpoints enforce their own IsAuthenticated permissions.
"""

from django.shortcuts import render
from django.views.decorators.cache import never_cache


@never_cache
def index(request):
    """
    Render the CMPDI AI Mining Intelligence Command Center.

    The template is served from templates/frontend/index.html.
    API_BASE is set to '' inside the template so all API requests
    are same-origin relative paths (e.g. /api/health/).
    No context data is required — the UI is fully self-contained.
    """
    return render(request, 'frontend/index.html')
