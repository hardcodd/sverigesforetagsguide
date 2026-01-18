from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class RatingBlock(blocks.StructBlock):
    rating = blocks.IntegerBlock(
        min_value=1,
        max_value=10,
        required=True,
        help_text="Rating from 1 to 10",
    )
    caption = blocks.CharBlock(
        required=True,
    )

    class Meta:
        template = "ratings/blocks/rating_block.html"


class ContentBlock(blocks.StructBlock):
    text = blocks.RichTextBlock(features=["h2", "bold", "italic"])
    images = blocks.ListBlock(ImageChooserBlock(), required=False)

    class Meta:
        template = "ratings/blocks/content_block.html"


class RatingCardBlock(blocks.PageChooserBlock):
    def __init__(
        self, page_type=None, can_choose_root=False, target_model=None, **kwargs
    ):
        if not page_type:
            page_type = "ratings.RatingPage"
        super().__init__(page_type, can_choose_root, target_model, **kwargs)

    class Meta:  # type: ignore
        icon = "pick"
        label = _("Rating")
        template = "ratings/blocks/rating_card_block.html"
