from django.db.models import Q
from django.test import SimpleTestCase, override_settings

from core.export_views import (
    get_parent_page_search_query,
    remove_base_fields_with_translations,
)


@override_settings(MODELTRANSLATION_LANGUAGES=["ru", "ka", "en"])
class RemoveBaseFieldsWithTranslationsTests(SimpleTestCase):
    def test_localized_fields_inherit_the_base_field_default(self):
        fields = [
            {"name": "title", "label": "Title", "default": True},
            {"name": "slug", "label": "Slug", "default": True},
            {"name": "description", "label": "Description", "default": False},
            {"name": "title_ru", "label": "Title [ru]", "default": False},
            {"name": "title_ka", "label": "Title [ka]", "default": False},
            {"name": "title_en", "label": "Title [en]", "default": False},
            {
                "name": "description_ru",
                "label": "Description [ru]",
                "default": False,
            },
        ]

        result = remove_base_fields_with_translations(fields)
        result_by_name = {field["name"]: field for field in result}

        self.assertNotIn("title", result_by_name)
        self.assertNotIn("description", result_by_name)
        self.assertTrue(result_by_name["title_ru"]["default"])
        self.assertTrue(result_by_name["title_ka"]["default"])
        self.assertTrue(result_by_name["title_en"]["default"])
        self.assertEqual(result_by_name["title_ru"]["translation_group"], "title")
        self.assertEqual(result_by_name["title_ka"]["translation_group"], "title")
        self.assertEqual(result_by_name["title_en"]["translation_group"], "title")
        self.assertFalse(result_by_name["description_ru"]["default"])
        self.assertEqual(
            result_by_name["description_ru"]["translation_group"],
            "description",
        )

    def test_base_field_is_kept_when_it_has_no_localized_fields(self):
        fields = [
            {"name": "slug", "label": "Slug", "default": True},
        ]

        result = remove_base_fields_with_translations(fields)

        self.assertEqual(result, fields)


class GetParentPageSearchQueryTests(SimpleTestCase):
    def test_text_query_searches_by_title(self):
        self.assertEqual(
            get_parent_page_search_query("рестораны"),
            Q(title__icontains="рестораны"),
        )

    def test_numeric_query_searches_by_title_or_id(self):
        self.assertEqual(
            get_parent_page_search_query("#410"),
            Q(title__icontains="#410") | Q(id=410),
        )
