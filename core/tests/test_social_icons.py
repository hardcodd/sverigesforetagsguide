from unittest.mock import patch

from django.template import Context, Template
from django.template.exceptions import TemplateDoesNotExist
from django.test import SimpleTestCase

from core.templatetags.core import social_network_icon


class SocialNetworkIconTests(SimpleTestCase):
    def test_supported_services_and_short_links(self):
        cases = {
            "https://wa.me/995555123456": "whatsapp",
            "https://api.whatsapp.com/send?phone=995555123456": "whatsapp",
            "https://vb.me/example": "viber",
            "https://invite.viber.com/example": "viber",
            "https://www.tiktok.com/@example": "tiktok",
            "https://vm.tiktok.com/example": "tiktok",
            "https://maps.app.goo.gl/example": "google",
            "https://goo.gl/maps/example": "google",
            "https://www.google.com/maps/place/example": "google",
            "https://maps.google.com/?q=example": "google",
            "https://yandex.ru/maps/org/example": "yandex",
            "https://ya.cc/example": "yandex",
            "https://www.facebook.com/example": "facebook",
            "https://www.instagram.com/example": "instagram",
            "https://x.com/example": "x",
            "https://twitter.com/example": "twitter",
            "https://t.me/example": "telegram",
            "https://youtu.be/example": "youtube",
            "https://youtube.com/example": "youtube",
            "https://linkedin.com/in/example": "linkedin",
            "https://vk.com/example": "vk",
            "https://pinterest.com/example": "pinterest",
            "https://dzen.ru/example": "dzen",
            "https://tripadvisor.com/example": "tripadvisor",
            "WA.ME/example": "whatsapp",
        }
        for url, icon in cases.items():
            with self.subTest(url=url):
                with patch("core.templatetags.core.get_template") as loader:
                    loader.return_value.render.return_value = "<svg></svg>"
                    self.assertEqual(social_network_icon(url), "<svg></svg>")
                    loader.assert_called_once_with(f"icons/{icon}.svg")

    def test_unknown_and_lookalike_hosts_remain_text(self):
        for url, expected in (
            ("https://wa.me.example.org/x", "wa.me.example.org"),
            ("https://notfacebook.com/x", "notfacebook.com"),
            ("https://example.org/?next=https://t.me/example", "example.org"),
            ("https://facebook.com@example.org/", "example.org"),
            ("https://example.org", "example.org"),
            ("https://google.com/search?q=maps", "google.com"),
            ("", ""),
        ):
            with self.subTest(url=url):
                self.assertEqual(social_network_icon(url), expected)

    def test_fallback_text_is_escaped_even_for_malformed_urls(self):
        for url in (
            "https://<script>alert(1)</script>",
            "https://[<img src=x onerror=alert(1)>",
        ):
            with self.subTest(url=url):
                rendered = Template(
                    "{% load core %}{{ url|social_network_icon }}"
                ).render(Context({"url": url}))
                self.assertNotIn("<script", rendered)
                self.assertNotIn("<img", rendered)
                self.assertIn("&lt;", rendered)

    def test_missing_template_falls_back_to_domain(self):
        with patch(
            "core.templatetags.core.get_template",
            side_effect=TemplateDoesNotExist("missing"),
        ):
            self.assertEqual(social_network_icon("https://wa.me/example"), "wa.me")

    def test_existing_icon_files_render_as_svg(self):
        for host in ("wa.me", "vb.me", "tiktok.com", "maps.app.goo.gl", "yandex.ru"):
            with self.subTest(host=host):
                self.assertIn("<svg", social_network_icon("https://" + host))
