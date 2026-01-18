from core.utils import paginate
from ratings.models import RatingCategoryPage, RatingPage, RatingsIndexPage


def get_ratings_index_page_service(context):
    page = context.get("page")
    return RatingsIndexPage.objects.live().ancestor_of(page, inclusive=True).first()


def _build_tree(pages, parent):
    tree = []

    for page in pages:
        page.children = []

        if page.is_child_of(parent):
            tree.append(page)

        children = page.get_children().type(RatingCategoryPage)
        if children:
            page.children = _build_tree(children, page)

    return tree


def get_ratings_categories_list_service(context):
    ratings_index_page = get_ratings_index_page_service(context)
    categories = RatingCategoryPage.objects.live().descendant_of(ratings_index_page)

    return _build_tree(categories, ratings_index_page)


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
