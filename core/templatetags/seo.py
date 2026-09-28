"""Metadata derived from the same content and images shown on public pages."""

import json
from html import unescape

from django import template
from django.http import HttpRequest
from django.utils.html import strip_tags
from django.utils.safestring import SafeString
from wagtail.blocks import StructValue
from wagtail.images.models import Image
from wagtail.models import Page

from blog.models import BlogPostPage

register = template.Library()


@register.simple_tag
def faq_jsonld(value: StructValue, page_url: str = "") -> str:
    """Describe rendered Q&A items; omit incomplete items and escape script delimiters.

    Blocks on the same page share an identity so their questions describe one
    FAQPage. Rich-text answers are expanded just as in the visible accordion.
    """
    questions: list[dict[str, object]] = []
    for item in value["items"]:
        question = str(item.value["question"]).strip()
        answer = str(item.value["answer"])
        if not question or not unescape(strip_tags(answer)).strip():
            continue
        questions.append(
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )
    if not questions:
        return ""
    data: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": questions,
    }
    if page_url:
        data["@id"] = f"{page_url}#faq"
    # JSON escaping alone does not prevent </script> from closing an HTML element.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.translate(
        str.maketrans({"<": r"\u003C", ">": r"\u003E", "&": r"\u0026"})
    )
    return SafeString(f'<script type="application/ld+json">{payload}</script>')


@register.simple_tag
def social_image(page: Page, fallback: Image | None = None) -> Image | None:
    """Choose a raster page image or logo that can produce a JPEG preview.

    Wagtail/Willow cannot rasterize SVGs. Skip them and omit the preview image
    when no raster candidate exists, without changing the site's visible logo.
    """
    candidates: tuple[Image | None, ...] = (
        getattr(page, "get_image", None),
        getattr(page, "image", None),
        fallback,
    )
    for candidate in candidates:
        if isinstance(candidate, Image) and not candidate.is_svg():
            return candidate
    return None


@register.simple_tag
def absolute_media_url(request: HttpRequest, url: str) -> str:
    """Resolve local media URLs while preserving absolute CDN URLs."""
    return request.build_absolute_uri(url) if url else ""


@register.filter
def social_type(page: Page) -> str:
    """Identify blog articles for Open Graph consumers."""
    return "article" if isinstance(page, BlogPostPage) else "website"
