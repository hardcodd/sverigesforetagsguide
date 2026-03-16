import re

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.shortcuts import redirect, reverse
from django.template.response import TemplateResponse
from django.utils.html import format_html, strip_tags
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from wagtail.admin.ui.tables import Column, UserColumn
from wagtail.admin.viewsets.model import ModelViewSet

from core.utils import is_ajax

from . import models
from .models import (
    COMMENT_DELETED,
    COMMENT_ON_MODERATION,
    COMMENT_PUBLISHED,
    COMMENT_REJECTED,
    Comment,
)

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

    if user.is_staff or user.is_superuser:
        status = COMMENT_PUBLISHED
    else:
        status = COMMENT_ON_MODERATION

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


class ApproveColumn(Column):
    def get_value(self, instance):
        url_1 = ""
        title_1 = ""
        url_2 = ""
        title_2 = ""

        if instance.status == COMMENT_ON_MODERATION:
            url_1 = reverse("comments:publish_comment", args=[instance.id])
            title_1 = _("Approve")
            url_2 = reverse("comments:reject_comment", args=[instance.id])
            title_2 = _("Reject")
        elif instance.status == COMMENT_PUBLISHED:
            url_1 = reverse("comments:reject_comment", args=[instance.id])
            title_1 = _("Reject")
            url_2 = reverse("comments:delete_comment", args=[instance.id])
            title_2 = _("Delete")
        elif instance.status == COMMENT_REJECTED:
            url_1 = reverse("comments:publish_comment", args=[instance.id])
            title_1 = _("Approve")
            url_2 = reverse("comments:delete_comment", args=[instance.id])
            title_2 = _("Delete")
        elif instance.status == COMMENT_DELETED:
            url_1 = reverse("comments:publish_comment", args=[instance.id])
            title_1 = _("Approve")
            url_2 = reverse("comments:reject_comment", args=[instance.id])
            title_2 = _("Reject")

        lang = get_language()

        prefix = f"/{lang}" if lang else ""

        # remove language prefix from URLs
        url_1 = url_1[len(prefix) :] if url_1.startswith(prefix) else url_1
        url_2 = url_2[len(prefix) :] if url_2.startswith(prefix) else url_2

        return format_html(
            '<a href="{}" class="button button-small button-secondary">{}</a> \
            <a href="{}" class="button button-small no">{}</a>',
            url_1,
            title_1,
            url_2,
            title_2,
        )


class ContentObjectColumn(Column):
    def get_value(self, instance):
        if len(instance.content_object.__str__()) > 50:
            title = instance.content_object.__str__()[:50] + " ..."
        else:
            title = instance.content_object.__str__()

        lang = get_language()

        prefix = f"/{lang}" if lang else ""

        # remove language prefix from URL
        url = instance.content_object.url
        url = url[len(prefix) :] if url.startswith(prefix) else url

        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            url,
            title,
        )


class StatusColumn(Column):
    def get_value(self, instance):
        if instance.status == COMMENT_PUBLISHED:
            return format_html(
                f"<span class='w-status w-status--primary'>{_('Published')}</span>"
            )
        elif instance.status == COMMENT_ON_MODERATION:
            return format_html(
                f"<span class='w-status w-status--warning'>{_('On Moderation')}</span>"
            )
        elif instance.status == COMMENT_REJECTED:
            return format_html(
                f"<span class='w-status w-status--danger'>{_('Rejected')}</span>"
            )
        elif instance.status == COMMENT_DELETED:
            return format_html(
                f"<span class='w-status w-status--secondary'>{_('Deleted')}</span>"
            )
        else:
            return instance.status


class ContentTypeColumn(Column):
    def get_value(self, instance):
        return f"{instance.content_type.app_label.title()}"


class CommentViewSet(ModelViewSet):
    model = Comment
    menu_label = _("Comments")  # type: ignore
    icon = "comment-add"
    add_to_admin_menu = True
    copy_view_enabled = False
    menu_order = 200
    search_fields = ("user__username", "comment")
    list_filter = ("status",)
    list_display = [
        "id",
        UserColumn("user", label=_("User")),
        StatusColumn("status"),
        ApproveColumn(name=""),
        ContentTypeColumn(name=_("App")),
        ContentObjectColumn(name=_("Content Object")),
    ]


comments_viewset = CommentViewSet("comments_list")
