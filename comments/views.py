import re

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core.utils import is_ajax

from . import models
from .models import COMMENT_DELETED, COMMENT_ON_MODERATION, COMMENT_PUBLISHED, COMMENT_REJECTED
from .utils import check_for_bad_words

USER_MODEL = get_user_model()


@csrf_protect
@require_POST
@login_required
def add_comment(request):
    data = request.POST.copy()

    user = request.user

    ctype = data.get("content_type", None)
    object_id = data.get("object_id", None)

    next_url = data.get("next", None)

    if not ctype or not object_id:
        return HttpResponse(_("Hacker?"), status=403)  # type: ignore

    try:
        app_name, model_name = ctype.split(".")
        model = apps.get_model(app_name, model_name)
    except Exception:  # noqa
        return HttpResponse(_("Hacker?"), status=403)  # type: ignore

    try:
        target = model.objects.get(id=object_id)
    except model.DoesNotExist:
        return HttpResponse(_("Hacker?"), status=403)  # type: ignore

    content_type = ContentType.objects.get_for_model(model)

    parent = None
    parent_id = data.get("parent_id")

    comment = data.get("comment").strip()

    if len(comment) < 3:
        # type: ignore
        return HttpResponse(_("Comment is too short!"), status=403)

    status = (
        COMMENT_ON_MODERATION if check_for_bad_words(
            comment) else COMMENT_PUBLISHED
    )

    if parent_id:
        try:
            parent = models.Comment.objects.get(id=parent_id)
        except models.Comment.DoesNotExist:  # type: ignore
            return HttpResponse(_("Hacker?"), status=403)  # type: ignore

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        ip_address = x_forwarded_for.split(",")[0]
    else:
        ip_address = request.META.get("REMOTE_ADDR", None)

    comment = strip_tags(comment)
    comment = re.sub(r"[\n]{3,}", "\n\n", comment)

    new_comment = models.Comment(
        content_type=content_type,
        object_id=object_id,
        user=user,
        ip_address=ip_address,
        parent=parent,
        comment=comment,
        status=status,
    )

    new_comment.save()

    if is_ajax(request):
        if new_comment.status == COMMENT_PUBLISHED:
            template = "comments/comment_published.html"
        else:
            template = "comments/comment_on_moderation.html"

        return TemplateResponse(request, template, {"node": new_comment})

    if next_url:
        return redirect(next_url)

    return redirect(target.url)


@require_GET
def count_header(request):
    data = request.GET.copy()

    ctype = data.get("content_type", None)
    object_id = data.get("object_id", None)

    if not ctype or not object_id:
        raise Exception('"content_type" and "object_id" are required')

    app_name, model_name = ctype.split(".")
    model = apps.get_model(app_name, model_name)

    target = model.objects.get(id=object_id)

    return TemplateResponse(request, "comments/header.html", {"page": target})


@login_required
@permission_required("comments.can_edit")
def delete_comment(request, comment_id):
    comment = models.Comment.objects.get(id=comment_id)
    comment.status = COMMENT_DELETED
    comment.save()

    if is_ajax(request):
        return TemplateResponse(
            request, "comments/comment_deleted.html", {"node": comment}
        )

    try:
        back_url = request.META["HTTP_REFERER"]
    except Exception:  # noqa
        back_url = comment.content_object.url

    return redirect(back_url)


@login_required
@permission_required("comments.can_edit")
def reject_comment(request, comment_id):
    comment = models.Comment.objects.get(id=comment_id)
    comment.status = COMMENT_REJECTED
    comment.save()

    if is_ajax(request):
        return TemplateResponse(
            request, "comments/comment_deleted.html", {"node": comment}
        )

    try:
        back_url = request.META["HTTP_REFERER"]
    except Exception:  # noqa
        back_url = comment.content_object.url

    return redirect(back_url)


@login_required
@permission_required("comments.can_edit")
def publish_comment(request, comment_id):
    comment = models.Comment.objects.get(id=comment_id)
    comment.status = COMMENT_PUBLISHED
    comment.save()
    back_url = request.META["HTTP_REFERER"]
    return redirect(back_url)
