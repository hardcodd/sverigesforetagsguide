import re
from unittest.mock import patch

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils.translation import override

from reviews.models import ReviewStatus


class HeroCounterTests(SimpleTestCase):
    def test_counters_render_matching_digit_groups(self) -> None:
        cases = (
            (0, "0"),
            (999, "999"),
            (1000, "1 000"),
            (505649, "505 649"),
            (1234567, "1 234 567"),
        )
        with (
            patch("catalog.services.Organization.objects.live") as organizations,
            patch("reviews.templatetags.reviews.Review.objects.filter") as reviews,
        ):
            for language in ("ru", "ka", "en"):
                for count, expected in cases:
                    with (
                        self.subTest(language=language, count=count),
                        override(language),
                    ):
                        cache.clear()
                        organizations.return_value.count.return_value = count
                        organizations.return_value.filter.return_value.count.return_value = (
                            count
                        )
                        reviews.return_value.count.return_value = count
                        reviews.reset_mock()
                        old_key = make_template_fragment_key(
                            "hero_counters_reviews", [language]
                        )
                        cache.set(
                            old_key, '<div class="hero-counter__number">old</div>'
                        )

                        html = render_to_string("includes/hero-counters.html")

                        self.assertEqual(
                            re.findall(
                                r'class="hero-counter__number">([^<]*)</div>', html
                            ),
                            [expected] * 3,
                        )
                        reviews.assert_called_once_with(status=ReviewStatus.PUBLISHED)
                        self.assertEqual(
                            render_to_string("includes/hero-counters.html"), html
                        )
                        reviews.return_value.count.assert_called_once_with()
