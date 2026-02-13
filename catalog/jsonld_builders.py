from datetime import time
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.utils.html import strip_tags
from django.utils.timezone import localtime
from wagtail.images.models import Image

from core.jsonld import build_jsonld
from reviews.models import Review, ReviewStatus

from .models import Organization


def _image_abs_url(request, image: Image, spec: str) -> str | None:
    """Return absolute rendition url for an image."""
    try:
        rendition = image.get_rendition(spec)
        return request.build_absolute_uri(rendition.url)
    except Exception:
        try:
            return request.build_absolute_uri(image.file.url)
        except Exception:
            return None


def _get_org_images(page, request) -> list[str] | None:
    """
    Returns up to 10 absolute image URLs (best for LocalBusiness.image).
    Uses page.images; if empty, uses settings.core.SiteSettings.default_organization_image.
    """
    urls: list[str] = []

    # Page images (up to 10)
    rel = getattr(page, "images", None)
    if rel is not None and rel.exists():
        for item in rel.all()[:10]:
            img = getattr(item, "image", None)
            if not img:
                continue
            url = _image_abs_url(request, img, "width-1200")
            if url:
                urls.append(url)

    # 2) Fallback default image from settings
    if not urls:
        try:
            from core.models import SiteSettings

            default_img = SiteSettings.for_request(request).default_organization_image
        except Exception:
            default_img = None

        if default_img:
            url = _image_abs_url(request, default_img, "width-1200")
            if url:
                urls.append(url)

    return urls or None


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def _split_commas(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _abs(request, path_or_url: str) -> str:
    if not path_or_url:
        return ""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return request.build_absolute_uri(path_or_url)


def _safe_decimal(value: Any) -> str | None:
    try:
        d = Decimal(str(value))
        return format(d.normalize(), "f")
    except Exception:
        return None


def _parse_ll(ll: str) -> tuple[str | None, str | None]:
    if not ll:
        return None, None
    cleaned = ll.replace(";", ",").replace("  ", " ").strip()
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    else:
        parts = [p.strip() for p in cleaned.split(" ") if p.strip()]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[1]


def format_time(value):
    """Return time in 00:00 format."""
    if isinstance(value, time):
        return value.strftime("%H:%M")
    elif isinstance(value, str):
        return value


def _opening_hours_spec_from_stream(working_hours) -> list[dict[str, Any]]:
    if not working_hours:
        return []

    DAYS = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    def get_day_name(day_index: int) -> str:
        return str(DAYS[day_index - 1])

    # day_index -> (start, end, holiday)
    explicit: dict[int, tuple[str, str, bool]] = {}

    for item in working_hours:
        value = getattr(item, "value", None) or {}
        day_index = int(value.get("day"))
        start = format_time(value.get("start"))
        end = format_time(value.get("end"))
        holiday = bool(value.get("holiday", False))
        explicit[day_index] = (start, end, holiday)

    if not explicit:
        return []

    filled = dict(explicit)

    # Fill in missing days by looking for consecutive days with the same hours/holiday status.
    days_sorted = sorted(explicit.keys())
    for left, right in zip(days_sorted, days_sorted[1:]):
        left_spec = explicit[left]
        right_spec = explicit[right]

        if left_spec == right_spec and right > left + 1:
            for d in range(left + 1, right):
                filled.setdefault(d, left_spec)

    # Sort by day index and convert to required format.
    result: list[dict[str, Any]] = []
    for d in sorted(filled.keys()):
        start, end, holiday = filled[d]
        result.append(
            {
                "dayOfWeek": get_day_name(d),
                "opens": start,
                "closes": end,
            }
        )

    return result


@build_jsonld.register  # type: ignore[misc]
def _(page: Organization, request):
    """
    Google-oriented LocalBusiness JSON-LD for Organization page.
    """

    page_url = _abs(request, page.url)
    entity_id = f"{page_url}#org"

    # sameAs (social + website links)
    same_as = []
    same_as += [_abs(request, u) for u in _split_lines(page.social_networks)]
    same_as += [_abs(request, u) for u in _split_lines(page.website_links)]
    same_as = [u for u in same_as if u] or None

    # Phones: primary in telephone, the rest in contactPoint
    phones = _split_commas(page.phones)
    telephone = "+" + phones[0] if phones else None
    contact_points = None
    if len(phones) > 1:
        contact_points = [
            {
                "@type": "ContactPoint",
                "telephone": f"+{p}",
                "contactType": "customer service",
            }
            for p in phones[1:]
        ]

    # Address (best effort with your single string field)
    address = None
    if page.address:
        # For strictness, adding addressCountry is recommended if you can determine it.
        # If you can’t, keep only streetAddress.
        address = {
            "@type": "PostalAddress",
            "streetAddress": page.address,
        }

    # Geo
    lat, lon = _parse_ll(page.ll)
    geo = None
    if lat and lon and page.show_on_map:
        geo = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon}

    # Parent organization relation (if nested)
    parent_org = None
    if page.located_in:
        parent_org = {
            "@type": "Organization",
            "name": page.located_in.title,
            "url": _abs(request, page.located_in.url),
        }

    # Languages
    knows_language = None
    if page.languages.exists():
        knows_language = [
            getattr(lang, "name", str(lang)) for lang in page.languages.all()
        ]

    # Opening hours
    opening_hours_spec = []
    if not page.temporarily_closed:
        opening_hours_spec = _opening_hours_spec_from_stream(page.working_hours)

    # Reviews / AggregateRating (Google expects consistency and real reviews)
    ct = ContentType.objects.get_for_model(Organization)
    reviews_qs = Review.objects.filter(
        content_type=ct,
        object_id=page.id,
        status=ReviewStatus.PUBLISHED,
    )

    review_count = reviews_qs.count()
    rating_value = _safe_decimal(page.avg_rating)

    aggregate_rating = None
    if review_count > 0 and rating_value:
        aggregate_rating = {
            "@type": "AggregateRating",
            "ratingValue": rating_value,
            "reviewCount": review_count,  # Google commonly uses reviewCount
            "bestRating": "5",
            "worstRating": "1",
        }

    reviews_json = None
    if review_count > 0:
        items = []
        for r in reviews_qs.order_by("-go_live_at", "-created_at")[:5]:
            items.append(
                {
                    "@type": "Review",
                    "reviewRating": {
                        "@type": "Rating",
                        "ratingValue": str(r.rating),
                        "bestRating": "5",
                        "worstRating": "1",
                    },
                    "reviewBody": r.comment,
                    "datePublished": localtime(
                        r.go_live_at or r.created_at
                    ).isoformat(),
                    "author": {"@type": "Person", "name": str(r.user)},
                }
            )
        if items:
            reviews_json = items

    # Description must be plain text for best compatibility
    description = (page.search_description or "") or ""
    description = strip_tags(description).strip() or None

    # Images (up to 10)
    images = _get_org_images(page, request)

    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "@id": entity_id,
        "mainEntityOfPage": page_url,
        "url": page_url,
        "name": page.h1_title or page.title,
        # Images
        "image": images,
        # Business identifiers (optional but fine)
        "legalName": page.legal_name or None,
        "taxID": page.tin or None,
        # Text
        "description": description,
        # Contact
        "email": page.email or None,
        "telephone": telephone,
        "contactPoint": contact_points,
        "sameAs": same_as,
        # Location
        "address": address,
        "geo": geo,
        # Relations
        "parentOrganization": parent_org,
        # Languages
        "knowsLanguage": knows_language,
        # Hours
        "openingHoursSpecification": opening_hours_spec or None,
        # Rating & reviews
        "aggregateRating": aggregate_rating,
        "review": reviews_json,
    }

    # Remove empty/nulls aggressively (better for strict validators)
    def _not_empty(v: Any) -> bool:
        return v not in (None, "", [], {}, ())

    data = {k: v for k, v in data.items() if _not_empty(v)}

    return data
