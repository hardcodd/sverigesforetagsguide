from django import template

from ..models import ContactPage

register = template.Library()


@register.simple_tag
def get_contacts_page():
    try:
        contact_page = ContactPage.objects.live().public().first()
        return contact_page
    except ContactPage.DoesNotExist:
        return None
