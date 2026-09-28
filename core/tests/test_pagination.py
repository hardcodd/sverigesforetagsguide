from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.core import signing
from django.contrib.auth import get_user_model
from django.http import Http404
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override
from wagtail.images import get_image_model
from wagtail.models import Page, Site

from authors.models import AuthorPage, AuthorsIndexPage
from blog.models import BlogIndexPage, BlogPostPage
from catalog.models import City, Organization
from core.pagination import PaginationRedirect, paginate, page_url
from core.templatetags.core import pagination_canonical, remove_page, set_page
from gallery.models import GalleryCategoryPage, GalleryImage, GalleryPostPage
from reviews.models import Review, ReviewStatus
from ratings.models import RatingsIndexPage


class PaginationContractTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_missing_page_and_existing_boundaries(self) -> None:
        for query, number, items in (
            ("", 1, [0, 1]),
            ("?page=2", 2, [2, 3]),
            ("?page=3", 3, [4]),
        ):
            with self.subTest(query=query):
                result = paginate(self.factory.get("/list/" + query), list(range(5)), 2)
                self.assertEqual(result.number, number)
                self.assertEqual(list(result), items)

    def test_empty_list_has_a_first_page_only(self) -> None:
        self.assertEqual(list(paginate(self.factory.get("/list/"), [])), [])
        with self.assertRaises(Http404):
            paginate(self.factory.get("/list/?page=2"), [])

    def test_invalid_values_and_repeated_parameter_raise_404(self) -> None:
        for query in (
            "page=",
            "page=abc",
            "page=0",
            "page=-1",
            "page=999",
            "page=1.5",
            "page=%2B2",
            "page=%202",
            "page=2%20",
            "page=٢",
            "page=1&page=2",
            "page=2&page=2",
            "page=0999",
            "page=" + "9" * 5000,
        ):
            with self.subTest(query=query[:60]), self.assertRaises(Http404):
                paginate(self.factory.get("/list/?" + query), list(range(5)), 2)

    def test_redirect_preserves_filters_and_repeated_values(self) -> None:
        for raw, expected in (("1", None), ("01", None), ("02", ["2"])):
            request = self.factory.get(
                f"/en/list/?page={raw}&tag=a&tag=b&q=a%26b&empty="
            )
            with self.subTest(raw=raw), self.assertRaises(PaginationRedirect) as caught:
                paginate(request, list(range(5)), 2)
            parts = urlsplit(caught.exception.url)
            self.assertEqual(parts.path, "/en/list/")
            query = parse_qs(parts.query, keep_blank_values=True)
            self.assertEqual(query.pop("page", None), expected)
            self.assertEqual(query, {"tag": ["a", "b"], "q": ["a&b"], "empty": [""]})

    def test_redirect_cannot_use_a_protocol_relative_host(self) -> None:
        request = self.factory.get("/list/?page=1")
        request.path = "//outside.example/list/"
        with self.assertRaises(PaginationRedirect) as caught:
            paginate(request, [1])
        self.assertEqual(caught.exception.url, "/%2Foutside.example/list/")

    def test_link_filters_preserve_query_and_fragment(self) -> None:
        url = "/en/list/?page=2&tag=a&tag=b&empty=#results"
        expected = "/en/list/?tag=a&tag=b&empty=#results"
        self.assertEqual(remove_page(url), expected)
        self.assertEqual(set_page(url, 1), expected)
        self.assertEqual(
            set_page(url, 3), "/en/list/?tag=a&tag=b&empty=&page=3#results"
        )
        self.assertEqual(page_url("/list/?q=page%3D2", 2), "/list/?q=page%3D2&page=2")

    def test_canonical_changes_only_pagination(self) -> None:
        base = "https://example.com/en/list/"
        for query, expected in (
            ("", base),
            ("?page=1", base),
            ("?page=2&tag=a", base + "?page=2"),
        ):
            with self.subTest(query=query):
                self.assertEqual(
                    pagination_canonical(base, self.factory.get("/list/" + query)),
                    expected,
                )

    def test_rendered_first_page_link_keeps_filters(self) -> None:
        request = self.factory.get("/list/?page=2&tag=a&tag=b")
        result = paginate(request, [1, 2, 3], 2)
        html = Template(
            '{% include "includes/pagination.html" with page_obj=result %}'
        ).render(Context({"request": request, "result": result}))
        self.assertIn('href="/list/?tag=a&amp;tag=b"', html)
        self.assertNotIn("?page=1", html)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class PublicPaginationTests(TestCase):
    def setUp(self) -> None:
        self.enterContext(override("ru"))

    @classmethod
    def setUpTestData(cls) -> None:
        root = Page.get_first_root_node()
        cls.home = root.add_child(
            instance=Page(title="Pagination fixtures", slug="pagination-fixtures")
        )
        Site.objects.all().delete()
        Site.objects.create(
            hostname="testserver", root_page=cls.home, is_default_site=True
        )
        cls.blog = cls.home.add_child(instance=BlogIndexPage(title="Blog", slug="blog"))
        cls.city = cls.home.add_child(instance=City(title="City", slug="city"))
        cls.authors = cls.home.add_child(
            instance=AuthorsIndexPage(title="Authors", slug="authors")
        )
        cls.ratings = cls.home.add_child(
            instance=RatingsIndexPage(title="Ratings", slug="ratings")
        )
        cls.gallery = cls.home.add_child(
            instance=GalleryCategoryPage(title="Galleries", slug="galleries")
        )
        cls.album = cls.gallery.add_child(
            instance=GalleryPostPage(title="Album", slug="album")
        )
        cls.organization = cls.city.add_child(
            instance=Organization(
                title="Business",
                slug="business",
                address="Fixture street",
                h1_title="Business",
            )
        )
        for number in range(17):
            cls.blog.add_child(
                instance=BlogPostPage(title=f"Post {number}", slug=f"post-{number}")
            )
            cls.authors.add_child(
                instance=AuthorPage(
                    title=f"Author {number}", slug=f"author-{number}", post="Writer"
                )
            )
        for number in range(20):
            cls.city.add_child(
                instance=Organization(
                    title=f"Business {number}",
                    slug=f"business-{number}",
                    address="Fixture street",
                )
            )
        image = get_image_model()(
            title="Fixture", file="pagination-fixture.png", width=1, height=1
        )
        get_image_model().objects.bulk_create([image])
        GalleryImage.objects.bulk_create(
            [
                GalleryImage(page=cls.album, image=image, sort_order=number)
                for number in range(25)
            ]
        )
        user = get_user_model().objects.create_user(username="pagination-reader")
        Review.objects.bulk_create(
            [
                Review(
                    content_type=cls.organization.content_type,
                    object_id=cls.organization.pk,
                    user=user,
                    rating=5,
                    status=ReviewStatus.PUBLISHED,
                )
                for number in range(11)
            ]
        )

    def test_full_public_templates_return_404_and_301(self) -> None:
        for page in (
            self.blog,
            self.city,
            self.authors,
            self.ratings,
            self.gallery,
            self.album,
            self.organization,
        ):
            url = page.url
            for query in (
                "page=abc",
                "page=",
                "page=0",
                "page=-1",
                "page=999",
                "page=1&page=2",
            ):
                with self.subTest(page=page.slug, query=query):
                    self.assertEqual(
                        self.client.get(url + "?" + query).status_code, 404
                    )
            for raw in ("1", "01"):
                with self.subTest(page=page.slug, raw=raw):
                    response = self.client.get(url, {"page": raw})
                    self.assertEqual(response.status_code, 301)
                    self.assertEqual(response["Location"], url)

    def test_existing_second_pages_render_with_their_own_canonical(self) -> None:
        for page in (self.blog, self.city, self.authors):
            with self.subTest(page=page.slug):
                response = self.client.get(page.url, {"page": "2"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    f'<link rel="canonical" href="http://testserver{page.url}?page=2">',
                    html=True,
                )
                self.assertNotContains(response, 'href="?page=1"')
                first = self.client.get(page.url)
                self.assertContains(
                    first,
                    f'<link rel="canonical" href="http://testserver{page.url}">',
                    html=True,
                )

    def test_normalized_second_page_preserves_language_and_filters(self) -> None:
        response = self.client.get("/en/blog/?page=02&tag=a&tag=b")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/en/blog/?tag=a&tag=b&page=2")
        response = self.client.head(self.blog.url + "?page=1")
        self.assertEqual(response.status_code, 301)

    def test_catalog_address_filter_accepts_pagination(self) -> None:
        url = reverse("catalog:organizations")
        params = {"address": "Fixture street", "page": "2"}
        self.assertEqual(self.client.get(url, params).status_code, 200)
        params["page"] = "1"
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            parse_qs(urlsplit(response["Location"]).query),
            {"address": ["Fixture street"]},
        )
        params["page"] = "999"
        self.assertEqual(self.client.get(url, params).status_code, 404)

    def test_ajax_batches_obey_the_same_contract(self) -> None:
        endpoints = (
            (
                reverse("gallery:load_more_images"),
                {"page-id": str(self.album.pk)},
                "gallery.views.render_to_string",
            ),
            (
                reverse("load-more-reviews"),
                {"token": signing.dumps(self.organization.pk)},
                "reviews.views.render_to_string",
            ),
        )
        for url, params, renderer in endpoints:
            with (
                self.subTest(url=url),
                patch(renderer, return_value="<article>Fixture item</article>"),
            ):
                response = self.client.get(url, params | {"page": "2"})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(
                    len(data if isinstance(data, list) else data["reviews"]), 1
                )
                for value in ("abc", "0", "999", ""):
                    self.assertEqual(
                        self.client.get(url, params | {"page": value}).status_code, 404
                    )
                response = self.client.get(url, params | {"page": "1"})
                self.assertEqual(response.status_code, 301)
                self.assertEqual(
                    parse_qs(urlsplit(response["Location"]).query),
                    {key: [value] for key, value in params.items()},
                )
                self.assertEqual(self.client.get(response["Location"]).status_code, 200)

    def test_search_http_statuses(self) -> None:
        url = reverse("search")
        self.assertEqual(self.client.get(url).status_code, 200)
        for value in ("abc", "", "0", "-1", "999"):
            with self.subTest(value=value):
                self.assertEqual(self.client.get(url, {"page": value}).status_code, 404)
        response = self.client.get(url, {"page": "1", "query": "fixture"})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], url + "?query=fixture")
