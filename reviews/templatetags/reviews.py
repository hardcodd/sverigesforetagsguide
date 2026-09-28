from __future__ import annotations

from collections.abc import Mapping

from django import template
from django.core.paginator import Page as PaginatorPage
from django.db.models import Prefetch
from django.http import HttpRequest
from wagtail.models import Page

from core.pagination import paginate
from reviews.models import Review, ReviewImage, ReviewStatus

register = template.Library()


@register.simple_tag
def get_reviews_count(page):
    """
    Return the number of reviews for a given page.
    """
    return Review.objects.filter(
        content_type=page.content_type,
        object_id=page.pk,
        status=ReviewStatus.PUBLISHED,
    ).count()


@register.simple_tag(takes_context=True)
def get_reviews(
    context: template.Context | Mapping[str, HttpRequest], page: Page
) -> PaginatorPage:
    """Return published reviews, applying the public pagination contract."""
    request = context["request"]

    reviews = (
        Review._default_manager.filter(
            content_type_id=page.content_type_id,
            object_id=page.pk,
            status=ReviewStatus.PUBLISHED,
        )
        .select_related("user")
        .prefetch_related(
            Prefetch(
                "images",
                queryset=ReviewImage._default_manager.select_related("image")
                .prefetch_related("image__renditions"),
            )
        )
        .order_by("-created_at")
    )

    return paginate(request, reviews, 10)


@register.simple_tag
def get_total_reviews_count() -> str:
    """Return the published review count with space-separated digit groups."""
    count = Review.objects.filter(status=ReviewStatus.PUBLISHED).count()
    return f"{count:,}".replace(",", " ")
