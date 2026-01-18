from django import template

from authors.models import AuthorPage
from authors.services import get_paginated_authors_service, get_total_publications_by_author_service

register = template.Library()


@register.simple_tag(takes_context=True)
def get_paginated_authors(context, count=16):
    return get_paginated_authors_service(context, count)


@register.simple_tag
def get_author_by_slug(author_slug):
    try:
        return AuthorPage.objects.get(slug=author_slug)
    except AuthorPage.DoesNotExist:
        return None


@register.simple_tag
def get_total_publications_by_author(author):
    return get_total_publications_by_author_service(author)
