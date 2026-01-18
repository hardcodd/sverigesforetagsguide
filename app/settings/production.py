from .base import *

DEBUG = False

ALLOWED_HOSTS = literal_eval(os.environ.get("ALLOWED_HOSTS", '["*"]'))

SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-insecure-@)t9&z#jm-$oh*_v!-i_6c^a7s30g(t#nr04vz*n4p5^h54h56"
)

WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "STATS_FILE": os.path.join(BASE_DIR, "app/static/webpack-stats.json"),
        "POLL_INTERVAL": 0.1,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}
