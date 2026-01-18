from django.urls import path

from .views import get_organizations_data, import_organization, organizations, search_cities

app_name = "catalog"
urlpatterns = [
    path("search-cities/", search_cities, name="search_cities"),
    path("organizations/", organizations, name="organizations"),
    path("import-organization/", import_organization, name="import_organization"),
    path(
        "get-organizations-data/", get_organizations_data, name="get_organizations_data"
    ),
]
