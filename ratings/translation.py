from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from ratings.models import RatingCategoryPage, RatingPage, RatingsIndexPage


@register(RatingsIndexPage)
class RatingsIndexPageTR(TranslationOptions):
    fields = ()


@register(RatingCategoryPage)
class RatingCategoryPageTR(TranslationOptions):
    fields = ()


@register(RatingPage)
class RatingPageTR(TranslationOptions):
    fields = (
        "content",
        "ratings",
        "blockquote",
    )
