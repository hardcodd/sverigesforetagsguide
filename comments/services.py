from dataclasses import dataclass
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.translation import gettext as _
from wagtail.models import Page

from comments.models import COMMENT_PUBLISHED, Comment
from core.import_users import (
    ImportUserError,
    get_or_create_import_user,
    parse_import_user,
)

MAX_IMPORT_BATCH_SIZE = 100


@dataclass(frozen=True)
class CommentImportResult:
    success: bool
    code: str
    message: str


class CommentImportRowForm(forms.Form):
    id = forms.IntegerField(min_value=1)
    text = forms.CharField(strip=True)
    user = forms.CharField(strip=True)
    date = forms.DateTimeField(
        input_formats=(
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )
    )

    def clean_user(self):
        return parse_import_user(self.cleaned_data["user"])


class CommentImportError(Exception):
    def __init__(self, message, *, code="invalid_data", status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def _format_form_errors(form):
    messages = []
    for field_name, errors in form.errors.items():
        messages.extend(f"{field_name}: {error}" for error in errors)
    return "; ".join(messages)


def _get_target(page_id):
    try:
        page = Page.objects.get(pk=page_id).specific
    except Page.DoesNotExist as error:
        raise CommentImportError(
            _("Page not found."),
            code="page_not_found",
            status=404,
        ) from error

    return ContentType.objects.get_for_model(page), page


def _import_comment_row(data: Any):
    if not isinstance(data, dict):
        raise CommentImportError(_("A JSON object is required."))

    for field_name in ("text", "user", "date"):
        if field_name in data and not isinstance(data[field_name], str):
            raise CommentImportError(
                _("%(field_name)s must be a string.") % {"field_name": field_name}
            )
    for field_name in ("id",):
        if field_name in data and (
            isinstance(data[field_name], bool)
            or not isinstance(data[field_name], (int, str))
        ):
            raise CommentImportError(
                _("%(field_name)s must be an integer.") % {"field_name": field_name}
            )

    form = CommentImportRowForm(data)
    if not form.is_valid():
        raise CommentImportError(_format_form_errors(form))

    content_type, target = _get_target(form.cleaned_data["id"])
    import_user = form.cleaned_data["user"]
    try:
        user = get_or_create_import_user(import_user)
    except ImportUserError as error:
        raise CommentImportError(str(error)) from error
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    created_at = form.cleaned_data["date"]
    comment_text = form.cleaned_data["text"]

    if Comment.objects.filter(
        user=user,
        content_type=content_type,
        object_id=target.pk,
        parent=None,
        comment=comment_text,
        created_at=created_at,
    ).exists():
        raise CommentImportError(
            _("Comment already exists."),
            code="already_exists",
            status=409,
        )

    comment = Comment.objects.create(
        user=user,
        content_type=content_type,
        object_id=target.pk,
        status=COMMENT_PUBLISHED,
        comment=comment_text,
    )
    Comment.objects.filter(pk=comment.pk).update(created_at=created_at)
    comment.created_at = created_at
    return comment


def _batch_lock_order(item):
    index, data = item
    if not isinstance(data, dict) or not isinstance(data.get("user"), str):
        return "", index
    username = data["user"].rpartition("/")[-1].strip()
    return username, index


@transaction.atomic
def import_comment_row(data: Any):
    return _import_comment_row(data)


@transaction.atomic
def import_comment_rows(rows: Any):
    if not isinstance(rows, list) or not rows:
        raise CommentImportError(_("A non-empty list of rows is required."))
    if len(rows) > MAX_IMPORT_BATCH_SIZE:
        raise CommentImportError(
            _("A batch may contain at most %(max_size)s rows.")
            % {"max_size": MAX_IMPORT_BATCH_SIZE}
        )

    results = [None] * len(rows)
    for index, data in sorted(enumerate(rows), key=_batch_lock_order):
        try:
            _import_comment_row(data)
        except CommentImportError as error:
            results[index] = CommentImportResult(
                success=False,
                code=error.code,
                message=str(error),
            )
            continue

        results[index] = CommentImportResult(
            success=True,
            code="imported",
            message=str(_("Comment created successfully.")),
        )

    return results
