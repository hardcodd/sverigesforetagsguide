import os

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from wagtail.models import Site
from wagtail.snippets.views.snippets import SnippetViewSet

from core.models import Footer, RobotsTxtSettings


class FooterViewSet(SnippetViewSet):
    model = Footer
    icon = "bars"  # type: ignore
    list_display = ["__str__"]  # type: ignore


def robots_txt(request):
    site = Site.find_for_request(request)
    settings = RobotsTxtSettings.for_site(site)
    return HttpResponse(settings.content or "", content_type="text/plain")


SITEMAP_ROOT = os.path.join(settings.BASE_DIR, "app", "templates", "sitemaps")


def sitemap_index(request):
    """
    Главный sitemap-index
    """
    template_path = os.path.join(SITEMAP_ROOT, "sitemap.xml")
    if not os.path.exists(template_path):
        raise Http404("Sitemap index not found")
    return render(request, "sitemaps/sitemap.xml", content_type="application/xml")


def sitemap_section(request, lang, section, num):
    """
    Отдельные sitemap-файлы для типа страниц и языка
    """
    if lang not in dict(settings.LANGUAGES):
        raise Http404(f"Unknown language: {lang}")

    # строим путь к файлу
    template_path = os.path.join(SITEMAP_ROOT, lang, section, f"sitemap-{num}.xml")

    if not os.path.exists(template_path):
        raise Http404(f"Sitemap not found: {lang}/{section}/sitemap-{num}.xml")

    # путь относительно templates/ — чтобы render нашёл
    template_relative = os.path.relpath(
        template_path, os.path.join(settings.BASE_DIR, "app", "templates")
    )
    return render(request, template_relative, content_type="application/xml")
