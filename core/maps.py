"""Resolve map previews without external I/O in the page-rendering path."""

from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings


def static_map_url(page_id: int, coordinates: str) -> str:
    """Reuse saved previews; let the browser fetch missing maps lazily.

    Existing map files are preserved. New previews use the same Google Static
    Maps endpoint as the previous fallback, without blocking a Django worker.
    """
    filename = f"maps/{page_id}-map.jpg"
    if (Path(settings.MEDIA_ROOT) / filename).is_file():
        return settings.MEDIA_URL + filename
    query = urlencode(
        {
            "center": coordinates,
            "zoom": 15,
            "size": "800x400",
            "markers": coordinates,
            "key": settings.GOOGLE_MAPS_API_KEY,
        }
    )
    return f"https://maps.googleapis.com/maps/api/staticmap?{query}"
