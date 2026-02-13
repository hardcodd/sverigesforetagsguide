from django.utils.timezone import localtime
from wagtail.models import Site

from core.jsonld import build_jsonld

from .models import HomePage


@build_jsonld.register  # type: ignore
def _(page: HomePage, request):
    """Build JSON-LD for HomePage."""
    domain = request.get_host()
    site = Site.find_for_request(request)
    site_name = site.site_name
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "url": f"https://{domain}/",
        "name": site_name,
        "description": page.search_description,
        "inLanguage": getattr(request, "LANGUAGE_CODE", "en"),
        "publisher": {
            "@type": "Organization",
            "name": site_name,
            "url": f"https://{domain}/",
        },
        "dateModified": localtime(page.last_published_at).isoformat()
        if page.last_published_at
        else None,
    }
    return data
