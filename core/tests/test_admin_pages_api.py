from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file, get_test_image_file_svg
from wagtail.models import Page

from catalog.models import City, Organization, OrganizationImage, OrganizationType
from authors.models import AuthorPage
from blog.models import BlogPostPage
from core.admin_pages_api import build_page_previews
from gallery.models import (
    GalleryCategoryPage,
    GalleryImage,
    GalleryIndexPage,
    GalleryPostPage,
)
from home.models import FlatPage, HomePage
from ratings.models import RatingPage


API_PATH = "/aristarx/api/main/pages/"


class AdminPagesAPITests(TestCase):
    def setUp(self) -> None:
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="api-admin", email="admin@example.com", password="example-pass"
        )
        self.client.force_login(self.admin)
        root = Page.get_first_root_node()
        self.home = root.add_child(
            instance=HomePage(title="Admin API Home", slug="k42-admin-api-home")
        )

    def test_list_is_restricted_to_admin_users(self) -> None:
        self.client.logout()
        response = self.client.get(API_PATH, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)

        user_model = get_user_model()
        ordinary_user = user_model.objects.create_user(
            username="api-reader", email="reader@example.com", password="example-pass"
        )
        self.client.force_login(ordinary_user)
        response = self.client.get(API_PATH, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)

    def test_limit_100_returns_100_pages_and_rejects_higher_limit(self) -> None:
        for index in range(101):
            self.home.add_child(
                instance=FlatPage(title=f"Page {index}", slug=f"page-{index}")
            )

        response = self.client.get(API_PATH, {"limit": 100})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 100)

        response = self.client.get(API_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 20)

        response = self.client.get(API_PATH, {"limit": 101})
        self.assertEqual(response.status_code, 400)

    def test_browser_navigation_returns_json(self) -> None:
        response = self.client.get(
            API_PATH,
            {"limit": 100},
            HTTP_ACCEPT="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("items", response.json())

    def test_list_includes_preview_noindex_and_draft_status(self) -> None:
        image = get_image_model().objects.create(
            title="Page image", file=get_test_image_file()
        )
        city = self.home.add_child(instance=City(title="City", slug="city"))
        category = city.add_child(
            instance=OrganizationType(
                title="Category", slug="category", image=image, noindex=True
            )
        )
        organization = category.add_child(
            instance=Organization(
                title="Organization", slug="organization", has_unpublished_changes=True
            )
        )
        OrganizationImage.objects.create(page=organization, image=image, sort_order=0)
        plain_page = self.home.add_child(instance=FlatPage(title="Plain", slug="plain"))

        response = self.client.get(API_PATH, {"limit": 100})
        self.assertEqual(response.status_code, 200)
        items = {item["id"]: item for item in response.json()["items"]}

        category_data = items[category.pk]
        self.assertIs(category_data["noindex"], True)
        preview = category_data["image"]
        self.assertIn("url", preview)
        self.assertIn(".max-1200x630.format-jpeg", preview["url"])

        organization_data = items[organization.pk]
        self.assertIn(".fill-720x405.format-jpeg", organization_data["image"]["url"])
        self.assertIsNone(organization_data["noindex"])
        self.assertIs(organization_data["has_unpublished_changes"], True)

        plain_data = items[plain_page.pk]
        self.assertIsNone(plain_data["image"])
        self.assertIsNone(plain_data["noindex"])
        self.assertIs(plain_data["has_unpublished_changes"], False)

    def test_preview_size_matches_page_type(self) -> None:
        image = get_image_model().objects.create(
            title="Shared page image", file=get_test_image_file(size=(1600, 1200))
        )
        pages = [
            HomePage(pk=1001, image=image),
            BlogPostPage(pk=1002, image=image),
            AuthorPage(pk=1003, image=image),
            GalleryCategoryPage(pk=1004, image=image),
        ]

        previews = build_page_previews(pages)

        for page, filter_spec in zip(
            pages,
            ("max-1200x630", "fill-720x405", "fill-768x1024", "fill-560x315"),
            strict=True,
        ):
            self.assertIn(f".{filter_spec}.format-jpeg", previews[page.pk]["url"])
            if filter_spec.startswith("fill-"):
                width, height = map(int, filter_spec.removeprefix("fill-").split("x"))
                self.assertEqual(
                    (previews[page.pk]["width"], previews[page.pk]["height"]),
                    (width, height),
                )

    def test_gallery_and_rating_use_their_page_image_size(self) -> None:
        image = get_image_model().objects.create(
            title="Gallery image", file=get_test_image_file()
        )
        city = self.home.add_child(instance=City(title="City", slug="city"))
        category = city.add_child(
            instance=OrganizationType(title="Category", slug="category")
        )
        organization = category.add_child(
            instance=Organization(title="Organization", slug="organization")
        )
        rating = RatingPage(pk=1006, to_organization_id=organization.pk)
        gallery_index = self.home.add_child(
            instance=GalleryIndexPage(title="Gallery", slug="gallery")
        )
        gallery_category = gallery_index.add_child(
            instance=GalleryCategoryPage(title="Category", slug="category")
        )
        gallery = gallery_category.add_child(
            instance=GalleryPostPage(title="Post", slug="post")
        )
        OrganizationImage.objects.create(page=organization, image=image, sort_order=0)
        GalleryImage.objects.create(page=gallery, image=image, sort_order=0)

        previews = build_page_previews([rating, gallery])

        self.assertIn(".fill-720x405.format-jpeg", previews[rating.pk]["url"])
        self.assertIn(".fill-560x315.format-jpeg", previews[gallery.pk]["url"])

    def test_svg_image_does_not_break_page_list(self) -> None:
        image = get_image_model().objects.create(
            title="Vector image", file=get_test_image_file_svg()
        )
        self.home.image = image
        self.home.save(update_fields=["image"])

        response = self.client.get(API_PATH)

        self.assertEqual(response.status_code, 200)
        items = {item["id"]: item for item in response.json()["items"]}
        self.assertIsNone(items[self.home.pk]["image"])
