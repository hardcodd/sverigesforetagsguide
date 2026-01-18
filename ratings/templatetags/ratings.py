from django import template

from ratings.services import (get_paginated_ratings_posts_service, get_ratings_categories_list_service,
                              get_ratings_index_page_service)

register = template.Library()


@register.simple_tag
def get_average_rating(page):
    total = sum(block.value["rating"] for block in page.ratings)
    count = len(page.ratings)
    if count == 0:
        return 0
    average = total / count
    scaled_average = (average / 10) * 5
    return scaled_average


@register.simple_tag(takes_context=True)
def get_ratings_index_page(context):
    return get_ratings_index_page_service(context)


@register.simple_tag(takes_context=True)
def get_ratings_categories_list(context):
    return get_ratings_categories_list_service(context)


@register.simple_tag(takes_context=True)
def get_paginated_ratings_posts(context, parent, count=16):
    return get_paginated_ratings_posts_service(context, parent, count)
