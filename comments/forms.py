from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

COMMENT_MAX_LENGTH = getattr(settings, 'COMMENT_MAX_LENGTH', 3000)


class CommentForm(forms.Form):
    content_type = forms.CharField(widget=forms.HiddenInput)
    object_id = forms.IntegerField(widget=forms.HiddenInput)
    parent_id = forms.IntegerField(widget=forms.HiddenInput)

    comment = forms.CharField(
        min_length=3,
        max_length=COMMENT_MAX_LENGTH,
        required=False,
        widget=forms.Textarea({
            'placeholder': _('Add comment ...'),
            'rows': 1
        })
    )
