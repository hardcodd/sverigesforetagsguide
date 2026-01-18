from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from core.panels import Panels


class AuthorsIndexPage(Panels, Page):
    parent_page_types = ["home.HomePage"]

    class Meta:
        verbose_name = _("Authors index page")


class AuthorPage(Panels, Page):
    parent_page_types = ["authors.AuthorsIndexPage"]

    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    post = models.CharField(verbose_name=_("post"))

    bio = RichTextField(blank=True)

    content_panels = Panels.content_panels + [
        FieldPanel("image"),
        FieldPanel("post"),
        FieldPanel("bio"),
    ]

    class Meta:
        verbose_name = _("Author")
        verbose_name_plural = _("Authors")
