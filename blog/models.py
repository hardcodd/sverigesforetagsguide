from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.models import ClusterableModel
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, MultipleChooserPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page, ParentalKey, Orderable
from wagtail.snippets.models import register_snippet
from blog import blocks as blog_blocks

from core import blocks
from core.panels import Panels


class BlogIndexPage(Panels, Page):
    parent_page_types = ["home.HomePage"]
    template = "blog/index_page.html"

    subtitle = RichTextField(
        features=["link"],
        blank=True,
        verbose_name=_("Subtitle"),
    )

    banners = StreamField(
        [("banner", blocks.InlineBannerBlock())],
        blank=True,
        verbose_name=_("Banners"),
    )

    content_panels = Panels.content_panels + [
        FieldPanel("subtitle"),
        FieldPanel("banners"),
    ]

    class Meta(Page.Meta):
        verbose_name = _("Blog index page")
        verbose_name_plural = _("Blog index pages")


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

    class Meta(Page.Meta):
        verbose_name = _("Blog category page")
        verbose_name_plural = _("Blog category pages")


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
            ("reviews", blocks.ReviewsBlock()),
            ("video", blocks.VideoBlock()),
            ("gallery", blog_blocks.GalleryBlock()),
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

    class Meta(Page.Meta):
        verbose_name = _("Blog post page")
        verbose_name_plural = _("Blog post pages")

    @property
    def get_image(self):
        if self.image:
            return self.image
        return None

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


@register_snippet
class BlogGallery(ClusterableModel):
    title = models.CharField(max_length=255)
    panels = [
        FieldPanel("title"),
        MultipleChooserPanel("images", heading=_("Images"), chooser_field_name="image"),
    ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(make_template_fragment_key("blog-gallery-block", [self.pk]))

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(make_template_fragment_key("blog-gallery-block", [self.pk]))

    class Meta:
        verbose_name = _("Blog gallery")
        verbose_name_plural = _("Blog galleries")


class BlogGalleryItem(Orderable):
    gallery = ParentalKey(BlogGallery, on_delete=models.CASCADE, related_name="images")
    image = models.ForeignKey(
        "wagtailimages.Image", on_delete=models.CASCADE, related_name="+"
    )

    panels = [
        FieldPanel("image"),
    ]
