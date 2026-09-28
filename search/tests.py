from __future__ import annotations

from django.core.paginator import Page as PaginatorPage
from django.db import connection
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext, override
from wagtail.contrib.search_promotions.models import Query
from wagtail.images import get_image_model
from wagtail.models import Page
from wagtail.search.backends import get_search_backend

from catalog.models import Organization, OrganizationImage
from search.views import search


class SearchOrderingTests(TestCase):
    query = "Searchclosurefixture"
    open_pages: list[Organization]
    closed_pages: list[Organization]
    other_page: Page
    draft_pk: int

    @classmethod
    def setUpTestData(cls) -> None:
        root = Page.get_first_root_node()
        assert root is not None
        backend = get_search_backend()
        cls.open_pages = []
        for number in range(11):
            organization = Organization(
                title=f"{cls.query} open business number {number}",
                slug=f"search-open-{number}",
            )
            root.add_child(instance=organization)
            backend.add(organization)
            cls.open_pages.append(organization)

        cls.other_page = Page(title=f"{cls.query} visitor guide", slug="search-guide")
        root.add_child(instance=cls.other_page)
        backend.add(cls.other_page)

        cls.closed_pages = []
        for number, title in enumerate(
            (cls.query, f"{cls.query} Closedonlyfixture cafe")
        ):
            organization = Organization(
                title=title,
                slug=f"search-closed-{number}",
                temporarily_closed=True,
            )
            root.add_child(instance=organization)
            backend.add(organization)
            cls.closed_pages.append(organization)

        draft = Organization(title=cls.query, slug="search-unpublished", live=False)
        root.add_child(instance=draft)
        backend.add(draft)
        cls.draft_pk = draft.pk

    def results(
        self, *, query: str | None = query, page: str | None = None
    ) -> PaginatorPage:
        params = {}
        if page is not None:
            params["page"] = page
        if query is not None:
            params["query"] = query
        response = search(RequestFactory().get("/search/", params))
        assert response.context_data is not None
        return response.context_data["search_results"]

    def all_result_ids(self) -> list[int]:
        first_page = self.results()
        return [
            result.pk
            for number in first_page.paginator.page_range
            for result in first_page.paginator.page(number)
        ]

    def test_closed_results_follow_all_other_pages_before_pagination(self) -> None:
        original_results = list(Page.objects.live().search(self.query))
        self.assertEqual(original_results[0].pk, self.closed_pages[0].pk)
        closed_ids = {page.pk for page in self.closed_pages}
        expected_ids = [
            page.pk for page in original_results if page.pk not in closed_ids
        ]
        expected_ids += [page.pk for page in original_results if page.pk in closed_ids]

        actual_ids = self.all_result_ids()

        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(len(actual_ids), 14)
        self.assertEqual(len(set(actual_ids)), 14)
        self.assertIn(self.other_page.pk, actual_ids[:-2])
        self.assertNotIn(self.draft_pk, actual_ids)
        self.assertEqual(len(self.results()), 10)
        self.assertEqual(len(self.results(page="2")), 4)

    def test_status_changes_take_effect_without_reindexing(self) -> None:
        reopened = self.closed_pages[0]
        newly_closed = self.open_pages[0]
        Organization.objects.filter(pk=reopened.pk).update(temporarily_closed=False)
        Organization.objects.filter(pk=newly_closed.pk).update(temporarily_closed=True)

        result_ids = self.all_result_ids()

        self.assertEqual(result_ids[0], reopened.pk)
        self.assertEqual(
            set(result_ids[-2:]), {newly_closed.pk, self.closed_pages[1].pk}
        )

    def test_search_can_return_only_closed_organizations(self) -> None:
        self.assertEqual(
            [page.pk for page in self.results(query="Closedonlyfixture")],
            [self.closed_pages[1].pk],
        )

    def test_search_without_closed_organizations_preserves_relevance(self) -> None:
        Organization.objects.filter(
            pk__in=[page.pk for page in self.closed_pages]
        ).update(temporarily_closed=False)
        self.assertEqual(
            self.all_result_ids(),
            [page.pk for page in Page.objects.live().search(self.query)],
        )

    def test_missing_or_empty_query_returns_no_results_and_logs_no_hit(self) -> None:
        for query in (None, "", "   ", "\t\n"):
            with self.subTest(query=query):
                with CaptureQueriesContext(connection) as captured:
                    self.assertEqual(list(self.results(query=query)), [])
                self.assertEqual(len(captured), 0)

    def test_unmatched_query_returns_an_empty_first_page(self) -> None:
        results = self.results(query="Unmatchedsearchfixture")
        self.assertEqual(list(results), [])
        self.assertEqual(results.number, 1)

    def test_invalid_or_out_of_range_page_raises_404(self) -> None:
        for page in ("invalid", "", "0", "-1", "999", "1.5"):
            with self.subTest(page=page), self.assertRaises(Http404):
                self.results(page=page)

    def test_result_rendering_reuses_loaded_page_data(self) -> None:
        results = self.results()
        with CaptureQueriesContext(connection) as captured:
            self.assertEqual(len(list(results)), 10)
        self.assertEqual(len(captured), 0)

    def test_nonempty_query_still_records_one_hit(self) -> None:
        self.results()
        self.assertEqual(Query.get(self.query).hits, 1)

    def test_query_whitespace_is_trimmed(self) -> None:
        self.assertEqual(
            [page.pk for page in self.results(query=f"  {self.query}  ")],
            [page.pk for page in self.results()],
        )

    def test_gallery_fetch_loads_only_first_image_for_each_visible_organization(
        self,
    ) -> None:
        image_model = get_image_model()
        image = image_model(
            title="Search fixture image", file="search-fixture.png", width=1, height=1
        )
        image_model.objects.bulk_create([image])
        first_ids: dict[int, int] = {}
        for organization in self.open_pages:
            OrganizationImage._default_manager.create(
                page=organization, image=image, sort_order=2
            )
            first = OrganizationImage._default_manager.create(
                page=organization, image=image, sort_order=1
            )
            first_ids[organization.pk] = first.pk

        with CaptureQueriesContext(connection) as captured:
            results = self.results()
        gallery_queries = [
            query
            for query in captured.captured_queries
            if 'FROM "catalog_organizationimage"' in query["sql"]
        ]
        self.assertEqual(len(gallery_queries), 1)
        for result in results:
            if isinstance(result, Organization):
                with CaptureQueriesContext(connection) as related_queries:
                    images = getattr(result, "search_images")
                    self.assertEqual(
                        [item.pk for item in images], [first_ids[result.pk]]
                    )
                    self.assertEqual(images[0].image.title, image.title)
                self.assertEqual(len(related_queries), 0)

    def test_search_page_localizes_heading_form_and_result_count(self) -> None:
        for language in ("ru", "ka", "en"):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("search"), {"query": self.query})
                self.assertContains(response, gettext("Search"))
                self.assertContains(
                    response,
                    f'<mark class="search-page__query">«{self.query}»</mark>',
                    html=True,
                )
                self.assertContains(response, gettext("Results found:"))
                self.assertContains(response, "<strong>14</strong>", html=True)
                self.assertContains(
                    response,
                    gettext("Showing %(start)s–%(end)s") % {"start": 1, "end": 10},
                )
                self.assertContains(response, 'id="search-page-query"')
                self.assertNotContains(response, 'method="get" hidden')

    def test_search_query_is_escaped_in_title_heading_and_input(self) -> None:
        query = '<img src=x onerror="alert(1)">'
        response = self.client.get(reverse("search"), {"query": query})
        self.assertContains(response, escape(query))
        self.assertNotContains(response, query)
        self.assertNotContains(response, "<img src=x")

    def test_empty_and_unmatched_searches_show_distinct_help(self) -> None:
        with override("ru"):
            empty = self.client.get(reverse("search"))
            self.assertContains(empty, gettext("What would you like to find?"))
            self.assertNotContains(empty, gettext("No results found"))
            unmatched = self.client.get(
                reverse("search"), {"query": "Unmatchedsearchfixture"}
            )
            self.assertContains(unmatched, gettext("No results found"))
            self.assertContains(
                unmatched,
                gettext("Check the spelling or try fewer, more general words."),
            )

    def test_closed_result_card_has_visible_status(self) -> None:
        with override("ru"):
            response = self.client.get(
                reverse("search"), {"query": "Closedonlyfixture"}
            )
            self.assertContains(response, 'class="search-item__status"')
            self.assertContains(response, gettext("Temporarily closed"))
