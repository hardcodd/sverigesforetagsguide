from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from home.models import ContactPage, FlatPage, HomePage


@register(HomePage)
class HomePageTR(TranslationOptions):
    fields = ("content",)


@register(FlatPage)
class FlatPageTR(TranslationOptions):
    fields = ("content",)


@register(ContactPage)
class ContactPageTR(TranslationOptions):
    fields = (
        "content",
        "form_code",
        "tabs",
    )
