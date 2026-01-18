from django import template

from catalog.services import (get_current_city_service, get_latest_organizations_service, get_located_in_service,
                              get_organization_status_service, get_organizations_count_service,
                              get_paginated_organizations_service, get_phones_service, get_social_networks_service,
                              get_top_organizations_service, get_updated_organizations_count_service,
                              get_website_links_service, get_working_hours_service)

register = template.Library()


@register.simple_tag(takes_context=True)
def get_current_city(context):
    return get_current_city_service(context)


@register.simple_tag
def get_phones(organization):
    return get_phones_service(organization)


@register.simple_tag
def get_website_links(organization):
    return get_website_links_service(organization)


@register.simple_tag
def get_social_networks(organization):
    return get_social_networks_service(organization)


@register.simple_tag
def get_working_hours(organization):
    return get_working_hours_service(organization)


@register.simple_tag
def get_organizations_count():
    return get_organizations_count_service()


@register.simple_tag
def get_updated_organizations_count():
    return get_updated_organizations_count_service()


@register.simple_tag
def get_located_in(organization):
    return get_located_in_service(organization)


@register.simple_tag
def get_top_organizations(page):
    return get_top_organizations_service(page)


@register.simple_tag
def get_latest_organizations(parent=None, count=4):
    return get_latest_organizations_service(parent, count)


@register.simple_tag(takes_context=True)
def get_paginated_organizations(context, parent=None, count=16):
    return get_paginated_organizations_service(context, parent, count)


@register.simple_tag
def get_organization_status(organization):
    return get_organization_status_service(organization)
