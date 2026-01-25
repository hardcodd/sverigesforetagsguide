import math
import os
from contextlib import contextmanager

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone, translation
from wagtail.models import Site

# --------------------
# НАСТРОЙКИ
# --------------------

LIMIT = 10_000

SITEMAP_ROOT = os.path.join(
    settings.BASE_DIR,
    "app",
    "templates",
    "sitemaps",
)

LANGUAGES = [code for code, _ in settings.LANGUAGES]

# имя sitemap -> app.Model
SITEMAP_PAGE_TYPES = {
    "catalog_cities": "catalog.City",
    "catalog_organization_types": "catalog.OrganizationType",
    "catalog_organizations": "catalog.Organization",
    "authors_index": "authors.AuthorsIndexPage",
    "authors": "authors.AuthorPage",
    "blog_index": "blog.BlogIndexPage",
    "blog_categories": "blog.BlogCategoryPage",
    "blog_posts": "blog.BlogPostPage",
    "pages_home": "home.HomePage",
    "pages_flat": "home.FlatPage",
    "pages_contact": "home.ContactPage",
    "ratings_index": "ratings.RatingsIndexPage",
    "ratings_categories": "ratings.RatingCategoryPage",
    "ratings_posts": "ratings.RatingPage",
}


# --------------------
# HELPERS
# --------------------


@contextmanager
def activate_language(lang: str):
    old_lang = translation.get_language()
    translation.activate(lang)
    try:
        yield
    finally:
        translation.activate(old_lang)


# --------------------
# COMMAND
# --------------------


class Command(BaseCommand):
    help = (
        "Генерирует sitemap для Wagtail + wagtail-modeltranslation "
        "(URL с языковым префиксом, hreflang)"
    )

    def handle(self, *args, **options):
        os.makedirs(SITEMAP_ROOT, exist_ok=True)

        site = Site.objects.get(is_default_site=True)
        base_url = site.root_url.rstrip("/")

        sitemap_index_entries: list[str] = []

        for sitemap_name, model_path in SITEMAP_PAGE_TYPES.items():
            model = apps.get_model(model_path)

            pages_qs = (
                model.objects.live().public().exclude(depth=1)
                # .only(
                #     "id",
                #     "url_path",
                #     "latest_revision_created_at",
                # )
            )

            total_pages = pages_qs.count()
            if not total_pages:
                continue

            chunks = math.ceil(total_pages / LIMIT)

            for lang in LANGUAGES:
                out_dir = os.path.join(
                    SITEMAP_ROOT,
                    lang,
                    sitemap_name,
                )
                os.makedirs(out_dir, exist_ok=True)

                self.stdout.write(
                    f"{sitemap_name} [{lang}] — {total_pages} страниц, {chunks} файлов"
                )

                with activate_language(lang):
                    for i in range(chunks):
                        pages = pages_qs.order_by("id")[i * LIMIT : (i + 1) * LIMIT]

                        filename = f"sitemap-{i + 1}.xml"
                        filepath = os.path.join(out_dir, filename)

                        with open(filepath, "w", encoding="utf-8") as f:
                            self.write_urlset(
                                file=f,
                                pages=pages,
                            )

                        sitemap_index_entries.append(
                            f"{base_url}/sitemaps/{lang}/{sitemap_name}/{filename}"
                        )

        self.write_index(sitemap_index_entries)

        self.stdout.write(self.style.SUCCESS("✅ Sitemap успешно сгенерированы"))

    # --------------------
    # XML WRITERS
    # --------------------

    def write_urlset(self, *, file, pages):
        file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        file.write(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        )

        for page in pages:
            try:
                loc_url = page.full_url
            except Exception:
                continue

            file.write("  <url>\n")
            file.write(f"    <loc>{loc_url}</loc>\n")

            # hreflang для всех языков
            for lang in LANGUAGES:
                with translation.override(lang):
                    try:
                        alt_url = page.full_url
                    except Exception:
                        continue

                file.write(
                    '    <xhtml:link rel="alternate" '
                    f'hreflang="{lang}" '
                    f'href="{alt_url}" />\n'
                )

            # x-default (если используется)
            with translation.override(settings.LANGUAGE_CODE):
                try:
                    default_url = page.full_url
                except Exception:
                    default_url = None

            if default_url:
                file.write(
                    '    <xhtml:link rel="alternate" '
                    'hreflang="x-default" '
                    f'href="{default_url}" />\n'
                )

            if page.latest_revision_created_at:
                lastmod = page.latest_revision_created_at.strftime("%Y-%m-%d")
                file.write(f"    <lastmod>{lastmod}</lastmod>\n")

            file.write("  </url>\n")

        file.write("</urlset>\n")

    def write_index(self, entries: list[str]):
        index_path = os.path.join(SITEMAP_ROOT, "sitemap.xml")
        now = timezone.now().strftime("%Y-%m-%d")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            )

            for loc in entries:
                f.write("  <sitemap>\n")
                f.write(f"    <loc>{loc}</loc>\n")
                f.write(f"    <lastmod>{now}</lastmod>\n")
                f.write("  </sitemap>\n")

            f.write("</sitemapindex>\n")
