from blog.models import BlogCategoryPage, BlogIndexPage, BlogPostPage, BlogTag
from core.utils import paginate


def get_blog_index_page_service(context):
    page = context.get("page")
    return BlogIndexPage.objects.live().ancestor_of(page, inclusive=True).first()


def get_paginated_blog_posts_service(context, parent, count=16):
    request = context.get("request")
    qs = BlogPostPage.objects.live().order_by("-first_published_at")
    if parent:
        qs = qs.descendant_of(parent)

    filters = {}

    author = request.GET.get("author")
    if author:
        filters["author__slug"] = author

    tag = request.GET.get("tag")
    if tag:
        tag = BlogTag.objects.filter(tag__slug=tag).first()
        if tag:
            filters["tags__slug"] = tag.tag.slug

    qs = qs.filter(**filters)

    return paginate(request, qs, count)


def _build_tree(pages, parent):
    tree = []

    for page in pages:
        page.children = []

        if page.is_child_of(parent):
            tree.append(page)

        children = page.get_children().type(BlogCategoryPage)
        if children:
            page.children = _build_tree(children, page)

    return tree


def get_blog_categories_list_service(context):
    blog = get_blog_index_page_service(context)
    categories = BlogCategoryPage.objects.live().descendant_of(blog)

    return _build_tree(categories, blog)


def get_blog_tags_list_service(context, count=20):
    index_blog_page = get_blog_index_page_service(context)

    blog_posts = (
        BlogPostPage.objects
        .live()
        .descendant_of(index_blog_page)
    )

    tag_relname = BlogTag.tag_relname()

    qs = (
        BlogTag.tags_for(
            BlogPostPage,
            **{f"{tag_relname}__content_object__in": blog_posts}
        )
        .order_by("name")
        .distinct()[:count]
    )

    return qs


def get_tag_by_slug_service(tag_slug):
    try:
        tag = BlogTag.objects.filter(tag__slug=tag_slug).first()
    except BlogTag.DoesNotExist:
        tag = None
    return tag


def get_authors_blogs_service(author):
    qs = BlogIndexPage.objects.live().order_by("-first_published_at")
    blogs = []
    for blog in qs:
        posts = BlogPostPage.objects.live().filter(author=author).descendant_of(blog)
        if posts.exists():
            blogs.append(blog)
    return blogs


def get_latest_authors_posts_service(author, blog, count=4):
    qs = (
        BlogPostPage.objects.live()
        .descendant_of(blog)
        .filter(author=author)
        .order_by("-first_published_at")
    )
    return qs[:count]


def get_latest_blog_posts_service(category=None, count=4):
    qs = BlogPostPage.objects.live().order_by("-first_published_at")
    if category:
        qs = qs.descendant_of(category)
    return qs[:count]
