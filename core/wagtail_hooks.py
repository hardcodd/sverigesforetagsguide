import os
import time
from pathlib import Path

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from draftjs_exporter.dom import DOM
from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.admin.rich_text.converters.html_to_contentstate import BlockElementHandler
from wagtail.admin.rich_text.editors.draftail.features import BlockFeature
from wagtail.images import get_image_model
from wagtail.images.formats import (
    Format,
    register_image_format,
    unregister_image_format,
)
from wagtail.snippets.models import register_snippet

from core.export_views import export_pages
from core.import_views import import_pages
from core.staticfiles import versioned_static
from core.views import FooterViewSet


@hooks.register("register_icons")  # type: ignore
def register_icons(icons):
    return icons + [
        "icons/building-solid.svg",
        "icons/store-solid.svg",
        "icons/briefcase-solid.svg",
        "icons/rectangle-group-solid.svg",
        "icons/queue-list-solid.svg",
        "icons/text-center.svg",
        "icons/text-right.svg",
    ]


@receiver(post_save, sender=get_image_model())
def crop_uploaded_image(sender, instance, created=False, **kwargs):
    # Only run on initial save
    if not created:
        return

    CROP_SPEC = "max-2560x1440"
    file_type = instance.file.name.split(".")[-1].lower()
    if file_type in ["jpeg", "jpg"]:
        CROP_SPEC += "|jpegquality-60"

    if file_type in ["svg", "ico", "gif"]:
        # Skip cropping for these file types
        return

    # Prevent recursion on instance.save()
    if getattr(instance, "_cropping", False):
        return
    instance._cropping = True

    original_file = instance.file.path

    # --- Generate rendition ---
    rendition = instance.get_rendition(CROP_SPEC)
    crop_path = Path(rendition.file.path)

    # --- Wait for rendition file to be actually written (race condition fix) ---
    timeout = 20  # seconds
    start = time.time()

    while not crop_path.exists():
        if time.time() - start > timeout:
            print(f"[CROP ERROR] Rendition not generated: {crop_path}")
            return  # do nothing, avoid breaking upload
        time.sleep(0.1)

    # --- Replace original file ---
    try:
        os.remove(original_file)
    except FileNotFoundError:
        pass

    os.rename(crop_path, original_file)

    # --- Update instance metadata ---
    instance.width = rendition.width
    instance.height = rendition.height
    instance.file_size = os.path.getsize(original_file)

    instance.save(update_fields=["width", "height", "file_size"])


unregister_image_format("fullwidth")
unregister_image_format("left")
unregister_image_format("right")

register_image_format(
    Format("fullwidth", _("Full width"), "richtext-image fullwidth", "width-1200")
)
register_image_format(
    Format("left", _("Left-aligned"), "richtext-image left", "width-500")
)
register_image_format(
    Format("right", _("Right-aligned"), "richtext-image right", "width-500")
)


@hooks.register("insert_global_admin_js")  # type: ignore
def global_admin_js():
    return format_html(
        '<script src="{}"></script>', versioned_static("madloba-admin.js")
    )


@hooks.register("insert_global_admin_js")  # type: ignore
def import_admin_js():
    return format_html(
        '<script src="{}"></script>', versioned_static("madloba-import.js")
    )


@hooks.register("insert_global_admin_js")  # type: ignore
def export_admin_js():
    return format_html(
        '<script src="{}"></script>', versioned_static("madloba-export.js")
    )


@hooks.register("insert_global_admin_css")  # type: ignore
def global_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">', versioned_static("madloba-admin.css")
    )


register_snippet(FooterViewSet)


# -----------------------------
# ALIGN CENTER
# -----------------------------
@hooks.register("register_rich_text_features")
def register_align_center(features):
    feature_name = "align-center"
    type_ = "ALIGN_CENTER"
    tag = "p"

    control = {
        "type": type_,
        "icon": "text-center",
        "description": "Align Center",
        "element": tag,
    }

    # Register block-level feature
    features.register_editor_plugin("draftail", feature_name, BlockFeature(control))

    # Database conversion
    features.register_converter_rule(
        "contentstate",
        feature_name,
        {
            "from_database_format": {
                f'{tag}[class="text-center"]': BlockElementHandler(type_)
            },
            "to_database_format": {
                "block_map": {
                    type_: {"element": tag, "props": {"class": "text-center"}}
                }
            },
        },
    )

    features.default_features.append(feature_name)


# -----------------------------
# ALIGN RIGHT
# -----------------------------
@hooks.register("register_rich_text_features")
def register_align_right(features):
    feature_name = "align-right"
    type_ = "ALIGN_RIGHT"
    tag = "p"

    control = {
        "type": type_,
        "icon": "text-right",
        "description": "Align Right",
        "element": tag,
    }

    features.register_editor_plugin("draftail", feature_name, BlockFeature(control))

    features.register_converter_rule(
        "contentstate",
        feature_name,
        {
            "from_database_format": {
                f'{tag}[class="text-right"]': BlockElementHandler(type_)
            },
            "to_database_format": {
                "block_map": {type_: {"element": tag, "props": {"class": "text-right"}}}
            },
        },
    )

    features.default_features.append(feature_name)


# -----------------------------
# INLINE CODE
# -----------------------------
def code_block_element(props):
    text = props["block"].get("text", "")

    return DOM.create_element(
        "code",
        {},
        f"{text}\n",
    )


@hooks.register("register_rich_text_features")
def register_code_block(features):
    feature_name = "code-block"
    type_ = "code-block"

    control = {
        "type": type_,
        "label": "{}",
        "description": "Code Block",
        "element": "pre",
    }

    features.register_editor_plugin(
        "draftail",
        feature_name,
        BlockFeature(control),
    )

    features.register_converter_rule(
        "contentstate",
        feature_name,
        {
            "from_database_format": {
                "pre": BlockElementHandler(type_),
                "pre code": BlockElementHandler(type_),
            },
            "to_database_format": {
                "block_map": {
                    type_: {
                        "element": code_block_element,
                        "wrapper": "pre",
                    }
                }
            },
        },
    )

    features.default_features.append(feature_name)


@hooks.register("register_admin_urls")
def register_import_export_pages():
    return [
        path("import-pages/", import_pages, name="import-pages"),
        path("export-pages/", export_pages, name="export-pages"),
    ]


@hooks.register("register_admin_menu_item")
def register_import_export_pages_menu_item():
    submenu = Menu(
        items=[
            MenuItem(
                _("Import pages"),
                reverse("import-pages"),
                icon_name="order-down",
            ),
            MenuItem(
                _("Export pages"),
                reverse("export-pages"),
                icon_name="order-up",
            ),
        ]
    )

    return SubmenuMenuItem(_("Import / Export"), submenu, icon_name="resubmit")
