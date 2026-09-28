import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils.translation import override
from wagtail.blocks import StructValue
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file, get_test_image_file_svg
from wagtail.models import Page, Site

from blog.models import BlogCategoryPage, BlogIndexPage, BlogPostPage
from core.blocks import QnABlock
from core.models import SiteSettings
from core.templatetags.seo import absolute_media_url, faq_jsonld, social_image
from home.models import FlatPage


def faq_value(items: list[tuple[str, str]]) -> StructValue:
    return QnABlock().to_python(
        {
            "title": "Questions",
            "items": [
                {"type": "item", "value": {"question": question, "answer": answer}}
                for question, answer in items
            ],
        }
    )


class FAQMetadataTests(SimpleTestCase):
    def test_rendered_block_matches_visible_questions_and_rich_answers(self):
        value = faq_value(
            [('A "quote" & café?', "<p>Answer <b>one</b>.</p><p>Next line.</p>")]
        )
        html = QnABlock().render(value)
        document = BeautifulSoup(html, "html.parser")
        scripts = document.select('script[type="application/ld+json"]')
        self.assertEqual(len(scripts), 1)
        data = json.loads(scripts[0].string)
        self.assertEqual(data["@type"], "FAQPage")
        question = data["mainEntity"][0]
        self.assertEqual(question["@type"], "Question")
        self.assertEqual(
            question["name"], document.select_one(".accordion__heading").text
        )
        self.assertEqual(question["acceptedAnswer"]["@type"], "Answer")
        self.assertHTMLEqual(
            question["acceptedAnswer"]["text"],
            document.select_one(".accordion__content").decode_contents(),
        )

    def test_empty_and_incomplete_items_are_omitted(self):
        for items in ([], [(" ", "<p>Answer</p>")], [("Question", "<p>&nbsp;</p>")]):
            with self.subTest(items=items):
                self.assertEqual(faq_jsonld(faq_value(items)), "")
        document = BeautifulSoup(
            faq_jsonld(faq_value([("", ""), ("Valid?", "<p>Yes</p>")])),
            "html.parser",
        )
        self.assertEqual(len(json.loads(document.script.string)["mainEntity"]), 1)

    def test_content_cannot_close_jsonld_script(self):
        question = '</script><script>alert("question")</script>'
        answer = '<p>&amp; "quoted"</p></script><script>alert("answer")</script>'
        document = BeautifulSoup(
            faq_jsonld(faq_value([(question, answer)])), "html.parser"
        )
        self.assertEqual(len(document.select("script")), 1)
        data = json.loads(document.script.string)
        self.assertEqual(data["mainEntity"][0]["name"], question)
        self.assertIn("</script>", data["mainEntity"][0]["acceptedAnswer"]["text"])

    def test_multiple_blocks_share_the_page_identity(self):
        for question in ("First?", "Second?"):
            document = BeautifulSoup(
                faq_jsonld(
                    faq_value([(question, "<p>Yes</p>")]),
                    "https://example.com/en/post/",
                ),
                "html.parser",
            )
            self.assertEqual(
                json.loads(document.script.string)["@id"],
                "https://example.com/en/post/#faq",
            )

    def test_media_urls_are_absolute_and_keep_cdn_host(self):
        request = RequestFactory().get("/en/post/", secure=True)
        for source, expected in (
            ("/media/image.jpg", "https://testserver/media/image.jpg"),
            ("https://cdn.example/image.jpg", "https://cdn.example/image.jpg"),
            ("//cdn.example/image.jpg", "https://cdn.example/image.jpg"),
            ("", ""),
        ):
            self.assertEqual(absolute_media_url(request, source), expected)


class OpenGraphTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        cls.blog = root.add_child(instance=BlogIndexPage(title="Blog", slug="seo-blog"))
        cls.category = cls.blog.add_child(
            instance=BlogCategoryPage(title="Category", slug="category")
        )
        cls.post = cls.category.add_child(
            instance=BlogPostPage(title="Article", slug="article")
        )
        Site.objects.update(is_default_site=False)
        cls.site = Site.objects.create(
            hostname="testserver",
            port=443,
            root_page=cls.blog,
            site_name="Test site",
            is_default_site=True,
        )

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.enable = override_settings(MEDIA_ROOT=self.media.name)
        self.enable.enable()
        self.addCleanup(self.enable.disable)
        self.request = RequestFactory().get(
            "/en/category/article/?utm_source=test", secure=True
        )
        self.request.user = AnonymousUser()
        self.logo = Image.objects.create(title="Site logo", file=get_test_image_file())

    def render_metadata(self, page: Page, logo: Image | None = None):
        return BeautifulSoup(
            render_to_string(
                "includes/open_graph.html",
                {
                    "page": page,
                    "canonical_url": "https://testserver/en/category/article/",
                    "request": self.request,
                    "settings": SimpleNamespace(
                        core=SimpleNamespace(SiteSettings=SimpleNamespace(logo=logo))
                    ),
                },
            ),
            "html.parser",
        )

    def test_article_metadata_uses_seo_fields_and_page_image(self):
        self.post.seo_title = 'SEO "title" & café'
        self.post.search_description = 'Description "quoted" & text'
        self.post.image = Image.objects.create(
            title='Article "image"', file=get_test_image_file(size=(1600, 900))
        )
        document = self.render_metadata(self.post, self.logo)
        metadata = {
            tag["property"]: tag["content"] for tag in document.select("meta[property]")
        }
        self.assertEqual(metadata["og:title"], self.post.seo_title)
        self.assertEqual(metadata["og:description"], self.post.search_description)
        self.assertEqual(metadata["og:type"], "article")
        self.assertEqual(metadata["og:site_name"], "Test site")
        self.assertEqual(metadata["og:url"], "https://testserver/en/category/article/")
        rendition = self.post.image.get_rendition("max-1200x630|format-jpeg")
        self.assertEqual(
            metadata["og:image"], self.request.build_absolute_uri(rendition.url)
        )
        self.assertEqual(metadata["og:image:width"], str(rendition.width))
        self.assertEqual(metadata["og:image:height"], str(rendition.height))
        self.assertEqual(metadata["og:image:alt"], self.post.image.title)

    def test_generic_page_uses_clean_title_and_logo(self):
        page = FlatPage(title="A [[marked]] title")
        document = self.render_metadata(page, self.logo)
        self.assertEqual(
            document.select_one('[property="og:title"]')["content"], "A marked title"
        )
        self.assertEqual(
            document.select_one('[property="og:type"]')["content"], "website"
        )
        self.assertIsNotNone(document.select_one('[property="og:image"]'))
        self.assertIsNone(document.select_one('[property="og:description"]'))

    def test_no_image_emits_no_broken_image_tags(self):
        self.assertIsNone(
            self.render_metadata(self.post).select_one('[property="og:image"]')
        )

    def test_svg_page_image_uses_raster_logo(self):
        self.post.image = Image.objects.create(
            title="Vector image", file=get_test_image_file_svg()
        )
        document = self.render_metadata(self.post, self.logo)
        rendition = self.logo.get_rendition("max-1200x630|format-jpeg")
        self.assertEqual(
            document.select_one('[property="og:image"]')["content"],
            self.request.build_absolute_uri(rendition.url),
        )

    def test_svg_logo_does_not_break_blog_index_or_emit_svg_preview(self):
        logo = Image.objects.create(title="Vector logo", file=get_test_image_file_svg())
        site_settings = SiteSettings.load()
        site_settings.logo = logo
        site_settings.save()
        response = self.blog.serve(self.request)
        response.render()
        document = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            document.head.select_one('[property="og:title"]')["content"], "Blog"
        )
        self.assertIsNone(document.head.select_one('[property^="og:image"]'))
        self.assertTrue(
            any(".svg" in tag.get("src", "") for tag in document.select("header img"))
        )

    def test_raster_page_image_takes_priority_over_svg_logo(self):
        self.post.image = self.logo
        vector_logo = Image.objects.create(
            title="Vector logo", file=get_test_image_file_svg()
        )
        document = self.render_metadata(self.post, vector_logo)
        rendition = self.logo.get_rendition("max-1200x630|format-jpeg")
        self.assertEqual(
            document.select_one('[property="og:image"]')["content"],
            self.request.build_absolute_uri(rendition.url),
        )

    def test_svg_page_and_svg_logo_have_no_social_image(self):
        vector_image = Image.objects.create(
            title="Vector", file=get_test_image_file_svg()
        )
        self.post.image = vector_image
        document = self.render_metadata(self.post, vector_image)
        self.assertIsNone(document.select_one('[property^="og:image"]'))

    def test_plain_image_field_is_supported(self):
        from authors.models import AuthorPage

        self.assertEqual(social_image(AuthorPage(image=self.logo)), self.logo)

    def test_metadata_uses_active_translation(self):
        self.post.title_en = "English title"
        self.post.title_ka = "ქართული"
        self.post.seo_title_en = ""
        self.post.seo_title_ka = ""
        for language, expected in (("en", "English title"), ("ka", "ქართული")):
            with override(language):
                document = self.render_metadata(self.post)
                self.assertEqual(
                    document.select_one('[property="og:title"]')["content"], expected
                )

    def test_full_article_keeps_blogposting_and_renders_faq_and_og(self):
        self.post.content = [
            ("qna", faq_value([("Visible question?", "<p>Visible answer</p>")]))
        ]
        response = self.post.serve(self.request)
        response.render()
        document = BeautifulSoup(response.content, "html.parser")
        schemas = [
            json.loads(script.string)
            for script in document.select('script[type="application/ld+json"]')
        ]
        self.assertEqual(
            [data["@type"] for data in schemas], ["BlogPosting", "FAQPage"]
        )
        self.assertEqual(len(document.head.select('[property="og:title"]')), 1)
        self.assertEqual(len(document.head.select('[property="og:url"]')), 1)
        self.assertEqual(
            document.select_one(".accordion__heading").text, "Visible question?"
        )

    def test_article_without_faq_does_not_emit_faqpage(self):
        response = self.post.serve(self.request)
        response.render()
        document = BeautifulSoup(response.content, "html.parser")
        schemas = [
            json.loads(script.string)
            for script in document.select('script[type="application/ld+json"]')
        ]
        self.assertEqual([data["@type"] for data in schemas], ["BlogPosting"])

    def test_rich_text_page_links_are_expanded_in_faq_answers(self):
        answer = (
            f'<p>Visit <a linktype="page" id="{self.category.pk}">the category</a>.</p>'
        )
        html = QnABlock().render(
            faq_value([("Where?", answer)]),
            context={"page": self.post, "request": self.request},
        )
        document = BeautifulSoup(html, "html.parser")
        data = json.loads(document.script.string)
        rendered_answer = data["mainEntity"][0]["acceptedAnswer"]["text"]
        self.assertNotIn("linktype", rendered_answer)
        self.assertIn('href="', rendered_answer)
        self.assertHTMLEqual(
            rendered_answer,
            document.select_one(".accordion__content").decode_contents(),
        )
        self.assertEqual(
            data["@id"], self.post.get_full_url(request=self.request) + "#faq"
        )
