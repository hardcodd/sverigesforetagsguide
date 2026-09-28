"""Find useful local alternatives without loading the catalog into Python."""

import math
import re
from dataclasses import dataclass
from urllib.parse import urlencode

from django.core import signing

from django.db.models import (
    Case,
    Count,
    F,
    FloatField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import (
    ASin,
    Cast,
    Coalesce,
    Cos,
    Floor,
    Greatest,
    Least,
    Radians,
    Sin,
    Sqrt,
    StrIndex,
    Substr,
)
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.translation import gettext as _

from catalog.models import Organization, OrganizationServiceType
from catalog.promotions import active_paid_subscriptions

EARTH_RADIUS_M = 6_371_008.8
MAX_DISTANCE_M = 5_000
RESULT_LIMIT = 6
DISTANCE_BAND_M = 250
# Bounded decimal syntax also makes SQL casts safe for malformed imported data.
NUMBER_PATTERN = r"[+-]?(?:[0-9]{1,3}(?:\.[0-9]{1,30})?|\.[0-9]{1,30})"
COORDINATES_PATTERN = rf"^\s*{NUMBER_PATTERN}\s*,\s*{NUMBER_PATTERN}\s*$"


@dataclass(frozen=True)
class NearbyOrganization:
    """A public organization and its straight-line distance from this page."""

    organization: Organization
    distance_m: float

    @property
    def distance_label(self) -> str:
        """Format approximate distance without implying walking directions."""
        if self.distance_m < 50:
            return _("Less than 50 m")
        if self.distance_m < 1_000:
            return _("About %(distance)s m") % {
                "distance": int(self.distance_m / 50 + 0.5) * 50,
            }
        return _("About %(distance)s km") % {
            "distance": formats.number_format(self.distance_m / 1_000, 1),
        }


@dataclass(frozen=True)
class NearbyBatch:
    """One bounded batch and a signed URL continuing after its last result."""

    items: list[NearbyOrganization]
    next_url: str | None = None


CURSOR_SALT = "catalog.nearby.v1"
CURSOR_MAX_AGE = 86_400


def _read_cursor(token: str, organization_id: int) -> tuple[float, int, int]:
    """Validate the source-bound ranking cursor; reject tampering and expiry."""
    if len(token) > 512:
        raise ValueError("Invalid nearby cursor")
    source, distance_value, shared_value, pk_value = (
        signing.TimestampSigner(
            salt=CURSOR_SALT,
        )
        .unsign(token, max_age=CURSOR_MAX_AGE)
        .split("|")
    )
    distance, shared, pk = float(distance_value), int(shared_value), int(pk_value)
    if (
        int(source) != organization_id
        or not math.isfinite(distance)
        or not 0 <= distance <= MAX_DISTANCE_M
        or shared < 0
        or pk <= 0
    ):
        raise ValueError("Invalid nearby cursor")
    return distance, shared, pk


def get_nearby_organizations(organization: Organization) -> list[NearbyOrganization]:
    """Return the initial six nearby organizations."""
    return get_nearby_batch(organization).items


def parse_coordinates(value: str) -> tuple[float, float] | None:
    """Accept finite latitude,longitude decimals; reject missing/invalid points."""
    if not re.fullmatch(COORDINATES_PATTERN, value):
        return None
    latitude, longitude = (float(part) for part in value.split(","))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def get_nearby_batch(
    organization: Organization,
    *,
    cursor: str | None = None,
) -> NearbyBatch:
    """Return up to six public, operating peers within 5 km for unpaid pages.

    The direct category and locale bound the search using Wagtail's indexed
    tree path. Within each 250 m distance band, shared service types win, then
    exact distance and page ID break ties. Unrelated categories never fill gaps.
    SQL performs validation, spherical distance, ranking and LIMIT; only the
    selected cards and their images are loaded. No result cache can keep private,
    unpublished or newly closed places visible after an editor changes them.
    """
    # Seek after a ranking key, so removing an earlier card does not skip a row.
    after = _read_cursor(cursor, organization.pk) if cursor is not None else None
    coordinates = parse_coordinates(str(organization.ll or ""))
    if coordinates is None or not organization.pk or not organization.show_on_map:
        return NearbyBatch([])
    if (
        active_paid_subscriptions(timezone.localdate())
        .filter(
            organization_id=organization.pk,
        )
        .exists()
    ):
        return NearbyBatch([])

    latitude, longitude = coordinates
    separator = StrIndex("ll", Value(","))
    latitude_sql = Case(
        When(
            ll__regex=COORDINATES_PATTERN,
            then=Cast(
                Substr("ll", 1, separator - 1),
                FloatField(),
            ),
        ),
        output_field=FloatField(),
    )
    longitude_sql = Case(
        When(
            ll__regex=COORDINATES_PATTERN,
            then=Cast(
                Substr("ll", separator + 1),
                FloatField(),
            ),
        ),
        output_field=FloatField(),
    )
    latitude_delta = math.degrees(MAX_DISTANCE_M / EARTH_RADIUS_M)
    candidates = (
        Organization.objects.live()
        .public()
        .filter(
            path__startswith=str(organization.path)[: -organization.steplen],
            depth=organization.depth,
            locale_id=organization.locale_id,
            temporarily_closed=False,
            show_on_map=True,
        )
        .exclude(pk=organization.pk)
        .alias(nearby_latitude=latitude_sql, nearby_longitude=longitude_sql)
        .filter(
            nearby_latitude__gte=max(-90, latitude - latitude_delta),
            nearby_latitude__lte=min(90, latitude + latitude_delta),
            nearby_longitude__gte=-180,
            nearby_longitude__lte=180,
        )
    )
    # Haversine is stable for neighboring points; clamp floating-point rounding.
    haversine = (
        Sin(Radians(F("nearby_latitude") - latitude) / 2) ** 2.0
        + math.cos(math.radians(latitude))
        * Cos(Radians("nearby_latitude"))
        * Sin(Radians(F("nearby_longitude") - longitude) / 2) ** 2.0
    )
    shared_services = (
        OrganizationServiceType.objects.filter(
            content_object_id=OuterRef("pk"),
            tag_id__in=OrganizationServiceType.objects.filter(
                content_object_id=organization.pk,
            ).values("tag_id"),
        )
        .order_by()
        .values("content_object_id")
        .annotate(total=Count("tag_id", distinct=True))
        .values("total")
    )
    ranked_query = (
        candidates.annotate(
            nearby_distance=2
            * EARTH_RADIUS_M
            * ASin(
                Sqrt(Least(Value(1.0), Greatest(Value(0.0), haversine))),
            ),
            shared_services=Coalesce(Subquery(shared_services), 0),
        )
        .alias(distance_band=Floor(F("nearby_distance") / DISTANCE_BAND_M))
        .filter(
            nearby_distance__lte=MAX_DISTANCE_M,
        )
    )
    if after is not None:
        distance, shared, pk = after
        band = math.floor(distance / DISTANCE_BAND_M)
        ranked_query = ranked_query.filter(
            Q(
                Q(distance_band__gt=band),
                Q(distance_band=band, shared_services__lt=shared),
                Q(
                    distance_band=band,
                    shared_services=shared,
                    nearby_distance__gt=distance,
                ),
                Q(
                    distance_band=band,
                    shared_services=shared,
                    nearby_distance=distance,
                    pk__gt=pk,
                ),
                _connector=Q.OR,
            )
        )
    ranked: list[tuple[int, float, int]] = list(
        ranked_query.order_by(
            "distance_band", "-shared_services", "nearby_distance", "pk"
        ).values_list("pk", "nearby_distance", "shared_services")[: RESULT_LIMIT + 1]
    )
    if not ranked:
        return NearbyBatch([])
    has_more = len(ranked) > RESULT_LIMIT
    ranked = ranked[:RESULT_LIMIT]
    cards: dict[int, Organization] = (
        Organization.objects.filter(pk__in=[pk for pk, _, _ in ranked])
        .defer_streamfields()
        .prefetch_related("images__image")
        .in_bulk()
    )
    next_url = None
    if has_more:
        pk, distance, shared = ranked[-1]
        token = signing.TimestampSigner(salt=CURSOR_SALT).sign(
            f"{organization.pk}|{distance!r}|{shared}|{pk}",
        )
        next_url = (
            reverse("catalog:nearby_organizations", args=[organization.pk])
            + "?"
            + urlencode({"cursor": token})
        )
    return NearbyBatch(
        [NearbyOrganization(cards[pk], distance) for pk, distance, _ in ranked],
        next_url,
    )
