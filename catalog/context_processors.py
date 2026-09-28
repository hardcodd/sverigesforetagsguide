from django.http import HttpRequest
from wagtail.query import PageQuerySet

from .models import City


def popular_cities(request: HttpRequest) -> dict[str, PageQuerySet]:
    """Share one lazy city list within a render without retaining requests."""
    cities = (
        City.objects.live()
        .defer_streamfields()
        .filter(popular=True)
        .order_by("title")[:20]
    )
    return {"popular_cities": cities}
