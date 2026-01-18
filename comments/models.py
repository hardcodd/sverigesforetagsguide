from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList, TabbedInterface

user_model = get_user_model()

COMMENT_PUBLISHED = 1
COMMENT_ON_MODERATION = 2
COMMENT_REJECTED = 3
COMMENT_DELETED = 4

COMMENT_STATUSES = (
    (COMMENT_PUBLISHED, _("Published")),
    (COMMENT_ON_MODERATION, _("On moderation")),
    (COMMENT_REJECTED, _("Rejected")),
    (COMMENT_DELETED, _("Deleted")),
)


class Comment(MPTTModel):
    parent = TreeForeignKey(
        "self",
        verbose_name=_("Parent"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    user = models.ForeignKey(
        user_model, verbose_name=_("User"), on_delete=models.CASCADE
    )

    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP address"), blank=True, null=True
    )

    created_at = models.DateTimeField(
        verbose_name=_("Created at"), auto_now=False, auto_now_add=True
    )
    status = models.IntegerField(verbose_name=_(
        "Status"), choices=COMMENT_STATUSES)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    comment = models.TextField(verbose_name=_("Comment text"))

    class MPTTMeta:
        order_insertion_by = ["-created_at"]

    class Meta(MPTTModel.Meta):
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        end = "..." if len(self.comment) > 50 else ""  # type: ignore
        comment = self.comment[:50] + end  # type: ignore
        return mark_safe("%s: %s" % (self.user_name, escape(comment)))

    comment_panel = [
        MultiFieldPanel(
            [
                FieldPanel("status"),
                FieldPanel("comment", classname="readonly"),
            ],
            heading=_("Comment"),
        )
    ]

    user_panel = [
        MultiFieldPanel(
            [
                FieldPanel("ip_address", classname="readonly"),
            ],
            heading=_("User"),
        )
    ]

    object_panel = [
        MultiFieldPanel(
            [
                FieldPanel("content_type", classname="readonly"),
                FieldPanel("object_id", classname="readonly"),
            ],
            heading=_("Object"),
        )
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(comment_panel, heading=_("Comment")),
            ObjectList(user_panel, heading=_("User")),
            ObjectList(object_panel, heading=_("Object")),
        ]
    )
