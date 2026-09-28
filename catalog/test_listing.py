from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.http import Http404
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.utils.translation import override
from wagtail.models import Page, PageViewRestriction, Site

from catalog.listing import OrganizationListing, has_category_listing
from catalog.models import (
    City,
    Language,
    Organization,
    OrganizationType,
    ServiceType,
    ServiceTypeCategory,
)
from catalog.services import get_paginated_organizations_service
from subscription.models import PremiumSubscription


class OrganizationListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        cls.city = root.add_child(
            instance=City(title="Filter city", slug="filter-city")
        )
        Site.objects.update(root_page=cls.city, hostname="testserver", port=80)
        cls.category = cls.city.add_child(
            instance=OrganizationType(title="Restaurants", slug="restaurants")
        )
        cls.other = cls.city.add_child(
            instance=OrganizationType(title="Hotels", slug="hotels")
        )
        cls.language = Language.objects.create(language_name="English")
        cuisine = ServiceTypeCategory.objects.create(title="Cuisine")
        facilities = ServiceTypeCategory.objects.create(title="Facilities")
        cls.georgian = ServiceType.objects.create(
            name="Georgian", slug="georgian", category=cuisine
        )
        cls.italian = ServiceType.objects.create(
            name="Italian", slug="italian", category=cuisine
        )
        cls.terrace = ServiceType.objects.create(
            name="Terrace", slug="terrace", category=facilities
        )
        cls.outside = ServiceType.objects.create(
            name="Hotel only", slug="hotel-only", category=facilities
        )
        cls.alpha = cls.category.add_child(
            instance=Organization(
                title="Alpha",
                slug="alpha",
                address="Garden street 10",
                verified=True,
                avg_rating="4.80",
                rating_score="4.40",
                first_published_at=timezone.now() - timedelta(days=10),
            )
        )
        cls.beta = cls.category.add_child(
            instance=Organization(
                title="Beta",
                slug="beta",
                avg_rating="4.10",
                first_published_at=timezone.now(),
            )
        )
        cls.closed = cls.category.add_child(
            instance=Organization(
                title="Closed",
                slug="closed",
                avg_rating="5.00",
                temporarily_closed=True,
            )
        )
        cls.alpha.languages.add(cls.language)
        cls.alpha.service_types.add(cls.georgian, cls.italian, cls.terrace)
        cls.alpha.save()
        cls.beta.service_types.add(cls.italian)
        cls.beta.save()
        cls.hotel = cls.other.add_child(
            instance=Organization(title="Hotel", slug="hotel")
        )
        cls.hotel.service_types.add(cls.outside)
        cls.hotel.save()
        cls.category.add_child(
            instance=Organization(title="Draft", slug="draft", live=False)
        )
        cls.private = cls.category.add_child(
            instance=Organization(title="Private", slug="private")
        )
        PageViewRestriction.objects.create(
            page=cls.private, restriction_type="password", password="secret"
        )

    def listing(self, params=None):
        request = RequestFactory().get("/restaurants/", params or {})
        return OrganizationListing(self.category, request)

    def ids(self, params=None):
        return list(self.listing(params).queryset.values_list("pk", flat=True))

    def test_scope_and_available_options_exclude_private_draft_and_other_categories(
        self,
    ):
        listing = self.listing()
        self.assertEqual(listing.total, 3)
        self.assertEqual(set(self.ids()), {self.alpha.pk, self.beta.pk, self.closed.pk})
        choices = {
            option.id
            for group in listing.service_groups.values()
            for option in group.options
        }
        self.assertEqual(
            choices, {str(self.georgian.pk), str(self.italian.pk), str(self.terrace.pk)}
        )

    def test_name_and_address_search_is_case_insensitive_and_scoped(self):
        for value in ("alpha", "GARDEN", "  Alpha  "):
            self.assertEqual(self.ids({"q": value}), [self.alpha.pk])
        self.assertEqual(self.ids({"q": "Hotel"}), [])

    def test_combined_rating_language_verified_and_status(self):
        params = {
            "rating": "4.5",
            "language": self.language.pk,
            "verified": "on",
            "hide_closed": "on",
        }
        self.assertEqual(self.ids(params), [self.alpha.pk])
        self.assertEqual(
            set(self.ids({"rating": "4"})),
            {self.alpha.pk, self.beta.pk, self.closed.pk},
        )
        self.assertNotIn(self.closed.pk, self.ids({"hide_closed": "on"}))

    def test_services_use_or_within_group_and_and_between_groups_without_duplicates(
        self,
    ):
        selected = [str(self.georgian.pk), str(self.italian.pk)]
        self.assertEqual(
            set(self.ids({"service_type": selected})), {self.alpha.pk, self.beta.pk}
        )
        selected.append(str(self.terrace.pk))
        self.assertEqual(self.ids({"service_type": selected}), [self.alpha.pk])
        self.assertEqual(
            self.ids({"service_type": str(self.terrace.pk)}), [self.alpha.pk]
        )

    def test_counts_respect_search_while_total_remains_category_scoped(self):
        listing = self.listing({"q": "Alpha"})
        self.assertEqual((listing.count, listing.total), (1, 3))
        counts = {
            option.id: option.count
            for group in listing.service_groups.values()
            for option in group.options
        }
        self.assertEqual(counts[str(self.italian.pk)], 1)

    def test_invalid_filters_fail_closed_without_exceptions(self):
        for params in (
            {"service_type": "bad"},
            {"service_type": str(self.outside.pk)},
            {"service_type": "9" * 500},
            {"language": "unknown"},
            {"rating": "nan"},
            {"rating": "3"},
            {"sort": "-password"},
            {"service_match": "invalid"},
            {"q": "a" * 121},
        ):
            with self.subTest(params=params):
                listing = self.listing(params)
                self.assertTrue(listing.form.errors)
                self.assertEqual(listing.count, 0)
                self.assertEqual(list(listing.queryset), [])

    def test_explicit_sort_and_default_paid_priority(self):
        PremiumSubscription.objects.create(
            organization=self.beta,
            level=PremiumSubscription.Level.PREMIUM,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=2),
            is_active=True,
        )
        self.assertEqual(self.ids()[0], self.beta.pk)
        self.assertEqual(
            self.ids({"sort": "rating"}), [self.closed.pk, self.alpha.pk, self.beta.pk]
        )
        self.assertEqual(
            self.ids({"sort": "name"}), [self.alpha.pk, self.beta.pk, self.closed.pk]
        )
        self.assertEqual(self.ids({"sort": "newest"})[0], self.beta.pk)

    def test_equal_ratings_have_stable_order(self):
        Organization.objects.filter(pk__in=[self.alpha.pk, self.beta.pk]).update(
            avg_rating=4, rating_score=4
        )
        self.assertEqual(
            self.ids({"sort": "rating", "hide_closed": "on"}),
            sorted([self.alpha.pk, self.beta.pk]),
        )

    def test_active_link_removes_only_one_value_and_resets_page(self):
        listing = self.listing(
            {
                "service_type": [str(self.georgian.pk), str(self.italian.pk)],
                "sort": "rating",
                "page": "3",
            }
        )
        chip = next(
            chip for chip in listing.active_filters if chip.label == str(self.georgian)
        )
        params = parse_qs(urlsplit(chip.remove_url).query)
        self.assertEqual(
            params, {"service_type": [str(self.italian.pk)], "sort": ["rating"]}
        )

    def test_query_count_does_not_grow_with_number_of_groups_or_options(self):
        with self.assertNumQueries(8):
            listing = self.listing({"service_type": str(self.terrace.pk)})
            list(listing.queryset)

    def test_filtered_pagination_and_other_editorial_lists(self):
        request = RequestFactory().get("/restaurants/", {"sort": "name", "page": "2"})
        context = self.category.get_context(request)
        result = get_paginated_organizations_service(context, self.category, 1)
        self.assertEqual(list(result), [self.beta])
        self.assertEqual(result.paginator.count, 3)
        request.GET = request.GET.copy()
        request.GET.pop("page")
        self.assertEqual(
            list(get_paginated_organizations_service(context, self.other, 1)),
            [self.hotel],
        )
        self.assertEqual(
            list(get_paginated_organizations_service(context, None, 1)), [self.alpha]
        )

    def test_out_of_range_page_keeps_existing_404_contract(self):
        request = RequestFactory().get("/restaurants/", {"q": "Alpha", "page": "2"})
        with self.assertRaises(Http404):
            get_paginated_organizations_service(
                self.category.get_context(request), self.category
            )

    def test_existing_service_link_and_empty_state_render(self):
        response = self.client.get("/restaurants/", {"service_type": self.terrace.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="organization-{self.alpha.pk}"')
        self.assertNotContains(response, f'id="organization-{self.beta.pk}"')
        self.assertContains(response, 'name="robots" content="noindex, follow"')
        with override("en"):
            listing = self.listing({"q": "missing"})
            html = render_to_string(
                "catalog/includes/organization-filters.html",
                {"listing": listing, "request": RequestFactory().get("/restaurants/")},
            )
            self.assertIn("No matching places", html)

    def test_editorial_list_is_filtered_without_duplicating_fallback(self):
        self.category.content = [
            (
                "cards_section",
                {
                    "cards": [
                        (
                            "paginated_organizations",
                            {"page": self.category, "count": 1},
                        )
                    ],
                    "in_row": "4",
                },
            )
        ]
        self.category.save()
        self.assertTrue(has_category_listing(self.category))
        response = self.client.get("/restaurants/", {"q": "Alpha"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="organization-{self.alpha.pk}"', count=1)
        self.assertNotContains(response, f'id="organization-{self.beta.pk}"')

    def test_content_without_category_list_gets_fallback(self):
        self.category.content = [("text", "<p>Editorial introduction</p>")]
        self.category.save()
        self.assertFalse(has_category_listing(self.category))
        response = self.client.get("/restaurants/", {"q": "Alpha"})
        self.assertContains(response, "Editorial introduction")
        self.assertContains(response, f'id="organization-{self.alpha.pk}"', count=1)

    def test_filter_markup_escapes_search_and_has_no_page_input(self):
        request = RequestFactory().get(
            "/restaurants/", {"q": '<script>alert("x")</script>'}
        )
        html = render_to_string(
            "catalog/includes/organization-filters.html",
            {
                "listing": OrganizationListing(self.category, request),
                "request": request,
            },
        )
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertNotIn('name="page"', html)
        self.assertIn('method="get"', html)

    def test_service_accordion_retains_selections_across_exclusive_groups(self):
        from bs4 import BeautifulSoup

        request = RequestFactory().get(
            "/restaurants/",
            {"service_type": [str(self.georgian.pk), str(self.terrace.pk)]},
        )
        html = render_to_string(
            "catalog/includes/organization-filters.html",
            {
                "listing": OrganizationListing(self.category, request),
                "request": request,
            },
        )
        document = BeautifulSoup(html, "html.parser")
        groups = document.select(".organization-filters__group")
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            {group.get("name") for group in groups}, {"organization-service-group"}
        )
        self.assertLessEqual(
            len(document.select(".organization-filters__group[open]")), 1
        )
        self.assertEqual(
            {
                item["value"]
                for item in document.select('input[name="service_type"][checked]')
            },
            {str(self.georgian.pk), str(self.terrace.pk)},
        )
        self.assertEqual(
            [badge.text for badge in document.select("[data-group-count]")], ["1", "1"]
        )

    def test_entire_active_chip_is_a_named_remove_action(self):
        from bs4 import BeautifulSoup

        request = RequestFactory().get("/restaurants/", {"verified": "on", "page": "2"})
        with override("en"):
            html = render_to_string(
                "catalog/includes/organization-filters.html",
                {
                    "listing": OrganizationListing(self.category, request),
                    "request": request,
                },
            )
        document = BeautifulSoup(html, "html.parser")
        chip = document.select_one(".organization-filters__active a")
        self.assertIsNotNone(chip)
        self.assertEqual(chip["aria-label"], "Remove filter: Verified by Madloba")
        self.assertEqual(
            chip.select_one(".organization-filters__active-label").text,
            "Verified by Madloba",
        )
        self.assertEqual(chip.select_one(".organization-filters__remove").text, "×")
        self.assertNotIn("verified", parse_qs(urlsplit(chip["href"]).query))
        self.assertNotIn("page", parse_qs(urlsplit(chip["href"]).query))

    def test_disjoint_groups_have_zero_counts_and_remain_removable(self):
        from bs4 import BeautifulSoup

        dog_area = ServiceType.objects.create(
            name="Dog area", slug="dog-area", category=self.terrace.category
        )
        self.beta.service_types.add(dog_area)
        self.beta.save()
        params = {"service_type": [self.georgian.pk, dog_area.pk]}
        listing = self.listing(params)
        counts = {
            option.id: option.count
            for group in listing.service_groups.values()
            for option in group.options
        }
        self.assertEqual(listing.count, 0)
        self.assertEqual(counts[str(self.georgian.pk)], 0)
        self.assertEqual(counts[str(dog_area.pk)], 0)
        self.assertEqual(counts[str(self.italian.pk)], 1)
        self.assertEqual(counts[str(self.terrace.pk)], 1)
        response = self.client.get("/restaurants/", params)
        document = BeautifulSoup(response.content, "html.parser")
        selected = document.select('input[name="service_type"][checked]')
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(not item.has_attr("disabled") for item in selected))
        self.assertTrue(all("is-empty" in item.parent["class"] for item in selected))

        params["service_match"] = "any"
        self.assertEqual(set(self.ids(params)), {self.alpha.pk, self.beta.pk})
        counts = {
            option.id: option.count
            for group in self.listing(params).service_groups.values()
            for option in group.options
        }
        self.assertEqual(counts[str(self.georgian.pk)], 1)
        self.assertEqual(counts[str(dog_area.pk)], 1)

    def test_any_mode_keeps_general_filters_and_deduplicates_overlapping_features(self):
        selected = [self.georgian.pk, self.italian.pk, self.terrace.pk]
        params = {"service_match": "any", "service_type": selected}
        self.assertEqual(set(self.ids(params)), {self.alpha.pk, self.beta.pk})
        for general in (
            {"q": "Alpha"},
            {"rating": "4.5"},
            {"language": self.language.pk},
            {"verified": "on"},
        ):
            with self.subTest(general=general):
                listing = self.listing(params | general)
                self.assertEqual(
                    list(listing.queryset.values_list("pk", flat=True)), [self.alpha.pk]
                )
                self.assertEqual(
                    {
                        option.count
                        for group in listing.service_groups.values()
                        for option in group.options
                    },
                    {1},
                )
        self.assertEqual(self.listing({"service_match": "any"}).count, 3)

    def test_counts_exclude_their_own_group_but_include_every_other_selected_group(
        self,
    ):
        with self.assertNumQueries(8):
            listing = self.listing(
                {"service_type": [self.georgian.pk, self.terrace.pk]}
            )
            list(listing.queryset)
        counts = {
            option.id: option.count
            for group in listing.service_groups.values()
            for option in group.options
        }
        self.assertEqual(counts[str(self.italian.pk)], 1)
        listing = self.listing({"service_type": [self.georgian.pk]})
        counts = {
            option.id: option.count
            for group in listing.service_groups.values()
            for option in group.options
        }
        self.assertEqual(counts[str(self.italian.pk)], 2)
        self.assertEqual(counts[str(self.terrace.pk)], 1)

    def test_preview_endpoint_matches_listing_and_preserves_mode_in_remove_links(self):
        params = {
            "service_type": [self.georgian.pk, self.italian.pk, self.terrace.pk],
            "service_match": "any",
            "page": "9",
        }
        listing = self.listing(params)
        response = self.client.get("/restaurants/filter-counts/", params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json(),
            {
                "count": listing.count,
                "counts": {
                    option.id: option.count
                    for group in listing.service_groups.values()
                    for option in group.options
                },
                "valid": True,
            },
        )
        self.assertEqual(response.json()["count"], 2)
        for chip in listing.active_filters:
            query = parse_qs(urlsplit(chip.remove_url).query)
            self.assertEqual(query["service_match"], ["any"])
            self.assertNotIn("page", query)

    def test_preview_rejects_invalid_and_out_of_scope_filters(self):
        for params in (
            {"service_match": "wrong"},
            {"service_type": self.outside.pk},
            {"q": "a" * 121},
        ):
            response = self.client.get("/restaurants/filter-counts/", params)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()["valid"])
            self.assertEqual(response.json()["count"], 0)
            self.assertTrue(
                all(count == 0 for count in response.json()["counts"].values())
            )

    def test_preview_respects_category_access_restrictions(self):
        PageViewRestriction.objects.create(
            page=self.category, restriction_type="password", password="secret"
        )
        response = self.client.get("/restaurants/filter-counts/")
        self.assertNotEqual(response.get("Content-Type"), "application/json")

    def test_preview_does_not_expose_draft_category(self):
        self.category.live = False
        self.category.save()
        response = self.client.get("/restaurants/filter-counts/")
        self.assertEqual(response.status_code, 404)
