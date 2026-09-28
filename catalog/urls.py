from django.urls import path

from .nearby_views import nearby_organizations
from .views import (
    get_organizations_data,
    organizations,
    search_cities,
)

app_name = "catalog"
urlpatterns = [
    path(
        "organizations/<int:organization_id>/nearby/",
        nearby_organizations,
        name="nearby_organizations",
    ),
    path("search-cities/", search_cities, name="search_cities"),
    path("organizations/", organizations, name="organizations"),
    path(
        "get-organizations-data/", get_organizations_data, name="get_organizations_data"
    ),
]
