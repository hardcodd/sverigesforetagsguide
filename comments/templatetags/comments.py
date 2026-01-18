from django import template
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.utils import timezone
from wagtail.models import Page

from comments.forms import CommentForm
from comments.models import COMMENT_DELETED, COMMENT_ON_MODERATION, COMMENT_PUBLISHED, COMMENT_REJECTED, Comment

register = template.Library()


@register.simple_tag(takes_context=True)
def render_comments_list(context, obj: Page):
    request = context["request"]
    ctype = ContentType.objects.get_for_model(obj)
    object_id = obj.pk

    context["COMMENT_PUBLISHED"] = COMMENT_PUBLISHED
    context["COMMENT_ON_MODERATION"] = COMMENT_ON_MODERATION
    context["COMMENT_REJECTED"] = COMMENT_REJECTED
    context["COMMENT_DELETED"] = COMMENT_DELETED

    context["comments"] = Comment.objects.filter(
        content_type=ctype, object_id=object_id, created_at__lte=timezone.now()
    )

    return render_to_string("comments/comments_list.html", context.flatten(), request)


@register.simple_tag(takes_context=True)
def render_comment_form(context, obj: Page):
    request = context["request"]
    app, model = obj.content_type.app_label, obj.content_type.model
    initial = {
        "content_type": f"{app}.{model}",
        "object_id": obj.pk,
        "parent_id": request.GET["reply"] if "reply" in request.GET else "",
    }
    context["form"] = CommentForm(initial)
    return render_to_string("comments/form.html", context.flatten(), request)


@register.simple_tag
def get_comments_count(obj: Page):
    ctype = ContentType.objects.get_for_model(obj)
    object_id = obj.pk

    return Comment.objects.filter(
        content_type=ctype,
        object_id=object_id,
        status=COMMENT_PUBLISHED,
        created_at__lte=timezone.now(),
    ).count()
