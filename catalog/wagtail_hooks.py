from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import AdminOnlyMenuItem, Menu, MenuItem, SubmenuMenuItem

from catalog.admin_views import import_organizations
from catalog.views import CatalogViewSetGroup, OrganizationReportView, service_type_category_chooser_viewset


@hooks.register("register_admin_viewset")
def register_service_type_category_chooser_viewset():
    return service_type_category_chooser_viewset


@hooks.register("register_admin_viewset")  # type: ignore
def register_viewset():
    return CatalogViewSetGroup()


@hooks.register("register_admin_urls")
def register_import_organizations():
    return [
        path("import-organizations/", import_organizations,
             name="import-organizations")
    ]


@hooks.register("register_admin_menu_item")
def register_import_organizations_menu_item():
    submenu = Menu(
        items=[
            MenuItem(
                "Organizations",
                reverse("import-organizations"),
                icon_name="briefcase-solid",
            )
        ]
    )

    return SubmenuMenuItem("Import", submenu, icon_name="resubmit")


@hooks.register("register_reports_menu_item")
def register_organizations_report_menu_item():
    return AdminOnlyMenuItem(
        "Organizations",
        reverse("organizations_report"),
        icon_name="briefcase-solid",
        order=700,
    )


@hooks.register("register_admin_urls")
def register_organizations_report_url():
    return [
        path(
            "reports/organizations/",
            OrganizationReportView.as_view(),
            name="organizations_report",
        ),
        path(
            "reports/organizations/results/",
            OrganizationReportView.as_view(results_only=True),
            name="organizations_report_results",
        ),
    ]
