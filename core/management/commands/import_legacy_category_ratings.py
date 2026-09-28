"""Import the curated legacy rating banners using portable page paths."""

from argparse import ArgumentParser
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import re
from typing import Any, cast

from django.conf import settings
from django.core.files import File
from django.core.files.storage import Storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.transaction import Atomic
from wagtail.images import get_image_model
from wagtail.models import Page

from catalog.models import OrganizationType


BUNDLE = Path(settings.BASE_DIR) / "catalog/data/legacy_category_ratings"
LANGUAGES = {
    "default": "ratings_text",
    "ru": "ratings_text_ru",
    "en": "ratings_text_en",
    "ka": "ratings_text_ka",
}


@dataclass(frozen=True)
class PromotionImport:
    """A fully validated category update with resolved destination page links."""

    category: OrganizationType
    image_path: Path
    text: dict[str, str]


def string_mapping(value: object) -> dict[str, str]:
    """Validate a string mapping at the JSON boundary."""
    if not isinstance(value, dict):
        raise CommandError("Expected a JSON object of strings.")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise CommandError("Expected string keys and values.")
        result[key] = item
    return result


def prepare_imports() -> list[PromotionImport]:
    """Resolve the complete bundle before writing; preserve configured categories.

    Missing categories, links, images or pending drafts abort the import rather
    than publishing incomplete content or replacing another editor's work.
    """
    records: object = json.loads((BUNDLE / "banners.json").read_text())
    if not isinstance(records, list):
        raise CommandError("Expected a list of category banners.")
    plans: list[PromotionImport] = []
    for record in records:
        if not isinstance(record, dict):
            raise CommandError("Invalid banner record.")
        path, filename = record.get("url_path"), record.get("image")
        if not isinstance(path, str) or not isinstance(filename, str):
            raise CommandError("A banner must have a page path and image filename.")
        image_path = BUNDLE / "images" / filename
        if Path(filename).name != filename or not image_path.is_file():
            raise CommandError(f"Missing or invalid banner image: {filename}")
        category = OrganizationType.objects.filter(url_path=path).first()
        if category is None:
            raise CommandError(f"Category not found: {path}")
        if category.ratings_image_id or any(
            getattr(category, name) for name in LANGUAGES.values()
        ):
            continue
        if category.has_unpublished_changes or not category.live:
            raise CommandError(
                f"Category has a pending draft or is unpublished: {path}"
            )
        links = string_mapping(record.get("page_links"))
        page_ids = dict(
            Page.objects.filter(url_path__in=links.values()).values_list(
                "url_path", "pk"
            )
        )
        if set(links.values()) - page_ids.keys():
            raise CommandError(f"Unresolved rating links in {path}")
        text = string_mapping(record.get("text"))
        if text.keys() != LANGUAGES.keys():
            raise CommandError(f"Missing translated fields for {path}")

        def replace_link(match: re.Match[str]) -> str:
            """Resolve a legacy page id without changing the surrounding markup."""
            old_id = match[2]
            if old_id not in links:
                raise CommandError(f"Missing link mapping for {old_id} in {path}")
            return f"{match[1]}{page_ids[links[old_id]]}{match[3]}"

        values = {
            LANGUAGES[language]: re.sub(
                r'(<a\b[^>]*\bid=")(\d+)(")', replace_link, value
            )
            for language, value in text.items()
        }
        plans.append(PromotionImport(category, image_path, values))
    return plans


class Command(BaseCommand):
    help = "Preview or import legacy category rating banners. Existing settings are preserved."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create images and publish the validated category updates.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Default to a read-only preview; apply all category updates atomically."""
        plans = prepare_imports()
        for plan in plans:
            self.stdout.write(plan.category.url_path)
        if not options["apply"]:
            self.stdout.write(
                f"Ready: {len(plans)} categories. Run with --apply to import."
            )
            return
        created: list[tuple[Storage, str]] = []
        try:
            # Django's untyped overload returns Atomic for a string database alias.
            with cast(Atomic, transaction.atomic(using="default")):
                self._apply_imports(plans, created)
        except Exception:
            # Storage writes are outside the database transaction.
            for storage, name in created:
                storage.delete(name)
            raise
        self.stdout.write(
            f"Imported {len(plans)} categories; created {len(created)} images."
        )

    def _apply_imports(
        self, plans: list[PromotionImport], created: list[tuple[Storage, str]]
    ) -> None:
        """Publish the prepared updates together, recording files for rollback cleanup."""
        for plan in plans:
            category = OrganizationType.objects.select_for_update().get(
                pk=plan.category.pk
            )
            if (
                category.has_unpublished_changes
                or not category.live
                or category.ratings_image_id
                or any(getattr(category, field) for field in LANGUAGES.values())
            ):
                raise CommandError(
                    f"Category changed during import: {category.url_path}"
                )
            digest = sha1(plan.image_path.read_bytes()).hexdigest()
            image = get_image_model().objects.filter(file_hash=digest).first()
            if image is None:
                image = get_image_model()(
                    title=plan.image_path.stem,
                    file_hash=digest,
                    file_size=plan.image_path.stat().st_size,
                )
                with plan.image_path.open("rb") as source:
                    image.file.save(plan.image_path.name, File(source), save=False)
                created.append((image.file.storage, image.file.name))
                image.save()
            category.ratings_image = image
            for name, value in plan.text.items():
                setattr(category, name, value)
            category.save_revision().publish()
