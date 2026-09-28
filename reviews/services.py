from dataclasses import dataclass
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.translation import gettext as _
from wagtail.models import Page

from core.import_users import (
    ImportUserError,
    get_or_create_import_user,
    parse_import_user,
)
from reviews.models import (
    MAX_REVIEW_RATING,
    MIN_REVIEW_RATING,
    Review,
    ReviewStatus,
    update_review_ratings,
)

MAX_IMPORT_BATCH_SIZE = 100


@dataclass(frozen=True)
class ReviewImportResult:
    success: bool
    code: str
    message: str


class ReviewImportRowForm(forms.Form):
    id = forms.IntegerField(min_value=1)
    text = forms.CharField(strip=True)
    user = forms.CharField(strip=True)
    date = forms.DateTimeField(
        input_formats=(
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )
    )
    rate = forms.IntegerField(
        min_value=MIN_REVIEW_RATING,
        max_value=MAX_REVIEW_RATING,
    )

    def clean_user(self):
        return parse_import_user(self.cleaned_data["user"])


class ReviewImportError(Exception):
    def __init__(self, message, *, code="invalid_data", status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def _format_form_errors(form):
    messages = []
    for field_name, errors in form.errors.items():
        messages.extend(f"{field_name}: {error}" for error in errors)
    return "; ".join(messages)


def _import_review_row(data: Any, *, defer_rating_update=False):
    if not isinstance(data, dict):
        raise ReviewImportError(_("A JSON object is required."))

    for field_name in ("text", "user", "date"):
        if field_name in data and not isinstance(data[field_name], str):
            raise ReviewImportError(
                _("%(field_name)s must be a string.") % {"field_name": field_name}
            )
    for field_name in ("id", "rate"):
        if field_name in data and (
            isinstance(data[field_name], bool)
            or not isinstance(data[field_name], (int, str))
        ):
            raise ReviewImportError(
                _("%(field_name)s must be an integer.") % {"field_name": field_name}
            )

    form = ReviewImportRowForm(data)
    if not form.is_valid():
        raise ReviewImportError(_format_form_errors(form))

    page_id = form.cleaned_data["id"]
    try:
        page = Page.objects.get(pk=page_id).specific
    except Page.DoesNotExist as error:
        raise ReviewImportError(
            _("Page not found."),
            code="page_not_found",
            status=404,
        ) from error

    content_type = ContentType.objects.get_for_model(page)
    import_user = form.cleaned_data["user"]
    try:
        user = get_or_create_import_user(import_user)
    except ImportUserError as error:
        raise ReviewImportError(str(error)) from error
    user = get_user_model().objects.select_for_update().get(pk=user.pk)

    if Review.objects.filter(
        user=user,
        content_type=content_type,
        object_id=page.pk,
    ).exists():
        raise ReviewImportError(
            _("Review already exists."),
            code="already_exists",
            status=409,
        )

    created_at = form.cleaned_data["date"]
    review = Review(
        user=user,
        content_type=content_type,
        object_id=page.pk,
        status=ReviewStatus.PUBLISHED,
        comment=form.cleaned_data["text"],
        rating=form.cleaned_data["rate"],
        go_live_at=created_at,
    )
    review._defer_rating_update = defer_rating_update
    review.save()
    Review.objects.filter(pk=review.pk).update(created_at=created_at)
    review.created_at = created_at
    return review


def _batch_lock_order(item):
    index, data = item
    if not isinstance(data, dict) or not isinstance(data.get("user"), str):
        return "", index
    username = data["user"].rpartition("/")[-1].strip()
    return username, index


@transaction.atomic
def import_review_row(data: Any):
    return _import_review_row(data)


@transaction.atomic
def import_review_rows(rows: Any):
    if not isinstance(rows, list) or not rows:
        raise ReviewImportError(_("A non-empty list of rows is required."))
    if len(rows) > MAX_IMPORT_BATCH_SIZE:
        raise ReviewImportError(
            _("A batch may contain at most %(max_size)s rows.")
            % {"max_size": MAX_IMPORT_BATCH_SIZE}
        )

    results = [None] * len(rows)
    affected_objects = {}

    for index, data in sorted(enumerate(rows), key=_batch_lock_order):
        try:
            review = _import_review_row(data, defer_rating_update=True)
        except ReviewImportError as error:
            results[index] = ReviewImportResult(
                success=False,
                code=error.code,
                message=str(error),
            )
            continue

        affected_objects[(review.content_type_id, review.object_id)] = review
        results[index] = ReviewImportResult(
            success=True,
            code="imported",
            message=str(_("Review created successfully.")),
        )

    for review in affected_objects.values():
        update_review_ratings(review)

    return results
