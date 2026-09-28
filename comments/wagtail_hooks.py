from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin import messages

from core.staticfiles import versioned_static

from .models import COMMENT_ON_MODERATION, Comment
from .views import CommentViewSetGroup, comments_viewset


@hooks.register("register_admin_viewset")  # type: ignore
def register_viewset():
    return CommentViewSetGroup()


@hooks.register("insert_global_admin_js")  # type: ignore
def import_comments_admin_js():
    return format_html(
        '<script src="{}"></script>', versioned_static("madloba-import-comments.js")
    )


@hooks.register("construct_main_menu")
def notify_reviews_moderation(request, *args):
    moderation_count = Comment.objects.filter(status=COMMENT_ON_MODERATION).count()
    if request.user.has_perm("comments.can_edit") and moderation_count > 0:
        moderation_url = f"%s?status={COMMENT_ON_MODERATION}" % reverse(
            f"{comments_viewset.url_prefix}:index"
        )

        button = messages.button(moderation_url, _("Moderation"))

        messages.warning(
            request,
            mark_safe(_("There are comments pending moderation.")),
            buttons=[button],
        )
