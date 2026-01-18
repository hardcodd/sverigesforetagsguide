from django.apps import apps
from wagtail.models import Page

from authors.models import AuthorPage
from core.utils import paginate


def get_paginated_authors_service(context, count=16):
    qs = AuthorPage.objects.live()
    return paginate(context.get("request"), qs, count)


def get_total_publications_by_author_service(author):
    total = 0
    for model in apps.get_models():
        if issubclass(model, Page) and hasattr(model, "author"):
            total += model.objects.live().filter(author=author).count()
    return total
