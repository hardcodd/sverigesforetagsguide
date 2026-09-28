from importlib import import_module

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page

from blog.models import BlogIndexPage


class SubtitleMigrationTests(TestCase):
    def test_preserves_literal_text_translations_and_revisions(self):
        page = Page.get_first_root_node().add_child(
            instance=BlogIndexPage(title="Blog", slug="subtitle-test")
        )
        original = {
            "subtitle": 'A <b>tag</b> & "quote"',
            "subtitle_ru": "Text &amp; text",
            "subtitle_en": "<" * 255,
            "subtitle_ka": None,
        }
        BlogIndexPage.objects.rewrite(False).filter(pk=page.pk).update(**original)
        page.refresh_from_db()
        revision = page.save_revision()
        original_revision = dict(revision.content)
        migration = import_module("blog.migrations.0007_preserve_subtitle_text")
        apps = (
            MigrationExecutor(connection)
            .loader.project_state([("blog", "0007_preserve_subtitle_text")])
            .apps
        )
        migration.preserve_subtitles(apps, connection.schema_editor())
        stored = (
            BlogIndexPage.objects.rewrite(False)
            .filter(pk=page.pk)
            .values(*original)
            .get()
        )
        revision.refresh_from_db()
        for name, value in original.items():
            with self.subTest(name=name):
                expected = migration.rich_subtitle(value)
                self.assertEqual(stored[name], expected)
                self.assertEqual(
                    revision.content[name],
                    migration.rich_subtitle(original_revision[name]),
                )

    def test_subtitle_editor_supports_links(self):
        field = BlogIndexPage._meta.get_field("subtitle")
        self.assertEqual(field.features, ["link"])
        self.assertIn(
            "banners_ru", BlogIndexPage.get_edit_handler().get_form_class().base_fields
        )

    def test_admin_editor_renders_translated_subtitle_and_banner_controls(self):
        page = Page.get_first_root_node().add_child(
            instance=BlogIndexPage(title="Blog", slug="editor-test")
        )
        user = get_user_model().objects.create_superuser(
            username="promotion-editor", email="editor@example.org", password="test-only"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("wagtailadmin_pages:edit", args=[page.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "id_subtitle_ru")
        self.assertContains(response, "banners_ru")
