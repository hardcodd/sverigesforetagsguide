from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils.translation import override
from wagtail.models import Page
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file

from blog.models import BlogCategoryPage, BlogIndexPage
from blog.services import get_blog_categories_list_service
from catalog.models import City, Organization, OrganizationImage, OrganizationType
from catalog.services import get_current_city_service, get_latest_organizations_service
from core.context_processors import footer
from core.maps import static_map_url
from core.page_tree import build_page_tree
from ratings.models import RatingCategoryPage, RatingsIndexPage
from ratings.services import get_ratings_categories_list_service
from reviews.models import Review, ReviewImage, ReviewStatus
from reviews.templatetags.reviews import get_reviews


LOCAL_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


class PageTreeTests(SimpleTestCase):
    def test_tree_preserves_order_without_queries_or_input_mutation(self):
        root = Page(path="00010001", depth=2)
        pages = [
            Page(path="0001000100020001", depth=4, title="Child"),
            Page(path="000100010002", depth=3, title="Second"),
            Page(path="000100010001", depth=3, title="First"),
            Page(path="0001000100030001", depth=4, title="Orphan"),
        ]
        tree = build_page_tree(pages, root)
        self.assertEqual([node.title for node in tree], ["Second", "First"])
        self.assertEqual([node.title for node in tree[0].children], ["Child"])
        self.assertFalse(hasattr(pages[0], "children"))
        self.assertEqual(build_page_tree([], root), [])


class MapPreviewTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.directory.name,
            MEDIA_URL="/media/",
            GOOGLE_MAPS_API_KEY="test-key",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    @patch("requests.get")
    def test_missing_preview_returns_encoded_url_without_network_or_file_writes(
        self, get
    ):
        result = static_map_url(12, "41.7,44.8")
        parts = urlsplit(result)
        self.assertEqual(parts.netloc, "maps.googleapis.com")
        self.assertEqual(
            parse_qs(parts.query),
            {
                "center": ["41.7,44.8"],
                "zoom": ["15"],
                "size": ["800x400"],
                "markers": ["41.7,44.8"],
                "key": ["test-key"],
            },
        )
        get.assert_not_called()
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    @patch("requests.get")
    def test_existing_preview_is_reused(self, get):
        maps = Path(self.directory.name) / "maps"
        maps.mkdir()
        (maps / "12-map.jpg").write_bytes(b"existing-map")
        self.assertEqual(static_map_url(12, "41.7,44.8"), "/media/maps/12-map.jpg")
        get.assert_not_called()


@override_settings(CACHES=LOCAL_CACHE)
class PublicQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = Page.get_first_root_node()
        cls.city = cls.root.add_child(instance=City(title="City", slug="perf-city"))
        cls.category = cls.city.add_child(
            instance=OrganizationType(title="Category", slug="category")
        )
        cls.organization = cls.category.add_child(
            instance=Organization(title="Place", slug="place")
        )
        cls.blog = cls.root.add_child(
            instance=BlogIndexPage(title="Blog", slug="perf-blog")
        )
        cls.blog_category = cls.blog.add_child(
            instance=BlogCategoryPage(title="Visible", slug="visible")
        )
        cls.blog_category.add_child(
            instance=BlogCategoryPage(title="Visible child", slug="visible-child")
        )
        cls.blog_category.add_child(
            instance=BlogCategoryPage(
                title="Hidden child", slug="hidden-child", live=False
            )
        )
        cls.ratings = cls.root.add_child(
            instance=RatingsIndexPage(title="Ratings", slug="perf-ratings")
        )
        cls.rating_category = cls.ratings.add_child(
            instance=RatingCategoryPage(title="Rating category", slug="category")
        )
        cls.rating_category.add_child(
            instance=RatingCategoryPage(title="Nested rating", slug="nested")
        )
        cls.user = get_user_model().objects.create_user(username="perf-author")
        for index in range(12):
            Review.objects.create(
                user=cls.user,
                content_type_id=cls.organization.content_type_id,
                object_id=cls.organization.pk,
                status=ReviewStatus.PUBLISHED,
                rating=5,
                comment=f"Review {index}",
            )
        Review.objects.create(
            user=cls.user,
            content_type_id=cls.organization.content_type_id,
            object_id=cls.organization.pk,
            status=ReviewStatus.MODERATION,
            rating=5,
            comment="Pending review",
        )

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def test_current_city_uses_one_query_regardless_of_depth(self):
        with self.assertNumQueries(1):
            self.assertEqual(
                get_current_city_service({"page": self.organization}), self.city.title
            )
        with self.assertNumQueries(0):
            self.assertEqual(
                get_current_city_service({"page": self.city}), self.city.title
            )
            self.assertEqual(get_current_city_service({}), "")
            self.assertEqual(get_current_city_service({"page": object()}), "")
        with self.assertNumQueries(1):
            self.assertEqual(get_current_city_service({"page": self.blog}), "")

    def test_current_city_preserves_translation_fallback(self):
        City.objects.filter(pk=self.city.pk).update(title_en="Translated city")
        with override("en"), self.assertNumQueries(1):
            self.assertEqual(
                get_current_city_service({"page": self.organization}), "Translated city"
            )

    def test_latest_organizations_keep_filter_limit_and_lazy_content(self):
        with self.assertNumQueries(1):
            cards = list(get_latest_organizations_service(self.city, 1))
        self.assertEqual([card.pk for card in cards], [self.organization.pk])
        self.assertIn("qna", cards[0].get_deferred_fields())
        with self.assertNumQueries(1):
            self.assertEqual(list(get_latest_organizations_service(self.blog, 4)), [])

    def test_footer_does_not_load_inside_a_cached_fragment(self):
        cache.set(make_template_fragment_key("perf_footer"), "cached footer")
        template = Template(
            "{% load cache %}{% cache 60 perf_footer %}{{ footer.navigations }}{% endcache %}"
        )
        with self.assertNumQueries(0):
            context = footer(self.factory.get("/"))
            self.assertEqual(template.render(Context(context)), "cached footer")

    def test_empty_footer_is_read_once_and_never_created_on_get(self):
        from core.models import Footer

        Footer.objects.all().delete()
        with self.assertNumQueries(1):
            lazy_footer = footer(self.factory.get("/"))["footer"]
            self.assertFalse(lazy_footer)
            self.assertFalse(lazy_footer)
        self.assertFalse(Footer.objects.exists())

    def test_blog_tree_has_fixed_query_count_and_omits_drafts(self):
        with self.assertNumQueries(2):
            tree = get_blog_categories_list_service({"page": self.blog_category})
        self.assertEqual([node.title for node in tree], ["Visible"])
        self.assertEqual([node.title for node in tree[0].children], ["Visible child"])

    def test_ratings_tree_has_fixed_query_count(self):
        with self.assertNumQueries(2):
            tree = get_ratings_categories_list_service({"page": self.rating_category})
        self.assertEqual([node.title for node in tree], ["Rating category"])
        self.assertEqual([node.title for node in tree[0].children], ["Nested rating"])

    def test_category_services_handle_pages_outside_the_section(self):
        for service in (
            get_blog_categories_list_service,
            get_ratings_categories_list_service,
        ):
            with self.subTest(service=service.__name__), self.assertNumQueries(1):
                self.assertEqual(service({"page": self.city}), [])

    def test_reviews_load_authors_and_images_in_constant_queries(self):
        self.organization.content_type
        with self.assertNumQueries(3):
            page = get_reviews({"request": self.factory.get("/")}, self.organization)
            reviews = list(page)
            names = [review.user.username for review in reviews]
            images = [list(review.images.all()) for review in reviews]
        self.assertEqual(page.paginator.count, 12)
        self.assertEqual(len(reviews), 10)
        self.assertEqual(names, ["perf-author"] * 10)
        self.assertEqual(images, [[] for _ in reviews])
        with self.assertNumQueries(3):
            second = get_reviews(
                {"request": self.factory.get("/?page=2")}, self.organization
            )
            self.assertEqual(len(list(second)), 2)

    def test_saving_organization_invalidates_current_card_cache_in_all_languages(self):
        keys = [
            make_template_fragment_key(key, [self.organization.pk, lang])
            for key in ("organization_item_i18n_v2", "organization_item_i18n_v4")
            for lang in ("ru", "en", "ka")
        ]
        for key in keys:
            cache.set(key, "old card")
        self.organization.save()
        self.assertTrue(all(cache.get(key) is None for key in keys))

    def test_cards_render_one_lazy_image_with_gallery_or_fallback(self):
        from bs4 import BeautifulSoup

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = get_image_model().objects.create(
                title="Card image", file=get_test_image_file()
            )
            for use_gallery in (False, True):
                with self.subTest(use_gallery=use_gallery):
                    cache.clear()
                    if use_gallery:
                        OrganizationImage.objects.create(
                            page=self.organization, image=image
                        )
                    html = render_to_string(
                        "catalog/includes/organization-item.html",
                        {
                            "organization": Organization.objects.get(
                                pk=self.organization.pk
                            ),
                            "settings": SimpleNamespace(
                                core=SimpleNamespace(
                                    SiteSettings=SimpleNamespace(
                                        default_organization_image=image
                                    )
                                )
                            ),
                        },
                    )
                    document = BeautifulSoup(html, "html.parser")
                    images = document.select(".organization-item img")
                    self.assertEqual(len(images), 1)
                    self.assertEqual(images[0]["loading"], "lazy")
                    self.assertNotIn("max-165x165", html)
                    self.assertIn("Place", document.get_text())

    def test_review_images_and_renditions_are_prefetched(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = get_image_model().objects.create(
                title="Review photo", file=get_test_image_file()
            )
            review = Review.objects.filter(status=ReviewStatus.PUBLISHED).latest(
                "created_at"
            )
            ReviewImage.objects.create(review=review, image=image)
            expected_renditions = list(image.renditions.values_list("pk", flat=True))
            with self.assertNumQueries(4):
                page = get_reviews(
                    {"request": self.factory.get("/")}, self.organization
                )
                photos = [photo for review in page for photo in review.images.all()]
                self.assertEqual(
                    [photo.image.title for photo in photos], ["Review photo"]
                )
                self.assertEqual(
                    [
                        [rendition.pk for rendition in photo.image.renditions.all()]
                        for photo in photos
                    ],
                    [expected_renditions],
                )
