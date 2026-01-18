from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.utils.translation import gettext_lazy as _
from wagtail.admin.ui.tables import StatusTagColumn, UserColumn
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.images.models import Image
from wagtail.models import ContentType

from core.utils import is_ajax
from reviews.models import Review, ReviewImage, ReviewStatus


class ReviewViewSet(ModelViewSet):
    model = Review
    icon = "glasses"
    menu_label = _("Reviews")
    add_to_admin_menu = True
    menu_order = 250
    list_display = (
        "id",
        UserColumn("user", label=_("User")),
        "content_type",
        "content_object",
        "rating",
        "status",
        StatusTagColumn(
            "status",
            lambda obj: obj.status == ReviewStatus.PUBLISHED,
            label=_("Status"),
        ),
    )


review_viewset = ReviewViewSet("reviews_list")


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

    try:
        review = Review(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
            rating=rating,
            comment=comment,
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
