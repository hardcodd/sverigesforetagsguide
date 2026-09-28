import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase
from django.db.models import Model

from core.views import import_page, set_attr


class SetAttrErrorTests(SimpleTestCase):
    def setUp(self):
        self.obj = Mock(spec=Model)

    def test_type_error_includes_the_field_name(self):
        with (
            patch(
                "core.views.run_field_handler",
                side_effect=TypeError("Invalid list value"),
            ),
            self.assertRaises(ValueError) as raised_error,
        ):
            set_attr(self.obj, "working_hours", "invalid")

        self.assertEqual(
            str(raised_error.exception),
            "Error setting field 'working_hours': Invalid list value",
        )

    def test_unexpected_field_error_includes_the_field_name_and_is_logged(self):
        with (
            patch(
                "core.views.run_field_handler",
                side_effect=RuntimeError("Handler failed"),
            ),
            patch("core.views.logger.exception") as log_exception,
            self.assertRaises(ValueError) as raised_error,
        ):
            set_attr(self.obj, "working_hours", "invalid")

        self.assertEqual(
            str(raised_error.exception),
            "Error setting field 'working_hours': Handler failed",
        )
        log_exception.assert_called_once_with(
            "Unexpected error setting import field %r",
            "working_hours",
        )


class ImportPageErrorResponseTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post(
            "/core/import-page/",
            {
                "page_type": "catalog.Organization",
                "csv_row": json.dumps({"legal_name": "Example"}),
                "field_mapping[legal_name]": "legal_name",
            },
        )
        setattr(
            self.request,
            "user",
            SimpleNamespace(
                is_anonymous=False,
                has_perms=lambda permissions: True,
            ),
        )

    def test_expected_row_error_is_returned_as_json(self):
        with patch(
            "core.views.get_page_model",
            side_effect=ValueError("Invalid row value"),
        ):
            response = import_page(self.request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"success": False, "message": "Invalid row value"},
        )

    def test_unexpected_row_error_is_returned_as_json_and_logged(self):
        with (
            patch(
                "core.views.get_page_model",
                side_effect=RuntimeError("Database rejected the row"),
            ),
            patch("core.views.logger.exception") as log_exception,
        ):
            response = import_page(self.request)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content),
            {"success": False, "message": "Database rejected the row"},
        )
        log_exception.assert_called_once_with(
            "Unexpected error while importing a page from a CSV row"
        )
