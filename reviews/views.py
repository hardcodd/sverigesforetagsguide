from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import csrf_protect
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, reverse
from django.utils.html import format_html
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from wagtail.admin.ui.tables import Column, UserColumn
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.images.models import Image
from wagtail.models import ContentType

from core.utils import is_ajax
from reviews.models import Review, ReviewImage, ReviewStatus


class StatusColumn(Column):
    def get_value(self, instance):
        if instance.status == ReviewStatus.PUBLISHED:
            return format_html(
                f"<span class='w-status w-status--primary'>{_('Published')}</span>"
            )
        elif instance.status == ReviewStatus.MODERATION:
            return format_html(
                f"<span class='w-status w-status--warning'>{_('On Moderation')}</span>"
            )
        elif instance.status == ReviewStatus.REJECTED:
            return format_html(
                f"<span class='w-status w-status--danger'>{_('Rejected')}</span>"
            )
        elif instance.status == ReviewStatus.DELETED:
            return format_html(
                f"<span class='w-status w-status--secondary'>{_('Deleted')}</span>"
            )
        else:
            return instance.status


class ApproveColumn(Column):
    def get_value(self, instance):
        url_1 = ""
        title_1 = ""
        url_2 = ""
        title_2 = ""

        if instance.status == ReviewStatus.MODERATION:
            url_1 = reverse("reviews:publish_review", args=[instance.id])
            title_1 = _("Approve")
            url_2 = reverse("reviews:reject_review", args=[instance.id])
            title_2 = _("Reject")
        elif instance.status == ReviewStatus.PUBLISHED:
            url_1 = reverse("reviews:reject_review", args=[instance.id])
            title_1 = _("Reject")
            url_2 = reverse("reviews:delete_review", args=[instance.id])
            title_2 = _("Delete")
        elif instance.status == ReviewStatus.REJECTED:
            url_1 = reverse("reviews:publish_review", args=[instance.id])
            title_1 = _("Approve")
            url_2 = reverse("reviews:delete_review", args=[instance.id])
            title_2 = _("Delete")
        elif instance.status == ReviewStatus.DELETED:
            url_1 = reverse("reviews:publish_review", args=[instance.id])
            title_1 = _("Approve")
            url_2 = reverse("reviews:reject_review", args=[instance.id])
            title_2 = _("Reject")

        lang = get_language()

        prefix = f"/{lang}" if lang else ""

        # remove language prefix from URLs
        url_1 = url_1[len(prefix) :] if url_1.startswith(prefix) else url_1
        url_2 = url_2[len(prefix) :] if url_2.startswith(prefix) else url_2

        return format_html(
            '<a href="{}" class="button button-small button-secondary">{}</a> \
            <a href="{}" class="button button-small no">{}</a>',
            url_1,
            title_1,
            url_2,
            title_2,
        )


class ContentTypeColumn(Column):
    def get_value(self, instance):
        return f"{instance.content_type.app_label.title()}"


class ContentObjectColumn(Column):
    def get_value(self, instance):
        if len(instance.content_object.__str__()) > 50:
            title = instance.content_object.__str__()[:50] + " ..."
        else:
            title = instance.content_object.__str__()

        lang = get_language()

        prefix = f"/{lang}" if lang else ""

        # remove language prefix from URL
        url = instance.content_object.url
        url = url[len(prefix) :] if url.startswith(prefix) else url

        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            url,
            title,
        )


class ReviewViewSet(ModelViewSet):
    model = Review
    icon = "glasses"
    menu_label = _("Reviews")
    add_to_admin_menu = True
    menu_order = 250
    search_fields = ("user__username", "comment")
    list_filter = ("status",)
    list_display = (
        "id",
        UserColumn("user", label=_("User")),
        StatusColumn("status"),
        ApproveColumn(name=""),
        ContentTypeColumn(name=_("App")),
        ContentObjectColumn(name=_("Content Object")),
    )


review_viewset = ReviewViewSet("reviews_list")


@csrf_protect
@require_POST
@login_required
def add_review(request):
    if not request.method == "POST" and not is_ajax(request):
        raise Http404

    images = request.FILES.getlist("images")
    comment = request.POST.get("comment")
    rating = int(request.POST.get("rating"))
    object_id = request.POST.get("object_id")

    try:
        content_type = request.POST.get("content_type")
        content_type = ContentType.objects.get(id=content_type)
    except ContentType.DoesNotExist:
        return JsonResponse(
            {"message": _("Invalid content type.")},
            status=400,
        )

    # Check if the user has already submitted a review for this object
    existing_review = Review.objects.filter(
        user=request.user,
        content_type=content_type,
        object_id=object_id,
    ).first()

    if existing_review:
        return JsonResponse(
            {"message": _("You have already submitted a review for this item.")},
            status=400,
        )

    try:
        if request.user.is_superuser or request.user.is_staff:
            status = ReviewStatus.PUBLISHED
        else:
            status = ReviewStatus.MODERATION
        review = Review(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
            rating=rating,
            comment=comment,
            status=status,
        )
        review.save()
    except Exception as e:
        return JsonResponse(
            {"message": _("Error saving review: %s" % str(e))},
            status=400,
        )

    if images:
        for image in images:
            if not image.name.endswith((".jpg", ".jpeg")):
                return JsonResponse(
                    {"error": _("Only .jpg and .jpeg files are allowed.")},
                    status=400,
                )
            if image.size > 2 * 1024 * 1024:
                return JsonResponse(
                    {"error": _("File size must be less than 2MB.")},
                    status=400,
                )
            wagtail_image = Image(
                title=f"[REVIEW] {request.user.username} - {review.content_object.title}",
                file=image,
                uploaded_by_user=request.user,
            )
            wagtail_image.save()
            review_image = ReviewImage(
                review=review,
                image=wagtail_image,
            )
            review_image.save()

    return JsonResponse(
        {
            "message": _(
                "Review submitted successfully. It will be published after admin approval."
            ),
        }
    )


@login_required
@permission_required("reviews.can_edit")
def delete_review(request, review_id):
    review = Review.objects.get(id=review_id)
    review.status = ReviewStatus.DELETED
    review.save()

    try:
        back_url = request.META["HTTP_REFERER"]
    except Exception:  # noqa
        back_url = review.content_object.url

    return redirect(back_url)


@login_required
@permission_required("reviews.can_edit")
def reject_review(request, review_id):
    review = Review.objects.get(id=review_id)
    review.status = ReviewStatus.REJECTED
    review.save()

    try:
        back_url = request.META["HTTP_REFERER"]
    except Exception:  # noqa
        back_url = review.content_object.url

    return redirect(back_url)


@login_required
@permission_required("reviews.can_edit")
def publish_review(request, review_id):
    review = Review.objects.get(id=review_id)
    review.status = ReviewStatus.PUBLISHED
    review.save()
    back_url = request.META["HTTP_REFERER"]
    return redirect(back_url)
