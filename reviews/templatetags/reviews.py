from django import template
from django.db.models import Avg

from reviews.models import Review, ReviewStatus

register = template.Library()


@register.simple_tag
def get_reviews_count(page):
    """
    Return the number of reviews for a given page.
    """
    return Review.objects.filter(
        content_type=page.content_type,
        object_id=page.pk,
        status=ReviewStatus.PUBLISHED,
    ).count()


@register.simple_tag
def get_reviews(page):
    """
    Return the reviews for a given page.
    """
    return Review.objects.filter(
        content_type=page.content_type,
        object_id=page.pk,
        status=ReviewStatus.PUBLISHED,
    ).order_by("-created_at")


@register.simple_tag
def get_total_reviews_count():
    """
    Return total reviews count over the website
    """
    return Review.objects.filter(status=ReviewStatus.PUBLISHED).count()
