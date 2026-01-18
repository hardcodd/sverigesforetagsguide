from django.utils.translation import gettext_lazy as _
from wagtail.blocks import IntegerBlock, PageChooserBlock, StructBlock


class OrganizationBlock(PageChooserBlock):
    def __init__(
        self, page_type=None, can_choose_root=False, target_model=None, **kwargs
    ):
        if not page_type:
            page_type = "catalog.Organization"
        super().__init__(page_type, can_choose_root, target_model, **kwargs)

    class Meta:  # type: ignore
        icon = "briefcase-solid"
        label = _("Organization")
        template = "catalog/blocks/organization-block.html"


class LatestOrganizationsFromCityBlock(StructBlock):
    count = IntegerBlock(default=4, label=_("Count"))
    page = PageChooserBlock(
        page_type="catalog.City",
        label=_("City"),
    )

    class Meta:  # type: ignore
        icon = "briefcase-solid"
        label = _("Latest organizations from city")
        template = "catalog/blocks/latest-organizations-block.html"


class LatestOrganizationsFromOrganizationTypeBlock(StructBlock):
    count = IntegerBlock(default=4, label=_("Count"))
    page = PageChooserBlock(
        page_type="catalog.OrganizationType",
        label=_("Organization type"),
    )

    class Meta:  # type: ignore
        icon = "briefcase-solid"
        label = _("Latest organizations from organization type")
        template = "catalog/blocks/latest-organizations-block.html"


class PaginatedOrganizationsBlock(StructBlock):
    count = IntegerBlock(default=16, label=_("Count"))
    page = PageChooserBlock(
        page_type=["catalog.OrganizationType", "catalog.City"],
        label=_("Parent page"),
        required=False,
    )

    class Meta:  # type: ignore
        icon = "briefcase-solid"
        label = _("Paginated organizations")
        template = "catalog/blocks/paginated-organizations-block.html"
