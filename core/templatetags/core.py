import random
import re
from datetime import time
from functools import lru_cache

from django import template
from django.conf import settings
from django.forms.renderers import get_template
from django.template.base import mark_safe
from django.template.exceptions import TemplateDoesNotExist
from slugify import slugify

from core.jsonld import render_jsonld
from core.models import SiteSettings
from core.utils import get_domain_name, truncate_string

register = template.Library()


@register.filter(name="slugify")
def slugify_filter(value: str):
    return slugify(value)


@register.filter(name="dir")
def obj_dir(obj):
    """
    Return the attributes of an object.
    """
    result = "<br>".join([f"{_}" for _ in dir(obj) if not _.startswith("_")])
    return mark_safe(f'<small style="display:block;line-height:1.2">{result}</small>')


@lru_cache()
def get_locales():
    """Return the default prefix and locales."""
    default_prefix = getattr(settings, "LANGUAGE_CODE", "en")
    languages = getattr(settings, "LANGUAGES", [])
    locales = [locale[0] for locale in languages]
    return default_prefix, locales


@register.simple_tag(takes_context=True)
def localize_url(context, value: str, prefix=None):
    """Return a localized URL."""
    if value.startswith("http"):
        return value

    default_prefix, locales = get_locales()

    try:
        request = context["request"]
        path = request.path[1:]
        prefix = prefix or path.split("/")[0]
    except KeyError:
        return value

    if any(value.startswith(f"/{locale}/") for locale in locales):
        value = f"/{value.split('/', 2)[-1]}"

    if prefix in locales and prefix != default_prefix:
        value = f"/{prefix}{value}"

    return value


@register.filter
def clear(value: str):
    """Return a cleared string."""
    return value.replace("[[", "").replace("]]", "")


@register.filter
def mark(value: str):
    """Return marked a part of a string."""
    return value.replace("[[", "<mark>").replace("]]", "</mark>")


@register.simple_tag
def section_title(value: str, level=2):
    """Return a section title."""
    value = mark(value)
    return mark_safe(f'<h{level} class="section__title">{value}</h{level}>')


@register.simple_tag
def get_random(*args):
    """Return a random value."""
    return random.choice(args)


@register.filter
def split(value: str, separator: str):
    """Return a split value. Separator may be a regex."""
    return re.split(separator, value)


@register.filter
def coords(value: str):
    """Return a formatted coordinates."""
    lon, lat = value.split(",")
    return "%.5f,%.5f" % (float(lat), float(lon))


@register.filter
def phone_excerpt(value: str):
    """Return a phone phone excerpt."""

    # Get digits only length.
    digits_len = len("".join([_ for _ in value if _.isdigit()]))
    digits_left = digits_len

    # Loop from the end of the string to the beginning.
    for i in range(len(value) - 1, -1, -1):
        # If the character is a digit, replace it with an "x".
        if value[i].isdigit():
            digits_left -= 1
            value = value[:i] + "x" + value[i + 1 :]

            # If there are more than 4 digits left, break the loop.
            if digits_left <= digits_len - 4:
                break

    return value


@register.filter
def truncate(value: str, length: int):
    """Return a truncated string."""
    return truncate_string(value, length)


@register.filter()
def set_page(value, page_number):
    """Sets 'page' property to the pagination link"""

    if "?page=" in value or "&page=" in value:
        value = re.sub(r"page=[\d]+", f"page={page_number}", value)
    elif re.search(r"\?[\w]+=", value):
        value = f"{value}&page={page_number}"
    else:
        value = f"{value}?page={page_number}"
    return value


@register.filter()
def remove_page(value):
    """Removes 'page' property from the pagination link"""

    if "?page=" in value or "&page=" in value:
        value = re.sub(r"[&?]page=[\d]+", "", value)
    if value.startswith("/&"):
        value = "/?" + value[2:]
    return value


@register.simple_tag()
def rating_percent(value):
    """Convert rating to percent"""
    if value is None:
        return 0
    return int(int(value) * 100 / 5)


@register.filter()
def replace(value, arg):
    """Replace a string with another string."""
    if not isinstance(arg, str):
        return value
    old, new = arg.split("|")
    return mark_safe(re.sub(old, new, value))


@register.filter()
def social_network_icon(url: str):
    """Return a social icon class based on the URL."""
    if not url:
        return ""

    html_icon = ""

    try:
        if "facebook.com" in url:
            html_icon = get_template("icons/facebook.svg").render()
        elif "instagram.com" in url:
            html_icon = get_template("icons/instagram.svg").render()
        elif "twitter.com" in url:
            html_icon = get_template("icons/twitter.svg").render()
        elif "x.com" in url:
            html_icon = get_template("icons/x.svg").render()
        elif "tripadvisor.com" in url:
            html_icon = get_template("icons/tripadvisor.svg").render()
        elif "youtube.com" in url:
            html_icon = get_template("icons/youtube.svg").render()
        elif "linkedin.com" in url:
            html_icon = get_template("icons/linkedin.svg").render()
        elif "tiktok.com" in url:
            html_icon = get_template("icons/tiktok.svg").render()
        elif "vk.com" in url:
            html_icon = get_template("icons/vk.svg").render()
        elif "pinterest.com" in url:
            html_icon = get_template("icons/pinterest.svg").render()
        elif "dzen.ru" in url:
            html_icon = get_template("icons/dzen.svg").render()
        elif "whatsapp.com" in url:
            html_icon = get_template("icons/whatsapp.svg").render()
        elif "t.me" in url:
            html_icon = get_template("icons/telegram.svg").render()
        else:
            html_icon = get_domain_name(url)
    except TemplateDoesNotExist:
        html_icon = get_domain_name(url)

    return mark_safe(html_icon)


@register.filter()
def website_name(url: str):
    """Return a website name based on the URL."""
    if not url:
        return ""

    try:
        return get_domain_name(url)
    except Exception:
        return url


@register.filter()
def website_title(url: str):
    """Return a website title based on the URL."""
    if not url:
        return ""

    try:
        domain = get_domain_name(url)
        title = domain.replace("www.", "").split(".")[0]
        return title.capitalize()
    except Exception:
        return url


@register.simple_tag()
def get_social_networks(settings: SiteSettings) -> list:
    """Return formatted social networks list from SiteSettings."""
    networks = []

    if not settings.social_networks:
        return networks

    for network in settings.social_networks.split("\n"):
        network = network.strip()
        if network:
            if not (network.startswith("http://") or network.startswith("https://")):
                network = "http://" + network
            networks.append(network)

    return networks


@register.filter(name="regex_replace")
def regex_replace(value, arg):
    """
    arg is a string formatted as: 'regex_pattern|substitution_string'
    """
    if "|" in arg:
        pattern_str, replacement_str = arg.split("|", 1)
        regex_pattern = re.compile(pattern_str)

        return regex_pattern.sub(replacement_str, str(value))
    else:
        return value  # Return the original value if the arg was not correctly formatted


@register.filter
def percentage(value, arg):
    return int((value / arg) * 100)


@register.filter
def format_number(value, args=None):
    """Format a number with commas and specified decimal places."""
    try:
        if args and isinstance(args, int):
            formatted_value = f"{float(value):,.{args}f}"
        elif args and isinstance(args, str) and args.isdigit():
            decimal_places = int(args)
            formatted_value = f"{float(value):,.{decimal_places}f}"
        elif args and isinstance(args, str) and "," in args:
            parts = args.split(",")
            multiplier = int(parts[1])
            formatted_value = f"{float(value) * multiplier:,.0f}"
        else:
            formatted_value = f"{float(value):,.0f}"
        return formatted_value
    except (ValueError, TypeError):
        return value


@register.simple_tag
def get_search_result_item_template(item) -> str:
    """Return the search result item template based on the item type."""
    default_template_name = "search/search_item.html"

    if hasattr(item, "specific"):
        item = item.specific

    template = item.template

    app_name = template.split("/")[0]
    template_name = template.split("/")[-1]

    search_template = f"{app_name}/search/{template_name}"

    try:
        # Check if the template exists
        get_template(search_template)
        return search_template
    except TemplateDoesNotExist:
        return default_template_name


@register.simple_tag(takes_context=True)
def jsonld(context):
    request = context.get("request")
    page = context.get("page")
    return render_jsonld(page, request) if page and request else ""


@register.filter()
def duration_format(value: time) -> str:
    """
    Convert datetime.time (e.g. 00:56:28) to ISO 8601 duration.

    Examples:
    00:03:12 -> PT3M12S
    01:05:00 -> PT1H5M
    00:00:45 -> PT45S
    """

    if not isinstance(value, time):
        return ""

    hours = value.hour or 0
    minutes = value.minute or 0
    seconds = value.second or 0

    if hours == 0 and minutes == 0 and seconds == 0:
        return "PT0S"

    duration = "PT"

    if hours:
        duration += f"{hours}H"
    if minutes:
        duration += f"{minutes}M"
    if seconds:
        duration += f"{seconds}S"

    return duration
