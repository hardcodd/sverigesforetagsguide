from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page

from reviews.models import Review, ReviewStatus
from reviews.services import update_review_ratings


class ImportReviewViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root_page = Page.objects.get(depth=1)
        cls.page = root_page.add_child(
            instance=Page(title="Review target", slug="review-target")
        )

        user_model = get_user_model()
        cls.importer = user_model.objects.create_user(
            username="review-importer",
            password="test-password",
        )
        add_review_permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Review),
            codename="add_review",
        )
        access_admin_permission = Permission.objects.get(
            content_type__app_label="wagtailadmin",
            codename="access_admin",
        )
        cls.importer.user_permissions.add(
            access_admin_permission,
            add_review_permission,
        )

    def setUp(self):
        self.client.force_login(self.importer)

    def payload(self, **overrides):
        data = {
            "id": self.page.pk,
            "text": "Imported review",
            "user": "Alice Original / alice",
            "date": "2026-08-10 12:30",
            "rate": 5,
        }
        data.update(overrides)
        return data

    def post_import(self, payload):
        return self.client.post(
            reverse("reviews:import_review"),
            data=payload,
            content_type="application/json",
        )

    def test_import_admin_page_renders(self):
        response = self.client.get(reverse("reviews_import:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<sup>*</sup> id", html=True)
        self.assertContains(response, "<sup>*</sup> rate", html=True)
        self.assertNotContains(response, "csv-table")

    def test_admin_listing_renders_imported_review(self):
        self.post_import(self.payload())

        response = self.client.get(reverse("reviews_list:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Imported review")
        self.assertContains(response, "Review target")

    def test_import_uses_existing_username_without_changing_name(self):
        user_model = get_user_model()
        existing_user = user_model.objects.create_user(
            username="alice",
            first_name="Existing Name",
        )

        response = self.post_import(self.payload(user="Different CSV Name / alice"))

        self.assertEqual(response.status_code, 200)
        review = Review.objects.get()
        self.assertEqual(review.user, existing_user)
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.first_name, "Existing Name")

    def test_import_without_username_uses_existing_imported_user(self):
        existing_user = get_user_model().objects.create_user(
            username="m_123_masha_mityaeva",
            first_name="Маша Митяева",
        )

        response = self.post_import(self.payload(user="Маша Митяева"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.get().user, existing_user)

    @patch("core.import_users.random.randint", return_value=234)
    def test_import_without_username_creates_generated_username(self, random_number):
        response = self.post_import(self.payload(user="Маша Митяева"))

        self.assertEqual(response.status_code, 200)
        review_user = Review.objects.get().user
        self.assertEqual(review_user.username, "m_234_masha_mitiaeva")
        self.assertEqual(review_user.first_name, "Маша Митяева")
        random_number.assert_called_once_with(100, 999)

    def test_import_preserves_csv_datetime(self):
        response = self.post_import(self.payload())

        self.assertEqual(response.status_code, 200)
        review = Review.objects.get()
        expected = timezone.make_aware(
            datetime(2026, 8, 10, 12, 30),
            timezone.get_current_timezone(),
        )
        self.assertEqual(review.created_at, expected)
        self.assertEqual(review.go_live_at, expected)

    def test_import_rejects_duplicate_for_same_content_object(self):
        first_response = self.post_import(self.payload())
        second_response = self.post_import(self.payload())

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(second_response.json()["code"], "already_exists")
        self.assertEqual(Review.objects.count(), 1)

    def test_batch_recalculates_ratings_once_per_content_object(self):
        rows = [
            self.payload(user="Alice / alice"),
            self.payload(user="Bob / bob", text="Second review", rate=4),
        ]

        with patch(
            "reviews.services.update_review_ratings",
            wraps=update_review_ratings,
        ) as update_ratings:
            response = self.post_import(rows)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [result["success"] for result in response.json()["results"]], [True, True]
        )
        self.assertEqual(Review.objects.count(), 2)
        update_ratings.assert_called_once()

    def test_duplicate_check_includes_content_type(self):
        user_model = get_user_model()
        review_user = user_model.objects.create_user(username="alice")
        Review.objects.create(
            user=review_user,
            content_type=ContentType.objects.get_for_model(user_model),
            object_id=self.page.pk,
            status=ReviewStatus.MODERATION,
            comment="Different object",
            rating=5,
        )

        response = self.post_import(self.payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.count(), 2)

    def test_invalid_page_does_not_create_user(self):
        user_model = get_user_model()

        response = self.post_import(self.payload(id=999999, user="New / new-user"))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(user_model.objects.filter(username="new-user").exists())
        self.assertFalse(Review.objects.exists())

    def test_invalid_rating_returns_validation_error(self):
        response = self.post_import(self.payload(rate=6))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_data")
        self.assertFalse(Review.objects.exists())

    def test_primitive_json_returns_validation_error(self):
        response = self.client.post(
            reverse("reviews:import_review"),
            data="123",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_data")

    def test_invalid_json_returns_json_error(self):
        response = self.client.post(
            reverse("reviews:import_review"),
            data="{invalid",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")

    def test_add_review_permission_is_required(self):
        user_model = get_user_model()
        unauthorized_user = user_model.objects.create_user(username="unauthorized")
        self.client.force_login(unauthorized_user)

        response = self.post_import(self.payload())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Review.objects.exists())
