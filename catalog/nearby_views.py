"""Public, uncached pagination for nearby organization cards."""

from django.core import signing
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from catalog.models import Organization
from catalog.nearby import get_nearby_batch


@require_GET
@never_cache
def nearby_organizations(request: HttpRequest, organization_id: int) -> JsonResponse:
    """Recheck visibility and subscription on every signed continuation request."""
    cursor = request.GET.get("cursor", "")
    if not isinstance(cursor, str) or not cursor:
        return JsonResponse({"error": "invalid_cursor"}, status=400)
    organization = get_object_or_404(
        Organization.objects.live().public().defer_streamfields(),
        pk=organization_id,
    )
    try:
        batch = get_nearby_batch(organization, cursor=cursor)
    except (signing.BadSignature, ValueError, OverflowError):
        return JsonResponse({"error": "invalid_cursor"}, status=400)
    html = render_to_string(
        "catalog/includes/nearby-organization-items.html",
        {"nearby_organizations": batch.items},
        request=request,
    )
    return JsonResponse({"html": html, "next_url": batch.next_url})
