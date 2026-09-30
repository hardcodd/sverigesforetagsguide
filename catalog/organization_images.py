"""Select consistent category imagery for organizations without gallery photos."""

import re
from collections import defaultdict
from pathlib import PurePosixPath

from django.http import HttpRequest
from wagtail.images import get_image_model
from wagtail.images.models import Image

from catalog.models import Organization, OrganizationType

PLACEHOLDER_COLLECTION = "Карточки-заглушки"
PLACEHOLDER_NAME = re.compile(r"(?P<slug>.+)-(?P<number>[1-9][0-9]*)$")


def _placeholder_match(image: Image) -> re.Match[str] | None:
    title = str(image.title).strip()
    if match := PLACEHOLDER_NAME.fullmatch(title):
        return match
    return PLACEHOLDER_NAME.fullmatch(PurePosixPath(image.file.name or "").stem)


class OrganizationImageFallbacks:
    """Load placeholder variants once and category covers once per category."""

    def __init__(self) -> None:
        self._placeholders: dict[str, list[Image]] | None = None
        self._categories: dict[str, OrganizationType | None] = {}

    def _load_placeholders(self) -> dict[str, list[Image]]:
        grouped: dict[str, list[tuple[int, Image]]] = defaultdict(list)
        images = get_image_model().objects.filter(
            collection__name=PLACEHOLDER_COLLECTION
        )
        for image in images:
            match = _placeholder_match(image)
            if match:
                grouped[match.group("slug")].append((int(match.group("number")), image))
        return {
            slug: [
                image
                for _, image in sorted(variants, key=lambda item: (item[0], item[1].pk))
            ]
            for slug, variants in grouped.items()
        }

    def category_for(self, organization: Organization) -> OrganizationType | None:
        """Cache the parent category so sibling cards share the same lookup."""
        category_path = str(organization.path)[: -organization.steplen]
        if category_path not in self._categories:
            self._categories[category_path] = (
                OrganizationType.objects.filter(path=category_path)
                .select_related("image")
                .first()
            )
        return self._categories[category_path]

    def select(
        self, organization: Organization, default_image: Image | None = None
    ) -> Image | None:
        """Return a stable variant, category cover, or site-wide default image."""
        category = self.category_for(organization)
        if category is None:
            return default_image

        if self._placeholders is None:
            self._placeholders = self._load_placeholders()
        variants = self._placeholders.get(str(category.slug), [])
        if variants:
            return variants[organization.pk % len(variants)]
        category_image = category.image
        return category_image if isinstance(category_image, Image) else default_image


def _selector_for(request: HttpRequest | None) -> OrganizationImageFallbacks:
    selector: OrganizationImageFallbacks | None = None
    if request is not None:
        selector = getattr(request, "_organization_image_fallbacks", None)
    if selector is None:
        selector = OrganizationImageFallbacks()
        if request is not None:
            setattr(request, "_organization_image_fallbacks", selector)
    return selector


def get_organization_fallback(
    organization: Organization,
    default_image: Image | None = None,
    request: HttpRequest | None = None,
) -> Image | None:
    """Select a fallback, sharing lookup work across one HTTP request."""
    return _selector_for(request).select(organization, default_image)


def get_organization_fallback_alt(
    organization: Organization, image: Image, request: HttpRequest | None = None
) -> str:
    """Describe a fallback without using organization names or variant filenames."""
    if image.description:
        return str(image.description)
    if _placeholder_match(image):
        category = _selector_for(request).category_for(organization)
        return str(category.title) if category else ""
    return str(image.title)
