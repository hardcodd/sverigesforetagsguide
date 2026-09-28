from django.http import Http404, HttpRequest, JsonResponse
from django.template.loader import render_to_string

from gallery.models import GalleryPostPage
from gallery.services import get_gallery_images_service


def load_more_images(request: HttpRequest) -> JsonResponse:
    """Return the requested gallery batch, with strict pagination errors."""
    page_id = request.GET.get("page-id")

    if not isinstance(page_id, str) or not page_id.isdigit():
        raise Http404

    try:
        page = GalleryPostPage.objects.get(pk=page_id)
    except GalleryPostPage.DoesNotExist:
        raise Http404

    images = get_gallery_images_service(page, request, 24)

    if not images:
        raise Http404

    response = []

    for image in images:
        image_html = render_to_string(
            "gallery/includes/image-item.html", {"image": image}
        )
        response.append(image_html)

    return JsonResponse(response, safe=False)
