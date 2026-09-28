import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.utils import timezone
from django.utils.html import strip_tags
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page

from reviews.models import ReviewStatus


def serialize_json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)

        return value.strftime("%d.%m.%Y %H:%M:%S")

    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")

    if isinstance(value, time):
        return value.replace(tzinfo=None).strftime("%H:%M:%S")

    if isinstance(value, Model):
        return {
            "id": value.pk,
            "label": str(value),
        }

    if isinstance(value, dict):
        return {str(key): serialize_json_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [serialize_json_value(item) for item in value]

    if hasattr(value, "source"):
        return strip_tags(str(value.source)).strip()

    return str(value)


def serialize_stream_value(value: Any) -> str:
    blocks = []

    for block in value:
        blocks.append(
            {
                "type": block.block_type,
                "value": serialize_json_value(block.value),
            }
        )

    return json.dumps(blocks, ensure_ascii=False)


def serialize_page_field(page: Page, field_name: str) -> Any:
    if field_name == "full_url":
        return page.full_url or ""

    if field_name == "parent_id":
        parent = page.get_parent()
        return parent.pk if parent else ""

    if field_name == "parent_title":
        parent = page.get_parent()
        return parent.specific_deferred.title if parent else ""

    if field_name == "reviews_count":
        reviews = getattr(page, "reviews", None)
        return reviews.filter(status=ReviewStatus.PUBLISHED).count() if reviews else 0

    try:
        model_field = page._meta.get_field(field_name)
    except FieldDoesNotExist:
        value = getattr(page, field_name, "")

        if callable(value):
            value = value()

        return serialize_json_value(value)

    value = getattr(page, field_name, None)

    if value is None:
        return ""

    if isinstance(model_field, StreamField):
        return serialize_stream_value(value)

    if isinstance(model_field, RichTextField):
        return strip_tags(str(value)).strip()

    if isinstance(model_field, ForeignKey):
        return value.pk if value else ""

    if isinstance(model_field, ManyToManyField) or getattr(
        model_field, "many_to_many", False
    ):
        return ", ".join(str(item) for item in value.all())

    if isinstance(value, Model):
        return value.pk

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(serialize_json_value(value), ensure_ascii=False)

    return serialize_json_value(value)
