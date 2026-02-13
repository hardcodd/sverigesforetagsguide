import json
from functools import singledispatch

from django.utils.html import mark_safe


@singledispatch
def build_jsonld(page, request):
    # default: no markup
    return None


def render_jsonld(page, request):
    data = build_jsonld(page, request)
    if not data:
        return ""
    return mark_safe(
        '<script type="application/ld+json">{}</script>'.format(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        )
    )
