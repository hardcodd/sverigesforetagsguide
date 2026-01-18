from functools import lru_cache

from .models import City


@lru_cache()
def popular_cities(_):
    try:
        popular_cities = City.objects.live().filter(
            popular=True).order_by("title")[:20]
    except Exception:
        popular_cities = []

    return {"popular_cities": popular_cities}
