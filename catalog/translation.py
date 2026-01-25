from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from catalog.models import (
    City,
    Organization,
    OrganizationType,
    Reward,
    ServiceType,
    ServiceTypeCategory,
)


@register(City)
class CityPageTR(TranslationOptions):
    fields = ("content",)


@register(OrganizationType)
class OrganizationTypePageTR(TranslationOptions):
    fields = ("content",)


@register(Organization)
class OrganizationPageTR(TranslationOptions):
    fields = (
        "h1_title",
        "description",
        "how_to_arrive",
        "address",
        "qna",
    )


@register(Reward)
class RewardTR(TranslationOptions):
    fields = (
        "title",
        "description",
    )


@register(ServiceTypeCategory)
class ServiceTypeCategoryTR(TranslationOptions):
    fields = ("title",)


@register(ServiceType)
class ServiceTypeTR(TranslationOptions):
    fields = ("name",)
