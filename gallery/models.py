import json

from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, MultipleChooserPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page

from core.panels import Panels


class GalleryIndexPage(Panels, Page):
    parent_page_types = ["home.HomePage"]
    subpage_types = ["gallery.GalleryCategoryPage"]
    max_count = 1

    description = RichTextField(blank=True)

    content_panels = Panels.content_panels + [
        FieldPanel("description"),
    ]

    class Meta(Page.Meta):
        verbose_name = _("Gallery index page")
        verbose_name_plural = _("Gallery index pages")


class GalleryCategoryPage(Panels, Page):
    parent_page_types = ["gallery.GalleryIndexPage", "gallery.GalleryCategoryPage"]
    subpage_types = ["gallery.GalleryCategoryPage", "gallery.GalleryPostPage"]

    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    description = RichTextField(blank=True)

    content_panels = Panels.content_panels + [
        FieldPanel("image"),
        FieldPanel("description"),
    ]

    class Meta(Page.Meta):
        verbose_name = _("Gallery category page")
        verbose_name_plural = _("Gallery category pages")


class GalleryPostPage(Panels, Page):
    parent_page_types = ["gallery.GalleryCategoryPage"]
    subpage_types = []

    description = RichTextField(blank=True)

    content_panels = Panels.content_panels + [
        FieldPanel("description"),
        MultipleChooserPanel("images", heading=_("Images"), chooser_field_name="image"),
    ]

    class Meta(Page.Meta):
        verbose_name = _("Gallery post page")
        verbose_name_plural = _("Gallery post pages")


class GalleryImage(Orderable):
    """Gallery image model."""

    page = ParentalKey(
        "gallery.GalleryPostPage", on_delete=models.CASCADE, related_name="images"
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
