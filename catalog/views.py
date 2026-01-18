import json
from functools import reduce

import django_filters
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.db.models import F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, Concat, JSONObject
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import DateRangePickerWidget, WagtailFilterSet
from wagtail.admin.views.reports import PageReportView
from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.viewsets.pages import PageListingViewSet
from wagtail.images.models import Rendition

from catalog.models import (City, Language, Organization, OrganizationImage, OrganizationType, Reward, ServiceType,
                            ServiceTypeCategory)
from catalog.utils import get_start_end_day, to_12h
from core.models import SiteSettings
from core.utils import get_weekday_name, get_weekday_number, is_ajax, paginate


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


def organizations(request):
    """Organizations list page."""
    filters = {}

    allowed_filters = ["address"]

    # Check if request is GET and has query parameters
    if request.method == "GET":
        for key, value in request.GET.items():
            if key in allowed_filters:
                filters[key] = value
    else:
        raise Http404

    organizations = (
        Organization.objects.live()
        .filter(**filters)
        .order_by("-avg_rating", "-first_published_at")
    )

    organizations = paginate(request, organizations, 20)

    context = {"organizations": organizations}
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


@permission_required("catalog.add_organization")
def import_organization(request):
    if not request.method == "POST":
        raise Http404

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    data_fields = data.keys()

    try:
        parent_id = data.get("parent_id")
        parent = OrganizationType.objects.get(id=int(parent_id))
    except (ValueError, OrganizationType.DoesNotExist):
        return JsonResponse(
            {"success": False, "message": "Invalid parent ID"}, status=400
        )

    # Check if Organization with this parent and legal name and address already exists
    legal_name = data.get("legal_name", "").strip()
    address = data.get("address_en", "").strip()
    if not legal_name:
        return JsonResponse(
            {"success": False, "message": "Legal name is required"}, status=400
        )
    if not address:
        return JsonResponse(
            {"success": False, "message": "AddressEn is required"}, status=400
        )
    if (
        Organization.objects.filter(
            legal_name__iexact=legal_name, address__iexact=address
        )
        .descendant_of(parent)
        .exists()
    ):
        return JsonResponse(
            {
                "success": False,
                "message": "Already exists!",
            },
            status=400,
        )

    awailable_fields = [
        "slug",
        "tin",
        "legal_name",
        "plus_code",
        "working_hours",
        "verified",
        "temporarily_closed",
        "languages",
        "ll",
        "show_on_map",
        "located_in",
        "service_types",
        "phones",
        "social_networks",
        "website_links",
    ]

    i18n_awailable_fields = [
        "title",
        "h1_title",
        "seo_title",
        "search_description",
        "description",
        "address",
        "how_to_arrive",
    ]

    awailable_locales = settings.MODELTRANSLATION_LANGUAGES

    for field in i18n_awailable_fields:
        for locale in awailable_locales:
            localized_field = f"{field}_{locale}"
            awailable_fields.append(localized_field)

    awailable_fields += i18n_awailable_fields

    new_organization = Organization()

    for field in data_fields:
        if field not in awailable_fields:
            continue

        # Get field type, ex: 'CharField', 'BooleanField', etc.
        field_type = new_organization._meta.get_field(field).get_internal_type()

        if field_type == "CharField":
            setattr(new_organization, field, data[field])
        elif field_type == "SlugField":
            slug = data[field].strip()
            if slug:
                setattr(new_organization, field, slug)
        elif (
            field_type == "TextField"
            and "search" not in field
            and "website" not in field
            and "social" not in field
        ):
            # Make paragraphs from text
            text = data[field].split("\n\n")
            text = "<p>" + "</p><p>".join(text) + "</p>"
            setattr(new_organization, field, text)
        elif field_type == "TextField":
            setattr(new_organization, field, data[field])
        elif field_type == "BooleanField":
            setattr(
                new_organization,
                field,
                data[field] in [True, "true", "True", 1, "yes", "on", "Yes", "On"],
            )
        elif field == "working_hours":
            if data[field]:
                wh = json.loads(data[field])
                days = []
                for day in wh:
                    if wh[day].lower() == "closed":
                        days.append(
                            {
                                "type": "day",
                                "value": {
                                    "day": get_weekday_number(day),
                                    "end": None,
                                    "start": None,
                                    "holiday": True,
                                    "last_client": False,
                                },
                            }
                        )
                    elif wh[day].lower() == "open 24 hours":
                        days.append(
                            {
                                "type": "day",
                                "value": {
                                    "day": get_weekday_number(day),
                                    "end": "23:59",
                                    "start": "00:00",
                                    "holiday": False,
                                    "last_client": False,
                                },
                            }
                        )
                    else:
                        try:
                            start, end = get_start_end_day(wh[day])
                        except ValueError:
                            return JsonResponse(
                                {
                                    "success": False,
                                    "message": f"Invalid working hours format for {day}",
                                },
                                status=400,
                            )

                        days.append(
                            {
                                "type": "day",
                                "value": {
                                    "day": get_weekday_number(day),
                                    "end": end,
                                    "start": start,
                                    "holiday": False,
                                },
                            }
                        )

                new_organization.working_hours = days
        elif field == "located_in":
            located_in = data.get(field, "")
            if located_in:
                try:
                    located_in = int(located_in)
                    new_organization.located_in = Organization.objects.get(
                        id=located_in
                    )
                except (ValueError, Organization.DoesNotExist):
                    return JsonResponse(
                        {"success": False, "message": "Invalid located_in ID"},
                        status=400,
                    )

    try:
        parent.numchild = parent.get_children().count()
        parent.add_child(instance=new_organization)
        parent.numchild += 1
        parent.save()
        new_organization.save_revision().publish()

        if "service_types" in data_fields:
            sts = []
            for st in data["service_types"].split(","):
                names = []
                for locale in awailable_locales:
                    field_name = f"name_{locale}__iexact"
                    names.append(Q(**{field_name: st.strip()}))

                try:
                    sts.append(
                        ServiceType.objects.get(reduce(lambda x, y: x | y, names))
                    )
                except ServiceType.DoesNotExist:
                    continue

                if sts:
                    new_organization.service_types.set(sts)
                    new_organization.save_revision().publish()

        if "languages" in data_fields:
            langs = []
            for lang in data["languages"].split(","):
                try:
                    language_obj = Language.objects.get(
                        language_name__iexact=lang.strip()
                    )
                    langs.append(language_obj)
                except Language.DoesNotExist:
                    continue

            if langs:
                new_organization.languages.set(langs)
                new_organization.save_revision().publish()

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

    return JsonResponse({"success": True}, status=200)


class OrganizationReportFilters(WagtailFilterSet):
    """Filters for the Organization report."""

    published_at = django_filters.DateFromToRangeFilter(
        # change to "last_published_at" if that's your field
        field_name="first_published_at",
        label="Published at",
        # Optional: force native date inputs
        widget=DateRangePickerWidget,
    )

    class Meta:
        model = Organization
        fields = {
            "live": ["exact"],
        }


def get_organization_export_fields():
    fields = (
        "id",
        ".h1_title",
        ".title",
        "legal_name",
        ".seo_title",
        ".search_description",
        ".description",
        ".how_to_arrive",
        "url",
        "phones",
        ".address",
        "tin",
        "plus_code",
        "working_hours",
        "ll",
        "show_on_map",
        "social_networks",
        "website_links",
        "verified",
        "temporarily_closed",
        "first_published_at",
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

        data[day["day"]] = get_hours(day["start"], day["end"], day["holiday"])

    return json.dumps(data, ensure_ascii=False)


def description_handler(value):
    """Convert description to a simple text without HTML tags."""
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

    list_export = get_organization_export_fields()

    export_headings = get_organization_export_headings()

    custom_field_preprocess = build_custom_field_preprocess()

    def get_queryset(self):
        return Organization.objects.live()


def get_organizations_data(request):
    """Возвращает данные организаций для заданного типа организаций — без Python-цикла."""

    if request.method == "GET" and is_ajax(request):
        org_type_id = request.GET.get("org_type_id", "").strip()

        try:
            org_type = OrganizationType.objects.get(id=int(org_type_id))
        except (ValueError, OrganizationType.DoesNotExist):
            return JsonResponse({"message": "Invalid organization type ID"}, status=400)

        org_type_url = org_type.url

        # --- Подзапрос: находим ID первого изображения организации ---
        first_image_id_sq = (
            OrganizationImage.objects.filter(page_id=OuterRef("pk"))
            .order_by("sort_order")
            .values("image_id")[:1]
        )

        # --- Подзапрос: рендер с шириной 720 ---
        rendition_file_sq = Rendition.objects.filter(
            image_id=Subquery(first_image_id_sq), filter_spec="width-720"
        ).values("file")[:1]

        # --- Подзапрос: оригинальный файл (если rendition нет) ---
        original_file_sq = (
            OrganizationImage.objects.filter(page_id=OuterRef("pk"))
            .order_by("sort_order")
            .values("image__file")[:1]
        )

        default_image = SiteSettings.default_organization_image

        # --- Итоговый URL картинки (Coalesce выбирает первый доступный вариант) ---
        image_file_sq = Coalesce(
            Subquery(rendition_file_sq),
            Subquery(original_file_sq),
            default_image.get_queryset().values("file")[:1],
        )
        image_url_expr = Concat(Value(settings.MEDIA_URL), image_file_sq)

        # --- Основной queryset ---
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

        # --- Преобразуем QuerySet в dict ---
        data = {str(pk): obj for pk, obj in qs}

        return JsonResponse(data, safe=False)

    raise Http404
