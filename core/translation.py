from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from core.models import Footer, NotFoundPageSettings, SiteSettings


@register(SiteSettings)
class SiteSettingsTR(TranslationOptions):
    fields = ("content_source", "footer_text", "ad_button_text", "ad_button_caption")


@register(Footer)
class FooterTR(TranslationOptions):
    fields = ("navigations",)


@register(NotFoundPageSettings)
class NotFoundPageSettingsTR(TranslationOptions):
    fields = ("title", "description", "cards", "banner")
