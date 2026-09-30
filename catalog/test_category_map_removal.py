from django.test import TestCase
from wagtail.models import Site

from catalog.models import City, Organization, OrganizationType


class CategoryMapRemovalTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        root = Site.objects.get(is_default_site=True).root_page
        city = root.add_child(instance=City(title="Map City", slug="map-city"))
        category = city.add_child(
            instance=OrganizationType(title="Restaurants", slug="restaurants")
        )
        category.add_child(
            instance=Organization(
                title="Restaurant",
                slug="restaurant",
                h1_title="Restaurant",
                ll="41.7,44.8",
                show_on_map=True,
            )
        )

    def test_category_page_exists_but_category_map_route_is_gone(self) -> None:
        self.assertEqual(self.client.get("/map-city/restaurants/").status_code, 200)
        self.assertEqual(self.client.get("/map-city/restaurants/map/").status_code, 410)

    def test_organization_keeps_its_location_map_without_category_map_link(
        self,
    ) -> None:
        response = self.client.get("/map-city/restaurants/restaurant/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="org-map-wrapper"')
        self.assertNotContains(response, 'href="/map-city/restaurants/map/"')
