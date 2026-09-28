from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from wagtail.admin.ui.tables import Column
from wagtail.admin.views import generic


def without_language_prefix(url):
    language = get_language()
    prefix = f"/{language}" if language else ""
    if prefix and (url == prefix or url.startswith(f"{prefix}/")):
        return url[len(prefix) :] or "/"
    return url


class TextPreviewColumn(Column):
    def __init__(self, name, *, length=120, **kwargs):
        super().__init__(name, **kwargs)
        self.length = length

    def get_value(self, instance):
        value = super().get_value(instance)
        return Truncator(value or "").chars(self.length)


class ContentObjectColumn(Column):
    def __init__(self, **kwargs):
        super().__init__(
            "content_object",
            label=kwargs.pop("label", _("Content Object")),
            **kwargs,
        )

    def get_value(self, instance):
        content_object = instance.content_object
        if content_object is None:
            return _("Unavailable")

        title = Truncator(str(content_object)).chars(80)
        url = getattr(content_object, "url", None)
        if not url:
            return title

        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            without_language_prefix(url),
            title,
        )


class RelatedContentIndexView(generic.IndexView):
    def get_base_queryset(self):
        return (
            super()
            .get_base_queryset()
            .select_related("user", "content_type")
            .prefetch_related("content_object")
        )
