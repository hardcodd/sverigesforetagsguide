import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import Http404, HttpResponseBase
from django.test import RequestFactory, SimpleTestCase

from core import views


class SitemapViewTests(SimpleTestCase):
    def setUp(self) -> None:
        directory = self.enterContext(TemporaryDirectory())
        self.template_root = Path(directory)
        self.sitemap_root = self.template_root / "sitemaps"
        self.sitemap_root.mkdir()
        self.enterContext(
            self.settings(
                TEMPLATES=[
                    {
                        "BACKEND": "django.template.backends.django.DjangoTemplates",
                        "DIRS": [str(self.template_root)],
                        "APP_DIRS": False,
                    }
                ]
            )
        )
        self.enterContext(patch.object(views, "SITEMAP_ROOT", str(self.sitemap_root)))
        self.requests = RequestFactory()

    def response_bytes(self, response: HttpResponseBase) -> bytes:
        try:
            return b"".join(response)
        finally:
            response.close()

    def test_index_reads_replaced_file_without_restart(self) -> None:
        path = self.sitemap_root / "sitemap.xml"
        path.write_bytes(b"<sitemapindex><old /></sitemapindex>")

        first = views.sitemap_index(self.requests.get("/sitemap.xml"))
        self.assertEqual(first["Content-Type"], "application/xml")
        replacement = path.with_name("sitemap.xml.tmp")
        replacement.write_bytes(b"<sitemapindex><new /></sitemapindex>")
        os.replace(replacement, path)
        self.assertEqual(
            self.response_bytes(first), b"<sitemapindex><old /></sitemapindex>"
        )

        second = views.sitemap_index(self.requests.get("/sitemap.xml"))
        self.assertEqual(
            self.response_bytes(second), b"<sitemapindex><new /></sitemapindex>"
        )
        self.assertTrue(second.streaming)

    def test_section_reads_replaced_file_without_restart(self) -> None:
        path = self.sitemap_root / "en" / "blog_posts" / "sitemap-1.xml"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"<urlset><old /></urlset>")
        request = self.requests.get("/sitemaps/en/blog_posts/sitemap-1.xml")

        first = views.sitemap_section(request, "en", "blog_posts", "1")
        self.assertEqual(first["Content-Type"], "application/xml")
        replacement = path.with_name("sitemap-1.xml.tmp")
        replacement.write_bytes(b"<urlset><new /></urlset>")
        os.replace(replacement, path)
        self.assertEqual(self.response_bytes(first), b"<urlset><old /></urlset>")

        second = views.sitemap_section(request, "en", "blog_posts", "1")
        self.assertEqual(self.response_bytes(second), b"<urlset><new /></urlset>")
        self.assertTrue(second.streaming)

    def test_missing_files_and_unknown_language_return_404(self) -> None:
        with self.assertRaises(Http404):
            views.sitemap_index(self.requests.get("/sitemap.xml"))
        with self.assertRaises(Http404):
            views.sitemap_section(
                self.requests.get("/sitemaps/en/blog_posts/sitemap-1.xml"),
                "en",
                "blog_posts",
                "1",
            )
        with self.assertRaises(Http404):
            views.sitemap_section(
                self.requests.get("/sitemaps/zz/blog_posts/sitemap-1.xml"),
                "zz",
                "blog_posts",
                "1",
            )
