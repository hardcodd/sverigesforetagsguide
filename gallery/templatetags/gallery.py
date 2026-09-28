from __future__ import annotations

from django import template
from django.core.paginator import Page as PaginatorPage

from gallery.models import GalleryPostPage, GalleryCategoryPage
from gallery.services import (
    get_gallery_images_service,
    get_paginated_galleries_service,
    get_first_gallery_image_service,
    get_gallery_categories_service,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def get_gallery_images(context: template.Context, count: int = 24) -> PaginatorPage:
    """Return the requested image page or propagate pagination errors."""
    page = context["page"]
    request = context["request"]
    return get_gallery_images_service(page, request, count)


@register.simple_tag(takes_context=True)
def get_paginated_galleries(
    context: template.Context, count: int = 24
) -> PaginatorPage:
    """Return the requested gallery page or propagate pagination errors."""
    page = context["page"]
    request = context["request"]
    return get_paginated_galleries_service(page, request, count)


@register.simple_tag
def get_first_gallery_image(gallery: GalleryPostPage):
    return get_first_gallery_image_service(gallery)


@register.simple_tag
def get_gallery_categories(gallery_category: GalleryCategoryPage):
    return get_gallery_categories_service(gallery_category)
