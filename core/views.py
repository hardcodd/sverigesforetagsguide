from django.http import HttpResponse
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


def sitemap(request, section=None):
    if section:
        template_name = f"sitemaps/sitemap-{section}.xml"
        return render(request, template_name)
    return render(request, "sitemaps/sitemap.xml")
