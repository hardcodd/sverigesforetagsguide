from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from catalog.jsonld_builders import _build_reviews_data
from catalog.models import Organization
from reviews.models import Review, ReviewStatus


class ReviewRatingTests(TestCase):
    object_id = 123

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="reviewer")
        cls.content_type = ContentType.objects.get_for_model(Organization)

    def create_review(self, rating, *, status=ReviewStatus.PUBLISHED):
        review = Review(
            user=self.user,
            content_type=self.content_type,
            object_id=self.object_id,
            status=status,
            rating=rating,
            comment=f"Rating {rating}",
        )
        review._defer_rating_update = True
        review.save()
        return review

    def test_model_validation_rejects_ratings_outside_one_to_five(self):
        for rating in (0, 6):
            with self.subTest(rating=rating):
                review = Review(
                    user=self.user,
                    content_type=self.content_type,
                    object_id=self.object_id,
                    rating=rating,
                    comment="Invalid rating",
                )
                with self.assertRaises(ValidationError):
                    review.full_clean()

    def test_submission_rejects_missing_or_out_of_range_rating(self):
        self.client.force_login(self.user)

        for rating in (None, "invalid", 0, 6):
            with self.subTest(rating=rating):
                data = {} if rating is None else {"rating": rating}
                response = self.client.post(reverse("reviews:add_review"), data)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(Review.objects.count(), 0)

    def test_jsonld_uses_only_published_ratings_in_valid_range(self):
        self.create_review(0)
        self.create_review(6)
        self.create_review(3, status=ReviewStatus.MODERATION)
        self.create_review(4)
        self.create_review(5)

        aggregate_rating, reviews = _build_reviews_data(Organization(id=self.object_id))

        assert aggregate_rating is not None
        assert reviews is not None
        self.assertEqual(aggregate_rating["ratingValue"], "4.5")
        self.assertEqual(aggregate_rating["reviewCount"], 2)
        self.assertEqual(aggregate_rating["worstRating"], 1)
        self.assertEqual(aggregate_rating["bestRating"], 5)
        self.assertCountEqual(
            [review["reviewRating"]["ratingValue"] for review in reviews],
            ["4", "5"],
        )

    def test_jsonld_omits_rating_data_when_no_valid_rating_exists(self):
        self.create_review(0)

        aggregate_rating, reviews = _build_reviews_data(Organization(id=self.object_id))

        self.assertIsNone(aggregate_rating)
        self.assertIsNone(reviews)

    def test_review_html_does_not_duplicate_jsonld_structured_data(self):
        review = self.create_review(5)

        html = render_to_string("reviews/review.html", {"review": review})

        self.assertNotIn("itemprop=", html)
        self.assertNotIn("itemscope", html)
        self.assertNotIn("schema.org/Review", html)
