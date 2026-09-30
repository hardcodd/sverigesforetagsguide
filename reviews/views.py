import json

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import csrf_protect
from django.core import signing
from django.http import Http404, HttpRequest, JsonResponse
from django.shortcuts import redirect, render, reverse
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.views.decorators.http import require_POST
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.tables import DateColumn, StatusTagColumn, UserColumn
from wagtail.admin.viewsets.base import ViewSet, ViewSetGroup
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.widgets.button import ListingButton
from wagtail.images.models import Image
from wagtail.models import ContentType, Page

from core.admin_columns import (
    ContentObjectColumn,
    RelatedContentIndexView,
    TextPreviewColumn,
    without_language_prefix,
)
from core.utils import is_ajax
from reviews.models import (
    MAX_REVIEW_RATING,
    MIN_REVIEW_RATING,
    Review,
    ReviewImage,
    ReviewStatus,
)
from reviews.services import ReviewImportError, import_review_row, import_review_rows
from reviews.templatetags.reviews import get_reviews


class ReviewIndexView(RelatedContentIndexView):
    page_title = _("Reviews")
    add_item_label = _("Add review")

    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        if not self.request.user.has_perm("reviews.can_edit"):
            return buttons

        actions = []
        if instance.status == ReviewStatus.MODERATION:
            actions = [
                (_("Approve"), "reviews:publish_review", "success"),
                (_("Reject"), "reviews:reject_review", "cross"),
            ]
        elif instance.status == ReviewStatus.PUBLISHED:
            actions = [
                (_("Reject"), "reviews:reject_review", "cross"),
                (_("Delete"), "reviews:delete_review", "bin"),
            ]
        elif instance.status == ReviewStatus.REJECTED:
            actions = [
                (_("Approve"), "reviews:publish_review", "success"),
                (_("Delete"), "reviews:delete_review", "bin"),
            ]
        elif instance.status == ReviewStatus.DELETED:
            actions = [
                (_("Approve"), "reviews:publish_review", "success"),
                (_("Reject"), "reviews:reject_review", "cross"),
            ]

        for priority, (label, url_name, icon_name) in enumerate(actions, start=40):
            buttons.append(
                ListingButton(
                    label,
                    url=without_language_prefix(
                        reverse(url_name, args=[instance.pk])
                    ),
                    icon_name=icon_name,
                    priority=priority,
                )
            )
        return buttons


class ReviewViewSet(ModelViewSet):
    model = Review
    icon = "glasses"
    menu_label = _("All reviews")
    add_to_admin_menu = False
    copy_view_enabled = False
    index_view_class = ReviewIndexView
    ordering = "-created_at"
    list_per_page = 50
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "comment",
    )
    list_filter = ("status", "rating", "content_type")
    list_display = (
        "id",
        UserColumn("user", label=_("User")),
        TextPreviewColumn("comment", label=_("Review")),
        "rating",
        StatusTagColumn(
            "get_status_display",
            label=_("Status"),
            sort_key="status",
            primary=lambda instance: instance.status == ReviewStatus.PUBLISHED,
        ),
        ContentObjectColumn(),
        DateColumn("created_at", label=_("Created at"), sort_key="created_at"),
    )


review_viewset = ReviewViewSet("reviews_list")


class ReviewImportMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.has_perm("reviews.add_review")


class ReviewImportViewSet(ViewSet):
    icon = "upload"
    menu_label = _("Import Reviews")
    menu_item_class = ReviewImportMenuItem

    def get_urlpatterns(self):
        return [path("", import_reviews, name="index")]


review_import_viewset = ReviewImportViewSet("reviews_import")


class ReviewViewSetGroup(ViewSetGroup):
    menu_label = _("Reviews")
    menu_icon = "pick"
    menu_order = 250
    items = (review_viewset, review_import_viewset)


@csrf_protect
@require_POST
@login_required
def add_review(request: HttpRequest) -> JsonResponse:
    if not request.method == "POST" and not is_ajax(request):
        raise Http404

    user = getattr(request, "user")
    images = request.FILES.getlist("images")
    comment = request.POST.get("comment")
    try:
        rating = int(request.POST.get("rating", ""))
    except (TypeError, ValueError):
        rating = None

    if rating is None or not MIN_REVIEW_RATING <= rating <= MAX_REVIEW_RATING:
        return JsonResponse(
            {"message": _("Rating must be between 1 and 5.")},
            status=400,
        )

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
        user=user,
        content_type=content_type,
        object_id=object_id,
    ).first()

    if existing_review:
        return JsonResponse(
            {"message": _("You have already submitted a review for this item.")},
            status=400,
        )

    try:
        if user.is_superuser or user.is_staff:
            status = ReviewStatus.PUBLISHED
        else:
            status = ReviewStatus.MODERATION
        review = Review(
            user=user,
            content_type=content_type,
            object_id=object_id,
            rating=rating,
            comment=comment,
            status=status,
        )
        review.save()
    except Exception as e:
        return JsonResponse(
            {"message": _("Error saving review: %(error)s") % {"error": str(e)}},
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
                title=f"[REVIEW] {user.username} - {review.content_object.title}",
                file=image,
                uploaded_by_user=user,
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


def load_more_reviews(request: HttpRequest) -> JsonResponse:
    """Return a published review batch or a strict pagination error."""
    token = request.GET.get("token")

    if not token:
        return JsonResponse({"error": "Token is required"}, status=400)

    page_pk = signing.loads(token)
    page = Page.objects.get(pk=page_pk)

    reviews = get_reviews({"request": request}, page.specific)

    return JsonResponse(
        {
            "reviews": [
                render_to_string("reviews/review.html", {"review": r})
                for r in reviews.object_list
            ],
            "page_number": reviews.next_page_number() if reviews.has_next() else None,
        }
    )


@permission_required("reviews.add_review", raise_exception=True)
def import_reviews(request):
    return render(request, "catalog/admin/import_reviews.html", {})


@require_POST
@permission_required("reviews.add_review", raise_exception=True)
def import_review(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "code": "invalid_json", "message": _("Invalid JSON.")},
            status=400,
        )

    try:
        if isinstance(data, list):
            results = import_review_rows(data)
            return JsonResponse(
                {
                    "success": True,
                    "results": [
                        {
                            "success": result.success,
                            "code": result.code,
                            "message": result.message,
                        }
                        for result in results
                    ],
                }
            )
        import_review_row(data)
    except ReviewImportError as error:
        return JsonResponse(
            {"success": False, "code": error.code, "message": str(error)},
            status=error.status,
        )

    return JsonResponse(
        {
            "success": True,
            "code": "imported",
            "message": _("Review created successfully."),
        }
    )
