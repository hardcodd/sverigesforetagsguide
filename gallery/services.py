from __future__ import annotations

from django.core.paginator import Page as PaginatorPage
from django.http import HttpRequest

from core.pagination import paginate
from gallery.models import (
    GalleryPostPage,
    GalleryCategoryPage,
    GalleryIndexPage,
)


def get_gallery_images_service(
    page: GalleryPostPage, request: HttpRequest, count: int = 24
) -> PaginatorPage:
    """Paginate gallery images using the public page parameter contract."""
    return paginate(request, page.images.all(), count)


def get_paginated_galleries_service(
    page: GalleryCategoryPage, request: HttpRequest, count: int = 24
) -> PaginatorPage:
    """Paginate the category's gallery pages with strict bounds checking."""
    galleries = page.get_children().type(GalleryPostPage)
    return paginate(request, galleries, count)


def get_first_gallery_image_service(gallery: GalleryPostPage):
    return gallery.specific.images.first()


def get_gallery_categories_service(page: GalleryIndexPage | GalleryCategoryPage):
    return page.get_children().type(GalleryCategoryPage)
