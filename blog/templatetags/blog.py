from django import template

from blog.services import (
    get_authors_blogs_service,
    get_blog_categories_list_service,
    get_blog_index_page_service,
    get_blog_tags_list_service,
    get_latest_authors_posts_service,
    get_latest_blog_posts_service,
    get_paginated_blog_posts_service,
    get_tag_by_slug_service,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def get_paginated_blog_posts(context, parent, count=16):
    return get_paginated_blog_posts_service(context, parent, count)


@register.simple_tag(takes_context=True)
def get_blog_index_page(context):
    return get_blog_index_page_service(context)


@register.simple_tag(takes_context=True)
def get_blog_categories_list(context):
    return get_blog_categories_list_service(context)


@register.simple_tag
def get_latest_blog_posts(category=None, count=4):
    return get_latest_blog_posts_service(category, count)


@register.simple_tag
def get_blog_tags_list(count: int = 20):
    return get_blog_tags_list_service(count)


@register.simple_tag
def get_tag_by_slug(tag_slug):
    return get_tag_by_slug_service(tag_slug)


@register.simple_tag
def get_authors_blogs(author):
    return get_authors_blogs_service(author)


@register.simple_tag
def get_latest_authors_posts(author, blog, count=4):
    return get_latest_authors_posts_service(author, blog, count)
