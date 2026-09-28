from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from gallery.models import GalleryPostPage, GalleryIndexPage, GalleryCategoryPage


@register(GalleryIndexPage)
class GalleryIndexPageTR(TranslationOptions):
    fields = ("description",)


@register(GalleryCategoryPage)
class GalleryCategoryPageTR(TranslationOptions):
    fields = ("description",)


@register(GalleryPostPage)
class GalleryPostPageTR(TranslationOptions):
    fields = ("description",)
