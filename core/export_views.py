import csv
import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Iterable, cast

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model, Q
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.html import strip_tags
from django.utils.module_loading import import_string
from django.utils.text import capfirst, format_lazy, slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET, require_POST
from wagtail.admin.auth import require_admin_access
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page, get_page_models

from core.serializers import serialize_page_field

EXPORTS_DIR = os.path.join(settings.BASE_DIR, "_exports")
EXPORT_FILE_MAX_AGE_SECONDS = 24 * 60 * 60

BASE_EXPORT_FIELDS = (
    "id",
    "title",
    "full_url",
    "first_published_at",
    "last_published_at",
    "parent_title",
    "seo_title",
    "search_description",
)

SYNTHETIC_EXPORT_FIELD_LABELS = {
    "full_url": gettext_lazy("URL"),
    "parent_id": format_lazy("{} — ID", gettext_lazy("Parent page")),
    "parent_title": format_lazy(
        "{} — {}",
        gettext_lazy("Parent page"),
        gettext_lazy("Title"),
    ),
    "reviews_count": gettext_lazy("Reviews count"),
}

EXCLUDED_EXPORT_FIELDS = frozenset(
    {
        "_revisions",
        "_workflow_states",
        "_specific_workflow_states",
        "index_entries",
        "alias_of",
        "page_ptr",
        "show_in_menus",
        "draft_title",
        "expire_at",
        "expired",
        "locked",
        "locked_at",
        "locked_by",
        "translation_key",
        "locale",
        "latest_revision",
        "path",
        "depth",
        "numchild",
        "content_type",
    }
)


def delete_export_artifact(file_path: str) -> None:
    exports_dir = os.path.realpath(EXPORTS_DIR)
    resolved_path = os.path.realpath(file_path)

    if os.path.dirname(resolved_path) != exports_dir:
        return

    try:
        os.remove(resolved_path)
    except FileNotFoundError:
        pass


def cleanup_stale_exports() -> None:
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    cutoff_timestamp = timezone.now().timestamp() - EXPORT_FILE_MAX_AGE_SECONDS

    with os.scandir(EXPORTS_DIR) as entries:
        for entry in entries:
            try:
                if (
                    not entry.is_file(follow_symlinks=False)
                    or entry.stat(follow_symlinks=False).st_mtime >= cutoff_timestamp
                ):
                    continue

                delete_export_artifact(entry.path)
            except FileNotFoundError:
                continue


class CleanupFileResponse(FileResponse):
    def __init__(
        self,
        *args: Any,
        cleanup_paths: Iterable[str],
        **kwargs: Any,
    ) -> None:
        self.cleanup_paths = tuple(cleanup_paths)
        super().__init__(*args, **kwargs)

    def close(self) -> None:
        try:
            super().close()
        finally:
            cleanup_paths = self.cleanup_paths
            self.cleanup_paths = ()

            for file_path in cleanup_paths:
                delete_export_artifact(file_path)


def export_pages(request):
    page_types = sorted(
        (get_page_type_payload(model) for model in get_allowed_page_models()),
        key=lambda item: item["label"].lower(),
    )

    return render(
        request,
        "core/export_pages.html",
        {
            "page_types": page_types,
            "export_fields_url": reverse("core:export_page_fields"),
            "search_parent_pages_url": reverse("core:search_parent_pages"),
            "start_export_url": reverse("core:start_pages_export"),
            "export_progress_url": reverse(
                "core:export_progress",
                kwargs={"job_id": "__JOB_ID__"},
            ),
        },
    )


def get_export_job_path(job_id: str) -> str:
    safe_job_id = "".join(character for character in job_id if character.isalnum())

    if not safe_job_id or safe_job_id != job_id:
        raise ValueError(_("Invalid export job ID"))

    return os.path.join(EXPORTS_DIR, f"{safe_job_id}.json")


def set_export_job(job_id: str, data: dict[str, Any]) -> None:
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    job_path = get_export_job_path(job_id)
    temporary_path = f"{job_path}.tmp"

    with open(temporary_path, "w", encoding="utf-8") as job_file:
        json.dump(data, job_file, ensure_ascii=False)

    os.replace(temporary_path, job_path)


def get_export_job(job_id: str) -> dict[str, Any] | None:
    try:
        job_path = get_export_job_path(job_id)
    except ValueError:
        return None

    if not os.path.exists(job_path):
        return None

    try:
        with open(job_path, encoding="utf-8") as job_file:
            value = json.load(job_file)
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(value, dict):
        return value

    return None


def get_allowed_page_models() -> list[type[Page]]:
    return [
        model for model in get_page_models() if model is not Page and model.is_creatable
    ]


def get_page_model(page_type: str) -> type[Page]:
    try:
        model_class = apps.get_model(page_type)
    except (LookupError, ValueError) as error:
        raise ValueError(_("Invalid page type")) from error

    if model_class not in get_allowed_page_models():
        raise ValueError(_("Invalid page type"))

    return cast(type[Page], model_class)


def get_page_type_payload(model: type[Page]) -> dict[str, str]:
    return {
        "value": model._meta.label,
        "label": str(model._meta.verbose_name),
    }


def is_exportable_model_field(field: Any) -> bool:
    if getattr(field, "auto_created", False) and not getattr(field, "concrete", False):
        return False

    if (
        getattr(field, "many_to_one", False)
        and getattr(field, "related_model", None) is None
    ):
        return False

    return getattr(field, "name", None) not in EXCLUDED_EXPORT_FIELDS


def remove_base_fields_with_translations(
    fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    language_suffixes = tuple(
        sorted(
            (
                str(language_code).replace("-", "_")
                for language_code in settings.MODELTRANSLATION_LANGUAGES
            ),
            key=len,
            reverse=True,
        )
    )
    fields_by_name = {field["name"]: field for field in fields}
    field_names = set(fields_by_name)
    translated_base_names = set()
    translated_field_base_names: dict[str, str] = {}

    for field_name in field_names:
        for language_suffix in language_suffixes:
            postfix = f"_{language_suffix}"

            if not field_name.endswith(postfix):
                continue

            base_field_name = field_name.removesuffix(postfix)

            if base_field_name in field_names:
                translated_base_names.add(base_field_name)
                translated_field_base_names[field_name] = base_field_name

            break

    result = []

    for field in fields:
        field_name = field["name"]

        if field_name in translated_base_names:
            continue

        base_field_name = translated_field_base_names.get(field_name)

        if base_field_name is None:
            result.append(field)
            continue

        base_field = fields_by_name[base_field_name]
        result.append(
            {
                **field,
                "default": bool(field.get("default") or base_field.get("default")),
                "translation_group": base_field_name,
            }
        )

    return result


def get_base_export_field_label(model: type[Page], field_name: str) -> str:
    synthetic_label = SYNTHETIC_EXPORT_FIELD_LABELS.get(field_name)

    if synthetic_label is not None:
        return capfirst(str(synthetic_label))

    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return capfirst(field_name.replace("_", " "))

    return capfirst(str(field.verbose_name))


def get_model_export_fields(model: type[Page]) -> list[dict[str, Any]]:
    seen = set()
    fields: list[dict[str, Any]] = []

    for field_name in BASE_EXPORT_FIELDS:
        seen.add(field_name)
        fields.append(
            {
                "name": field_name,
                "label": get_base_export_field_label(model, field_name),
                "default": True,
            }
        )

    for field in model._meta.get_fields():
        field_name = getattr(field, "name", "")

        if not field_name or field_name in seen or not is_exportable_model_field(field):
            continue

        seen.add(field_name)

        if field_name == "reviews":
            fields.append(
                {
                    "name": "reviews_count",
                    "label": capfirst(
                        str(SYNTHETIC_EXPORT_FIELD_LABELS["reviews_count"])
                    ),
                    "default": False,
                }
            )
            continue

        fields.append(
            {
                "name": field_name,
                "label": capfirst(str(getattr(field, "verbose_name", field_name))),
                "default": False,
            }
        )

    return remove_base_fields_with_translations(fields)


@require_admin_access
@require_GET
def export_page_types(request):
    page_types = sorted(
        (get_page_type_payload(model) for model in get_allowed_page_models()),
        key=lambda item: item["label"].lower(),
    )

    return JsonResponse({"page_types": page_types})


@require_admin_access
@require_GET
def export_page_fields(request):
    page_type = request.GET.get("page_type", "").strip()

    if not page_type:
        return JsonResponse({"fields": []})

    try:
        page_model = get_page_model(page_type)
    except (ImportError, ValueError):
        return JsonResponse({"message": _("Invalid page type")}, status=400)

    return JsonResponse({"fields": get_model_export_fields(page_model)})


@require_admin_access
@require_GET
def search_parent_pages(request):
    query = request.GET.get("q", "").strip()
    page_type = request.GET.get("page_type", "").strip()

    pages = Page.objects.all()

    if page_type:
        try:
            page_model = get_page_model(page_type)
            allowed_parent_models = page_model.allowed_parent_page_models()
            pages = pages.type(*allowed_parent_models)
        except (ImportError, ValueError):
            return JsonResponse({"results": []})

    if query:
        pages = pages.filter(get_parent_page_search_query(query))

    results = [
        {
            "id": page.id,
            "title": page.specific_deferred.title,
            "path": page.url_path,
        }
        for page in pages.order_by("title", "id")[:20]
    ]

    return JsonResponse({"results": results})


def get_parent_page_search_query(query: str) -> Q:
    page_query = Q(title__icontains=query)
    possible_page_id = query.removeprefix("#").strip()

    if possible_page_id.isdecimal():
        page_query |= Q(id=int(possible_page_id))

    return page_query


def parse_date_filter(value: str) -> datetime | None:
    parsed = parse_date((value or "").strip())

    if parsed is None:
        return None

    return timezone.make_aware(datetime.combine(parsed, datetime.min.time()))


def serialize_stream_value(value: Any) -> str:
    blocks = []

    for block in value:
        block_value = block.value

        if hasattr(block_value, "source"):
            serialized_value = strip_tags(str(block_value.source)).strip()
        elif isinstance(block_value, str):
            serialized_value = strip_tags(block_value).strip()
        elif isinstance(block_value, dict):
            serialized_value = {
                key: strip_tags(str(item)).strip() if isinstance(item, str) else item
                for key, item in block_value.items()
            }
        else:
            serialized_value = str(block_value)

        blocks.append(
            {
                "type": block.block_type,
                "value": serialized_value,
            }
        )

    return json.dumps(blocks, ensure_ascii=False)


def serialize_value(obj: Page, field_name: str) -> Any:
    if field_name == "full_url":
        return obj.full_url or ""

    if field_name == "parent_id":
        return obj.get_parent().id if obj.get_parent() else ""

    if field_name == "parent_title":
        parent = obj.get_parent()
        return parent.specific_deferred.title if parent else ""

    try:
        model_field = obj._meta.get_field(field_name)
    except FieldDoesNotExist:
        return getattr(obj, field_name, "")

    value = getattr(obj, field_name, "")

    if value is None:
        return ""

    if isinstance(model_field, StreamField):
        return serialize_stream_value(value)

    if isinstance(model_field, RichTextField):
        return strip_tags(str(value)).strip()

    if isinstance(model_field, ForeignKey):
        return getattr(value, "pk", "") if value else ""

    if isinstance(model_field, ManyToManyField):
        return ", ".join(str(item) for item in value.all())

    if isinstance(value, Model):
        return getattr(value, "pk", str(value))

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)

    return value


def build_export_queryset(page_model: type[Page], filters: dict[str, Any]):
    queryset = page_model.objects.all().specific()

    created_from = parse_date_filter(filters.get("created_from", ""))
    created_to = parse_date_filter(filters.get("created_to", ""))
    updated_from = parse_date_filter(filters.get("updated_from", ""))
    updated_to = parse_date_filter(filters.get("updated_to", ""))
    parent_id = filters.get("parent_id")
    live = filters.get("live")

    if created_from:
        queryset = queryset.filter(first_published_at__gte=created_from)

    if created_to:
        queryset = queryset.filter(first_published_at__lte=created_to)

    if updated_from:
        queryset = queryset.filter(latest_revision_created_at__gte=updated_from)

    if updated_to:
        queryset = queryset.filter(latest_revision_created_at__lte=updated_to)

    if parent_id:
        parent_page = Page.objects.get(id=int(parent_id))
        queryset = queryset.descendant_of(parent_page)

    if live == "true":
        queryset = queryset.live()
    elif live == "false":
        queryset = queryset.not_live()

    return queryset.order_by("id")


def run_export_job(job_id: str, payload: dict[str, Any]) -> None:
    file_path = ""

    try:
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        page_model = get_page_model(payload["page_type"])
        fields = payload["fields"]
        filters = payload["filters"]

        queryset = build_export_queryset(page_model, filters)
        total = queryset.count()

        filename = f"pages-{slugify(page_model.__name__)}-{job_id}.csv"
        file_path = os.path.join(EXPORTS_DIR, filename)

        set_export_job(
            job_id,
            {
                "status": "running",
                "processed": 0,
                "total": total,
                "progress": 0,
                "file_path": file_path,
                "filename": filename,
            },
        )

        with open(file_path, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(fields)

            for index, page in enumerate(queryset.iterator(chunk_size=500), start=1):
                writer.writerow(
                    [serialize_page_field(page, field_name) for field_name in fields]
                )

                if index % 25 == 0 or index == total:
                    set_export_job(
                        job_id,
                        {
                            "status": "running",
                            "processed": index,
                            "total": total,
                            "progress": (
                                100 if total == 0 else round(index / total * 100)
                            ),
                            "file_path": file_path,
                            "filename": filename,
                        },
                    )

        set_export_job(
            job_id,
            {
                "status": "done",
                "processed": total,
                "total": total,
                "progress": 100,
                "file_path": file_path,
                "filename": filename,
            },
        )

    except Exception as error:
        if file_path:
            delete_export_artifact(file_path)

        set_export_job(
            job_id,
            {
                "status": "error",
                "message": str(error),
                "processed": 0,
                "total": 0,
                "progress": 0,
            },
        )


@require_admin_access
@require_POST
def start_pages_export(request):
    try:
        payload = json.loads(request.body.decode(settings.DEFAULT_CHARSET))
    except json.JSONDecodeError as error:
        return JsonResponse(
            {"message": _("Invalid JSON: %(error)s") % {"error": error}},
            status=400,
        )

    page_type = payload.get("page_type", "")
    fields = payload.get("fields", [])
    filters = payload.get("filters", {})

    if not page_type:
        return JsonResponse({"message": _("Page type is required")}, status=400)

    if not isinstance(fields, list) or not fields:
        return JsonResponse({"message": _("Fields are required")}, status=400)

    try:
        get_page_model(page_type)
    except (ImportError, ValueError):
        return JsonResponse({"message": _("Invalid page type")}, status=400)

    cleanup_stale_exports()

    job_id = uuid.uuid4().hex

    set_export_job(
        job_id,
        {
            "status": "queued",
            "processed": 0,
            "total": 0,
            "progress": 0,
        },
    )

    thread = threading.Thread(
        target=run_export_job,
        args=(
            job_id,
            {
                "page_type": page_type,
                "fields": fields,
                "filters": filters,
            },
        ),
        daemon=True,
    )
    thread.start()

    return JsonResponse({"job_id": job_id})


@require_admin_access
@require_GET
def export_progress(request, job_id: str):
    job = get_export_job(job_id)

    if job is None:
        return JsonResponse({"message": _("Export job was not found")}, status=404)

    response = {
        "status": job.get("status"),
        "processed": job.get("processed", 0),
        "total": job.get("total", 0),
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
    }

    if job.get("status") == "done":
        response["download_url"] = reverse(
            "core:download_pages_export",
            kwargs={"job_id": job_id},
        )

    return JsonResponse(response)


@require_admin_access
@require_GET
def download_pages_export(request, job_id: str):
    job = get_export_job(job_id)

    if job is None or job.get("status") != "done":
        raise Http404

    file_path = job.get("file_path")

    if not file_path or not os.path.exists(file_path):
        raise Http404

    return CleanupFileResponse(
        open(file_path, "rb"),
        cleanup_paths=(file_path, get_export_job_path(job_id)),
        as_attachment=True,
        filename=job.get("filename", "pages-export.csv"),
    )
