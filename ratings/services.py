from collections.abc import Mapping

from django.template import Context

from core.page_tree import PageTreeNode, build_page_tree
from core.utils import paginate
from ratings.models import RatingCategoryPage, RatingPage, RatingsIndexPage


def get_ratings_index_page_service(context):
    page = context.get("page")
    return RatingsIndexPage.objects.live().ancestor_of(page, inclusive=True).first()


def get_ratings_categories_list_service(
    context: Context | Mapping[str, object],
) -> list[PageTreeNode]:
    """Build rating navigation without recursively querying every category."""
    ratings_index_page = get_ratings_index_page_service(context)
    if ratings_index_page is None:
        return []
    categories = RatingCategoryPage.objects.live().descendant_of(ratings_index_page)
    return build_page_tree(categories, ratings_index_page)


def get_paginated_ratings_posts_service(context, parent, count=16):
    request = context.get("request")
    qs = RatingPage.objects.live().order_by("-first_published_at")
    if parent:
        qs = qs.descendant_of(parent)

    filters = {}

    author = request.GET.get("author")
    if author:
        filters["author__slug"] = author

    qs = qs.filter(**filters)

    return paginate(request, qs, count)
