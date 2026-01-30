from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import (
    FieldPanel,
    HelpPanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
)
from wagtail.blocks import CharBlock, ListBlock, StructBlock
from wagtail.contrib.settings.models import (
    BaseGenericSetting,
    BaseSiteSetting,
    register_setting,
)
from wagtail.fields import StreamField

from core.blocks import BannerBlock, CardStyle5Block, ExternalCodeBlock, LinkBlock


@register_setting
class SiteSettings(BaseGenericSetting):
    """Site settings for the site. E.g. Logo, etc."""

    logo = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Site logo"),
        help_text=_("The logo of the site."),
    )

    logo_mobile = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Mobile logo"),
        help_text=_("The logo of the site for mobile devices."),
    )

    default_organization_image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Default organization image"),
        help_text=_("The default image for organizations."),
    )

    flag = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Flag"),
        help_text=_("Flag for hero banner on home page."),
    )

    social_networks = models.TextField(
        blank=True,
        verbose_name=_("Social networks"),
        help_text=_("Enter one social network link per line."),
    )

    content_source = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Content source"),
        help_text=_("Source of the content displayed on the site."),
    )

    panels = [
        FieldPanel("logo"),
        FieldPanel("logo_mobile"),
        FieldPanel("default_organization_image"),
        FieldPanel("flag"),
        FieldPanel("social_networks"),
        FieldPanel("content_source"),
    ]

    class Meta(BaseGenericSetting.Meta):
        verbose_name = _("Site settings")

    def save(self, *args, **kwargs):
        for language in getattr(settings, "MODELTRANSLATION_LANGUAGES", []):
            for key in ["footer", "site_settings"]:
                key = make_template_fragment_key(key, [language])
                cache.delete(key)

        return super().save(*args, **kwargs)


@register_setting
class RobotsTxtSettings(BaseSiteSetting):
    """Robots.txt settings for the site."""

    content = models.TextField(
        blank=True,
        verbose_name=_("Robots.txt content"),
        help_text=_("Content of the robots.txt file."),
    )

    panels = [
        FieldPanel("content"),
    ]

    class Meta(BaseGenericSetting.Meta):
        verbose_name = _("Robots.txt")

    def save(self, *args, **kwargs):
        key = make_template_fragment_key("robots_txt")
        cache.delete(key)
        return super().save(*args, **kwargs)


@register_setting
class ExternalCodeSettings(BaseGenericSetting):
    """External code settings for the site. E.g. Google Analytics, Facebook Pixel, etc."""

    help_text = _(
        "Add external code snippets e.g. Google Analytics, Facebook Pixel, etc... "
        + "to the header, body, or footer of your site."
    )

    header_code = StreamField(
        [("code", ExternalCodeBlock())],
        blank=True,
        verbose_name=_("Header code"),
    )

    body_code = StreamField(
        [("code", ExternalCodeBlock())],
        blank=True,
        verbose_name=_("Body code"),
    )

    footer_code = StreamField(
        [("code", ExternalCodeBlock())],
        blank=True,
        verbose_name=_("Footer code"),
    )

    panels = [
        HelpPanel(content=str(help_text)),
        MultiFieldPanel(
            [
                FieldPanel("header_code"),
                FieldPanel("body_code"),
                FieldPanel("footer_code"),
            ],
        ),
    ]

    class Meta(BaseGenericSetting.Meta):
        verbose_name = _("External code")

    def save(self, *args, **kwargs):
        for key in ["header", "body", "footer"]:
            key = make_template_fragment_key("external_code", [key])
            cache.delete(key)

        return super().save(*args, **kwargs)


@register_setting
class NotFoundPageSettings(BaseGenericSetting):
    """404 Not Found Page settings for the site."""

    title = models.CharField(
        max_length=200,
        verbose_name=_("404 Page Title"),
        help_text=_("Title displayed on the 404 Not Found page."),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("404 Page Description"),
        help_text=_("Description displayed on the 404 Not Found page."),
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("404 Page Image"),
        help_text=_("Image displayed on the 404 Not Found page."),
    )

    cards = StreamField(
        [
            ("card", CardStyle5Block()),
        ],
        blank=True,
        verbose_name=_("404 Page Cards"),
        block_counts={"card": {"max_num": 3}},
    )

    banner = StreamField(
        [("banner", BannerBlock())],
        blank=True,
        verbose_name=_("404 Page Banner"),
        block_counts={"banner": {"max_num": 1}},
    )

    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
        FieldPanel("image"),
        FieldPanel("cards"),
        FieldPanel("banner"),
    ]

    class Meta(BaseGenericSetting.Meta):
        verbose_name = _("Page 404")


class Footer(models.Model):
    navigations = StreamField(
        [
            (
                "navigation",
                StructBlock(
                    [
                        ("title", CharBlock(max_length=50, label=_("Title"))),
                        ("links", ListBlock(LinkBlock(), label=_("Links"))),
                    ],
                    template="core/blocks/footer_navigation_block.html",
                ),
            )
        ],
        block_counts={"navigation": {"max_num": 4}},
        verbose_name=_("Navigations"),
        blank=True,
    )

    navigation_panels = [
        FieldPanel("navigations"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(navigation_panels, heading=_("Navigation")),
        ]
    )

    class Meta:
        verbose_name = _("Footer")
        verbose_name_plural = _("Footer")

    def __str__(self) -> str:
        return "Footer"

    def save(self, *args, **kwargs):
        # Check if there are no other footer instances
        if Footer.objects.exists() and not self.pk:  # type: ignore
            raise Exception(_("There can be only one footer instance."))

        for language in getattr(settings, "MODELTRANSLATION_LANGUAGES", []):
            key = make_template_fragment_key("footer", [language])
            cache.delete(key)

        return super().save(*args, **kwargs)
