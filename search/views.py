from django.db.models import Exists, OuterRef, Prefetch, prefetch_related_objects
from django.http import HttpRequest
from django.template.response import TemplateResponse
from wagtail.contrib.search_promotions.models import Query
from wagtail.models import Page

from catalog.models import Organization, OrganizationImage
from core.pagination import paginate


def search(request: HttpRequest) -> TemplateResponse:
    """Search live pages, placing closed organizations last before pagination."""
    raw_query = request.GET.get("query")
    search_query = raw_query.strip() if isinstance(raw_query, str) else ""

    # Search
    if search_query:
        closed_organizations = Organization.objects.filter(
            pk=OuterRef("pk"), temporarily_closed=True
        )
        # The configured PostgreSQL search backend exposes a lazy queryset.
        # Keep its relevance score and tie-breaker within each status group.
        search_results = (
            Page.objects.live()
            .defer_streamfields()
            .search(search_query)
            .annotate_score("search_score")
            .get_queryset()
            .alias(search_closed=Exists(closed_organizations))
            .order_by("search_closed", "-search_score", "-pk")
            .specific()
        )

        query = Query.get(search_query)
        query.add_hit()

    else:
        search_results = Page.objects.none().specific()

    # Pagination
    search_page = paginate(request, search_results, 10)

    # Fetch specific models and just the first gallery image for this page.
    # Batch loading avoids one model/image query per result during rendering.
    result_pages: list[Page] = list(search_page.object_list)
    organizations: list[Organization] = [
        result for result in result_pages if isinstance(result, Organization)
    ]
    prefetch_related_objects(
        organizations,
        Prefetch(
            "images",
            queryset=OrganizationImage._default_manager.select_related("image")
            .prefetch_related("image__renditions")
            .order_by("page_id", "sort_order", "pk")
            .distinct("page_id"),
            to_attr="search_images",
        ),
    )
    search_page.object_list = result_pages

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_page,
        },
    )
