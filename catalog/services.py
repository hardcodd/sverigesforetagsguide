from collections.abc import Mapping
from datetime import datetime, time
from datetime import time as dtime
from typing import Any

from django.core.paginator import Page as PaginatorPage
from django.template import Context
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.models import Page
from wagtail.query import PageQuerySet

from catalog.models import City, Organization
from catalog.utils import to_12h
from core.utils import paginate


def get_working_hours_service(organization: Organization) -> str:
    """Render working hours for the organization."""

    def format_time(time_value: time | str | None) -> str | None:
        """Return time in HH:MM format."""
        if isinstance(time_value, time):
            return time_value.strftime("%H:%M")

        if isinstance(time_value, str):
            return time_value

        return None

    def get_day_name(day_index: int) -> str:
        """Return the translated short day name for the given index."""
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

    def append_result(
        first_day: str,
        last_day: str,
        start: str | None,
        end: str | None,
        holiday: bool,
    ) -> None:
        """Append a formatted group of working days to the result."""
        nonlocal result

        if first_day == last_day:
            day_range = first_day
        else:
            day_range = f"{first_day}–{last_day}"

        if holiday:
            day_str = f"{day_range}: {_('Holiday')}"
        elif start == "00:00" and end == "23:59":
            day_str = f"{day_range}: {_('Open 24 hours')}"
        elif start and end:
            day_str = f"{day_range}: {start}–{end}"
        elif start:
            day_str = f"{day_range}: {start}"
        elif end:
            day_str = f"{day_range}: {end}"
        else:
            day_str = day_range

        if result:
            result += ", "

        result += day_str

    first_day: str | None = None
    first_start: str | None = None
    first_end: str | None = None
    first_holiday = False

    previous_day: str | None = None
    previous_start: str | None = None
    previous_end: str | None = None
    previous_holiday = False

    result = ""

    for block in organization.working_hours:  # type: ignore
        value = dict(block.value)

        day = get_day_name(int(value["day"]))
        start = format_time(value.get("start"))
        end = format_time(value.get("end"))

        last_client = bool(value.get("last_client"))
        holiday = bool(value.get("holiday"))

        if last_client:
            if end:
                end = f"{end} ({_('Until the last client')})"
            else:
                end = str(_("Until the last client"))

        if first_day is None:
            first_day = day
            first_start = start
            first_end = end
            first_holiday = holiday

            previous_day = day
            previous_start = start
            previous_end = end
            previous_holiday = holiday
            continue

        same_schedule = (
            start == previous_start
            and end == previous_end
            and holiday == previous_holiday
        )

        if same_schedule:
            previous_day = day
            continue

        append_result(
            first_day=first_day,
            last_day=previous_day or first_day,
            start=first_start,
            end=first_end,
            holiday=first_holiday,
        )

        first_day = day
        first_start = start
        first_end = end
        first_holiday = holiday

        previous_day = day
        previous_start = start
        previous_end = end
        previous_holiday = holiday

    if first_day is not None:
        append_result(
            first_day=first_day,
            last_day=previous_day or first_day,
            start=first_start,
            end=first_end,
            holiday=first_holiday,
        )

    return result


def get_current_city_service(context: Context | Mapping[str, object]) -> str:
    """Find the nearest city in one query, without loading each ancestor's body."""
    page = context.get("page")
    if not isinstance(page, Page):
        return ""
    if isinstance(page, City):
        return str(page.title)
    city = (
        City.objects.ancestor_of(page, inclusive=True)
        .defer_streamfields()
        .order_by("-depth")
        .first()
    )
    return str(city.title) if city else ""


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


def get_latest_organizations_service(
    parent: Page | None = None, count: int = 4
) -> PageQuerySet:
    """Return latest cards without fetching unused translated StreamFields."""
    qs = Organization.objects.live().defer_streamfields().order_by("-first_published_at")
    if parent:
        qs = qs.descendant_of(parent)
    return qs[:count]


def get_paginated_organizations_service(
    context: Context | Mapping[str, Any], parent: Page | None = None, count: int = 16
) -> PaginatorPage:
    """Paginate category filters only for lists belonging to the current page."""
    request = context.get("request")
    listing = context.get("organization_listing")
    page = context.get("page")
    if listing is not None and (parent is None or parent.pk == page.pk):
        return paginate(request, listing.queryset, count)
    qs = Organization.objects.live().defer_streamfields()
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
            return {"code": "closed", "status": _("Closed")}

        start_t = _to_time(value.get("start"))
        end_t = _to_time(value.get("end"))
        last_client = bool(value.get("last_client"))

        # 24 часа
        if start_t == dtime(0, 0) and end_t in (dtime(23, 59), dtime(23, 59, 59)):
            return {"code": "open", "status": _("Open 24 hours")}

        if _in_range(now_t, start_t, end_t):
            if last_client and (end_t is None or now_t <= end_t):
                return {"code": "open", "status": _("Open until the last client")}
            if end_t:
                return {
                    "code": "open",
                    "status": _("Open until %(time)s")
                    % {"time": to_12h(end_t.strftime("%H:%M"))},
                }
            return {"code": "open", "status": _("Open")}

    if found_today:
        return {"code": "closed", "status": _("Closed")}
    return {"code": "unknown", "status": _("Unknown")}
