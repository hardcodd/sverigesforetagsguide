import math
from datetime import timedelta
from types import SimpleNamespace

from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.translation import override
from wagtail.models import Page, PageViewRestriction, Site

from catalog.models import (
    City,
    Organization,
    OrganizationType,
    ServiceType,
    ServiceTypeCategory,
)
from catalog.nearby import (
    EARTH_RADIUS_M,
    NearbyOrganization,
    get_nearby_batch,
    get_nearby_organizations,
    parse_coordinates,
)
from subscription.models import PremiumSubscription


class CoordinateTests(SimpleTestCase):
    def test_valid_coordinates(self):
        for value, expected in (
            ("41.7,44.8", (41.7, 44.8)),
            (" -90, +180 ", (-90, 180)),
            ("0,0", (0, 0)),
            (".5, -.5", (0.5, -0.5)),
        ):
            with self.subTest(value=value):
                self.assertEqual(parse_coordinates(value), expected)

    def test_invalid_coordinates(self):
        for value in (
            "",
            " ",
            "41",
            "41,44,45",
            "NaN,44",
            "inf,0",
            "91,44",
            "41,181",
            "1e300,0",
            "1;2",
            "x,44",
            "0," + "9" * 100,
        ):
            with self.subTest(value=value):
                self.assertIsNone(parse_coordinates(value))

    def test_distance_labels(self):
        with override("en"):
            for distance, label in (
                (0, "Less than 50 m"),
                (49, "Less than 50 m"),
                (120, "About 100 m"),
                (999, "About 1000 m"),
                (1250, "About 1.2 km"),
            ):
                self.assertEqual(
                    NearbyOrganization(Organization(), distance).distance_label, label
                )


class NearbyOrganizationTests(TestCase):
    def setUp(self):
        self.enterContext(override("ru"))

    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        cls.city = root.add_child(
            instance=City(title="Nearby city", slug="nearby-city")
        )
        Site.objects.create(hostname="nearby.test", root_page=cls.city)
        cls.category = cls.city.add_child(
            instance=OrganizationType(title="Restaurants", slug="restaurants")
        )
        cls.other_category = cls.city.add_child(
            instance=OrganizationType(title="Hotels", slug="hotels")
        )
        cls.source = cls.category.add_child(
            instance=Organization(title="Source", slug="source", ll="41.7,44.8")
        )
        service_category = ServiceTypeCategory.objects.create(title="Cuisine")
        cls.service = ServiceType.objects.create(
            name="Georgian", slug="georgian", category=service_category
        )
        cls.source.service_types.add(cls.service)
        cls.source.save()

    def add_peer(self, slug, distance=100, parent=None, **kwargs):
        latitude = 41.7 + math.degrees(distance / EARTH_RADIUS_M)
        values = {"title": slug, "slug": slug, "ll": f"{latitude:.14f},44.8"} | kwargs
        return (parent or self.category).add_child(instance=Organization(**values))

    def ids(self):
        return [item.organization.pk for item in get_nearby_organizations(self.source)]

    def test_distance_limit_and_category(self):
        near = self.add_peer("near", 80)
        edge = self.add_peer("edge", 4999)
        self.add_peer("outside", 5001)
        self.add_peer("unrelated", 1, parent=self.other_category)
        result = get_nearby_organizations(self.source)
        self.assertEqual([item.organization.pk for item in result], [near.pk, edge.pk])
        self.assertAlmostEqual(result[0].distance_m, 80, places=4)

    def test_services_rank_only_within_nearby_distance_band(self):
        closest = self.add_peer("closest", 260)
        matched = self.add_peer("matched", 400)
        matched.service_types.add(self.service)
        matched.save()
        farther = self.add_peer("farther", 510)
        farther.service_types.add(self.service)
        farther.save()
        self.assertEqual(self.ids(), [matched.pk, closest.pk, farther.pk])

    def test_limit_and_stable_distance_order(self):
        peers = [self.add_peer(f"peer-{index}", 100 + index * 10) for index in range(8)]
        self.assertEqual(self.ids(), [peer.pk for peer in peers[:6]])
        self.assertEqual(self.ids(), [peer.pk for peer in peers[:6]])

    def test_same_coordinates_are_valid_for_distinct_businesses(self):
        peer = self.add_peer("same-building", ll=self.source.ll)
        result = get_nearby_organizations(self.source)
        self.assertEqual([item.organization.pk for item in result], [peer.pk])
        self.assertAlmostEqual(result[0].distance_m, 0)

    def test_invalid_imported_coordinates_never_break_query(self):
        valid = self.add_peer("valid")
        for index, value in enumerate(
            (
                "",
                "broken",
                "NaN,44",
                "41,inf",
                "41,181",
                "91,44",
                "41,44,45",
                "1e300,0",
                "41," + "9" * 100,
            )
        ):
            self.add_peer(f"invalid-{index}", ll=value)
        self.assertEqual(self.ids(), [valid.pk])

    def test_unpublished_private_closed_and_hidden_map_candidates(self):
        valid = self.add_peer("valid")
        self.add_peer("draft", live=False)
        self.add_peer("closed", temporarily_closed=True)
        self.add_peer("hidden-map", show_on_map=False)
        private = self.add_peer("private")
        PageViewRestriction.objects.create(page=private, restriction_type="login")
        self.assertEqual(self.ids(), [valid.pk])
        PageViewRestriction.objects.create(page=self.category, restriction_type="login")
        self.assertEqual(self.ids(), [])

    def test_changes_are_visible_without_cache_expiry(self):
        peer = self.add_peer("peer")
        self.assertEqual(self.ids(), [peer.pk])
        Organization.objects.filter(pk=peer.pk).update(ll="0,0")
        self.assertEqual(self.ids(), [])
        Organization.objects.filter(pk=peer.pk).update(ll=self.source.ll, live=False)
        self.assertEqual(self.ids(), [])

    def test_missing_or_hidden_source_coordinates_skip_database(self):
        for value in ("", "bad", "91,0"):
            self.source.ll = value
            with self.assertNumQueries(0):
                self.assertEqual(self.ids(), [])
        self.source.ll = "41.7,44.8"
        self.source.show_on_map = False
        with self.assertNumQueries(0):
            self.assertEqual(self.ids(), [])

    def test_all_active_paid_levels_hide_nearby(self):
        self.add_peer("peer")
        today = timezone.localdate()
        for level in (1, 2, 3):
            subscription = PremiumSubscription.objects.create(
                organization=self.source,
                level=level,
                start_date=today,
                end_date=today,
                is_active=True,
            )
            with self.assertNumQueries(1):
                self.assertEqual(self.ids(), [])
            subscription.delete()

    def test_inactive_expired_future_free_subscriptions_allow_nearby(self):
        peer = self.add_peer("peer")
        today = timezone.localdate()
        for changes in (
            {"is_active": False},
            {"end_date": today - timedelta(days=1)},
            {"start_date": today + timedelta(days=1)},
            {"level": 0},
        ):
            values = (
                dict(
                    organization=self.source,
                    level=3,
                    start_date=today,
                    end_date=today,
                    is_active=True,
                )
                | changes
            )
            subscription = PremiumSubscription.objects.create(**values)
            self.assertEqual(self.ids(), [peer.pk])
            subscription.delete()

    def test_query_count_is_bounded_and_ranking_is_limited_in_sql(self):
        for index in range(8):
            self.add_peer(f"peer-{index}", 100 + index)
        with CaptureQueriesContext(connection) as queries:
            result = get_nearby_organizations(self.source)
            for item in result:
                list(item.organization.images.all())
        self.assertEqual(len(queries), 5)
        self.assertTrue(any("LIMIT 7" in query["sql"] for query in queries))
        self.assertTrue(
            all("qna" in item.organization.get_deferred_fields() for item in result)
        )

    def test_context_includes_nearby(self):
        peer = self.add_peer("peer")
        context = self.source.get_context(RequestFactory().get("/"))
        self.assertEqual(
            [item.organization.pk for item in context["nearby_organizations"]],
            [peer.pk],
        )

    def test_rendering_localization_escaping_and_empty_state(self):
        peer = self.add_peer("peer", title='<script>alert("x")</script>')
        template = "catalog/includes/nearby-organizations.html"
        self.assertNotIn(
            "<section", render_to_string(template, {"nearby_organizations": []})
        )
        context = {
            "nearby_organizations": get_nearby_organizations(self.source),
            "settings": SimpleNamespace(
                core=SimpleNamespace(
                    SiteSettings=SimpleNamespace(default_organization_image=None)
                )
            ),
        }
        for language, title in (
            ("en", "Similar places nearby"),
            ("ru", "Похожие организации рядом"),
            ("ka", "მსგავსი ორგანიზაციები ახლომახლო"),
        ):
            with override(language):
                html = render_to_string(template, context)
                self.assertIn(title, html)
                self.assertIn("&lt;script&gt;", html)
                self.assertNotIn("<script>", html)
                self.assertIn(peer.url, html)

    def test_antimeridian_and_poles(self):
        self.source.ll = "0,179.99"
        peer = self.add_peer("across-date-line", ll="0,-179.99")
        self.assertEqual(self.ids(), [peer.pk])
        self.source.ll = "89.99,0"
        Organization.objects.filter(pk=peer.pk).update(ll="89.99,180")
        self.assertEqual(self.ids(), [peer.pk])

    def test_load_more_returns_six_then_remaining_without_duplicates(self):
        from bs4 import BeautifulSoup

        peers = [
            self.add_peer(f"page-peer-{index}", 100 + index) for index in range(14)
        ]
        first = get_nearby_batch(self.source)
        self.assertEqual(
            [item.organization.pk for item in first.items],
            [peer.pk for peer in peers[:6]],
        )
        second = self.client.get(first.next_url)
        self.assertEqual(second.status_code, 200)
        payload = second.json()
        links = BeautifulSoup(payload["html"], "html.parser").select(
            "a.nearby-organizations__card"
        )
        self.assertEqual(
            [link["href"] for link in links], [peer.url for peer in peers[6:12]]
        )
        last = self.client.get(payload["next_url"]).json()
        links = BeautifulSoup(last["html"], "html.parser").select(
            "a.nearby-organizations__card"
        )
        self.assertEqual(
            [link["href"] for link in links], [peer.url for peer in peers[12:]]
        )
        self.assertIsNone(last["next_url"])
        self.assertIn("no-store", second.headers["Cache-Control"])

    def test_exact_batch_size_has_no_more_button(self):
        for index in range(6):
            self.add_peer(f"peer-{index}")
        batch = get_nearby_batch(self.source)
        self.assertEqual(len(batch.items), 6)
        self.assertIsNone(batch.next_url)
        context = self.source.get_context(RequestFactory().get("/"))
        html = render_to_string("catalog/includes/nearby-organizations.html", context)
        self.assertNotIn("nearby-organizations__load-more", html)

    def test_removing_previous_result_does_not_skip_next_result(self):
        from bs4 import BeautifulSoup

        peers = [self.add_peer(f"peer-{index}", 100 + index) for index in range(8)]
        batch = get_nearby_batch(self.source)
        Organization.objects.filter(pk=peers[0].pk).update(live=False)
        html = self.client.get(batch.next_url).json()["html"]
        links = BeautifulSoup(html, "html.parser").select(
            "a.nearby-organizations__card"
        )
        self.assertEqual(
            [link["href"] for link in links], [peer.url for peer in peers[6:]]
        )

    def test_pagination_handles_equal_rank_keys(self):
        peers = [self.add_peer(f"equal-{index}", 100) for index in range(8)]
        first = get_nearby_batch(self.source)
        second = self.client.get(first.next_url).json()
        for peer in peers[:6]:
            self.assertNotIn(f'href="{peer.url}"', second["html"])
        for peer in peers[6:]:
            self.assertIn(f'href="{peer.url}"', second["html"])

    def test_load_more_rechecks_subscription_and_visibility(self):
        for index in range(8):
            self.add_peer(f"peer-{index}")
        batch = get_nearby_batch(self.source)
        today = timezone.localdate()
        subscription = PremiumSubscription.objects.create(
            organization=self.source,
            level=1,
            start_date=today,
            end_date=today,
            is_active=True,
        )
        payload = self.client.get(batch.next_url).json()
        self.assertNotIn("nearby-organizations__card", payload["html"])
        self.assertIsNone(payload["next_url"])
        subscription.delete()
        Organization.objects.filter(pk=self.source.pk).update(live=False)
        self.assertEqual(self.client.get(batch.next_url).status_code, 404)
        Organization.objects.filter(pk=self.source.pk).update(live=True)
        PageViewRestriction.objects.create(page=self.category, restriction_type="login")
        self.assertEqual(self.client.get(batch.next_url).status_code, 404)

    def test_load_more_rejects_missing_tampered_foreign_and_expired_cursors(self):
        import time
        from unittest.mock import patch
        from django.urls import reverse
        from catalog.nearby import CURSOR_MAX_AGE

        for index in range(8):
            self.add_peer(f"peer-{index}")
        url = reverse("catalog:nearby_organizations", args=[self.source.pk])
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, {"cursor": "invalid"}).status_code, 400)
        batch = get_nearby_batch(self.source)
        self.assertEqual(self.client.get(batch.next_url + "tampered").status_code, 400)
        other = self.add_peer("other-source")
        foreign_url = batch.next_url.replace(f"/{self.source.pk}/", f"/{other.pk}/")
        self.assertEqual(self.client.get(foreign_url).status_code, 400)
        with patch(
            "django.core.signing.time.time",
            return_value=time.time() + CURSOR_MAX_AGE + 1,
        ):
            self.assertEqual(self.client.get(batch.next_url).status_code, 400)
        self.assertEqual(self.client.post(batch.next_url).status_code, 405)

    def test_load_more_uses_requested_language_and_escapes_content(self):
        for index in range(7):
            self.add_peer(f"peer-{index}", 100 + index, title="<script>unsafe</script>")
        with override("en"):
            batch = get_nearby_batch(self.source)
            self.assertTrue(batch.next_url.startswith("/en/"))
        payload = self.client.get(batch.next_url).json()
        self.assertIn("About", payload["html"])
        self.assertIn("&lt;script&gt;", payload["html"])
        self.assertNotIn("<script>", payload["html"])
        self.assertIn("/en/", payload["html"])

    def test_continuation_preserves_service_priority_before_distance(self):
        plain = [self.add_peer(f"plain-{index}", 100 + index) for index in range(3)]
        for index in range(6):
            matched = self.add_peer(f"matched-{index}", 150 + index)
            matched.service_types.add(self.service)
            matched.save()
        first = get_nearby_batch(self.source)
        self.assertTrue(
            all(item.organization.title.startswith("matched-") for item in first.items)
        )
        second = self.client.get(first.next_url).json()
        for peer in plain:
            self.assertIn(f'href="{peer.url}"', second["html"])
        self.assertIsNone(second["next_url"])
