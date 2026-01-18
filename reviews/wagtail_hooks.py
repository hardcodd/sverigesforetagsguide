from django.utils.translation import gettext_lazy as _
from wagtail import hooks

from reviews.views import review_viewset


@hooks.register("register_admin_viewset")
def register_viewset():
    return review_viewset
