from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page

from comments.models import COMMENT_PUBLISHED, Comment


class ImportCommentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root_page = Page.objects.get(depth=1)
        cls.page = root_page.add_child(
            instance=Page(title="Comment target", slug="comment-target")
        )
        user_model = get_user_model()
        cls.importer = user_model.objects.create_user(
            username="comment-importer",
            password="test-password",
            is_staff=True,
        )
        add_comment_permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Comment),
            codename="add_comment",
        )
        access_admin_permission = Permission.objects.get(
            content_type__app_label="wagtailadmin",
            codename="access_admin",
        )
        cls.importer.user_permissions.add(
            access_admin_permission,
            add_comment_permission,
        )

    def setUp(self):
        self.client.force_login(self.importer)

    def payload(self, **overrides):
        data = {
            "id": self.page.pk,
            "text": "Imported comment",
            "user": "Alice Original / alice",
            "date": "2026-08-10 12:30",
        }
        data.update(overrides)
        return data

    def post_import(self, payload):
        return self.client.post(
            reverse("comments:import_comment"),
            data=payload,
            content_type="application/json",
        )

    def test_import_admin_page_renders(self):
        response = self.client.get(reverse("comments_import:index"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<th>id</th>", html=True)
        self.assertContains(response, "<th>text</th>", html=True)
        self.assertNotContains(response, "content_type")
        self.assertNotContains(response, "csv-table")

    def test_admin_listing_renders_imported_comment(self):
        self.post_import(self.payload())

        response = self.client.get(reverse("comments_list:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Imported comment")
        self.assertContains(response, "Comment target")

    def test_import_uses_existing_username_without_changing_name(self):
        user_model = get_user_model()
        existing_user = user_model.objects.create_user(
            username="alice",
            first_name="Existing Name",
        )

        response = self.post_import(self.payload(user="Different CSV Name / alice"))

        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get()
        self.assertEqual(comment.user, existing_user)
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.first_name, "Existing Name")

    def test_import_creates_explicit_username(self):
        response = self.post_import(
            self.payload(user="Маша Митяева / m_234_masha_mityaeva")
        )

        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get()
        self.assertEqual(comment.user.username, "m_234_masha_mityaeva")
        self.assertEqual(comment.user.first_name, "Маша Митяева")

    def test_import_without_username_uses_existing_imported_user(self):
        existing_user = get_user_model().objects.create_user(
            username="m_123_masha_mityaeva",
            first_name="Маша Митяева",
        )

        response = self.post_import(self.payload(user="Маша Митяева"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.get().user, existing_user)

    @patch("core.import_users.random.randint", side_effect=[234, 235])
    def test_import_without_username_retries_when_generated_username_exists(
        self, random_number
    ):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="m_234_masha_mitiaeva",
            first_name="Another User",
        )
        user_model.objects.create_user(
            username="regular-masha",
            first_name="Маша Митяева",
        )

        response = self.post_import(self.payload(user="Маша Митяева"))

        self.assertEqual(response.status_code, 200)
        comment_user = Comment.objects.get().user
        self.assertEqual(comment_user.username, "m_235_masha_mitiaeva")
        self.assertEqual(comment_user.first_name, "Маша Митяева")
        self.assertEqual(random_number.call_count, 2)

    def test_import_preserves_csv_datetime_and_publishes_comment(self):
        response = self.post_import(self.payload())

        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get()
        expected = timezone.make_aware(
            datetime(2026, 8, 10, 12, 30),
            timezone.get_current_timezone(),
        )
        self.assertEqual(comment.created_at, expected)
        self.assertEqual(comment.status, COMMENT_PUBLISHED)

    def test_import_rejects_identical_comment(self):
        first_response = self.post_import(self.payload())
        second_response = self.post_import(self.payload())

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(second_response.json()["code"], "already_exists")
        self.assertEqual(Comment.objects.count(), 1)

    def test_batch_reports_each_row_and_continues_after_invalid_row(self):
        rows = [
            self.payload(user="Alice / alice"),
            self.payload(id=999999, user="Missing / missing"),
            self.payload(user="Bob / bob", text="Second comment"),
        ]

        response = self.post_import(rows)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [result["success"] for result in response.json()["results"]],
            [True, False, True],
        )
        self.assertEqual(response.json()["results"][1]["code"], "page_not_found")
        self.assertEqual(Comment.objects.count(), 2)
        self.assertFalse(get_user_model().objects.filter(username="missing").exists())

    def test_invalid_page_does_not_create_user(self):
        response = self.post_import(self.payload(id=999999, user="New / new-user"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "page_not_found")
        self.assertFalse(get_user_model().objects.filter(username="new-user").exists())
        self.assertFalse(Comment.objects.exists())

    def test_primitive_json_returns_validation_error(self):
        response = self.client.post(
            reverse("comments:import_comment"),
            data="123",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_data")

    def test_invalid_json_returns_json_error(self):
        response = self.client.post(
            reverse("comments:import_comment"),
            data="{invalid",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")

    def test_add_comment_permission_is_required(self):
        unauthorized_user = get_user_model().objects.create_user(
            username="unauthorized"
        )
        self.client.force_login(unauthorized_user)

        response = self.post_import(self.payload())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Comment.objects.exists())
