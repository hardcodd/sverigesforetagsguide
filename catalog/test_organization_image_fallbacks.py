from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection, Page

from catalog.models import City, Organization, OrganizationImage, OrganizationType
from catalog.jsonld_builders import _get_org_images
from catalog.organization_images import (
    get_organization_fallback,
    get_organization_fallback_alt,
)
from core.templatetags.seo import social_image, social_image_alt


class OrganizationImageFallbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        city = root.add_child(instance=City(title="City", slug="fallback-city"))
        cls.category = city.add_child(
            instance=OrganizationType(title="Restaurants", slug="restaurants")
        )
        cls.first = cls.category.add_child(
            instance=Organization(title="First", slug="first")
        )
        cls.second = cls.category.add_child(
            instance=Organization(title="Second", slug="second")
        )
        cls.other = city.add_child(
            instance=OrganizationType(title="Hotels", slug="hotels")
        ).add_child(instance=Organization(title="Other", slug="other"))

    def setUp(self):
        self.media = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()
        cache.clear()
        collection = Collection.get_first_root_node().add_child(
            name="Карточки-заглушки"
        )
        image_model = get_image_model()
        self.placeholders = [
            image_model.objects.create(
                title=f"restaurants-{number}",
                description=f"Restaurant interior {number}",
                collection=collection,
                file=get_test_image_file(),
            )
            for number in (1, 2, 3)
        ]
        self.category_image = image_model.objects.create(
            title="Category cover",
            description="Restaurant tables",
            file=get_test_image_file(),
        )
        self.default_image = image_model.objects.create(
            title="Default cover",
            description="General cover",
            file=get_test_image_file(),
        )

    def tearDown(self):
        cache.clear()
        self.media_override.disable()
        self.media.cleanup()

    def test_variants_are_stable_and_shared_without_repeated_queries(self):
        request = RequestFactory().get("/")
        first = get_organization_fallback(self.first, self.default_image, request)
        self.assertEqual(first, self.placeholders[self.first.pk % 3])
        with self.assertNumQueries(0):
            second = get_organization_fallback(self.second, self.default_image, request)
            self.assertEqual(second, self.placeholders[self.second.pk % 3])

    def test_category_then_general_fallback_and_collection_scope(self):
        image_model = get_image_model()
        image_model.objects.create(
            title="hotels-1", description="Wrong collection", file=get_test_image_file()
        )
        self.other.get_parent().specific.image = self.category_image
        self.other.get_parent().specific.save()
        self.assertEqual(
            get_organization_fallback(self.other, self.default_image),
            self.category_image,
        )
        self.category_image.description = ""
        self.assertEqual(
            get_organization_fallback_alt(self.other, self.category_image),
            "Category cover",
        )
        self.other.get_parent().specific.image = None
        self.other.get_parent().specific.save()
        self.assertEqual(
            get_organization_fallback(self.other, self.default_image),
            self.default_image,
        )

    def test_own_photo_precedes_fallback_on_card_and_social_image(self):
        request = RequestFactory().get("/")
        fallback = self.placeholders[self.first.pk % 3]
        self.assertEqual(
            social_image(self.first, None, request, self.default_image), fallback
        )
        self.assertEqual(
            social_image_alt(self.first, fallback, request), fallback.description
        )

        OrganizationImage.objects.create(page=self.first, image=self.category_image)
        self.assertEqual(
            social_image(self.first, None, request, self.default_image),
            self.category_image,
        )
        self.assertEqual(
            social_image_alt(self.first, self.category_image, request),
            "Category cover",
        )
        html = render_to_string(
            "catalog/includes/organization-item.html",
            {"organization": self.first, "request": request},
        )
        self.assertIn("fill-720x405", html)
        self.assertIn("Restaurant tables", html)
        self.assertNotIn("Restaurant interior", html)

    def test_placeholder_card_uses_description_and_16_by_9_image(self):
        html = render_to_string(
            "catalog/includes/organization-item.html",
            {"organization": self.first, "request": RequestFactory().get("/")},
        )
        selected = self.placeholders[self.first.pk % 3]
        self.assertIn(f'alt="{selected.description}"', html)
        self.assertIn("fill-720x405", html)
        self.assertNotIn('alt="First"', html)

    def test_missing_placeholder_description_uses_category_title(self):
        selected = self.placeholders[self.first.pk % 3]
        selected.description = ""
        selected.save(update_fields=["description"])
        html = render_to_string(
            "catalog/includes/organization-item.html",
            {"organization": self.first, "request": RequestFactory().get("/")},
        )
        self.assertIn('alt="Restaurants"', html)
        self.assertNotIn(f'alt="{selected.title}"', html)

    def test_detail_gallery_and_open_graph_use_same_placeholder(self):
        request = RequestFactory().get("/")
        selected = self.placeholders[self.first.pk % 3]
        site_settings = SimpleNamespace(
            core=SimpleNamespace(
                SiteSettings=SimpleNamespace(
                    default_organization_image=self.default_image,
                    logo=self.default_image,
                )
            )
        )
        context = {
            "page": self.first,
            "request": request,
            "settings": site_settings,
            "canonical_url": "http://testserver/first/",
        }
        gallery = render_to_string(
            "catalog/includes/organization-images-template.html", context
        )
        metadata = render_to_string("includes/open_graph.html", context)
        self.assertIn(selected.description, gallery)
        self.assertIn("fill-720x405", gallery)
        self.assertIn(f'content="{selected.description}"', metadata)
        self.assertIn(selected.get_rendition("max-1200x630|format-jpeg").url, metadata)
        self.assertEqual(
            _get_org_images(self.first, request),
            [request.build_absolute_uri(selected.get_rendition("width-1200").url)],
        )
