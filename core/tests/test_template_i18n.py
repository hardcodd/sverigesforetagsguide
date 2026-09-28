from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import polib
from django.conf import settings
from django.core import signing
from django.core.cache import caches
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template import Context, Engine
from django.template.loader import get_template, render_to_string
from django.template.loader_tags import BlockNode
from django.templatetags.cache import CacheNode
from django.templatetags.i18n import BlockTranslateNode, TranslateNode
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.translation import gettext, ngettext, override


ROOT = Path(settings.BASE_DIR)
PUBLIC_TEMPLATES = sorted(
    path
    for path in ROOT.glob("*/templates/**/*.html")
    if not {"admin", "wagtailadmin"}.intersection(path.parts)
    and path.name not in {"import_pages.html", "export_pages.html"}
)
LOCAL_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def template_name(path: Path) -> str:
    return str(path).split("/templates/", 1)[1]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.literals: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        for name, value in attrs:
            if name in {
                "alt",
                "title",
                "placeholder",
                "aria-label",
                "data-tippy-content",
            }:
                self.record(re.sub(r"<[^>]*>", "", value or ""))
            if (
                tag == "input"
                and name == "value"
                and dict(attrs).get("type") in {"submit", "button"}
            ):
                self.record(value or "")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.record(data)

    def record(self, value: str) -> None:
        if any(char.isalpha() for char in value) and value.strip() != "Madloba":
            self.literals.append(value.strip())


@override_settings(CACHES=LOCAL_CACHE)
class PublicTemplateTranslationTests(SimpleTestCase):
    def test_all_public_templates_compile_and_have_complete_compiled_translations(
        self,
    ) -> None:
        catalogs = {
            lang: polib.pofile(str(ROOT / f"app/locale/{lang}/LC_MESSAGES/django.po"))
            for lang in ("ru", "ka")
        }
        for path in PUBLIC_TEMPLATES:
            template = get_template(template_name(path)).template
            messages: list[tuple[str, str | None]] = []
            for node in template.nodelist.get_nodes_by_type(TranslateNode):
                self.assertFalse(node.noop, str(path))
                self.assertIsNone(node.filter_expression.var.lookups, str(path))
                messages.append((str(node.filter_expression.var.literal), None))
            for node in template.nodelist.get_nodes_by_type(BlockTranslateNode):
                singular, _ = node.render_token_list(node.singular)
                plural = node.render_token_list(node.plural)[0] if node.plural else None
                messages.append((singular, plural))
            for lang, catalog in catalogs.items():
                with override(lang):
                    for message, plural in messages:
                        with self.subTest(
                            template=template_name(path), lang=lang, message=message
                        ):
                            entry = catalog.find(message)
                            self.assertIsNotNone(entry)
                            assert entry is not None
                            self.assertTrue(entry.translated())
                            if plural:
                                self.assertEqual(entry.msgid_plural, plural)
                                for count in (0, 1, 2, 5, 11, 21, 22, 25, 101):
                                    translated = ngettext(message, plural, count)
                                    self.assertIn(
                                        translated, entry.msgstr_plural.values()
                                    )
                                    self.assertEqual(
                                        set(re.findall(r"%\((\w+)\)s", message)),
                                        set(re.findall(r"%\((\w+)\)s", translated)),
                                    )
                            else:
                                self.assertEqual(gettext(message), entry.msgstr)
                                self.assertEqual(
                                    set(re.findall(r"%\((\w+)\)s", message)),
                                    set(re.findall(r"%\((\w+)\)s", entry.msgstr)),
                                )

    def test_no_unmarked_user_facing_literals(self) -> None:
        for path in PUBLIC_TEMPLATES:
            source = path.read_text()
            source = re.sub(
                r"{%\s*(blocktrans|blocktranslate)\b.*?{%\s*end\1\s*%}",
                "12345",
                source,
                flags=re.S,
            )
            source = re.sub(
                r"{%\s*comment\b.*?{%\s*endcomment\s*%}", "", source, flags=re.S
            )
            source = re.sub(
                r"{%\s*block\s+body_class\s*%}.*?{%\s*endblock(?:\s+body_class)?\s*%}",
                "",
                source,
                flags=re.S,
            )
            source = re.sub(r"{#.*?#}|<!--.*?-->", "", source, flags=re.S)
            source = re.sub(r"{%.*?%}|{{.*?}}", "12345", source, flags=re.S)
            parser = VisibleTextParser()
            parser.feed(source)
            with self.subTest(template=template_name(path)):
                self.assertEqual(parser.literals, [])

    def test_every_public_fragment_cache_varies_by_active_language(self) -> None:
        for path in PUBLIC_TEMPLATES:
            template = get_template(template_name(path)).template
            for node in template.nodelist.get_nodes_by_type(CacheNode):
                caches["default"].clear()
                for language in ("ru", "ka", "ru"):
                    with self.subTest(
                        template=template_name(path),
                        fragment=node.fragment_name,
                        language=language,
                    ):
                        context = Context(
                            {
                                "lang": language,
                                "current_lang": language,
                                "fragment_language": language,
                                "page": {"pk": 1},
                                "post": {"pk": 1},
                                "organization": {"pk": 1},
                                "blog": {"pk": 1},
                                "blog_index_page": {"pk": 1},
                                "self": {"gallery": {"id": 1}},
                                "label": language,
                            }
                        )
                        with (
                            override(language),
                            patch.object(
                                node,
                                "nodelist",
                                Engine().from_string("{{ label }}").nodelist,
                            ),
                        ):
                            self.assertEqual(node.render(context), language)

    def test_error_page_renders_without_request_or_database(self) -> None:
        for language in ("ru", "ka"):
            with override(language), self.subTest(language=language):
                html = render_to_string("500.html")
                self.assertIn(f'lang="{language}"', html)
                self.assertIn(gettext("Internal server error"), html)
                self.assertNotIn("Internal server error", html)

    def test_comment_plural_forms_render_in_both_languages(self) -> None:
        with (
            patch("comments.templatetags.comments.ContentType.objects.get_for_model"),
            patch("comments.templatetags.comments.Comment.objects.filter") as comments,
        ):
            for language in ("ru", "ka"):
                for count in (0, 1, 2, 5, 11, 21, 22, 25):
                    comments.return_value.count.return_value = count
                    with (
                        override(language),
                        self.subTest(language=language, count=count),
                    ):
                        html = render_to_string(
                            "comments/header.html", {"page": SimpleNamespace(pk=1)}
                        )
                        expected = ngettext(
                            "%(counter)s comment", "%(counter)s comments", count
                        ) % {"counter": count}
                        self.assertIn(expected, html)
                        self.assertNotIn("comment<", html)

    def test_rating_accessible_text_is_localized(self) -> None:
        for language in ("ru", "ka"):
            with override(language), self.subTest(language=language):
                html = render_to_string("includes/stars-rating.html", {"stars": 4})
                self.assertIn(
                    gettext("Rating: %(rating)s out of 5") % {"rating": 4}, html
                )
                self.assertNotIn("gray stars", html)
                self.assertNotIn("red stars", html)

    def test_old_review_shows_its_localized_date(self) -> None:
        created = datetime(2020, 1, 2, tzinfo=timezone.utc)
        review = SimpleNamespace(
            pk=1, created_at=created, user="Author", rating=4, comment="", images=[]
        )
        for language in ("ru", "ka"):
            with override(language), self.subTest(language=language):
                html = render_to_string("reviews/review.html", {"review": review})
                self.assertIn(date_format(created, "DATE_FORMAT"), html)
                self.assertIn("2020", html)

    def test_language_switcher_exposes_language_names(self) -> None:
        request = RequestFactory().get("/ka/search/?query=test")
        with override("ka"):
            html = render_to_string(
                "includes/lang-switcher.html",
                {"request": request, "LANGUAGES": settings.LANGUAGES},
            )
        for name in ("ქართული", "Русский", "English"):
            self.assertIn(f'<div class="sr-only">{name}</div>', html)
        self.assertIn('href="/ka/search/?query=test"', html)
        self.assertNotIn('alt="ka"', html)

    def test_address_heading_escapes_user_input_and_translates_phrase(self) -> None:
        template = get_template("catalog/organizations.html").template
        node = template.nodelist.get_nodes_by_type(BlockTranslateNode)[0]
        request = RequestFactory().get(
            "/catalog/", {"address": '<img src=x onerror="alert(1)">'}
        )
        for language in ("ru", "ka"):
            with override(language), self.subTest(language=language):
                context = Context({"request": request})
                with context.bind_template(template):
                    node.render(context)
                html = render_to_string(
                    "includes/section-header.html",
                    {"section_title": context["section_title"]},
                )
                self.assertNotIn("<img", html)
                self.assertIn("&lt;img", html)
                self.assertNotIn("By address", html)

    def test_maps_request_the_active_language(self) -> None:
        template = get_template("catalog/organization_type_map.html").template
        scripts = next(
            node
            for node in template.nodelist.get_nodes_by_type(BlockNode)
            if node.name == "extra_js"
        )
        for language in ("ru", "ka"):
            with override(language), self.subTest(language=language):
                context = Context({"GOOGLE_MAPS_API_KEY": "test-key"})
                with context.bind_template(template):
                    html = scripts.render(context)
                self.assertIn(f"&language={language}&libraries=marker", html)
                with patch("core.maps.Path.is_file", return_value=True):
                    html = render_to_string(
                        "catalog/includes/organization-map.html",
                        {
                            "page": SimpleNamespace(pk=1, ll="41.7,44.8"),
                            "GOOGLE_MAPS_API_KEY": "test-key",
                        },
                    )
                self.assertIn(f'&language={language}"', html)
                self.assertIn(gettext("Location map"), html)


@override_settings(CACHES=LOCAL_CACHE)
class ReviewFragmentLanguageTests(TestCase):
    def test_more_reviews_keep_page_language_despite_browser_preference(self) -> None:
        review = SimpleNamespace(
            pk=1,
            created_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
            user="Author",
            rating=4,
            comment="",
            images=[],
        )
        with (
            patch("reviews.views.Page.objects.get"),
            patch(
                "reviews.views.get_reviews",
                return_value=Paginator([review] * 21, 10).page(2),
            ),
        ):
            for language, prefix in (("ru", ""), ("ka", "/ka"), ("en", "/en")):
                with override(language):
                    url = reverse("load-more-reviews")
                    expected_rating = gettext("Rating: %(rating)s out of 5") % {
                        "rating": 4
                    }
                    expected_date = date_format(review.created_at, "DATE_FORMAT")
                with self.subTest(language=language):
                    self.assertEqual(url, f"{prefix}/reviews/load-more/")
                    with override(language):
                        response = self.client.get(
                            url,
                            {"page": "2", "token": signing.dumps(1)},
                            HTTP_ACCEPT_LANGUAGE="en",
                        )
                    assert isinstance(response, JsonResponse)
                    payload = json.loads(response.content)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["Content-Language"], language)
                    self.assertEqual(payload["page_number"], 3)
                    for html in payload["reviews"]:
                        self.assertIn(expected_rating, html)
                        self.assertIn(expected_date, html)
            self.assertEqual(
                reverse("reviews:load_more_reviews"), "/reviews/load-more/"
            )

    def test_more_reviews_link_has_language_prefix(self) -> None:
        review = SimpleNamespace(
            pk=1,
            created_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
            user="Author",
            rating=4,
            comment="",
            images=[],
        )
        with patch(
            "reviews.templatetags.reviews.paginate",
            return_value=Paginator([review] * 21, 10).page(1),
        ):
            for language, prefix in (("ru", ""), ("ka", "/ka"), ("en", "/en")):
                with override(language), self.subTest(language=language):
                    html = render_to_string(
                        "reviews/reviews-list.html",
                        {
                            "page": SimpleNamespace(pk=1, content_type_id=1),
                            "request": RequestFactory().get("/"),
                        },
                    )
                    self.assertIn(
                        f'href="{prefix}/reviews/load-more/?page=2&token=', html
                    )
