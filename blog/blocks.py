from django.utils.translation import gettext_lazy as _
from wagtail.blocks import IntegerBlock, PageChooserBlock, StructBlock


class BlogPostBlock(PageChooserBlock):
    def __init__(
        self, page_type=None, can_choose_root=False, target_model=None, **kwargs
    ):
        if not page_type:
            page_type = "blog.BlogPostPage"
        super().__init__(page_type, can_choose_root, target_model, **kwargs)

    class Meta:  # type: ignore
        icon = "pilcrow"
        label = _("Blog post")
        template = "blog/includes/post-item.html"


class LatestBlogPostsFromCategoryBlock(StructBlock):
    count = IntegerBlock(default=4, label=_("Count"))
    page = PageChooserBlock(
        page_type="blog.BlogCategoryPage",
        label=_("Blog category page"),
    )

    class Meta:  # type: ignore
        icon = "list-ul"
        label = _("Latest blog posts from category")
        template = "blog/blocks/latest-blog-posts-from-category-block.html"


class LatestBlogPostsBlock(StructBlock):
    count = IntegerBlock(default=4, label=_("Count"))
    page = PageChooserBlock(
        page_type="blog.BlogIndexPage",
        label=_("Blog index page"),
    )

    class Meta:  # type: ignore
        icon = "list-ul"
        label = _("Latest blog posts")
        template = "blog/blocks/latest-blog-posts-block.html"


class PaginatedOrganizationsBlock(StructBlock):
    count = IntegerBlock(default=16, label=_("Count"))
    page = PageChooserBlock(
        page_type=["catalog.OrganizationType", "catalog.City"],
        label=_("Parent page"),
        required=False,
    )

    class Meta:  # type: ignore
        icon = "briefcase-solid"
        label = _("Paginated organizations")
        template = "catalog/blocks/paginated-organizations-block.html"
