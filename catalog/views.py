import json
from datetime import datetime

import django_filters
from django.conf import settings
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import (
    CharField,
    Count,
    F,
    OuterRef,
    Subquery,
    Value,
)
from django.db.models.functions import Cast, Coalesce, Concat, JSONObject
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import DateRangePickerWidget, WagtailFilterSet
from wagtail.admin.views.reports import PageReportView
from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.viewsets.pages import PageListingViewSet
from wagtail.images.models import Rendition

from catalog.models import (
    City,
    Language,
    Organization,
    OrganizationImage,
    OrganizationType,
    Reward,
    ServiceType,
    ServiceTypeCategory,
)
from catalog.utils import to_12h
from core.models import SiteSettings
from core.utils import get_weekday_name, is_ajax, paginate


def search_cities(request):
    """Used for AJAX city search in header."""
    if request.method == "GET" and is_ajax(request):
        query = request.GET.get("q", "").strip().lower()
        cities = (
            City.objects.live().filter(title__istartswith=query).order_by("title")[:20]
        )
        cities = map(lambda city: {"url": city.url, "title": city.title}, cities)
        return JsonResponse(list(cities), safe=False)
    raise Http404


def organizations(request: HttpRequest) -> HttpResponse:
    """Organizations list page."""
    filters = {}
    parent_id = None
    parent = None

    allowed_filters = ["address", "organization_type"]

    # Check if request is GET and has query parameters
    if request.method == "GET":
        for key, value in request.GET.items():
            if key == "page":
                continue
            if key in allowed_filters:
                if key == "organization_type":
                    parent_id = value
                    continue
                filters[key] = value
            else:
                raise Http404
    else:
        raise Http404

    if not filters:
        raise Http404

    if parent_id:
        try:
            parent = OrganizationType.objects.live().get(id=parent_id)
        except OrganizationType.DoesNotExist:
            raise Http404

    orgs = Organization.objects.live().defer_streamfields()

    if parent:
        orgs = orgs.descendant_of(parent)
    if filters:
        orgs = orgs.filter(**filters)

    if not orgs:
        raise Http404

    orgs = paginate(request, orgs, 20)

    context = {"organizations": orgs}
    return render(request, "catalog/organizations.html", context)


class CityPageFilterSet(PageListingViewSet.filterset_class):  # type: ignore
    class Meta:
        model = City
        fields = ["popular"]


class CityPageListingViewSet(PageListingViewSet):
    model = City
    menu_label = _("Cities")
    add_to_admin_menu = False
    icon = "building-solid"
    filterset_class = CityPageFilterSet


class OrganizationTypePageListingViewSet(PageListingViewSet):
    model = OrganizationType
    menu_label = _("Organizations types")
    add_to_admin_menu = False
    icon = "store-solid"


class OrganizationPageListingViewSet(PageListingViewSet):
    model = Organization
    menu_label = _("Organizations")
    add_to_admin_menu = False
    icon = "briefcase-solid"


class ServiceTypeCategoryViewSet(ModelViewSet):
    model = ServiceTypeCategory
    menu_label = _("Service type categories")  # type: ignore
    add_to_admin_menu = False
    icon = "folder-open-inverse"
    search_fields = ["title"]  # type: ignore


class ServiceTypeCategoryChooserViewSet(ChooserViewSet):
    model = ServiceTypeCategory
    icon = "folder-open-inverse"
    choose_one_text = _("Choose a category")
    choose_another_text = _("Choose another category")
    edit_item_text = _("Edit this category")


service_type_category_chooser_viewset = ServiceTypeCategoryChooserViewSet(
    "catalog_service_type_category_chooser"
)


class ServiceTypeViewSet(ModelViewSet):
    model = ServiceType
    menu_label = _("Service types")  # type: ignore
    add_to_admin_menu = False
    icon = "tag"
    search_fields = ["name"]  # type: ignore


class LanguageViewSet(ModelViewSet):
    model = Language
    menu_label = _("Languages")  # type: ignore
    add_to_admin_menu = False
    icon = "globe"
    form_fields = ("language_name", "icon")


class RewardViewSet(ModelViewSet):
    model = Reward
    icon = "pick"  # type: ignore


class CatalogViewSetGroup(ViewSetGroup):
    menu_label = _("Catalog")
    menu_icon = "folder-open-inverse"
    items = (
        CityPageListingViewSet("catalog_city_pages"),
        OrganizationTypePageListingViewSet("catalog_organization_type_pages"),
        OrganizationPageListingViewSet("catalog_organization_pages"),
        ServiceTypeCategoryViewSet("catalog_service_type_categories"),
        ServiceTypeViewSet("catalog_service_types"),
        RewardViewSet("catalog_rewards"),
        LanguageViewSet("catalog_languages"),
    )
    menu_order = 100


class OrganizationReportFilters(WagtailFilterSet):
    """Filters for the Organization report."""

    published_at = django_filters.DateFromToRangeFilter(
        field_name="first_published_at",
        label=_("Published at"),
        widget=DateRangePickerWidget,
    )

    updated_at = django_filters.DateFromToRangeFilter(
        field_name="last_published_at",
        label=_("Updated at"),
        widget=DateRangePickerWidget,
    )

    city = django_filters.CharFilter(
        label=_("City"),
    )

    organization_type = django_filters.CharFilter(label=_("Organization type"))

    def filter_queryset(self, queryset):
        live = self.data.get("live")
        if live:
            live = live == "true"
            queryset = queryset.filter(live=live)

        published_at_from = self.data.get("published_at_from")
        published_at_to = self.data.get("published_at_to")
        updated_at_from = self.data.get("updated_at_from")
        updated_at_to = self.data.get("updated_at_to")

        if published_at_from:
            published_at_from = published_at_from.strip()
            queryset = queryset.filter(
                first_published_at__gte=make_aware(
                    datetime.strptime(published_at_from, "%Y-%m-%d")
                )
            )
        if published_at_to:
            published_at_to = published_at_to.strip()
            queryset = queryset.filter(
                first_published_at__lte=make_aware(
                    datetime.strptime(published_at_to, "%Y-%m-%d")
                )
            )

        if updated_at_from:
            updated_at_from = updated_at_from.strip()
            queryset = queryset.filter(
                latest_revision_created_at__gte=make_aware(
                    datetime.strptime(updated_at_from, "%Y-%m-%d")
                )
            )

        if updated_at_to:
            updated_at_to = updated_at_to.strip()
            queryset = queryset.filter(
                latest_revision_created_at__lte=make_aware(
                    datetime.strptime(updated_at_to, "%Y-%m-%d")
                )
            )

        city = self.data.get("city")
        if city:
            city = city.strip()
            city = City.objects.filter(title__iexact=city).first()
            if not city:
                return queryset.none()
            queryset = queryset.descendant_of(city)

        organization_type = self.data.get("organization_type")
        if organization_type:
            organization_type = organization_type.strip()
            organization_type = OrganizationType.objects.filter(
                title__iexact=organization_type
            )

            if not organization_type:
                return queryset.none()

            if city:
                organization_type = organization_type.descendant_of(city)

            _qs = []
            for ot in organization_type:
                _qs += queryset.descendant_of(ot)
            queryset = _qs
        return queryset

    class Meta:
        model = Organization
        fields = {
            "live": ["exact"],
        }


def get_organization_export_fields():
    fields = (
        "id",
        "url",
        ".title",
        ".h1_title",
        ".seo_title",
        ".search_description",
        "tin",
        "legal_name",
        "verified",
        "plus_code",
        "email",
        "phones",
        "social_networks",
        "website_links",
        "working_hours",
        "temporarily_closed",
        "languages",
        ".description",
        ".address",
        ".how_to_arrive",
        "ll",
        "show_on_map",
        "images_count",
        "images_captions",
        "images_ids",
        "reviews_count",
        "avg_rating",
        "organization_type",
        "city",
    )

    i18n_fields = []

    for field in fields:
        if field.startswith("."):
            base_field = field[1:]
            for locale in settings.MODELTRANSLATION_LANGUAGES:
                i18n_fields.append(f"{base_field}_{locale}")
        else:
            i18n_fields.append(field)

    return i18n_fields


def get_organization_export_headings():
    headings = {}

    for field in get_organization_export_fields():
        headings[field] = field

    return headings


def working_hours_handler(value):
    data = {}
    days = value.raw_data

    if not days:
        return ""

    def get_hours(start, end, holiday):
        if holiday:
            return "Closed"
        if not start or not end:
            return ""
        return f"{to_12h(start)}-{to_12h(end)}"

    for day in days:
        day = day["value"]
        day["day"] = get_weekday_name(int(day["day"]))

        data[day["day"]] = get_hours(
            day.get("start", _("Unknown")),
            day.get("end", _("Unknown")),
            day.get("holiday", _("Unknown")),
        )

    return json.dumps(data, ensure_ascii=False)


def description_handler(value):
    """Convert a description to a simple text without HTML tags."""
    if not value:
        return ""

    # Remove HTML tags and decode entities
    return strip_tags(value).strip()


def url_handler(value):
    # Make full URL from the page URL
    if not value:
        return ""

    full_url = settings.WAGTAILADMIN_BASE_URL + value
    return full_url if full_url.endswith("/") else full_url + "/"


# base handlers once
_BASE_PREPROCESS = {
    "working_hours": {
        "csv": working_hours_handler,
        "xlsx": working_hours_handler,
    },
    "url": {
        "csv": url_handler,
        "xlsx": url_handler,
    },
    "description": {
        "csv": description_handler,
        "xlsx": description_handler,
    },
}


def build_custom_field_preprocess():
    # start with base
    out = dict(_BASE_PREPROCESS)
    extra = {}

    for locale in settings.MODELTRANSLATION_LANGUAGES:
        for field, handlers in _BASE_PREPROCESS.items():
            # Create a localized version of the field
            localized_field = f"{field}_{locale}"
            if hasattr(Organization, localized_field):
                extra[localized_field] = handlers
    # Add localized handlers to the output
    out.update(extra)
    return out


class OrganizationReportView(PageReportView):
    page_title = _("Organizations report")
    index_url_name = "organizations_report"
    index_results_url_name = "organizations_report_results"
    filterset_class = OrganizationReportFilters

    search_fields = ["title", "h1_title"]
    is_searchable = True

    list_export = get_organization_export_fields()

    export_headings = get_organization_export_headings()

    custom_field_preprocess = build_custom_field_preprocess()

    def get_queryset(self):
        qs = Organization.objects.live().defer_streamfields()

        def is_downloading():
            is_export = self.request.GET.get("export", False)
            return is_export and is_export in ["csv", "xlsx"]

        if is_downloading():
            qs = qs.annotate(
                images_count=Count("images", distinct=True),
                reviews_count=Count("reviews", distinct=True),
                images_captions=StringAgg(
                    "images__image__title", delimiter="\n", distinct=True
                ),
                images_ids=StringAgg(
                    Cast("images__image__id", CharField()),
                    delimiter=", ",
                    distinct=True,
                ),
            )

        if self.search_query:
            qs = qs.search(self.search_query)

        return qs


def get_organizations_data(request):
    """Return organization data for a given organization type — without a Python loop."""

    if request.method == "GET" and is_ajax(request):
        org_type_id = request.GET.get("org_type_id", "").strip()

        try:
            org_type = OrganizationType.objects.get(id=int(org_type_id))
        except (ValueError, OrganizationType.DoesNotExist):
            return JsonResponse({"message": "Invalid organization type ID"}, status=400)

        org_type_url = org_type.url

        # --- Subquery: find the ID of the first organization image ---
        first_image_id_sq = (
            OrganizationImage.objects.filter(page_id=OuterRef("pk"))
            .order_by("sort_order")
            .values("image_id")[:1]
        )

        # --- Subquery: render with width 720 ---
        rendition_file_sq = Rendition.objects.filter(
            image_id=Subquery(first_image_id_sq), filter_spec="width-720"
        ).values("file")[:1]

        # --- Subquery: original file (if rendition doesn't exist) ---
        original_file_sq = (
            OrganizationImage.objects.filter(page_id=OuterRef("pk"))
            .order_by("sort_order")
            .values("image__file")[:1]
        )

        default_image = SiteSettings.default_organization_image

        # --- Final image URL (Coalesce selects the first available option) ---
        image_file_sq = Coalesce(
            Subquery(rendition_file_sq),
            Subquery(original_file_sq),
            default_image.get_queryset().values("file")[:1],
        )
        image_url_expr = Concat(Value(settings.MEDIA_URL), image_file_sq)

        # --- Main queryset ---
        qs = (
            Organization.objects.live()
            .descendant_of(org_type)
            .annotate(
                image_url=image_url_expr,
                payload=JSONObject(
                    title=F("title"),
                    rating=F("avg_rating"),
                    ll=F("ll"),
                    url=Concat(Value(org_type_url), F("slug"), Value("/")),
                    image=F("image_url"),
                ),
            )
            .values_list("id", "payload")
        )

        # --- Convert QuerySet to dict ---
        data = {str(pk): obj for pk, obj in qs}

        return JsonResponse(data, safe=False)

    raise Http404
