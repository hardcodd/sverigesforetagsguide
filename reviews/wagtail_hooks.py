from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin import messages

from reviews.views import review_viewset

from .models import Review, ReviewStatus


@hooks.register("register_admin_viewset")
def register_viewset():
    return review_viewset


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
