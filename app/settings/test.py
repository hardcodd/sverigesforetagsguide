import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = "django-test-only-secret-key-not-for-production"
ALLOWED_HOSTS = ["testserver"]

WORKING_DATABASE_NAME = DATABASES["default"]["NAME"]  # noqa: F405
TEST_DATABASE_NAME = os.environ.get("DB_TEST_NAME", "test_newmadloba")
MAINTENANCE_DATABASE_NAME = os.environ.get(
    "DB_TEST_MAINTENANCE_NAME",
    "postgres",
)

if not TEST_DATABASE_NAME.startswith("test_"):
    raise ImproperlyConfigured("DB_TEST_NAME must start with 'test_'.")
if TEST_DATABASE_NAME == WORKING_DATABASE_NAME:
    raise ImproperlyConfigured("The test and working database names must differ.")
if MAINTENANCE_DATABASE_NAME == WORKING_DATABASE_NAME:
    raise ImproperlyConfigured(
        "The maintenance and working database names must differ."
    )

DATABASES["default"]["NAME"] = MAINTENANCE_DATABASE_NAME  # noqa: F405
DATABASES["default"]["TEST"] = {"NAME": TEST_DATABASE_NAME}  # noqa: F405

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Test database isolation does not isolate caches; never share site URL or HTML
# entries with the running application.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "madloba-test-default",
    },
    "renditions": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "madloba-test-renditions",
    },
}

WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": True,
        "STATS_FILE": os.path.join(BASE_DIR, "app/static/webpack-stats.json"),  # noqa: F405
        "POLL_INTERVAL": 0.1,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}
