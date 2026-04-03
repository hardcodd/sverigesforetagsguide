from urllib.parse import urlparse

from django import http
from django.conf import settings
from django.utils import translation
from wagtail.contrib.redirects import models
from wagtail.contrib.redirects.middleware import RedirectMiddleware, get_redirect


class MultilingualRedirectMiddleware(RedirectMiddleware):
    """Custom Wagtail redirect middleware that respects multilingual settings
    and redirects to the correct language version of the page.
    """

    def process_response(self, request, response):
        if not settings.USE_I18N:
            return super().process_response(request, response)

        # No need to check for a redirect for non-404 responses.
        if response.status_code != 404:
            return response

        # Keep Wagtail's original behavior.
        path = models.Redirect.normalise_path(request.get_full_path())

        # Detect only the language prefix that is actually present in the URL.
        language_from_path = translation.get_language_from_path(request.path_info)

        # Remove the language code from the path if it is really present.
        if language_from_path and path.startswith(f"/{language_from_path}/"):
            path_without_lang = path[len(language_from_path) + 1 :]
        else:
            path_without_lang = path

        redirect = get_redirect(request, path_without_lang)
        if redirect is None:
            # Get the path without the query string or params.
            path_without_query = urlparse(path_without_lang).path

            if path_without_lang == path_without_query:
                # Don't try again if we know we will get the same response.
                return response

            redirect = get_redirect(request, path_without_query)
            if redirect is None:
                return response

        if redirect.link is None:
            return response

        # Default target URL.
        redirect_url = redirect.link

        # If the redirect is site-agnostic and the original request had a language
        # prefix, add that prefix back to the redirect target.
        if (
            redirect.site is None
            and redirect.link.startswith("/")
            and language_from_path
            and not redirect.link.startswith(f"/{language_from_path}/")
        ):
            redirect_url = f"/{language_from_path}{redirect.link}"

        if redirect.is_permanent:
            return http.HttpResponsePermanentRedirect(redirect_url)

        return http.HttpResponseRedirect(redirect_url)
