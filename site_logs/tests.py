import os
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse

from site_logs.logging import LOG_RECORD_SEPARATOR, clean_old_log_files
from site_logs.services import (
    list_downloadable_log_files,
    open_log_file,
    read_recent_log_records,
)
from site_logs.views import download_log, log_list
from site_logs.wagtail_hooks import register_reports_menu_item

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write_log(path, *records):
    content = "".join(f"{record}\n{LOG_RECORD_SEPARATOR}\n" for record in records)
    path.write_text(content, encoding="utf-8")


class LoguruConfigurationTests(SimpleTestCase):
    def test_standard_logging_is_split_by_severity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = os.environ.copy()
            environment.update(
                {
                    "DJANGO_SETTINGS_MODULE": "app.settings.production",
                    "SITE_LOG_DIR": temp_dir,
                }
            )
            code = (
                "import django, logging; from loguru import logger; "
                "django.setup(); "
                "log = logging.getLogger('site_logs.test'); "
                "log.warning('warning marker'); "
                "log.error('error marker'); "
                "logger.error('direct Loguru marker')"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            warning_text = next(Path(temp_dir).glob("warnings.*.log")).read_text()
            error_text = next(Path(temp_dir).glob("errors.*.log")).read_text()
            self.assertIn("warning marker", warning_text)
            self.assertNotIn("error marker", warning_text)
            self.assertIn("error marker", error_text)
            self.assertIn("direct Loguru marker", error_text)
            self.assertNotIn("warning marker", error_text)
            self.assertRegex(warning_text, r"pid=\d+ \| __main__:<module>:\d+")
            self.assertEqual(
                stat.S_IMODE(
                    next(Path(temp_dir).glob("warnings.*.log")).stat().st_mode
                ),
                0o600,
            )

    def test_warning_log_is_rotated_and_compressed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = os.environ.copy()
            environment.update(
                {
                    "DJANGO_SETTINGS_MODULE": "app.settings.production",
                    "SITE_LOG_CONSOLE_LEVEL": "CRITICAL",
                    "SITE_LOG_DIR": temp_dir,
                    "SITE_LOG_ROTATION_MB": "1",
                }
            )
            code = (
                "import django, logging; "
                "django.setup(); "
                "log = logging.getLogger('site_logs.rotation_test'); "
                "log.warning('x' * 600000); "
                "log.warning('y' * 600000)"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rotated_files = list(Path(temp_dir).glob("warnings.*.log.gz"))
            current_files = list(Path(temp_dir).glob("warnings.*.log"))
            self.assertTrue(rotated_files)
            self.assertTrue(current_files)
            for path in rotated_files + current_files:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_non_positive_rotation_setting_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = os.environ.copy()
            environment.update(
                {
                    "DJANGO_SETTINGS_MODULE": "app.settings.production",
                    "SITE_LOG_DIR": temp_dir,
                    "SITE_LOG_ROTATION_MB": "0",
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", "import django; django.setup()"],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "SITE_LOG_ROTATION_MB must be greater than zero.", result.stderr
            )

    def test_cleanup_removes_only_expired_log_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            old_warning = log_dir / "warnings.999999.20260101T000000000000Z.log.gz"
            recent_warning = log_dir / "warnings.999999.20260102T000000000000Z.log.gz"
            unrelated = log_dir / "unrelated.log"
            for path in (old_warning, recent_warning, unrelated):
                path.touch()

            now = datetime(2026, 2, 1, tzinfo=UTC)
            old_timestamp = (now - timedelta(days=31)).timestamp()
            recent_timestamp = (now - timedelta(days=29)).timestamp()
            os.utime(old_warning, (old_timestamp, old_timestamp))
            os.utime(recent_warning, (recent_timestamp, recent_timestamp))
            os.utime(unrelated, (old_timestamp, old_timestamp))

            clean_old_log_files(
                log_dir,
                {"warnings": 30, "errors": 90},
                now=now,
            )

            self.assertFalse(old_warning.exists())
            self.assertTrue(recent_warning.exists())
            self.assertTrue(unrelated.exists())


class LogReadingTests(SimpleTestCase):
    def test_recent_records_are_merged_and_limited(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            _write_log(
                log_dir / "errors.101.20260910T100000000000Z.log",
                "2026-09-10 10:00:00.000 +0700 | ERROR | first",
                "2026-09-10 10:02:00.000 +0700 | ERROR | third",
            )
            _write_log(
                log_dir / "errors.102.20260910T100000000000Z.log",
                "2026-09-10 10:01:00.000 +0700 | ERROR | second",
            )

            result = read_recent_log_records(
                log_dir,
                "errors",
                record_limit=2,
                file_limit=4,
                bytes_per_file=4096,
            )

            self.assertEqual(result.files_read, 2)
            self.assertEqual(len(result.records), 2)
            self.assertIn("third", result.records[0])
            self.assertIn("second", result.records[1])

    def test_symlinked_log_file_is_not_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            target = log_dir / "secret.txt"
            target.write_text("secret", encoding="utf-8")
            (log_dir / "errors.101.20260910T100000000000Z.log").symlink_to(target)

            result = read_recent_log_records(
                log_dir,
                "errors",
                record_limit=10,
                file_limit=4,
                bytes_per_file=4096,
            )

            self.assertEqual(result.records, ())
            self.assertEqual(result.files_read, 0)

    def test_incomplete_final_record_is_not_displayed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "errors.101.20260910T100000000000Z.log"
            _write_log(path, "2026-09-10 10:00:00.000 +0700 | ERROR | complete")
            with path.open("a", encoding="utf-8") as log_file:
                log_file.write("2026-09-10 10:01:00.000 +0700 | ERROR | partial")

            result = read_recent_log_records(
                temp_dir,
                "errors",
                record_limit=10,
                file_limit=4,
                bytes_per_file=4096,
            )

            self.assertEqual(len(result.records), 1)
            self.assertIn("complete", result.records[0])
            self.assertNotIn("partial", result.records[0])

    def test_invalid_level_and_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            read_recent_log_records(
                "/unused",
                "debug",
                record_limit=10,
                file_limit=4,
                bytes_per_file=4096,
            )
        with self.assertRaises(ValueError):
            read_recent_log_records(
                "/unused",
                "errors",
                record_limit=0,
                file_limit=4,
                bytes_per_file=4096,
            )

    def test_downloadable_files_are_filtered_and_ordered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            older_error = log_dir / "errors.101.20260910T100000000000Z.log.gz"
            newer_error = log_dir / "errors.102.20260910T100000000000Z.log"
            warning = log_dir / "warnings.103.20260910T100000000000Z.log"
            unrelated = log_dir / "secret.txt"
            for path in (older_error, newer_error, warning, unrelated):
                path.write_bytes(b"log")
            os.utime(older_error, (1, 1))
            os.utime(newer_error, (2, 2))

            files = list_downloadable_log_files(log_dir, "errors", file_limit=10)

            self.assertEqual(
                [log_file.name for log_file in files],
                [newer_error.name, older_error.name],
            )

    def test_direct_file_open_rejects_unapproved_names_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            target = log_dir / "secret.txt"
            target.write_text("secret", encoding="utf-8")
            filename = "errors.101.20260910T100000000000Z.log"
            (log_dir / filename).symlink_to(target)

            with self.assertRaises(OSError):
                open_log_file(log_dir, filename)
            with self.assertRaises(FileNotFoundError):
                open_log_file(log_dir, "secret.txt")


class LogAdminUnitTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        settings_override = override_settings(SITE_LOG_DIR=self.temp_dir.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.request_factory = RequestFactory()

    def _request(self, is_superuser):
        request = self.request_factory.get(
            "/admin/site-logs/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        request.user = SimpleNamespace(
            is_anonymous=False,
            is_superuser=is_superuser,
            has_perms=lambda permissions: True,
        )
        return request

    def test_report_and_download_are_superuser_only(self):
        request = self._request(is_superuser=False)
        filename = "errors.101.20260910T100000000000Z.log"
        (Path(self.temp_dir.name) / filename).write_bytes(b"private")

        with self.assertRaises(PermissionDenied):
            log_list(request)
        with self.assertRaises(PermissionDenied):
            download_log(request, filename)
        self.assertFalse(register_reports_menu_item().is_shown(request))

    def test_superuser_gets_bounded_report_and_file_download(self):
        request = self._request(is_superuser=True)
        filename = "errors.101.20260910T100000000000Z.log"
        path = Path(self.temp_dir.name) / filename
        _write_log(path, "2026-09-10 10:00:00.000 +0700 | ERROR | marker")

        with patch("site_logs.views.render", return_value=HttpResponse("ok")) as render:
            response = log_list(request)
        context = render.call_args.args[2]
        download = download_log(request, filename)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(context["record_count"], 1)
        self.assertIn("marker", context["log_text"])
        self.assertEqual(len(context["downloadable_files"]), 1)
        self.assertEqual(b"".join(download.streaming_content), path.read_bytes())
        self.assertTrue(register_reports_menu_item().is_shown(request))


class LogAdminViewTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.settings_override = override_settings(SITE_LOG_DIR=self.temp_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_superuser_can_view_logs(self):
        user = get_user_model().objects.create_superuser(
            username="log-admin",
            email="",
            password="password",
        )
        self.client.force_login(user)
        log_path = Path(self.temp_dir.name) / "errors.101.20260910T100000000000Z.log"
        _write_log(
            log_path,
            "2026-09-10 10:00:00.000 +0700 | ERROR | visible marker",
        )

        response = self.client.get(reverse("site_logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "visible marker")
        self.assertContains(
            response, reverse("site_logs_download", args=[log_path.name])
        )

    def test_superuser_can_download_log_file(self):
        user = get_user_model().objects.create_superuser(
            username="download-log-admin",
            email="",
            password="password",
        )
        self.client.force_login(user)
        log_path = Path(self.temp_dir.name) / "errors.101.20260910T100000000000Z.log"
        log_path.write_bytes(b"download marker")

        response = self.client.get(reverse("site_logs_download", args=[log_path.name]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"download marker")
        self.assertIn("attachment;", response.headers["Content-Disposition"])

    def test_unapproved_file_cannot_be_downloaded(self):
        user = get_user_model().objects.create_superuser(
            username="invalid-download-log-admin",
            email="",
            password="password",
        )
        self.client.force_login(user)
        (Path(self.temp_dir.name) / "secret.txt").write_text(
            "secret",
            encoding="utf-8",
        )

        response = self.client.get(reverse("site_logs_download", args=["secret.txt"]))

        self.assertEqual(response.status_code, 404)

    def test_symlinked_log_file_cannot_be_downloaded(self):
        user = get_user_model().objects.create_superuser(
            username="symlink-download-log-admin",
            email="",
            password="password",
        )
        self.client.force_login(user)
        target = Path(self.temp_dir.name) / "secret.txt"
        target.write_text("secret", encoding="utf-8")
        log_path = Path(self.temp_dir.name) / "errors.101.20260910T100000000000Z.log"
        log_path.symlink_to(target)

        response = self.client.get(reverse("site_logs_download", args=[log_path.name]))

        self.assertEqual(response.status_code, 404)

    def test_non_superuser_cannot_download_log_file(self):
        user = get_user_model().objects.create_user(
            username="download-editor",
            password="password",
            is_staff=True,
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            )
        )
        self.client.force_login(user)
        filename = "errors.101.20260910T100000000000Z.log"
        (Path(self.temp_dir.name) / filename).write_text("private marker")

        response = self.client.get(
            reverse("site_logs_download", args=[filename]),
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 403)

    def test_log_content_is_escaped_in_admin_page(self):
        user = get_user_model().objects.create_superuser(
            username="escaping-log-admin",
            email="",
            password="password",
        )
        self.client.force_login(user)
        path = Path(self.temp_dir.name) / "errors.101.20260910T100000000000Z.log"
        _write_log(
            path, "2026-09-10 10:00:00.000 +0700 | ERROR | <script>bad()</script>"
        )

        response = self.client.get(reverse("site_logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;")
        self.assertNotContains(response, "<script>bad()</script>")

    def test_non_superuser_cannot_view_logs(self):
        user = get_user_model().objects.create_user(
            username="editor",
            password="password",
            is_staff=True,
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            )
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("site_logs"),
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_level_returns_not_found(self):
        user = get_user_model().objects.create_superuser(
            username="second-log-admin",
            email="",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("site_logs"), {"level": "debug"})

        self.assertEqual(response.status_code, 404)
