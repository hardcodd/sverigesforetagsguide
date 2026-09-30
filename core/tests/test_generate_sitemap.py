import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from django.core.management import call_command
from django.test import SimpleTestCase

from core.management.commands import generate_sitemap


class FakePages:
    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    def live(self) -> "FakePages":
        return self

    def exclude(self, **kwargs: int) -> "FakePages":
        return self

    def order_by(self, field: str) -> "FakePages":
        return self

    def count(self) -> int:
        return len(self.urls)

    def iterator(self, *, chunk_size: int):
        yield from (SimpleNamespace(full_url=url) for url in self.urls)


class GenerateSitemapTests(SimpleTestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.patch_root = patch.object(generate_sitemap, "SITEMAP_ROOT", str(self.root))
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.patch_site = patch(
            "wagtail.models.Site.objects.get",
            return_value=SimpleNamespace(root_url="https://example.com"),
        )
        self.patch_site.start()
        self.addCleanup(self.patch_site.stop)

    def write_section(self, section: str, number: int = 1) -> Path:
        directory = self.root / "en" / section
        directory.mkdir(parents=True, exist_ok=True)
        file = directory / f"sitemap-{number}.xml"
        file.write_text("<urlset />", encoding="utf-8")
        return file

    def index_entries(self) -> dict[str, str]:
        tree = ElementTree.parse(self.root / "sitemap.xml")
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return {
            sitemap.findtext("s:loc", namespaces=namespace): sitemap.findtext(
                "s:lastmod", namespaces=namespace
            )
            for sitemap in tree.findall("s:sitemap", namespace)
        }

    def test_partial_run_keeps_other_sections_and_their_modification_dates(
        self,
    ) -> None:
        organizations = self.write_section("catalog_organizations")
        previous_day = datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp()
        os.utime(organizations, (previous_day, previous_day))

        def run_job(args: tuple) -> list[str]:
            self.write_section("blog_posts")
            return ["https://example.com/sitemaps/en/blog_posts/sitemap-1.xml"]

        with (
            patch.object(generate_sitemap, "LANGUAGES", ["en"]),
            patch.object(
                generate_sitemap,
                "SITEMAP_PAGE_TYPES",
                {
                    "blog_posts": "blog.BlogPostPage",
                    "catalog_organizations": "catalog.Organization",
                },
            ),
            patch.object(generate_sitemap, "_run_job", side_effect=run_job),
        ):
            generate_sitemap.Command().handle(
                langs=None, only=["blog_posts"], processes=1
            )

        entries = self.index_entries()
        self.assertIn(
            "https://example.com/sitemaps/en/blog_posts/sitemap-1.xml", entries
        )
        self.assertEqual(
            entries[
                "https://example.com/sitemaps/en/catalog_organizations/sitemap-1.xml"
            ],
            "2026-09-29",
        )

    def test_regenerated_section_removes_stale_numbered_files(self) -> None:
        self.write_section("blog_posts", 2)
        pages = FakePages(["https://example.com/en/post/"])
        with patch(
            "django.apps.apps.get_model", return_value=SimpleNamespace(objects=pages)
        ):
            generate_sitemap._run_job(
                (
                    generate_sitemap.Job("blog_posts", "blog.BlogPostPage", "en"),
                    str(self.root),
                    ["en"],
                    2,
                )
            )

        self.assertTrue((self.root / "en" / "blog_posts" / "sitemap-1.xml").exists())
        self.assertFalse((self.root / "en" / "blog_posts" / "sitemap-2.xml").exists())

    def test_empty_regenerated_section_removes_old_files(self) -> None:
        self.write_section("blog_posts")
        pages = FakePages([])
        with patch(
            "django.apps.apps.get_model", return_value=SimpleNamespace(objects=pages)
        ):
            entries = generate_sitemap._run_job(
                (
                    generate_sitemap.Job("blog_posts", "blog.BlogPostPage", "en"),
                    str(self.root),
                    ["en"],
                    2,
                )
            )

        self.assertEqual(entries, [])
        self.assertFalse((self.root / "en" / "blog_posts" / "sitemap-1.xml").exists())

    def test_failed_section_write_keeps_previous_file(self) -> None:
        previous = self.write_section("blog_posts")
        with patch.object(
            generate_sitemap, "xml_text", side_effect=ValueError("bad URL")
        ):
            with self.assertRaises(ValueError):
                generate_sitemap._write_urlset_file(
                    pages=[SimpleNamespace(full_url="https://example.com/en/post/")],
                    lang="en",
                    out_dir=str(previous.parent),
                    file_index=1,
                    default_lang="en",
                    languages=["en"],
                )

        self.assertEqual(previous.read_text(encoding="utf-8"), "<urlset />")
        self.assertEqual(list(previous.parent.iterdir()), [previous])

    def test_atomic_write_preserves_existing_file_permissions(self) -> None:
        previous = self.write_section("blog_posts")
        os.chmod(previous, 0o640)

        with generate_sitemap.atomic_xml_file(str(previous)) as output:
            output.write("<urlset></urlset>")

        self.assertEqual(stat.S_IMODE(previous.stat().st_mode), 0o640)

    def test_exclude_option_skips_organizations(self) -> None:
        with (
            patch.object(generate_sitemap, "LANGUAGES", ["en"]),
            patch.object(
                generate_sitemap,
                "SITEMAP_PAGE_TYPES",
                {
                    "blog_posts": "blog.BlogPostPage",
                    "catalog_organizations": "catalog.Organization",
                },
            ),
            patch.object(generate_sitemap, "_run_job", return_value=[]) as run_job,
        ):
            call_command("generate_sitemap", "--exclude", "catalog_organizations")

        self.assertEqual(run_job.call_count, 1)
        self.assertEqual(run_job.call_args.args[0][0].sitemap_name, "blog_posts")
