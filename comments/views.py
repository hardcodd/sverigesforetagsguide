import json
import re

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, reverse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.tables import (
    BooleanColumn,
    DateColumn,
    StatusTagColumn,
    UserColumn,
)
from wagtail.admin.viewsets.base import ViewSet, ViewSetGroup
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.widgets.button import ListingButton

from core.admin_columns import (
    ContentObjectColumn,
    RelatedContentIndexView,
    TextPreviewColumn,
    without_language_prefix,
)
from core.utils import is_ajax

from . import models
from .models import (
    COMMENT_DELETED,
    COMMENT_ON_MODERATION,
    COMMENT_PUBLISHED,
    COMMENT_REJECTED,
    Comment,
)
from .services import CommentImportError, import_comment_row, import_comment_rows

USER_MODEL = get_user_model()


@permission_required("comments.add_comment", raise_exception=True)
def import_comments(request):
    return render(request, "comments/admin/import_comments.html", {})


@require_POST
@permission_required("comments.add_comment", raise_exception=True)
def import_comment(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "code": "invalid_json", "message": _("Invalid JSON.")},
            status=400,
        )

    try:
        if isinstance(data, list):
            results = import_comment_rows(data)
            return JsonResponse(
                {
                    "success": True,
                    "results": [
                        {
                            "success": result.success,
                            "code": result.code,
                            "message": result.message,
                        }
                        for result in results
                    ],
                }
            )
        import_comment_row(data)
    except CommentImportError as error:
        return JsonResponse(
            {"success": False, "code": error.code, "message": str(error)},
            status=error.status,
        )

    return JsonResponse(
        {
            "success": True,
            "code": "imported",
            "message": _("Comment created successfully."),
        }
    )


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


class CommentIndexView(RelatedContentIndexView):
    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        if not self.request.user.has_perm("comments.can_edit"):
            return buttons

        actions = []
        if instance.status == COMMENT_ON_MODERATION:
            actions = [
                (_("Approve"), "comments:publish_comment", "success"),
                (_("Reject"), "comments:reject_comment", "cross"),
            ]
        elif instance.status == COMMENT_PUBLISHED:
            actions = [
                (_("Reject"), "comments:reject_comment", "cross"),
                (_("Delete"), "comments:delete_comment", "bin"),
            ]
        elif instance.status == COMMENT_REJECTED:
            actions = [
                (_("Approve"), "comments:publish_comment", "success"),
                (_("Delete"), "comments:delete_comment", "bin"),
            ]
        elif instance.status == COMMENT_DELETED:
            actions = [
                (_("Approve"), "comments:publish_comment", "success"),
                (_("Reject"), "comments:reject_comment", "cross"),
            ]

        for priority, (label, url_name, icon_name) in enumerate(actions, start=40):
            buttons.append(
                ListingButton(
                    label,
                    url=without_language_prefix(
                        reverse(url_name, args=[instance.pk])
                    ),
                    icon_name=icon_name,
                    priority=priority,
                )
            )
        return buttons


class CommentViewSet(ModelViewSet):
    model = Comment
    menu_label = _("All comments")  # type: ignore
    icon = "comment-add"
    add_to_admin_menu = False
    copy_view_enabled = False
    index_view_class = CommentIndexView
    ordering = "-created_at"
    list_per_page = 50
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "comment",
        "ip_address",
    )
    list_filter = ("status", "pin", "content_type")
    list_display = [
        "id",
        UserColumn("user", label=_("User")),
        TextPreviewColumn("comment", label=_("Comment")),
        StatusTagColumn(
            "get_status_display",
            label=_("Status"),
            sort_key="status",
            primary=lambda instance: instance.status == COMMENT_PUBLISHED,
        ),
        ContentObjectColumn(),
        BooleanColumn("pin", label=_("Pinned"), sort_key="pin"),
        DateColumn("created_at", label=_("Created at"), sort_key="created_at"),
    ]


comments_viewset = CommentViewSet("comments_list")


class CommentImportMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.has_perm("comments.add_comment")


class CommentImportViewSet(ViewSet):
    icon = "upload"
    menu_label = _("Import Comments")
    menu_item_class = CommentImportMenuItem

    def get_urlpatterns(self):
        return [path("", import_comments, name="index")]


comment_import_viewset = CommentImportViewSet("comments_import")


class CommentViewSetGroup(ViewSetGroup):
    menu_label = _("Comments")
    menu_icon = "comment"
    menu_order = 200
    items = (comments_viewset, comment_import_viewset)
