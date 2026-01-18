from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from authors.models import AuthorPage, AuthorsIndexPage


@register(AuthorsIndexPage)
class AuthorsIndexPageTR(TranslationOptions):
    fields = ()


@register(AuthorPage)
class AuthorPageTR(TranslationOptions):
    fields = (
        "post",
        "bio",
    )
