"""Select paid promotions without caching subscription-dependent visibility."""

from datetime import date

from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from catalog.models import Organization
from subscription.models import PremiumSubscription


def active_paid_subscriptions(day: date) -> QuerySet[PremiumSubscription]:
    """Return enabled paid subscriptions whose inclusive date range covers day."""
    return PremiumSubscription.objects.filter(
        is_active=True,
        level__gt=PremiumSubscription.Level.COMPETITOR,
        start_date__lte=day,
        end_date__gte=day,
    )


def get_competitors(organization: Organization) -> list[Organization]:
    """Show at most four live Premium peers only on an unpaid organization's page.

    Categories are direct parents in the page tree. Subscription visibility is
    checked on every request, including activation, expiry and future starts.
    Random selection keeps the legacy rotation within eligible category peers.
    """
    paid = active_paid_subscriptions(timezone.localdate())
    if paid.filter(organization_id=organization.pk).exists():
        return []
    premium = paid.filter(
        organization_id=OuterRef("pk"),
        level=PremiumSubscription.Level.PREMIUM,
    )
    return list(
        Organization.objects.live()
        .public()
        .filter(
            Exists(premium),
            path__startswith=str(organization.path)[: -organization.steplen],
            depth=organization.depth,
        )
        .exclude(pk=organization.pk)
        .defer_streamfields()
        .select_related("premium_subscription")
        .prefetch_related("images__image", "rewards__reward")
        .order_by("?")[:4]
    )
