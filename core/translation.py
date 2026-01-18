from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from core.models import Footer, NotFoundPageSettings


@register(Footer)
class FooterTR(TranslationOptions):
    fields = ("navigations",)


@register(NotFoundPageSettings)
class NotFoundPageSettingsTR(TranslationOptions):
    fields = ("title", "description", "cards", "banner")
