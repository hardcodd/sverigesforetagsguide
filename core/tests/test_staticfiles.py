from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from core.staticfiles import versioned_static


class VersionedStaticTests(SimpleTestCase):
    def test_appends_content_hash(self):
        asset_path = Path(__file__)
        expected_version = sha256(asset_path.read_bytes()).hexdigest()[:12]

        with patch("core.staticfiles.finders.find", return_value=str(asset_path)):
            self.assertEqual(
                versioned_static("admin.js"),
                f"/static/admin.js?v={expected_version}",
            )

    def test_preserves_existing_query_parameters(self):
        asset_path = Path(__file__)

        with (
            patch("core.staticfiles.static", return_value="/static/admin.js?lang=ru"),
            patch("core.staticfiles.finders.find", return_value=str(asset_path)),
        ):
            self.assertIn("?lang=ru&v=", versioned_static("admin.js"))

    def test_returns_plain_url_when_file_is_not_found(self):
        with patch("core.staticfiles.finders.find", return_value=None):
            self.assertEqual(versioned_static("missing.js"), "/static/missing.js")
