import json

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.shortcuts import render
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from wagtail.models import Page, get_page_models

CUSTOM_FIELDS = (("parent_id", _("parent id")),)

STANDARD_FIELD_NAMES = (
    "id",
    "title",
    "slug",
    "seo_title",
    "search_description",
    "first_published_at",
)

EXCLUDED_FIELD_NAMES = frozenset(
    {
        "avg_rating",
        "rating_score",
        "image",
    }
)


def get_language_suffixes():
    return tuple(
        sorted(
            (
                language_code.replace("-", "_")
                for language_code, _language_name in settings.LANGUAGES
            ),
            key=len,
            reverse=True,
        )
    )


def get_base_field_name(field_name, language_suffixes):
    for suffix in language_suffixes:
        postfix = f"_{suffix}"

        if field_name.endswith(postfix):
            return field_name.removesuffix(postfix)

    return field_name


def get_translated_field_names(field_name):
    yield field_name

    for suffix in get_language_suffixes():
        yield f"{field_name}_{suffix}"


def get_standard_fields(meta):
    fields = []

    for base_field_name in STANDARD_FIELD_NAMES:
        for field_name in get_translated_field_names(
            base_field_name,
        ):
            try:
                field = meta.get_field(field_name)
            except FieldDoesNotExist:
                continue

            fields.append(
                (
                    field.name,
                    force_str(field.verbose_name),
                )
            )

    return fields


def prepare_fields(fields):
    field_map = dict(fields)
    language_suffixes = get_language_suffixes()

    translated_base_names = set()

    for field_name in field_map:
        base_field_name = get_base_field_name(
            field_name,
            language_suffixes,
        )

        if base_field_name != field_name and base_field_name in field_map:
            translated_base_names.add(base_field_name)

    return [
        (field_name, field_label)
        for field_name, field_label in field_map.items()
        if (
            field_name not in translated_base_names
            and get_base_field_name(
                field_name,
                language_suffixes,
            )
            not in EXCLUDED_FIELD_NAMES
        )
    ]


def import_pages(request):
    page_models = []

    for page_model in get_page_models():
        if (
            page_model is Page
            or not page_model.is_creatable
            or page_model.max_count is not None
        ):
            continue

        # noinspection PyProtectedMember
        meta = page_model._meta

        standard_fields = get_standard_fields(meta)

        custom_fields = [
            (
                field_name,
                force_str(field_label),
            )
            for field_name, field_label in CUSTOM_FIELDS
        ]

        local_fields = [
            (
                field.name,
                force_str(field.verbose_name),
            )
            for field in (
                *meta.local_fields,
                *meta.local_many_to_many,
            )
            if not field.auto_created
        ]

        fields = prepare_fields(
            (
                *custom_fields,
                *standard_fields,
                *local_fields,
            )
        )

        page_models.append(
            (
                f"{page_model.__module__}.{page_model.__name__}",
                force_str(meta.verbose_name),
                json.dumps(
                    fields,
                    ensure_ascii=False,
                ),
            )
        )

    return render(
        request,
        "core/import_pages.html",
        {
            "page_models": page_models,
        },
    )
