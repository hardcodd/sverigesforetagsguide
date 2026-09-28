import json
import logging
import os
from typing import Any, Iterable, cast

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from django.db.models.options import Options
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST
from wagtail.admin.auth import require_admin_access
from wagtail.models import Page, Site, get_page_models
from wagtail.snippets.views.snippets import SnippetViewSet

from core import field_handlers
from core.models import Footer, RobotsTxtSettings

logger = logging.getLogger(__name__)


class FooterViewSet(SnippetViewSet):
    model = Footer
    icon = "bars"  # type: ignore
    list_display = ["__str__"]  # type: ignore


def robots_txt(request):
    site = Site.find_for_request(request)
    rt_settings = RobotsTxtSettings.for_site(site)
    content = str(rt_settings.content or "").encode(settings.DEFAULT_CHARSET)
    return HttpResponse(content, content_type="text/plain")


SITEMAP_ROOT = os.path.join(settings.BASE_DIR, "app", "templates", "sitemaps")


def sitemap_index(request):
    """
    Главный sitemap-index
    """
    template_path = os.path.join(SITEMAP_ROOT, "sitemap.xml")
    if not os.path.exists(template_path):
        raise Http404("Sitemap index not found")
    return render(request, "sitemaps/sitemap.xml", content_type="application/xml")


def sitemap_section(request, lang, section, num):
    """
    Отдельные sitemap-файлы для типа страниц и языка
    """
    if lang not in dict(settings.LANGUAGES):
        raise Http404(f"Unknown language: {lang}")

    # строим путь к файлу
    template_path = os.path.join(SITEMAP_ROOT, lang, section, f"sitemap-{num}.xml")

    if not os.path.exists(template_path):
        raise Http404(f"Sitemap not found: {lang}/{section}/sitemap-{num}.xml")

    # путь относительно templates/ — чтобы render нашёл
    template_relative = os.path.relpath(
        template_path, os.path.join(settings.BASE_DIR, "app", "templates")
    )
    return render(request, template_relative, content_type="application/xml")


def get_page_model(page_type: str) -> type[Page]:
    model_class = import_string(page_type)

    allowed_page_models = {
        candidate_model
        for candidate_model in get_page_models()
        if (
            candidate_model is not Page
            and candidate_model.is_creatable
            and candidate_model.max_count is None
        )
    }

    if not isinstance(model_class, type) or model_class not in allowed_page_models:
        raise ValueError(_("Invalid page type"))

    return cast(type[Page], model_class)


def run_field_handler(obj: Model, field_name: str, field_value: Any) -> None:
    model_meta = cast(Options, getattr(obj, "_meta"))
    model_field = model_meta.get_field(field_name)
    handler_names = (
        f"{field_name}_handler",
        f"{model_field.get_internal_type().lower()}_handler",
    )

    for handler_name in dict.fromkeys(handler_names):
        handler = getattr(field_handlers, handler_name, None)

        if handler is None:
            continue
        if not callable(handler):
            raise TypeError(
                _("Field handler %(handler_name)r is not callable")
                % {"handler_name": handler_name}
            )

        handler(obj, field_name, field_value)
        return

    raise ValueError(
        _("No handler found for field %(field)r; tried: %(handler_names)s")
        % {"field": field_name, "handler_names": ", ".join(handler_names)}
    )


def check_unique(
    page_model: type[Page],
    field_names: Iterable[str],
    mapped_data: dict[str, Any],
    exclude_page_id: int | None = None,
) -> None:
    model_meta = cast(Options, getattr(page_model, "_meta"))
    unknown_fields: list[str] = []
    empty_fields: list[str] = []
    non_unique_fields: list[str] = []

    for field_name in sorted(field_names):
        try:
            model_meta.get_field(field_name)
        except FieldDoesNotExist:
            unknown_fields.append(field_name)
            continue

        field_value = mapped_data.get(field_name)

        if field_value is None or field_value == "":
            empty_fields.append(field_name)
            continue

        duplicates = page_model.objects.filter(**{field_name: field_value})

        if exclude_page_id is not None:
            duplicates = duplicates.exclude(pk=exclude_page_id)

        if duplicates.exists():
            non_unique_fields.append(field_name)

    errors: list[str] = []

    if unknown_fields:
        errors.append(
            ngettext(
                "Unknown unique field: %(fields)s",
                "Unknown unique fields: %(fields)s",
                len(unknown_fields),
            )
            % {"fields": ", ".join(map(repr, unknown_fields))}
        )

    if empty_fields:
        errors.append(
            ngettext(
                "Field %(fields)s cannot be empty",
                "Fields %(fields)s cannot be empty",
                len(empty_fields),
            )
            % {"fields": ", ".join(map(repr, empty_fields))}
        )

    if non_unique_fields:
        errors.append(
            ngettext(
                "Field %(fields)s must be unique",
                "Fields %(fields)s must be unique",
                len(non_unique_fields),
            )
            % {"fields": ", ".join(map(repr, non_unique_fields))}
        )

    if errors:
        raise ValueError("; ".join(errors))


def set_attr(obj: Model, field_name: str, field_value: Any) -> None:
    if field_value is None or field_value == "":
        return

    skip_fields = frozenset({"parent_id"})

    if field_name in skip_fields:
        return

    try:
        run_field_handler(obj, field_name, field_value)
    except FieldDoesNotExist as field_error:
        raise ValueError(
            _("Object %(obj)s does not have field %(field)r")
            % {"obj": obj, "field": field_name}
        ) from field_error
    except Exception as handler_error:
        if not isinstance(handler_error, (KeyError, TypeError, ValueError)):
            logger.exception("Unexpected error setting import field %r", field_name)
        raise ValueError(
            _("Error setting field %(field)r: %(error)s")
            % {"field": field_name, "error": handler_error}
        ) from handler_error

    print(
        _("Set field %(field)r to %(value)r on %(obj)r")
        % {"field": field_name, "value": field_value, "obj": obj}
    )


@require_admin_access
@require_POST
def import_page(request):
    def result(success: bool, message: str, status: int) -> JsonResponse:
        return JsonResponse(
            {
                "success": success,
                "message": message,
            },
            status=status,
            json_dumps_params={"ensure_ascii": False},
        )

    page_type = request.POST.get("page_type", "").strip()

    if not page_type:
        return result(False, "Page type not provided", 400)

    raw_csv_row = request.POST.get("csv_row")

    if raw_csv_row is None:
        return result(False, "CSV row was not provided", 400)

    try:
        csv_row = json.loads(raw_csv_row)
    except json.JSONDecodeError as json_error:
        return result(False, f"CSV row contains invalid JSON: {json_error}", 400)

    if not isinstance(csv_row, dict):
        return result(False, "CSV row must be a JSON object", 400)

    field_mapping: dict[str, str] = {}
    unique_fields: set[str] = set()

    for request_key, request_value in request.POST.items():
        if request_key.startswith("field_mapping[") and request_key.endswith("]"):
            mapping_field_name = request_key[len("field_mapping[") : -1]

            if mapping_field_name and request_value:
                field_mapping[mapping_field_name] = request_value

        elif request_key.startswith("unique[") and request_key.endswith("]"):
            unique_field_name = request_key[len("unique[") : -1]

            if unique_field_name:
                unique_fields.add(unique_field_name)

    if not field_mapping:
        return result(False, _("Field mapping was not provided"), 400)

    missing_csv_fields = sorted(
        missing_field_name
        for missing_field_name in field_mapping.values()
        if missing_field_name not in csv_row
    )

    if missing_csv_fields:
        message = _("CSV fields not found: %(missing_csv_fields)s") % {
            "missing_csv_fields": ", ".join(missing_csv_fields)
        }
        return result(
            False,
            message,
            400,
        )

    mapped_data = {
        mapped_field_name: csv_row[source_field_name]
        for mapped_field_name, source_field_name in field_mapping.items()
    }

    try:
        page_model = get_page_model(page_type)

        page_id = mapped_data.pop("id", None)
        unique_fields.discard("id")

        try:
            page_id = int(page_id) if page_id else None
        except (TypeError, ValueError):
            return result(False, "Invalid page ID", 400)

        check_unique(
            page_model,
            unique_fields,
            mapped_data,
            exclude_page_id=page_id,
        )

        if page_id:
            try:
                existing_page = Page.objects.get(id=page_id).specific
            except Page.DoesNotExist:
                return result(False, "Page does not exist", 400)

            if not isinstance(existing_page, page_model):
                return result(False, _("Page type does not match existing page"), 400)

            if not existing_page.permissions_for_user(request.user).can_edit():
                return result(False, _("Permission denied"), 403)

            for field_name, field_value in mapped_data.items():
                set_attr(existing_page, field_name, field_value)

            try:
                existing_page.save_revision().publish()
            except Exception as save_error:
                return result(False, str(save_error), 400)

            return result(True, _("Updated successfully"), 200)

        parent_id = mapped_data.get("parent_id", None)
        if not parent_id:
            return result(False, "parent_id is required", 400)

        try:
            parent_page = Page.objects.get(id=int(parent_id)).specific
        except (TypeError, ValueError, Page.DoesNotExist):
            return result(False, "parent_id does not exist", 400)

        if not parent_page.permissions_for_user(request.user).can_add_subpage():
            return result(False, _("Permission denied"), 403)

        if page_model not in type(
            parent_page
        ).creatable_subpage_models() or not page_model.can_create_at(parent_page):
            return result(False, _("Page type is not allowed under this parent"), 400)

        new_page = page_model()

        for field_name, field_value in mapped_data.items():
            set_attr(new_page, field_name, field_value)

        try:
            parent_page.numchild = parent_page.get_children().count()
            parent_page.add_child(instance=new_page)
            parent_page.numchild += 1
            parent_page.save()
            new_page.save_revision().publish()
        except Exception as save_error:
            return result(False, str(save_error), 400)

        return result(True, _("Imported successfully"), 200)

    except (ImportError, TypeError, ValueError, KeyError) as import_error:
        return result(False, str(import_error), 400)
    except Exception as import_error:
        logger.exception("Unexpected error while importing a page from a CSV row")
        message = str(import_error) or _("Unexpected page import error")
        return result(False, message, 500)
