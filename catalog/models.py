from django import forms
from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import models
from django.db.models import Exists, F, OuterRef
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalManyToManyField
from modeltranslation.utils import get_language
from taggit.models import ItemBase, TagBase
from wagtail.admin.panels import FieldPanel, MultipleChooserPanel, ObjectList, TabbedInterface, TitleFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, route
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page, PageManager, ParentalKey
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from core import blocks
from core.panels import Panels


class Language(models.Model):
    language_name = models.CharField(max_length=100, unique=True)
    icon = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Icon"),
        help_text=_("Use 100x100px image."),
        blank=True,
        null=True,
    )

    panels = [
        FieldPanel("language_name"),
        FieldPanel("icon"),
    ]

    def __str__(self) -> str:
        return str(self.language_name)


class OrganizationManager(PageManager):
    def get_queryset(self):
        images = OrganizationImage.objects.filter(page=OuterRef("pk"))
        queryset = (
            (
                super()
                .get_queryset()
                .select_related(
                    "premium_subscription",
                )
                .prefetch_related(
                    "images",
                    "rewards",
                )
            )
            .annotate(
                subscription_priority=models.F("premium_subscription__level"),
                has_images=Exists(images),
            )
            .order_by(
                "temporarily_closed",
                F("subscription_priority").desc(nulls_last=True),
                F("has_images").desc(),
                "-avg_rating",
                "-first_published_at",
            )
        )
        return queryset


class City(Panels, Page):
    """City page model."""

    template = "catalog/city_page.html"
    parent_page_types = ["home.HomePage"]

    popular = models.BooleanField(
        _("Popular"),
        default=False,  # type: ignore
    )

    ll = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Latitude and longitude"),
    )

    content = StreamField(
        [
            ("text", blocks.TextBlock(label=_("Text"))),
            ("cards_section", blocks.SectionCardsBlock()),
            ("qna", blocks.QnABlock()),
            ("banner", blocks.BannerBlock()),
            ("html", blocks.HTMLBlock()),
        ],
        blank=True,
        verbose_name=_("Content"),
    )

    content_panels = Panels.content_panels + [
        FieldPanel("ll"),
        FieldPanel("content"),
    ]

    promote_panels = Panels.promote_panels + [
        FieldPanel(
            "popular",
            help_text=_("Mark this city as popular."),
        ),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("seo_title", boost=3),
        index.SearchField("search_description"),
    ]

    @property
    def get_image(self):
        """Return the first image of the city."""
        if self.flag:
            return self.flag
        return None

    class Meta(Page.Meta):
        verbose_name = _("City")
        verbose_name_plural = _("Cities")


class OrganizationType(RoutablePageMixin, Panels, Page):
    """Organization type page model."""

    template = "catalog/organization_type_page.html"
    parent_page_types = ["catalog.City"]

    noindex = models.BooleanField(verbose_name=_("Noindex"), default=False)

    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Image"),
        blank=True,
        null=True,
    )

    content = StreamField(
        [
            ("text", blocks.TextBlock(label=_("Text"))),
            ("cards_section", blocks.SectionCardsBlock()),
            ("qna", blocks.QnABlock()),
            ("banner", blocks.BannerBlock()),
            ("html", blocks.HTMLBlock()),
        ],
        blank=True,
        verbose_name=_("Content"),
    )

    content_panels = [
        TitleFieldPanel("title"),
        FieldPanel("image"),
        FieldPanel("content"),
    ]

    promote_panels = Panels.promote_panels + [FieldPanel("noindex")]

    search_fields = Page.search_fields + [
        index.SearchField("seo_title", boost=3),
        index.SearchField("search_description"),
    ]

    @route(r"^map/$")
    def map_view(self, request, *args, **kwargs):
        """Map view of the organization type."""
        organizations = (
            Organization.objects.live()
            .filter(show_on_map=True)
            .descendant_of(self)
            .distinct()
        )

        return render(
            request,
            "catalog/organization_type_map.html",
            {
                "page": self,
                "organizations": organizations,
            },
        )

    @property
    def get_image(self):
        """Return the first image of the organization type."""
        if self.image:
            return self.image
        return None

    def get_context(self, request):
        """Get the context for the template."""
        context = super().get_context(request)

        if request.method == "GET":
            service_type = request.GET.get("service_type")
            try:
                service_type = ServiceType.objects.get(pk=service_type)  # type: ignore  # fmt: off
            except ServiceType.DoesNotExist:  # type: ignore
                service_type = None

            if service_type:
                context["active_service_type"] = service_type

        return context

    class Meta(Page.Meta):
        verbose_name = _("Organization type")
        verbose_name_plural = _("Organization types")


class Organization(Page):
    """Organization page model."""

    objects = OrganizationManager()
    template = "catalog/organization_page.html"
    parent_page_types = ["catalog.OrganizationType"]
    subpage_types = []

    h1_title = models.CharField(
        verbose_name=_("h1 title"), max_length=255, blank=True, null=True
    )

    tin = models.CharField(
        max_length=12,
        blank=True,
        verbose_name=_("TIN"),
    )

    legal_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Legal name"),
    )

    verified = models.BooleanField(
        _("Verified"),
        default=False,  # type: ignore
    )

    plus_code = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Plus code"),
    )

    email = models.EmailField(
        max_length=255,
        blank=True,
        verbose_name=_("Email"),
    )

    phones = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Phones"),
        help_text=_("Separate multiple phone numbers with a comma."),
    )

    social_networks = models.TextField(
        blank=True,
        verbose_name=_("Social networks"),
        help_text=_("Enter one social network link per line."),
    )

    website_links = models.TextField(
        blank=True,
        verbose_name=_("Website links"),
        help_text=_("Enter one website link per line."),
    )

    website_links_as_text = models.BooleanField(
        _("Show website links as text"),
        default=True,  # type: ignore
        help_text=_("Show website links as plain text instead of clickable links."),
    )

    working_hours = StreamField(
        [("day", blocks.DayBlock(icon="date", label=_("Day")))],
        blank=True,
        verbose_name=_("Working hours"),
    )

    temporarily_closed = models.BooleanField(
        _("Temporarily closed"),
        default=False,  # type: ignore
    )

    languages = ParentalManyToManyField(
        Language,
        blank=True,
        verbose_name=_("Languages"),
    )

    description = RichTextField(
        blank=True,
        verbose_name=_("Description"),
    )

    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Address"),
    )

    how_to_arrive = RichTextField(
        blank=True,
        verbose_name=_("How to arrive"),
    )

    ll = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Latitude and longitude"),
    )

    show_on_map = models.BooleanField(
        _("Show on map"),
        default=True,  # type: ignore
    )

    located_in = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="located_organizations",
        verbose_name=_("Located in"),
    )

    service_types = ClusterTaggableManager(
        through="catalog.OrganizationServiceType",
        blank=True,
        verbose_name=_("Service types"),
    )

    avg_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
    )

    content_panels = [
        TitleFieldPanel("h1_title"),
        TitleFieldPanel("title", targets=["slug"]),
        FieldPanel("tin"),
        FieldPanel("legal_name"),
        FieldPanel("working_hours", icon="time"),
        FieldPanel(
            "languages",
            icon="globe",
            widget=forms.CheckboxSelectMultiple,
            help_text=_("The languages spoken in the organization."),
        ),
        FieldPanel("service_types", icon="tag"),
    ]

    contacts_panels = [
        FieldPanel("email", icon="mail"),
        FieldPanel("phones", icon="mobile-alt"),
        FieldPanel("social_networks", icon="globe"),
        FieldPanel("website_links", icon="link-external"),
        FieldPanel("website_links_as_text"),
    ]

    location_panels = [
        FieldPanel("ll"),
        FieldPanel("show_on_map", help_text=_("Show this organization on the map.")),
        FieldPanel("plus_code"),
        FieldPanel("address"),
        FieldPanel(
            "located_in",
            help_text=_(
                "The organization is located in building of another organization."
            ),
        ),
        FieldPanel("how_to_arrive"),
    ]

    images_panels = [
        MultipleChooserPanel("images", heading=_("Images"), chooser_field_name="image"),
    ]

    description_panels = [
        FieldPanel("description"),
    ]

    rewards_panels = [
        MultipleChooserPanel(
            "rewards",
            heading=_("Rewards"),
            chooser_field_name="reward",
        ),
    ]

    promote_panels = Panels.promote_panels + [
        FieldPanel("verified", help_text=_("Mark this organization as verified.")),
        FieldPanel(
            "temporarily_closed",
            help_text=_("Mark this organization as temporarily closed."),
        ),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(content_panels, heading=_("General")),
            ObjectList(contacts_panels, heading=_("Contacts")),
            ObjectList(description_panels, heading=_("Description")),
            ObjectList(location_panels, heading=_("Location")),
            ObjectList(images_panels, heading=_("Images")),
            ObjectList(rewards_panels, heading=_("Rewards")),
            ObjectList(promote_panels, heading=_("Promote")),
            ObjectList(Page.settings_panels, heading="Settings"),
        ]
    )

    search_fields = Page.search_fields + [
        index.SearchField("h1_title", boost=3),
        index.AutocompleteField("h1_title"),
        index.SearchField("seo_title", boost=4),
        index.SearchField("search_description"),
        index.SearchField("address"),
        index.SearchField("description"),
        index.SearchField("phones"),
        index.RelatedFields(
            "service_types",
            [
                index.SearchField("name", boost=2),
            ],
        ),
    ]

    @property
    def get_image(self):
        """Return the first image of the organization."""
        if self.images.exists():
            return self.images.first().image
        return None

    class Meta(Page.Meta):
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")

    def get_context(self, request):
        """Get the context for the template."""
        context = super().get_context(request)
        context["service_types"] = self.service_types.select_related("category").all()
        return context

    def save(self, *args, **kwargs):
        keys = ["organization", "organization_images", "organization_item"]
        languages = getattr(settings, "LANGUAGES", ["en"])

        for key in keys:
            for lang in languages:
                cache.delete(make_template_fragment_key(key, [self.pk, lang[0]]))

        return super().save(*args, **kwargs)


class OrganizationImage(Orderable):
    """Gallery image model."""

    page = ParentalKey(
        "catalog.Organization", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Image"),
    )

    panels = [
        FieldPanel("image"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Image")
        verbose_name_plural = _("Images")


@register_snippet
class Reward(models.Model):
    """Reward model."""

    title = models.CharField(
        max_length=100,
        verbose_name=_("Reward"),
    )
    description = models.TextField(
        verbose_name=_("Description"),
        max_length=255,
    )
    icon = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Icon"),
    )

    panels = [
        FieldPanel("title"),
        FieldPanel(
            "description",
            widget=forms.Textarea(
                attrs={
                    "cols": 1,
                    "rows": 1,
                    "class": "w-field__autosize",
                    "data-controller": "w-autosize",
                }
            ),
        ),
        FieldPanel(
            "icon",
            help_text=_("Use 100x100px image."),
        ),
    ]

    def __str__(self) -> str:
        return str(self.title)

    class Meta:
        verbose_name = _("Reward")
        verbose_name_plural = _("Rewards")


class OrganizationReward(Orderable):
    """Organization Reward model."""

    page = ParentalKey("catalog.Organization", related_name="rewards")

    reward = models.ForeignKey(
        "catalog.Reward",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Reward"),
    )

    panels = [
        FieldPanel("reward"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Reward")
        verbose_name_plural = _("Rewards")


class ServiceTypeCategory(models.Model):
    """Service type category model."""

    title = models.CharField(
        max_length=100,
        verbose_name=_("Title"),
    )

    def __str__(self) -> str:
        return str(self.title)

    class Meta:
        verbose_name = _("Service type category")
        verbose_name_plural = _("Service type categories")


class ServiceType(TagBase):
    """Service type model."""

    free_tagging = False

    name = models.CharField(
        max_length=100,
        verbose_name=_("Title"),
    )

    category = models.ForeignKey(
        "catalog.ServiceTypeCategory",
        on_delete=models.CASCADE,
        related_name="service_types",
        verbose_name=_("Category"),
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("category"),
    ]

    def __str__(self) -> str:  # type: ignore
        return str(self.name)

    def clean(self):
        """Check if the service type already exists."""
        lang = get_language()
        title_field = f"name_{lang}"
        title_value = getattr(self, title_field)

        # Try to get the existing service type
        qs = ServiceType.objects.filter(  # type: ignore
            **{title_field: title_value, "category": self.category}
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.exists():
            raise forms.ValidationError(
                _("This service type already exists in this category.")
            )

    class Meta(TagBase.Meta):
        verbose_name = _("Service type")
        verbose_name_plural = _("Service types")


class OrganizationServiceType(ItemBase):
    """Organization service type model."""

    tag = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE,
        related_name="tagged_organizations",
    )

    content_object = ParentalKey(
        to="catalog.Organization",
        on_delete=models.CASCADE,
        related_name="tagged_items",
    )
