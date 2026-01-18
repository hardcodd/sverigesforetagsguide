from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from core import blocks
from core.panels import Panels


class HomePage(Panels, Page):
    max_count = 1

    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Image"),
        help_text=_("Main image for the home page."),
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
        FieldPanel("image"),
        FieldPanel("content"),
    ]

    @property
    def get_image(self):
        if self.image:
            return self.image

    class Meta(Page.Meta):
        verbose_name = _("Home page")
        verbose_name_plural = _("Home pages")


class FlatPage(Panels, Page):
    """A simple page with a title and body."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []

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
        FieldPanel("content"),
    ]

    class Meta(Page.Meta):
        verbose_name = _("Flat page")
        verbose_name_plural = _("Flat pages")


class ContactPage(Panels, Page):
    """A contact page with a title and body."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

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

    form_code = models.TextField(
        blank=True,
        verbose_name=_("Form code"),
        help_text=_("HTML code for the contact form."),
    )

    tabs = StreamField(
        [
            (
                "tab",
                blocks.StructBlock(
                    [
                        ("title", blocks.CharBlock(max_length=100, label=_("Title"))),
                        (
                            "content",
                            blocks.RichTextBlock(
                                features=["bold", "italic", "link"], label=_("Content")
                            ),
                        ),
                    ]
                ),
            ),
        ],
        blank=True,
        verbose_name=_("Tabs"),
    )

    social_networks = models.TextField(
        blank=True,
        verbose_name=_("Social networks"),
        help_text=_("Enter one social network link per line."),
    )

    content_panels = Panels.content_panels + [
        FieldPanel("content"),
        FieldPanel("form_code"),
        FieldPanel("tabs"),
        FieldPanel("social_networks"),
    ]

    class Meta(Page.Meta):
        verbose_name = _("Contact page")
        verbose_name_plural = _("Contact pages")
