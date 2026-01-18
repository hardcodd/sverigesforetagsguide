from django.utils.translation import gettext_lazy as _
from wagtail import hooks

from subscription.views import premium_subscription_viewset


@hooks.register("register_admin_viewset")  # type: ignore
def register_viewset():
    return premium_subscription_viewset
