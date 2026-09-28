import json
from typing import Any

from django.db.models import Model
from django.db.models.fields.related import ForeignKey
from django.utils.text import slugify

from catalog.utils import get_start_end_day
from core.utils import get_weekday_number

RAW_TEXT_FIELD_NAME_PARTS = frozenset(
    {
        "search",
        "website",
        "social",
    }
)


def should_preserve_plain_text(field: str) -> bool:
    return any(part in field for part in RAW_TEXT_FIELD_NAME_PARTS)


def charfield_handler(obj: Model, field: str, value: Any) -> None:
    setattr(obj, field, value)


def slugfield_handler(obj: Model, field: str, value: Any) -> None:
    slug = slugify(str(value).strip(), allow_unicode=True)

    if not slug:
        return

    setattr(obj, field, slug)


def textfield_handler(obj: Model, field: str, value: Any) -> None:
    text = str(value)

    if should_preserve_plain_text(field):
        setattr(obj, field, text)
        return

    paragraphs = [
        paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()
    ]

    if not paragraphs:
        return

    setattr(obj, field, "<p>" + "</p><p>".join(paragraphs) + "</p>")


def booleanfield_handler(obj: Model, field: str, value: Any) -> None:
    setattr(
        obj,
        field,
        value in [True, "true", "True", 1, "1", "yes", "on", "Yes", "On"],
    )


def working_hours_handler(obj: Model, field: str, value: Any) -> None:
    if not value:
        return

    try:
        working_hours = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("Invalid working hours JSON") from error

    if not isinstance(working_hours, dict):
        raise ValueError("Invalid working hours format")

    days = []

    for day, hours in working_hours.items():
        normalized_hours = str(hours).strip().lower()

        if normalized_hours == "closed":
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
        elif normalized_hours == "open 24 hours":
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
                start, end = get_start_end_day(hours)
            except ValueError as error:
                raise ValueError(f"Invalid working hours format for {day}") from error

            days.append(
                {
                    "type": "day",
                    "value": {
                        "day": get_weekday_number(day),
                        "end": end,
                        "start": start,
                        "holiday": False,
                        "last_client": False,
                    },
                }
            )

    setattr(obj, field, days)


def located_in_handler(obj: Model, field: str, value: Any) -> None:
    model_field = obj._meta.get_field(field)

    if not isinstance(model_field, ForeignKey):
        raise ValueError(f"{field!r} is not a ForeignKey field")

    related_model = model_field.related_model

    if related_model is None:
        raise ValueError(f"Could not resolve related model for {field!r}")

    try:
        related_id = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {field} ID") from error

    try:
        related_obj = related_model.objects.get(id=related_id)
    except related_model.DoesNotExist as error:
        raise ValueError(f"Invalid {field} ID") from error

    setattr(obj, field, related_obj)
