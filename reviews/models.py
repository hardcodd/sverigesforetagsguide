from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultipleChooserPanel
from wagtail.models import ClusterableModel, Orderable, ParentalKey

from core.utils import starsort

USER_MODEL = get_user_model()


class ReviewStatus(models.TextChoices):
    MODERATION = "moderation", _("Moderation")
    PUBLISHED = "published", _("Published")
    REJECTED = "rejected", _("Rejected")
    DELETED = "deleted", _("Deleted")


class Review(ClusterableModel):
    user = models.ForeignKey(
        USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.MODERATION,
    )

    rating = models.PositiveIntegerField(
        verbose_name=_("Rating"),
        help_text=_("Rating value"),
    )

    comment = models.TextField(
        verbose_name=_("Comment"),
        help_text=_("Comment text"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("Creation date and time"),
    )
    go_live_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Go live at"),
        help_text=_("Date and time when the review will be published"),
    )

    panels = [
        FieldPanel("user", read_only=True),
        "status",
        "rating",
        "comment",
        "go_live_at",
        MultipleChooserPanel(
            "images",
            heading=_("Images"),
            chooser_field_name="image",
        ),
    ]

    def __str__(self):
        return f"{self.user}"


class ReviewImage(Orderable):
    review = ParentalKey(
        "reviews.Review",
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("Image"),
    )

    panels = [
        FieldPanel("image"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Image")
        verbose_name_plural = _("Images")


@receiver(post_save, sender=Review)
def update_organization_rating_after_add_review(sender, instance, *args, **kwargs):
    update_avg_rating(sender, instance, **kwargs)
    update_rating_score(sender, instance, *args, **kwargs)


@receiver(post_delete, sender=Review)
def update_organization_rating_after_delete_review(sender, instance, *args, **kwargs):
    update_avg_rating(sender, instance, **kwargs)
    update_rating_score(sender, instance, *args, **kwargs)


def update_avg_rating(sender, instance, **kwargs):
    """Update content_object avg_rating after Review save"""

    if instance.status == ReviewStatus.PUBLISHED:
        content_object = instance.content_object
        all_reviews = Review.objects.filter(
            content_type=ContentType.objects.get_for_model(content_object),
            object_id=content_object.pk,
            status=ReviewStatus.PUBLISHED,
        )
        avg_rating = all_reviews.aggregate(models.Avg("rating"))["rating__avg"]
        content_object.avg_rating = avg_rating
        content_object.save()


def update_rating_score(sender, instance, *args, **kwargs):
    obj = instance.content_object

    if not hasattr(obj, "avg_rating"):
        return

    obj_reviews = sender.objects.filter(
        status=ReviewStatus.PUBLISHED,
        object_id=obj.id,
        content_type=obj.content_type,
        # parent=None,
        rating__gte=0,
    )

    stars = (
        obj_reviews.filter(rating=5).count(),
        obj_reviews.filter(rating=4).count(),
        obj_reviews.filter(rating=3).count(),
        obj_reviews.filter(rating=2).count(),
        obj_reviews.filter(rating=1).count(),
    )

    obj.rating_score = float(starsort(stars))
    obj.save()
