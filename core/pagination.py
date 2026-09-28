"""Strict pagination and URL normalization for public lists."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.core.paginator import InvalidPage, Page, Paginator
from django.db.models import QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponsePermanentRedirect,
)

T = TypeVar("T")


class PaginationRedirect(Exception):
    """Carry a normalized local URL out of a view or template tag."""

    def __init__(self, url: str) -> None:
        self.url: str = url
        super().__init__(url)


def page_url(url: str, number: int | None) -> str:
    """Replace only page, preserving other query values and the fragment."""
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "page"
    ]
    if number is not None and number > 1:
        query.append(("page", str(number)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def paginate(
    request: HttpRequest, queryset: QuerySet[T] | Sequence[T], count: int = 16
) -> Page:
    """Return a valid page, raise Http404 for invalid input, or normalize via 301.

    Missing page selects the first page, including an empty result set. Only a
    single ASCII decimal value is accepted. Bounds are checked before redirecting
    leading zeros, so nonexistent pages never redirect to another result set.
    PaginationMiddleware handles redirects even during template rendering.
    """
    values: list[str] = request.GET.getlist("page") or []
    raw_number = values[0] if values else "1"
    if len(values) > 1 or re.fullmatch(r"[0-9]+", raw_number) is None:
        raise Http404("Invalid page number.")
    try:
        number = int(raw_number)
        result = Paginator(queryset, count).page(number)
    except (ValueError, InvalidPage) as error:
        raise Http404("Page does not exist.") from error

    if values and (number == 1 or raw_number != str(number)):
        path = request.get_full_path()
        # Prevent a leading double slash from becoming an external redirect.
        if path.startswith("//"):
            path = "/%2F" + path[2:]
        raise PaginationRedirect(page_url(path, number))
    return result


class PaginationMiddleware:
    """Convert only pagination redirects raised by views or template rendering."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response: Callable[[HttpRequest], HttpResponse] = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> HttpResponsePermanentRedirect | None:
        if isinstance(exception, PaginationRedirect):
            return HttpResponsePermanentRedirect(exception.url)
        return None
