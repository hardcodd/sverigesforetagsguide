from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, TitleFieldPanel


class Panels:
    content_panels = [
        TitleFieldPanel("title"),
    ]

    promote_panels = [
        FieldPanel("slug"),
        FieldPanel("seo_title"),
        FieldPanel("search_description"),
        FieldPanel("show_in_menus"),
    ]
