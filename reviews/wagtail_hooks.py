from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin import messages

from core.staticfiles import versioned_static
from reviews.views import ReviewViewSetGroup, review_viewset

from .models import Review, ReviewStatus


@hooks.register("register_admin_viewset")
def register_viewset():
    return ReviewViewSetGroup()


@hooks.register("insert_global_admin_js")  # type: ignore
def import_reviews_admin_js():
    return format_html(
        '<script src="{}"></script>', versioned_static("madloba-import-reviews.js")
    )


@hooks.register("construct_main_menu")
def notify_reviews_moderation(request, *args):
    moderation_count = Review.objects.filter(status=ReviewStatus.MODERATION).count()
    if request.user.has_perm("reviews.can_edit") and moderation_count > 0:
        moderation_url = f"%s?status={ReviewStatus.MODERATION}" % reverse(
            f"{review_viewset.url_prefix}:index"
        )

        button = messages.button(moderation_url, _("Moderation"))

        messages.warning(
            request,
            mark_safe(_("There are reviews pending moderation.")),
            buttons=[button],
        )
