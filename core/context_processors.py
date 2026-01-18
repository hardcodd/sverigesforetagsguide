from functools import lru_cache

from django.conf import settings

from core.models import Footer


@lru_cache()
def footer(request):
    context = {"footer": None}

    footer = Footer.objects.first()  # type: ignore
    if not footer:
        footer = Footer()
        footer.save()

    context["footer"] = footer  # type: ignore

    return context


@lru_cache()
def api_keys(request):
    return {
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }


@lru_cache()
def base_settings(request):
    return {
        "DEFAULT_LAT_LNG": settings.DEFAULT_LAT_LNG,
    }
