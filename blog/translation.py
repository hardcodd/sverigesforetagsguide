from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from blog.models import BlogCategoryPage, BlogIndexPage, BlogPostPage


@register(BlogIndexPage)
class BlogIndexPageTR(TranslationOptions):
    fields = ("subtitle",)


@register(BlogCategoryPage)
class BlogCategoryPageTR(TranslationOptions):
    fields = ("subtitle",)


@register(BlogPostPage)
class BlogPostPageTR(TranslationOptions):
    fields = ("content",)
