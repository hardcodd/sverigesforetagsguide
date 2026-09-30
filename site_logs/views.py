"""Superuser-only Wagtail views for reading and downloading application logs."""

from __future__ import annotations

from typing import cast

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from wagtail.admin.auth import require_admin_access

from site_logs.logging import LOG_RECORD_SEPARATOR
from site_logs.services import (
    list_downloadable_log_files,
    open_log_file,
    read_recent_log_records,
)


@require_admin_access
def log_list(request: HttpRequest) -> HttpResponse:
    """Render a bounded, superuser-only view of recent application logs."""
    # AuthenticationMiddleware adds user dynamically; Wagtail checks it first.
    if not cast(AbstractUser, getattr(request, "user")).is_superuser:
        raise PermissionDenied

    selected_level = request.GET.get("level", "errors")
    if selected_level not in {"errors", "warnings"}:
        raise Http404

    result = read_recent_log_records(
        settings.SITE_LOG_DIR,
        selected_level,
        record_limit=settings.SITE_LOG_VIEW_RECORD_LIMIT,
        file_limit=settings.SITE_LOG_VIEW_FILE_LIMIT,
        bytes_per_file=settings.SITE_LOG_VIEW_BYTES_PER_FILE,
    )
    downloadable_files = list_downloadable_log_files(
        settings.SITE_LOG_DIR,
        selected_level,
        settings.SITE_LOG_DOWNLOAD_FILE_LIMIT,
    )
    separator = f"\n\n{LOG_RECORD_SEPARATOR}\n\n"
    return render(
        request,
        "site_logs/log_list.html",
        {
            "files_read": result.files_read,
            "downloadable_files": downloadable_files,
            "log_text": separator.join(result.records),
            "record_count": len(result.records),
            "record_limit": settings.SITE_LOG_VIEW_RECORD_LIMIT,
            "selected_level": selected_level,
            "updated_at": timezone.localtime(),
        },
    )


@require_admin_access
def download_log(request: HttpRequest, filename: str) -> FileResponse:
    """Download one validated application log file for a superuser."""
    if not cast(AbstractUser, getattr(request, "user")).is_superuser:
        raise PermissionDenied

    try:
        log_file = open_log_file(settings.SITE_LOG_DIR, filename)
    except (OSError, ValueError):
        raise Http404 from None

    content_type = "application/gzip" if filename.endswith(".gz") else "text/plain"
    return FileResponse(
        log_file,
        as_attachment=True,
        filename=filename,
        content_type=content_type,
    )
