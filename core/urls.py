from django.urls import path

from core import export_views
from core.views import import_page

app_name = "core"
urlpatterns = [
    path("import-page/", import_page, name="import_page"),
    path("export-pages/", export_views.export_pages, name="export_pages"),
    path(
        "export-pages/page-types/",
        export_views.export_page_types,
        name="export_page_types",
    ),
    path(
        "export-pages/fields/",
        export_views.export_page_fields,
        name="export_page_fields",
    ),
    path(
        "export-pages/search-parent-pages/",
        export_views.search_parent_pages,
        name="search_parent_pages",
    ),
    path(
        "export-pages/start/",
        export_views.start_pages_export,
        name="start_pages_export",
    ),
    path(
        "export-pages/progress/<str:job_id>/",
        export_views.export_progress,
        name="export_progress",
    ),
    path(
        "export-pages/download/<str:job_id>/",
        export_views.download_pages_export,
        name="download_pages_export",
    ),
]
