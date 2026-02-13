from django.utils.html import escapejs

from core.jsonld import build_jsonld

from .models import BlogCategoryPage, BlogIndexPage, BlogPostPage


@build_jsonld.register  # type: ignore
def _(page: BlogIndexPage, request):
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": escapejs(page.title),
        "description": escapejs(page.search_description),
        "url": page.full_url,
    }

    return data


@build_jsonld.register  # type: ignore
def _(page: BlogCategoryPage, request):
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": escapejs(page.title),
        "description": escapejs(page.search_description),
        "url": page.full_url,
    }

    return data


@build_jsonld.register  # type: ignore
def _(page: BlogPostPage, request):
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": escapejs(page.title),
        "description": escapejs(page.search_description),
        "url": page.full_url,
    }

    return data
