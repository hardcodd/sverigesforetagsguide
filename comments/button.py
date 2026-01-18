from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from wagtail.contrib.modeladmin.helpers import PageButtonHelper as WagtailPageButtonHelper

from .models import COMMENT_DELETED, COMMENT_PUBLISHED, COMMENT_REJECTED


class CommentButtonHelper(WagtailPageButtonHelper):
    publish_button_classnames = []

    def publish_button(self, pk, classnames_add=None, classnames_exclude=None):
        classnames_add = classnames_add or []
        classnames_exclude = classnames_exclude or []
        classnames = self.publish_button_classnames + classnames_add
        cn = self.finalise_classname(classnames, classnames_exclude)
        return {
            'url': reverse('comments:publish_comment', args=[pk]),
            'label': _('Publish'),
            'classname': cn,
            'title': _('Publish this %s') % self.verbose_name,
        }

    def reject_button(self, pk, classnames_add=None, classnames_exclude=None):
        classnames_add = classnames_add or []
        classnames_exclude = classnames_exclude or []
        classnames = self.publish_button_classnames + classnames_add
        cn = self.finalise_classname(classnames, classnames_exclude)
        return {
            'url': reverse('comments:reject_comment', args=[pk]),
            'label': _('Reject'),
            'classname': cn,
            'title': _('Reject this %s') % self.verbose_name,
        }

    def delete_button(self, pk, classnames_add=None, classnames_exclude=None):
        classnames_add = classnames_add or []
        classnames_add.append('no button-secondary')
        classnames_exclude = classnames_exclude or []
        classnames = self.publish_button_classnames + classnames_add
        cn = self.finalise_classname(classnames, classnames_exclude)
        return {
            'url': reverse('comments:delete_comment', args=[pk]),
            'label': _('Delete'),
            'classname': cn,
            'title': _('Delete this %s') % self.verbose_name,
        }

    def get_buttons_for_obj(self, obj, exclude=None, classnames_add=None, classnames_exclude=None):
        exclude = exclude or ['delete']  # Unable original "Delete" button
        classnames_add = classnames_add or []
        classnames_exclude = classnames_exclude or []
        ph = self.permission_helper
        usr = self.request.user
        pk = getattr(obj, self.opts.pk.attname)
        buttons = super().get_buttons_for_obj(obj, exclude, classnames_add, classnames_exclude)

        custom_buttons = [
            self.publish_button,
            self.reject_button,
            self.delete_button
        ]

        _buttons = []

        for button in custom_buttons:
            status = self._get_button_status(button)
            if button.__name__ not in exclude and ph.user_can_edit_obj(usr, obj) and obj.status != status:
                _buttons.append(button(pk, classnames_add, classnames_exclude))

        return [buttons[0]] + _buttons + buttons[1:]

    def _get_button_status(self, button):
        button_name = button.__name__
        status = None
        if button_name.startswith('publish'):
            status = COMMENT_PUBLISHED
        elif button_name.startswith('reject'):
            status = COMMENT_REJECTED
        elif button_name.startswith('delete'):
            status = COMMENT_DELETED
        return status
