from datetime import timedelta
from tempfile import TemporaryDirectory

from django.template.loader import render_to_string
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from django.utils.translation import override
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page, PageViewRestriction

from catalog.models import City, Organization, OrganizationType
from catalog.promotions import get_competitors
from core.blocks import InlineBannerBlock
from subscription.models import PremiumSubscription


LOCAL_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCAL_CACHE)
class OrganizationPromotionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        city = root.add_child(instance=City(title="City", slug="promotion-city"))
        cls.category = city.add_child(
            instance=OrganizationType(title="Category", slug="category")
        )
        cls.other_category = city.add_child(
            instance=OrganizationType(title="Other", slug="other")
        )
        cls.organization = cls.category.add_child(
            instance=Organization(title="Visitor", slug="visitor")
        )
        cls.premium = cls.category.add_child(
            instance=Organization(title="Premium", slug="premium")
        )
        cls.today = timezone.localdate()
        cls.subscription = PremiumSubscription.objects.create(
            organization=cls.premium,
            level=PremiumSubscription.Level.PREMIUM,
            start_date=cls.today,
            end_date=cls.today,
            is_active=True,
        )

    def test_unpaid_page_shows_premium_peer_in_same_category(self):
        self.assertEqual(get_competitors(self.organization), [self.premium])

    def test_every_active_paid_level_hides_competitors(self):
        for level in (
            PremiumSubscription.Level.BASIC,
            PremiumSubscription.Level.STANDARD,
            PremiumSubscription.Level.PREMIUM,
        ):
            with self.subTest(level=level):
                subscription = PremiumSubscription.objects.create(
                    organization=self.organization,
                    level=level,
                    start_date=self.today,
                    end_date=self.today,
                    is_active=True,
                )
                with self.assertNumQueries(1):
                    self.assertEqual(get_competitors(self.organization), [])
                subscription.delete()

    def test_expired_future_disabled_and_free_subscriptions_do_not_hide_competitors(
        self,
    ):
        cases = (
            {
                "start_date": self.today - timedelta(days=2),
                "end_date": self.today - timedelta(days=1),
            },
            {
                "start_date": self.today + timedelta(days=1),
                "end_date": self.today + timedelta(days=2),
            },
            {"is_active": False},
            {"level": PremiumSubscription.Level.COMPETITOR},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                values = dict(
                    organization=self.organization,
                    level=PremiumSubscription.Level.PREMIUM,
                    start_date=self.today,
                    end_date=self.today,
                    is_active=True,
                )
                subscription = PremiumSubscription.objects.create(**(values | changes))
                self.assertEqual(get_competitors(self.organization), [self.premium])
                subscription.delete()

    def test_ineligible_candidates_are_excluded(self):
        for changes in (
            {"level": PremiumSubscription.Level.BASIC},
            {"level": PremiumSubscription.Level.STANDARD},
            {"level": PremiumSubscription.Level.COMPETITOR},
            {"is_active": False},
            {"end_date": self.today - timedelta(days=1)},
            {"start_date": self.today + timedelta(days=1)},
        ):
            with self.subTest(changes=changes):
                PremiumSubscription.objects.filter(pk=self.subscription.pk).update(
                    **changes
                )
                self.assertEqual(get_competitors(self.organization), [])
                self.subscription.save()

    def test_unpublished_private_other_category_and_self_are_excluded(self):
        self.assertEqual(get_competitors(self.premium), [])
        Organization.objects.filter(pk=self.premium.pk).update(live=False)
        self.assertEqual(get_competitors(self.organization), [])
        Organization.objects.filter(pk=self.premium.pk).update(live=True)
        restriction = PageViewRestriction.objects.create(
            page=self.premium, restriction_type="login"
        )
        self.assertEqual(get_competitors(self.organization), [])
        restriction.delete()
        self.premium.move(self.other_category, pos="last-child")
        self.assertEqual(get_competitors(self.organization), [])

    def test_at_most_four_unique_candidates(self):
        for index in range(5):
            peer = self.category.add_child(
                instance=Organization(title=f"Peer {index}", slug=f"peer-{index}")
            )
            PremiumSubscription.objects.create(
                organization=peer,
                level=3,
                start_date=self.today,
                end_date=self.today,
                is_active=True,
            )
        peers = get_competitors(self.organization)
        self.assertEqual(len(peers), 4)
        self.assertEqual(len({peer.pk for peer in peers}), 4)

    def test_category_ratings_do_not_depend_on_subscription(self):
        self.category.ratings_text = '<h3>Popular ratings</h3><p><a href="https://example.org/rating/">Rating</a></p>'
        self.category.save()
        request = RequestFactory().get("/")
        for page in (self.organization, self.premium):
            with self.subTest(page=page.pk):
                self.assertEqual(
                    page.get_context(request)["promotion_category"].ratings_text,
                    self.category.ratings_text,
                )


@override_settings(CACHES=LOCAL_CACHE)
class PromotionRenderingTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.override = override_settings(MEDIA_ROOT=directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.image = get_image_model().objects.create(
            title="Promotion", file=get_test_image_file()
        )

    def test_category_block_requires_image_and_text(self):
        category = OrganizationType(
            ratings_image=self.image, ratings_text="<p>Rating</p>"
        )
        template = "catalog/includes/category_ratings.html"
        self.assertIn(
            "<p>Rating</p>", render_to_string(template, {"category": category})
        )
        category.ratings_image = None
        self.assertNotIn("<aside", render_to_string(template, {"category": category}))
        category.ratings_image = self.image
        category.ratings_text = ""
        self.assertNotIn("<aside", render_to_string(template, {"category": category}))

    def test_configurable_banner_escapes_text_and_has_no_nested_container(self):
        block = InlineBannerBlock()
        value = block.to_python(
            {
                "title": "<script>Title</script>",
                "description": "Text & more",
                "image": self.image.pk,
                "page": None,
                "url": "https://example.org/promotion/",
                "button_text": "Open",
                "style": "light-blue",
            }
        )
        html = block.render(value)
        self.assertIn("&lt;script&gt;Title&lt;/script&gt;", html)
        self.assertIn('href="https://example.org/promotion/"', html)
        self.assertNotIn('class="container"', html)
        self.assertIn("<img", html)
        value["url"] = ""
        self.assertNotIn("<a ", block.render(value))
        value["page"] = Page.get_first_root_node()
        self.assertNotIn("<a ", block.render(value))

    def test_banner_url_rejects_executable_schemes(self):
        block = InlineBannerBlock()
        for value in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                block.child_blocks["url"].clean(value)

    def test_premium_banner_uses_legacy_copy_and_localized_link(self):
        for language, title, link in (
            (
                "ru",
                "Хотите увеличить количество клиентов в 5 раз?",
                "/premium-contacts/",
            ),
            (
                "en",
                "Do you want to increase the number of clients by 5 times?",
                "/en/premium-contacts/",
            ),
        ):
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "catalog/includes/premium_banner.html",
                    {
                        "request": RequestFactory().get(
                            "/en/" if language == "en" else "/"
                        )
                    },
                )
                self.assertIn(title, html)
                self.assertIn(f'href="{link}"', html)
                self.assertIn("banners/premium-placement.png", html)
