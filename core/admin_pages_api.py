"""Compact page previews and metadata for the authenticated admin API."""

import logging
from typing import TypedDict

from django.db.models import QuerySet
from rest_framework.fields import BooleanField, Field
from rest_framework.renderers import JSONRenderer
from wagtail.admin.api.serializers import AdminPageSerializer
from wagtail.admin.api.views import PagesAdminAPIViewSet
from wagtail.images import get_image_model
from wagtail.images.models import SourceImageIOError
from wagtail.models import Page

from authors.models import AuthorPage
from blog.models import BlogPostPage
from catalog.models import Organization, OrganizationImage
from gallery.models import GalleryCategoryPage, GalleryImage, GalleryPostPage
from ratings.models import RatingPage


logger = logging.getLogger(__name__)


class PagePreview(TypedDict):
    url: str
    width: int
    height: int


def preview_filter_for_page(page: Page) -> str:
    """Match the rendition size used for this page's representative image."""
    if isinstance(page, AuthorPage):
        return "fill-768x1024|format-jpeg"
    if isinstance(page, (GalleryCategoryPage, GalleryPostPage)):
        return "fill-560x315|format-jpeg"
    if isinstance(page, (BlogPostPage, Organization, RatingPage)):
        return "fill-720x405|format-jpeg"
    return "max-1200x630|format-jpeg"


def build_page_previews(pages: list[Page]) -> dict[int, PagePreview | None]:
    """Resolve image IDs and renditions in batches for one API page of results."""
    organization_ids = {page.pk for page in pages if isinstance(page, Organization)} | {
        page.to_organization_id for page in pages if isinstance(page, RatingPage)
    }
    first_photo_ids: dict[int, int] = {}
    if organization_ids:
        photos = (
            OrganizationImage.objects.filter(page_id__in=organization_ids)
            .order_by("page_id", "sort_order", "pk")
            .values_list("page_id", "image_id")
        )
        for page_id, image_id in photos:
            first_photo_ids.setdefault(page_id, image_id)

    gallery_ids = [page.pk for page in pages if isinstance(page, GalleryPostPage)]
    first_gallery_image_ids: dict[int, int] = {}
    if gallery_ids:
        gallery_images = (
            GalleryImage.objects.filter(page_id__in=gallery_ids)
            .order_by("page_id", "sort_order", "pk")
            .values_list("page_id", "image_id")
        )
        for page_id, image_id in gallery_images:
            first_gallery_image_ids.setdefault(page_id, image_id)

    page_images: dict[int, tuple[int, str]] = {}
    filters_by_image: dict[int, set[str]] = {}
    for page in pages:
        if isinstance(page, Organization):
            image_id = first_photo_ids.get(page.pk)
        elif isinstance(page, RatingPage):
            image_id = first_photo_ids.get(page.to_organization_id)
        elif isinstance(page, GalleryPostPage):
            image_id = first_gallery_image_ids.get(page.pk)
        else:
            image_id = getattr(page, "image_id", None)
            if image_id is None:
                image_id = getattr(page, "flag_id", None)
        if image_id is not None:
            filter_spec = preview_filter_for_page(page)
            page_images[page.pk] = (image_id, filter_spec)
            filters_by_image.setdefault(image_id, set()).add(filter_spec)

    previews_by_image: dict[tuple[int, str], PagePreview] = {}
    if filters_by_image:
        image_model = get_image_model()
        images = image_model.objects.filter(
            pk__in=filters_by_image
        ).prefetch_renditions(
            *{
                filter_spec
                for specs in filters_by_image.values()
                for filter_spec in specs
            }
        )
        for image in images:
            if image.is_svg():
                continue
            for filter_spec in filters_by_image[image.pk]:
                try:
                    rendition = image.get_rendition(filter_spec)
                except SourceImageIOError:
                    logger.warning(
                        "Cannot render admin API preview for image %s", image.pk
                    )
                    continue
                previews_by_image[(image.pk, filter_spec)] = {
                    "url": rendition.url,
                    "width": rendition.width,
                    "height": rendition.height,
                }

    return {
        page.pk: previews_by_image.get(page_images[page.pk])
        if page.pk in page_images
        else None
        for page in pages
    }


class PagePreviewField(Field):
    """Serialize the rendition used for the page's representative image."""

    def get_attribute(self, instance: Page) -> Page:
        return instance

    def to_representation(self, page: Page) -> PagePreview | None:
        previews = getattr(self.context["view"], "page_previews", None)
        if previews is None:
            previews = build_page_previews([page])
        return previews.get(page.pk)


class OptionalNoindexField(Field):
    """Distinguish an unset page type from a stored false value."""

    def get_attribute(self, instance: Page) -> Page:
        return instance

    def to_representation(self, page: Page) -> bool | None:
        return getattr(page, "noindex", None)


class AdminPageListingSerializer(AdminPageSerializer):
    image = PagePreviewField(read_only=True)
    noindex = OptionalNoindexField(read_only=True)
    has_unpublished_changes = BooleanField(read_only=True)


class AdminPagesAPIViewSet(PagesAdminAPIViewSet):
    """Expose compact SEO metadata on admin page listings only."""

    renderer_classes = [JSONRenderer]
    base_serializer_class = AdminPageListingSerializer
    body_fields = PagesAdminAPIViewSet.body_fields + [
        "image",
        "noindex",
        "has_unpublished_changes",
    ]
    listing_default_fields = PagesAdminAPIViewSet.listing_default_fields + [
        "image",
        "noindex",
        "has_unpublished_changes",
    ]

    def paginate_queryset(self, queryset: QuerySet[Page]) -> list[Page] | None:
        pages = super().paginate_queryset(queryset)
        if pages is None:
            return None
        page_list = list(pages)
        self.page_previews = build_page_previews(page_list)
        return page_list
