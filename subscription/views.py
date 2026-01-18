import django_filters
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import DateRangePickerWidget
from wagtail.admin.viewsets.model import ModelViewSet

from subscription.models import PremiumSubscription


class PremiumSubscriptionFilter(django_filters.FilterSet):
    start_date = django_filters.DateFromToRangeFilter(
        field_name="start_date",
        label=_("Start Date"),
        widget=DateRangePickerWidget,
    )
    end_date = django_filters.DateFromToRangeFilter(
        field_name="end_date",
        label=_("End Date"),
        widget=DateRangePickerWidget,
    )

    class Meta:
        model = PremiumSubscription
        fields = [
            "level",
            "is_active",
            "start_date",
            "end_date",
        ]


class PremiumSubscriptionViewSet(ModelViewSet):
    model = PremiumSubscription
    menu_label = _("Subscriptions")  # type: ignore
    icon = "pick"
    add_to_admin_menu = True
    copy_view_enabled = False
    menu_order = 200

    list_display = [
        "organization",
        "organization_id",
        "__str__",
        "start_date",
        "end_date",
        "is_active",
    ]

    filterset_class = PremiumSubscriptionFilter

    search_fields = [
        "organization__title",
        "organization__id",
    ]


premium_subscription_viewset = PremiumSubscriptionViewSet(
    "premium_subscriptions",
)
