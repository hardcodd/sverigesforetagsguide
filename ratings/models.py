from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from core.panels import Panels
from ratings.blocks import ContentBlock, RatingBlock


class RatingsIndexPage(Panels, Page):
    parent_page_types = ["home.HomePage"]
    subpage_types = ["ratings.RatingCategoryPage"]
    max_count = 1

    class Meta:
        verbose_name = "Overviews Index Page"


class RatingCategoryPage(Panels, Page):
    parent_page_types = [
        "ratings.RatingsIndexPage",
        "ratings.RatingCategoryPage",
    ]
    subpage_types = [
        "ratings.RatingPage",
        "ratings.RatingCategoryPage",
    ]

    class Meta:
        verbose_name = "Overviews Category Page"


class RatingPage(Page):
    parent_page_types = ["ratings.RatingCategoryPage"]
    subpage_types = []

    content = StreamField([("block", ContentBlock())])

    blockquote = models.TextField(blank=True)

    ratings = StreamField([("rating", RatingBlock())], blank=True)

    to_organization = models.ForeignKey(
        "catalog.Organization",
        on_delete=models.PROTECT,
    )

    author = models.ForeignKey(
        "authors.AuthorPage",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    content_panels = Panels.content_panels + [
        FieldPanel(
            "content",
        ),
        FieldPanel("blockquote"),
        FieldPanel("ratings"),
        "to_organization",
        "author",
    ]

    class Meta:
        verbose_name = "Overviews Post Page"
