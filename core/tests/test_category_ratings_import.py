from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page

from catalog.models import City, OrganizationType


class CategoryRatingsImportTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        (self.folder / "images").mkdir()
        image_file = get_test_image_file()
        image_file.seek(0)
        (self.folder / "images/banner.png").write_bytes(image_file.read())
        self.media = self.folder / "media"
        self.settings_override = override_settings(MEDIA_ROOT=str(self.media))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        root = Page.get_first_root_node()
        city = root.add_child(instance=City(title="City", slug="import-city"))
        self.category = city.add_child(
            instance=OrganizationType(title="Category", slug="category")
        )
        self.category.has_unpublished_changes = False
        self.category.save()
        self.target = root.add_child(instance=Page(title="Rating", slug="rating-link"))
        self.record = {
            "url_path": self.category.url_path,
            "image": "banner.png",
            "text": {
                language: '<p><a linktype="page" id="987654">Rating</a></p>'
                for language in ("default", "ru", "en", "ka")
            },
            "page_links": {"987654": self.target.url_path},
        }
        self.save_bundle()
        self.bundle_patch = patch(
            "core.management.commands.import_legacy_category_ratings.BUNDLE",
            self.folder,
        )
        self.bundle_patch.start()
        self.addCleanup(self.bundle_patch.stop)

    def save_bundle(self):
        (self.folder / "banners.json").write_text(json.dumps([self.record]))

    def test_default_is_read_only(self):
        before = get_image_model().objects.count()
        output = StringIO()
        call_command("import_legacy_category_ratings", stdout=output)
        self.category.refresh_from_db()
        self.assertIsNone(self.category.ratings_image_id)
        self.assertEqual(get_image_model().objects.count(), before)
        self.assertIn("Ready: 1", output.getvalue())

    def test_import_remaps_links_publishes_and_is_repeatable(self):
        call_command("import_legacy_category_ratings", apply=True, stdout=StringIO())
        self.category.refresh_from_db()
        self.assertIsNotNone(self.category.ratings_image_id)
        self.assertIn(f'id="{self.target.pk}"', self.category.ratings_text)
        self.assertNotIn("987654", self.category.ratings_text)
        self.assertTrue(self.category.live)
        self.assertFalse(self.category.has_unpublished_changes)
        self.assertEqual(
            self.category.get_latest_revision().content["ratings_text_ru"],
            self.category.ratings_text_ru,
        )
        before = get_image_model().objects.count()
        output = StringIO()
        call_command("import_legacy_category_ratings", apply=True, stdout=output)
        self.assertEqual(get_image_model().objects.count(), before)
        self.assertIn("Imported 0", output.getvalue())

    def test_missing_link_aborts_before_writing(self):
        self.record["page_links"]["987654"] = "/missing/"
        self.save_bundle()
        before = get_image_model().objects.count()
        with self.assertRaisesMessage(CommandError, "Unresolved rating links"):
            call_command(
                "import_legacy_category_ratings", apply=True, stdout=StringIO()
            )
        self.assertEqual(get_image_model().objects.count(), before)

    def test_categories_sharing_an_image_reuse_one_image_record(self):
        other = self.category.get_parent().add_child(
            instance=OrganizationType(title="Second", slug="second")
        )
        other.has_unpublished_changes = False
        other.save()
        second = dict(self.record, url_path=other.url_path)
        (self.folder / "banners.json").write_text(json.dumps([self.record, second]))
        before = get_image_model().objects.count()
        call_command("import_legacy_category_ratings", apply=True, stdout=StringIO())
        self.category.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.category.ratings_image_id, other.ratings_image_id)
        self.assertEqual(get_image_model().objects.count(), before + 1)

    def test_pending_draft_is_preserved(self):
        self.category.has_unpublished_changes = True
        self.category.save()
        with self.assertRaisesMessage(CommandError, "pending draft"):
            call_command(
                "import_legacy_category_ratings", apply=True, stdout=StringIO()
            )

    def test_existing_category_settings_are_preserved(self):
        self.category.ratings_text = "<p>Existing</p>"
        self.category.save()
        call_command("import_legacy_category_ratings", apply=True, stdout=StringIO())
        self.category.refresh_from_db()
        self.assertEqual(self.category.ratings_text, "<p>Existing</p>")

    def test_failed_publish_rolls_back_and_removes_new_image_files(self):
        before = get_image_model().objects.count()
        with patch.object(
            OrganizationType,
            "save_revision",
            side_effect=RuntimeError("publish failed"),
        ):
            with self.assertRaisesMessage(RuntimeError, "publish failed"):
                call_command(
                    "import_legacy_category_ratings", apply=True, stdout=StringIO()
                )
        self.category.refresh_from_db()
        self.assertIsNone(self.category.ratings_image_id)
        self.assertEqual(get_image_model().objects.count(), before)
        self.assertEqual([path for path in self.media.rglob("*") if path.is_file()], [])
