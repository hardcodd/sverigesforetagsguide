from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page, ParentalKey

from core import blocks
from core.panels import Panels


class BlogIndexPage(Panels, Page):
    parent_page_types = ["home.HomePage"]
    template = "blog/index_page.html"

    subtitle = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Subtitle"),
    )

    content_panels = Panels.content_panels + [
        FieldPanel("subtitle"),
    ]


class BlogCategoryPage(Panels, Page):
    parent_page_types = ["blog.BlogIndexPage", "blog.BlogCategoryPage"]
    template = "blog/category_page.html"

    subtitle = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Subtitle"),
    )

    def save(self, *args, **kwargs):
        blog_id = self.get_ancestors().type(BlogIndexPage).first().id

        for language in getattr(settings, "WAGTAIL_CONTENT_LANGUAGES", []):
            key = make_template_fragment_key(
                "blog_categories_list", [language[0], blog_id]
            )
            cache.delete(key)

        return super().save(*args, **kwargs)

    content_panels = Panels.content_panels + [
        FieldPanel("subtitle"),
    ]


class BlogTag(TaggedItemBase):
    content_object = ParentalKey(
        "blog.BlogPostPage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )


class BlogPostPage(Panels, Page):
    parent_page_types = ["blog.BlogCategoryPage"]
    template = "blog/post_page.html"

    author = models.ForeignKey(
        "authors.AuthorPage",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Image"),
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

    tags = ClusterTaggableManager(through=BlogTag, blank=True)

    content_panels = Panels.content_panels + [
        FieldPanel("author"),
        FieldPanel("image"),
        FieldPanel("tags"),
        FieldPanel("content"),
    ]

    @property
    def get_image(self):
        if self.image:
            return self.image

    def save(self, *args, **kwargs):
        languages = getattr(settings, "LANGUAGES", ["en"])
        blog_id = self.get_ancestors().type(BlogIndexPage).first().id

        for lang in languages:
            cache.delete(
                make_template_fragment_key("blog_post_item", [self.pk, lang[0]])
            )

            key = make_template_fragment_key("blog_tags_list", [lang[0], blog_id])
            cache.delete(key)

        return super().save(*args, **kwargs)
