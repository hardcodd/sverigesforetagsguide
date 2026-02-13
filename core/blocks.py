from django.utils.translation import gettext_lazy as _
from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    ChoiceBlock,
    DateBlock,
    PageChooserBlock,
    RawHTMLBlock,
    RichTextBlock,
    StreamBlock,
    StructBlock,
    StructValue,
    TimeBlock,
)
from wagtail.blocks import TextBlock as WagtailTextBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock

from blog.blocks import LatestBlogPostsBlock, LatestBlogPostsFromCategoryBlock
from catalog.blocks import (
    LatestOrganizationsFromCityBlock,
    LatestOrganizationsFromOrganizationTypeBlock,
    OrganizationBlock,
    PaginatedOrganizationsBlock,
)
from ratings.blocks import RatingCardBlock


class LinkStructValue(StructValue):
    """Additional logic for urls"""

    def get_url(self):
        page = self.get("page")
        url = self.get("url")
        if page:
            return page.url
        elif url:
            return url
        return "#"


class DayBlock(StructBlock):
    day = ChoiceBlock(
        choices=[
            (1, _("Monday")),
            (2, _("Tuesday")),
            (3, _("Wednesday")),
            (4, _("Thursday")),
            (5, _("Friday")),
            (6, _("Saturday")),
            (7, _("Sunday")),
        ],
        label=_("Day"),
    )
    holiday = BooleanBlock(
        default=False,
        label=_("Holiday"),
        required=False,
    )
    start = TimeBlock(
        label=_("Start"),
        required=False,
    )
    end = TimeBlock(
        label=_("End"),
        required=False,
    )
    last_client = BooleanBlock(
        default=False,
        label=_("Until the last client"),
        required=False,
    )


class TextBlock(RichTextBlock):
    class Meta:
        template = "core/blocks/text_block.html"


class ExternalCodeBlock(StructBlock):
    public = BooleanBlock(default=True, required=False, label=_("Public"))
    title = CharBlock(label=_("Title"))
    code = RawHTMLBlock(label=_("Code"))

    class Meta:
        template = "core/blocks/external_code_block.html"


class LinkBlock(StructBlock):
    title = CharBlock(
        max_length=50,
        label=_("Title"),
    )
    page = PageChooserBlock(
        required=False,
        label=_("Page"),
    )
    url = CharBlock(
        max_length=200,
        label=_("URL"),
        required=False,
    )

    class Meta:
        template = "core/blocks/link_block.html"
        value_class = LinkStructValue


class CardStle1Block(StructBlock):
    title = CharBlock(max_length=255, label=_("Title"))
    image = ImageChooserBlock(label=_("Image"))
    page = PageChooserBlock(label=_("Page"))
    button_text = CharBlock(max_length=50, label=_("Button text"))

    class Meta:
        template = "core/blocks/card-style-1.html"
        label = _("Card (Style 1)")


class CardStyle2Block(StructBlock):
    title = CharBlock(max_length=255, label=_("Title"))
    image = ImageChooserBlock(label=_("Image"))
    page = PageChooserBlock(label=_("Page"))

    class Meta:
        template = "core/blocks/card-style-2.html"
        label = _("Card (Style 2)")


class CardStyle3Block(CardStyle2Block):
    class Meta:
        template = "core/blocks/card-style-3.html"
        label = _("Card (Style 3)")


class CardStyle4Block(StructBlock):
    title = CharBlock(max_length=255, label=_("Title"))
    description = CharBlock(max_length=255, label=_("Description"))
    image = ImageChooserBlock(label=_("Image"))
    page = PageChooserBlock(label=_("Page"), required=False)

    class Meta:
        template = "core/blocks/card-style-4.html"
        label = _("Card (Style 4)")


class CardStyle5Block(StructBlock):
    title = CharBlock(max_length=255, label=_("Title"))
    description = CharBlock(max_length=255, label=_("Description"))
    image = ImageChooserBlock(label=_("Image"))
    page = PageChooserBlock(label=_("Page"), required=False)
    url = CharBlock(max_length=200, label=_("URL"), required=False)
    button_text = CharBlock(max_length=50, label=_("Button text"), required=False)

    class Meta:
        template = "core/blocks/card-style-5.html"
        label = _("Card (Style 5)")
        value_class = LinkStructValue


class CardStyle6Block(StructBlock):
    content = RichTextBlock(label=_("Content"))
    page = PageChooserBlock(label=_("Page"), required=False)
    url = CharBlock(max_length=200, label=_("URL"), required=False)
    button_text = CharBlock(max_length=50, label=_("Button text"), required=False)

    class Meta:
        template = "core/blocks/card-style-6.html"
        label = _("Card (Style 6)")
        value_class = LinkStructValue


class SectionCardsBlock(StructBlock):
    title = CharBlock(
        max_length=255,
        label=_("Title"),
        required=False,
    )
    pageurl = PageChooserBlock(required=False, label=_("Page URL"))
    button_text = CharBlock(
        max_length=50,
        label=_("Button text"),
        required=False,
    )
    in_row = ChoiceBlock(
        choices=[
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        label=_("Cards in row"),
        default="4",
    )
    as_carousel = BooleanBlock(
        required=False,
        help_text=_("Not working for <code>Paginated organizations</code>"),
    )
    cards = StreamBlock(
        [
            (
                "card_style_1",
                CardStle1Block(),
            ),
            (
                "card_style_2",
                CardStyle2Block(),
            ),
            (
                "card_style_3",
                CardStyle3Block(),
            ),
            (
                "card_style_4",
                CardStyle4Block(),
            ),
            (
                "card_style_5",
                CardStyle5Block(),
            ),
            (
                "card_style_6",
                CardStyle6Block(),
            ),
            (
                "organization",
                OrganizationBlock(),
            ),
            (
                "city_latest_organizations",
                LatestOrganizationsFromCityBlock(),
            ),
            (
                "organization_type_latest_organizations",
                LatestOrganizationsFromOrganizationTypeBlock(),
            ),
            (
                "paginated_organizations",
                PaginatedOrganizationsBlock(),
            ),
            (
                "rating_card",
                RatingCardBlock(),
            ),
            (
                "latest_blog_posts",
                LatestBlogPostsBlock(),
            ),
            (
                "latest_blog_posts_from_category",
                LatestBlogPostsFromCategoryBlock(),
            ),
        ],
        min_num=1,
        label=_("Cards"),
    )

    class Meta:
        template = "core/blocks/section_cards_block.html"
        label = _("Section with cards")
        icon = "rectangle-group-solid"


class QnABlock(StructBlock):
    title = CharBlock(
        max_length=255,
        label=_("Title"),
        required=True,
    )
    items = StreamBlock(
        [
            (
                "item",
                StructBlock(
                    [
                        ("question", CharBlock(max_length=255, label=_("Question"))),
                        ("answer", RichTextBlock(label=_("Answer"))),
                    ],
                    label=_("Q&A Item"),
                    icon="help",
                ),
            ),
        ],
        label=_("Q&A items"),
    )

    class Meta:
        template = "core/blocks/qna_block.html"
        label = _("Question and Answer")
        icon = "queue-list-solid"


class BannerBlock(StructBlock):
    title = CharBlock(
        max_length=255,
        label=_("Title"),
        required=False,
    )
    description = WagtailTextBlock(label=_("Description"), required=False)
    image = ImageChooserBlock(label=_("Image"))
    page = PageChooserBlock(label=_("Page"), required=False)
    url = CharBlock(
        max_length=200,
        label=_("URL"),
        required=False,
    )
    button_text = CharBlock(
        max_length=50,
        label=_("Button text"),
        required=False,
    )
    style = ChoiceBlock(
        choices=[
            ("purple-red", _("Purple-Red")),
            ("blue-green", _("Blue-Green")),
            ("light-blue", _("Light Blue")),
        ],
        label=_("Color"),
        default="purple-red",
    )

    class Meta:
        template = "core/blocks/banner_block.html"
        label = _("Banner")
        icon = "info-circle"
        value_class = LinkStructValue


class HTMLBlock(RawHTMLBlock):
    class Meta:
        template = "core/blocks/html_block.html"
        icon = "code"


class ReviewBlock(StructBlock):
    author = CharBlock(max_length=255, label=_("Author"))
    rating = ChoiceBlock(
        choices=[
            (1, "1"),
            (2, "2"),
            (3, "3"),
            (4, "4"),
            (5, "5"),
        ],
        label=_("Rating"),
    )
    comment = RichTextBlock(label=_("Comment"), features=["bold", "italic", "link"])

    class Meta:
        template = "core/blocks/review_block.html"
        label = _("Review")
        icon = "comment"


class ReviewsBlock(StructBlock):
    title = CharBlock(
        max_length=255,
        label=_("Title"),
        required=False,
    )
    reviews = StreamBlock(
        [
            ("review_card", ReviewBlock()),
        ],
        label=_("Reviews"),
    )

    class Meta:
        template = "core/blocks/reviews_block.html"
        label = _("Reviews")
        icon = "pick"


class VideoBlock(StructBlock):
    embed = EmbedBlock(label=_("Video url"))
    video_id = CharBlock(max_length=255, label=_("Video ID"))
    title = CharBlock(max_length=255, label=_("Title"))
    description = CharBlock(max_length=255, label=_("Description"))
    upload_date = DateBlock(label=_("Upload date"))
    duration = TimeBlock(label=_("Duration"), format="%H:%M:%S")
    image = ImageChooserBlock(label=_("Thumbnail image"))

    class Meta:
        template = "core/blocks/video_block.html"
        label = _("Video")
        icon = "media"
