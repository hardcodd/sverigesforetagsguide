from django.conf import settings
from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject

from core.models import Footer


def footer(request: HttpRequest) -> dict[str, SimpleLazyObject]:
    """Load the footer only on a fragment-cache miss, without writing on GET."""
    return {"footer": SimpleLazyObject(Footer._default_manager.first)}


def api_keys(request: HttpRequest) -> dict[str, str]:
    """Expose browser API configuration without retaining the request."""
    return {
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }


def base_settings(request: HttpRequest) -> dict[str, str]:
    """Expose display defaults without retaining the request."""
    return {
        "DEFAULT_LAT_LNG": settings.DEFAULT_LAT_LNG,
    }
