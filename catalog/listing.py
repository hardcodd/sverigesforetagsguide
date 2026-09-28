"""Category-scoped filters shared by editorial and fallback organization lists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from django import forms
from django.db.models import Count, F, Q
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from wagtail.blocks.stream_block import StreamValue
from wagtail.query import PageQuerySet

from catalog.models import Language, Organization, OrganizationType, ServiceType


class OrganizationFilterForm(forms.Form):
    """Validate URL filters against options present in the public category."""

    q = forms.CharField(
        required=False,
        max_length=120,
        label=_("Name or address"),
        widget=forms.SearchInput(attrs={"placeholder": _("Search in this category")}),
    )
    sort = forms.ChoiceField(
        required=False,
        label=_("Sort by"),
        choices=[
            ("", _("Recommended order")),
            ("rating", _("Highest rating")),
            ("newest", _("Newest first")),
            ("name", _("Name: A to Z")),
        ],
    )
    rating = forms.ChoiceField(
        required=False,
        label=_("Minimum rating"),
        choices=[("", _("Any rating")), ("4", "4+"), ("4.5", "4.5+")],
    )
    language = forms.ChoiceField(required=False, label=_("Language spoken"))
    verified = forms.BooleanField(required=False, label=_("Verified by Madloba"))
    hide_closed = forms.BooleanField(required=False, label=_("Hide temporarily closed"))
    service_type = forms.MultipleChoiceField(required=False)
    service_match = forms.ChoiceField(
        required=False,
        choices=[
            ("", _("All conditions")),
            ("all", _("All conditions")),
            ("any", _("At least one")),
        ],
    )

    def __init__(
        self,
        request: HttpRequest,
        services: list[ServiceType],
        languages: list[Language],
    ) -> None:
        super().__init__(data=request.GET, auto_id="organization-filter-%s")
        self.fields["service_type"].choices = [
            (str(service.pk), str(service)) for service in services
        ]
        self.fields["language"].choices = [("", _("Any language"))] + [
            (str(language.pk), str(language)) for language in languages
        ]


@dataclass(frozen=True)
class ServiceOption:
    id: str
    label: str
    count: int
    selected: bool


@dataclass
class ServiceGroup:
    label: str
    options: list[ServiceOption]
    selected_count: int = 0


@dataclass(frozen=True)
class ActiveFilter:
    label: str
    remove_url: str


class OrganizationListing:
    """Build SQL filters without loading organizations into memory.

    Service choices are ORed inside a group; the visitor chooses AND or OR
    across groups. Facets respect general filters and, in AND mode, other
    selected groups. Their own group is excluded so alternatives stay available.
    Invalid parameters produce an explicit error and no results. Default ordering
    preserves the manager's commercial/editorial priorities; explicit sorts use
    the visitor's chosen criterion, with a primary-key tie breaker for pagination.
    """

    form: OrganizationFilterForm
    queryset: PageQuerySet
    service_groups: dict[int, ServiceGroup]
    active_filters: list[ActiveFilter]
    total: int
    count: int
    has_verified: bool
    has_closed: bool
    has_ratings: bool
    has_languages: bool
    is_filtered: bool
    service_match: Literal["all", "any"]
    counts_url: str

    def __init__(self, page: OrganizationType, request: HttpRequest) -> None:
        self.counts_url = request.path + page.reverse_subpage("filter_counts")
        base = Organization.objects.live().public().descendant_of(page)
        totals = base.aggregate(
            total=Count("pk"),
            verified=Count("pk", filter=Q(verified=True)),
            closed=Count("pk", filter=Q(temporarily_closed=True)),
            rated=Count("pk", filter=Q(avg_rating__gt=0)),
        )
        self.total = totals["total"]
        self.has_verified = bool(totals["verified"])
        self.has_closed = bool(totals["closed"])
        self.has_ratings = bool(totals["rated"])
        service_counts = self._service_counts(base)
        services = list(
            ServiceType.objects.filter(pk__in=service_counts)
            .select_related("category")
            .order_by("category__title", "name", "pk")
        )
        languages = list(
            Language._default_manager.filter(
                pk__in=base.order_by().values("languages")
            ).order_by("language_name", "pk")
        )
        self.has_languages = bool(languages)
        self.form = OrganizationFilterForm(request, services, languages)
        valid = self.form.is_valid()
        data = self.form.cleaned_data
        selected: list[str] = data.get("service_type", [])
        self.service_match = "any" if data.get("service_match") == "any" else "all"
        selected_groups: dict[int, list[int]] = {}
        for service in services:
            if str(service.pk) in selected:
                selected_groups.setdefault(service.category_id, []).append(service.pk)

        queryset = base
        if not valid:
            queryset = queryset.none()
        search: str = data.get("q", "")
        if search:
            queryset = queryset.filter(
                Q(
                    title__icontains=search,
                    h1_title__icontains=search,
                    address__icontains=search,
                    _connector=Q.OR,
                )
            )
        if data.get("rating"):
            queryset = queryset.filter(avg_rating__gte=data["rating"])
        if data.get("language"):
            queryset = queryset.filter(languages__pk=data["language"])
        if data.get("verified"):
            queryset = queryset.filter(verified=True)
        if data.get("hide_closed"):
            queryset = queryset.filter(temporarily_closed=False)
        facet_conditions: list[Q] = []
        service_conditions: list[Q] = []
        for group_id, ids in selected_groups.items():
            # Subqueries avoid row multiplication when several tags match.
            matches = Q(
                pk__in=base.order_by().filter(service_types__pk__in=ids).values("pk")
            )
            service_conditions.append(matches)
            if self.service_match == "all":
                # Bypass a group's own selection in the same join used to count
                # its options. All groups are counted in one aggregate query.
                facet_conditions.append(
                    Q(Q(service_types__category_id=group_id), matches, _connector=Q.OR)
                )
        service_counts = self._service_counts(queryset, Q(*facet_conditions))
        self.service_groups = {}
        for service in services:
            chosen = str(service.pk) in selected
            group = self.service_groups.setdefault(
                service.category_id, ServiceGroup(str(service.category), [])
            )
            group.options.append(
                ServiceOption(
                    str(service.pk),
                    str(service),
                    service_counts.get(service.pk, 0),
                    chosen,
                )
            )
            group.selected_count += int(chosen)
        queryset = queryset.filter(
            Q(
                *service_conditions,
                _connector=Q.OR if self.service_match == "any" else Q.AND,
            )
        )
        sort: str = data.get("sort", "")
        if sort == "rating":
            queryset = queryset.order_by("-avg_rating", "-rating_score", "pk")
        elif sort == "newest":
            queryset = queryset.order_by(
                F("first_published_at").desc(nulls_last=True), "pk"
            )
        elif sort == "name":
            queryset = queryset.order_by("title", "pk")
        else:
            queryset = queryset.order_by(*queryset.query.order_by, "pk")
        self.queryset = queryset.defer_streamfields().select_related(
            "premium_subscription"
        )
        self.is_filtered = any(
            any(request.GET.getlist(name) or [])
            for name in self.form.fields
            if name != "service_match"
        )
        self.count = (
            self.queryset.count() if self.is_filtered or not valid else self.total
        )
        self.active_filters = self._active_filters(request, data, services, languages)

    @staticmethod
    def _service_counts(
        queryset: PageQuerySet, conditions: Q | None = None
    ) -> dict[int, int]:
        """Count distinct public places per option without fetching their rows."""
        return dict(
            queryset.order_by()
            .filter(
                conditions if conditions is not None else Q(),
                service_types__isnull=False,
            )
            .values("service_types")
            .annotate(count=Count("pk", distinct=True))
            .values_list("service_types", "count")
        )

    def _active_filters(
        self,
        request: HttpRequest,
        data: dict[str, Any],
        services: list[ServiceType],
        languages: list[Language],
    ) -> list[ActiveFilter]:
        """Build removable applied-filter links; discard pagination on every edit."""
        values: list[tuple[str, str, str]] = []
        if data.get("q"):
            values.append(("q", data["q"], data["q"]))
        if data.get("rating"):
            values.append(
                (
                    "rating",
                    data["rating"],
                    str(_("Minimum rating")) + ": " + data["rating"] + "+",
                )
            )
        for name in ("verified", "hide_closed"):
            if data.get(name):
                values.append(
                    (
                        name,
                        str(request.GET.get(name, "")),
                        str(self.form.fields[name].label),
                    )
                )
        for language in languages:
            if str(language.pk) == data.get("language"):
                values.append(("language", str(language.pk), str(language)))
        for service in services:
            if str(service.pk) in data.get("service_type", []):
                values.append(("service_type", str(service.pk), str(service)))
        result: list[ActiveFilter] = []
        for name, value, label in values:
            params = request.GET.copy()
            params.pop("page", None)
            params.setlist(
                name, [item for item in (params.getlist(name) or []) if item != value]
            )
            result.append(
                ActiveFilter(
                    label,
                    request.path + "?" + params.urlencode() + "#organization-filters",
                )
            )
        return result


def has_category_listing(page: OrganizationType) -> bool:
    """Detect the category's editable list without resolving PageChooser objects."""
    content = page.content
    if not isinstance(content, StreamValue):
        return False
    return any(
        card["type"] == "paginated_organizations"
        and card["value"].get("page") in (None, page.pk)
        for block in StreamValue.get_prep_value(content)
        if block["type"] == "cards_section"
        for card in block["value"].get("cards", [])
    )
