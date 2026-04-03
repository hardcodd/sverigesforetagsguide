from urllib.parse import urlparse

from django import http
from django.conf import settings
from django.utils import translation
from wagtail.contrib.redirects import models
from wagtail.contrib.redirects.middleware import RedirectMiddleware, get_redirect


class MultilingualRedirectMiddleware(RedirectMiddleware):
    """Custom wagtail 7.0 redirect middleware that respects multilingual settings and redirects to the correct language
    version of the page."""

    def process_response(self, request, response):
        if not settings.USE_I18N:
            return super().process_response(request, response)

        # No need to check for a redirect for non-404 responses.
        if response.status_code != 404:
            return response

        lang_code = request.LANGUAGE_CODE
        path = models.Redirect.normalise_path(request.get_full_path())

        # Remove the language code from the path if it exists
        if path.startswith(f"/{lang_code}/"):
            path_without_lang = path[len(lang_code) + 1 :]
        else:
            path_without_lang = path

        redirect = get_redirect(request, path_without_lang)
        if redirect is None:
            # Get the path without the query string or params
            path_without_query = urlparse(path_without_lang).path

            if path_without_lang == path_without_query:
                # don't try again if we know we will get the same response
                return response

            redirect = get_redirect(request, path_without_query)
            if redirect is None:
                return response

        if redirect.link is None:
            return response

        # If the redirect is site-agnostic, we need to add the language code back in
        language_from_path = translation.get_language_from_path(request.path_info)

        if redirect.site is None and redirect.link.startswith("/"):
            if language_from_path and not redirect.link.startswith(
                f"/{language_from_path}/"
            ):
                redirect_url = f"/{language_from_path}{redirect.link}"
            else:
                redirect_url = redirect.link

        return http.HttpResponsePermanentRedirect(redirect_url)
