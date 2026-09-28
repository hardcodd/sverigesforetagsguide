from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse

from comments.views import (
    CommentViewSetGroup,
    comment_import_viewset,
    comments_viewset,
)
from reviews.views import ReviewViewSetGroup, review_import_viewset, review_viewset


class FeedbackAdminMenuTests(SimpleTestCase):
    def test_review_menu_contains_listing_then_import(self):
        self.assertEqual(
            ReviewViewSetGroup().registerables,
            [review_viewset, review_import_viewset],
        )

    def test_comment_menu_contains_listing_then_import(self):
        self.assertEqual(
            CommentViewSetGroup().registerables,
            [comments_viewset, comment_import_viewset],
        )

    def test_legacy_import_update_urls_are_removed(self):
        for url_name in (
            "import-organizations",
            "update-organizations",
            "import-reviews",
            "import-comments",
            "catalog:import_organization",
            "catalog:update_organization",
        ):
            with self.subTest(url_name=url_name):
                with self.assertRaises(NoReverseMatch):
                    reverse(url_name)

    def test_current_import_urls_remain_available(self):
        self.assertTrue(reverse("import-pages"))
        self.assertTrue(reverse("export-pages"))
        self.assertTrue(reverse("reviews_import:index"))
        self.assertTrue(reverse("comments_import:index"))
