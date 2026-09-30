"""Register Wagtail administration routes and menu items for application logs."""

from __future__ import annotations

from django.urls import path, reverse
from django.urls.resolvers import URLPattern, URLResolver
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import AdminOnlyMenuItem

from site_logs.views import download_log, log_list


@hooks.register("register_admin_urls")  # pyright: ignore[reportOptionalCall]
def register_admin_urls() -> list[URLPattern | URLResolver]:
    """Register superuser-only log report and download routes."""
    return [
        path("site-logs/", log_list, name="site_logs"),
        path(
            "site-logs/download/<str:filename>/",
            download_log,
            name="site_logs_download",
        ),
    ]


@hooks.register("register_reports_menu_item")  # pyright: ignore[reportOptionalCall]
def register_reports_menu_item() -> AdminOnlyMenuItem:
    """Add the application-log report to Wagtail's reports menu."""
    return AdminOnlyMenuItem(
        _("Application logs"),
        reverse("site_logs"),
        icon_name="warning",
        order=1000,
    )
