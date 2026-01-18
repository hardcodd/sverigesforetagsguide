from datetime import datetime
from datetime import time
from datetime import time as dtime

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalog.models import Organization
from catalog.utils import to_12h
from core.utils import is_catalog_city, is_page, paginate


def get_working_hours_service(organization: Organization) -> str:
    """Render working hours for the organization."""

    def format_time(value):
        """Return time in 00:00 format."""
        if isinstance(value, time):
            return value.strftime("%H:%M")
        elif isinstance(value, str):
            return value

    def get_day_name(day_index: int) -> str:
        """Return day name for a given index."""
        days = [
            _("Mon"),
            _("Tue"),
            _("Wed"),
            _("Thu"),
            _("Fri"),
            _("Sat"),
            _("Sun"),
        ]
        return str(days[day_index - 1])

    def append_result(first_day, last_day, start, end, holiday) -> None:
        """Append the formatted result to the result string."""
        if first_day == last_day:
            if start and end and start == "00:00" and end == "23:59":
                day_str = f"{first_day}: Open 24 hours"
            elif start and end:
                day_str = f"{first_day}: {start}–{end}"
            elif start:
                day_str = f"{first_day}: {start}"
            elif end:
                day_str = f"{first_day}: {end}"
            elif holiday:
                day_str = f"{first_day}: {_("Holiday")}"
            else:
                day_str = first_day
        else:
            if start and end and start == "00:00" and end == "23:59":
                day_str = f"{first_day}–{last_day}: Open 24 hours"
            elif start and end:
                day_str = f"{first_day}–{last_day}: {start}–{end}"
            elif holiday:
                day_str = f"{first_day}–{last_day}: {_("Holiday")}"
            elif start:
                day_str = f"{first_day}–{last_day}: {start}"
            elif end:
                day_str = f"{first_day}–{last_day}: {end}"
            else:
                day_str = f"{first_day}–{last_day}"
        nonlocal result
        if result:
            result += ", "
        result += day_str

    first_day = None
    first_start = None
    first_end = None
    previous_day = None
    previous_start = None
    previous_end = None
    result = ""

    for block in organization.working_hours:  # type: ignore
        value = dict(block.value)
        day = get_day_name(int(value["day"]))
        start = format_time(value["start"])
        end = format_time(value["end"])
        last_client = value["last_client"]
        holiday = value["holiday"]

        if last_client:
            if end:
                end += f' ({_("Until the last client")})'
            else:
                end = _("Until the last client")

        if first_day is None:
            first_day = day
            first_start = start
            first_end = end
            previous_day = day
            previous_start = start
            previous_end = end
            continue

        if start == previous_start and end == previous_end:
            previous_day = day
        else:
            append_result(first_day, previous_day,
                          first_start, first_end, holiday)
            first_day = day
            first_start = start
            first_end = end
            previous_day = day
            previous_start = start
            previous_end = end

    if first_day is not None:
        append_result(first_day, previous_day, first_start, first_end, holiday)

    return result


def get_current_city_service(context) -> str:
    """Return the current city if current page is a catalog.city page.
    Else try to get the city from parent pages."""

    page = context.get("page")

    if not is_page(page):
        return ""

    if is_catalog_city(page):
        return page.specific.title

    # Try to get the city from parent pages
    for parent_page in page.get_ancestors().reverse():
        if is_catalog_city(parent_page):
            return parent_page.specific.title

    return ""


def get_phones_service(organization: Organization) -> list:
    """Return formatted phones for the organization."""
    phones = []

    if not organization.phones:
        return phones

    for phone in organization.phones.split(","):
        phone = phone.strip()
        if phone:
            phone = "+" + phone if phone[0].isdigit() else phone
            phones.append(phone)

    return phones


def get_website_links_service(organization: Organization) -> list:
    """Return formatted website links for the organization."""
    links = []

    if not organization.website_links:
        return links

    for link in organization.website_links.split("\n"):
        link = link.strip()
        if link:
            if not (link.startswith("http://") or link.startswith("https://")):
                link = "http://" + link
            links.append(link)

    return links


def get_social_networks_service(organization: Organization) -> list:
    """Return formatted social networks for the organization."""
    networks = []

    if not organization.social_networks:
        return networks

    for network in organization.social_networks.split("\n"):
        network = network.strip()
        if network:
            if not (network.startswith("http://") or network.startswith("https://")):
                network = "http://" + network
            networks.append(network)

    return networks


def get_organizations_count_service() -> str:
    """Return the count of organizations."""
    count = Organization.objects.live().count()
    return f"{count:,}".replace(",", " ")


def get_updated_organizations_count_service() -> str:
    """Return the count of updated organizations in last 24 hours."""

    def get_count(days: int) -> int:
        return (
            Organization.objects.live()
            .filter(
                latest_revision_created_at__gte=timezone.now()
                - timezone.timedelta(days=days)
            )
            .count()
        )

    count = 0
    days = 1

    while count == 0 and days < 7:
        count = get_count(days)
        days += 1

    return f"{count:,}".replace(",", " ")


def get_located_in_service(organization: Organization):
    """Return organizations located in the building."""
    if not organization.pk:
        return []
    return organization.located_organizations.filter(locale=organization.locale)


def get_top_organizations_service(page):
    """Return premium organizations for the page."""
    # TODO: filter for top organizations
    return page.get_descendants().live()


def get_latest_organizations_service(parent=None, count=4):
    """Return latest organizations for."""
    qs = Organization.objects.live()
    if parent:
        qs = qs.descendant_of(parent)
    return qs[:count]


def get_paginated_organizations_service(context, parent=None, count=16):
    """Return paginated organizations"""
    request = context.get("request")
    qs = Organization.objects.live()
    if parent:
        qs = qs.descendant_of(parent)
    return paginate(request, qs, count)


def _to_time(val):
    if not val:
        return None
    if isinstance(val, dtime):
        return val
    if isinstance(val, datetime):
        return val.time()
    if isinstance(val, str):
        s = val.strip()
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                pass
        # на всякий случай ISO 8601
        try:
            return dtime.fromisoformat(s)
        except ValueError:
            return None
    return None


def _in_range(now_t: dtime, start_t: dtime | None, end_t: dtime | None) -> bool:
    if start_t and end_t:
        if start_t <= end_t:  # обычный интервал, напр. 09:00–18:00
            return start_t <= now_t <= end_t
        else:  # через полночь, напр. 22:00–02:00
            return now_t >= start_t or now_t <= end_t
    if start_t and not end_t:  # «с ... и до закрытия»
        return now_t >= start_t
    if end_t and not start_t:  # «открыто до ...»
        return now_t <= end_t
    return False


def get_organization_status_service(organization: Organization):
    """Return organization status - 'open', 'closed', 'unknown'."""
    now = timezone.localtime()
    now_t = now.time()

    found_today = False

    for block in organization.working_hours:  # type: ignore
        value = dict(block.value)

        found_today = True

        if value.get("holiday"):
            return _("Closed")

        start_t = _to_time(value.get("start"))
        end_t = _to_time(value.get("end"))
        last_client = bool(value.get("last_client"))

        # 24 часа
        if start_t == dtime(0, 0) and end_t in (dtime(23, 59), dtime(23, 59, 59)):
            return _("Open 24 hours")

        if _in_range(now_t, start_t, end_t):
            if last_client and (end_t is None or now_t <= end_t):
                return _("Open until the last client")
            if end_t:
                return _("Open until %(time)s") % {
                    "time": to_12h(end_t.strftime("%H:%M"))
                }
            return _("Open")

    if found_today:
        return _("Closed")
    return _("Unknown")
