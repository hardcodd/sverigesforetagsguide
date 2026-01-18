from django.core.paginator import Paginator


def is_ajax(request):
    """Check if request is AJAX."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def is_page(page) -> bool:
    """Check if page is a Page model instance."""
    if not hasattr(page, "specific"):
        return False
    return True


def is_catalog_city(page) -> bool:
    """Check if page is a catalog.City model instance."""

    # Check if page is a Page instance
    if not is_page(page):
        return False

    # Check if page's app_label is catalog
    if page.specific._meta.app_label != "catalog":
        return False

    # Check if page is a catalog.City instance
    if page.specific.__class__.__name__ != "City":
        return False

    return True


def is_catalog_organization_type(page) -> bool:
    """Check if page is a catalog.OrganizationType model instance."""

    # Check if page is a Page instance
    if not is_page(page):
        return False

    # Check if page's app_label is catalog
    if page.specific._meta.app_label != "catalog":
        return False

    # Check if page is a catalog.OrganizationType instance
    if page.specific.__class__.__name__ != "OrganizationType":
        return False

    return True


def truncate_string(string: str, length: int = 50) -> str:
    """Truncate a string to a specified length."""
    if len(string) > length:
        return string[:length] + "..."
    return string


def get_domain_name(url: str) -> str:
    """Extract the domain name from a URL."""
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    return parsed_url.netloc or parsed_url.path.split("/")[0] if parsed_url.path else ""


def paginate(request, queryset, count=16):
    paginator = Paginator(queryset, count)
    page_number = request.GET.get("page", 1)
    objects = paginator.get_page(page_number)
    return objects


def get_weekday_number(weekday: str) -> int:
    """Convert a weekday name to its corresponding number."""
    weekdays = {
        "monday": 1,
        "tuesday": 2,
        "wednesday": 3,
        "thursday": 4,
        "friday": 5,
        "saturday": 6,
        "sunday": 7,
    }
    return weekdays.get(weekday.lower(), -1)  # Return -1 if not found


def get_weekday_name(weekday_number: int) -> str:
    """Convert a weekday number to its corresponding name."""

    if not isinstance(weekday_number, int) or weekday_number < 1 or weekday_number > 7:
        return ""  # Return empty string for invalid input

    weekdays = {
        1: "Monday",
        2: "Tuesday",
        3: "Wednesday",
        4: "Thursday",
        5: "Friday",
        6: "Saturday",
        7: "Sunday",
    }
    return weekdays.get(weekday_number, "")  # Return empty string if not found
