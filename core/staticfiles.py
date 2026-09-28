from hashlib import sha256
from pathlib import Path

from django.contrib.staticfiles import finders
from django.templatetags.static import static


def versioned_static(path: str) -> str:
    """Return a static URL with a content-based cache version."""
    url = static(path)
    asset_path = finders.find(path)

    if not isinstance(asset_path, str):
        return url

    try:
        version = sha256(Path(asset_path).read_bytes()).hexdigest()[:12]
    except OSError:
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={version}"
