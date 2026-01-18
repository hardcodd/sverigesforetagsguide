from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.admin.sites import JavaScriptCatalog
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from core.views import robots_txt, sitemap
from search import views as search_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("aristarx/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("reviews/", include("reviews.urls"), name="reviews"),
    path("select2/", include("django_select2.urls")),
    path("accounts/", include("allauth.urls")),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap),
    path("sitemap-<section>.xml", sitemap),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += debug_toolbar_urls()


if "rosetta" in settings.INSTALLED_APPS:
    urlpatterns += i18n_patterns(
        path("rosetta/", include("rosetta.urls")), prefix_default_language=False
    )

urlpatterns += i18n_patterns(
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("search/", search_views.search, name="search"),
    path("catalog/", include("catalog.urls"), name="catalog"),
    path("comments/", include("comments.urls", namespace="comments")),
    path("", include(wagtail_urls)),
    prefix_default_language=False,
)
