import math
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from wagtail.contrib.sitemaps.sitemap_generator import Sitemap
from wagtail.models import Page, Site

SITEMAP_DIR = os.path.join(settings.BASE_DIR, "app", "templates", "sitemaps")
SITEMAP_URL = Site.objects.first().root_url
LIMIT = 10000  # сколько страниц в одном sitemap-файле


class Command(BaseCommand):
    help = "Генерирует статические sitemap XML файлы для Wagtail страниц"

    def handle(self, *args, **options):
        os.makedirs(SITEMAP_DIR, exist_ok=True)

        # Берем только нужные поля — чтобы не грузить всю модель
        pages_qs = (
            Page.objects.live()
            .exclude(depth=1)
            .public()
            .only("id", "url_path", "latest_revision_created_at")
        )
        total = pages_qs.count()
        chunks = math.ceil(total / LIMIT)

        self.stdout.write(
            self.style.NOTICE(
                f"Найдено {total} страниц, создаю {chunks} sitemap-файлов..."
            )
        )

        sitemap_files = []

        for i in range(chunks):
            start = i * LIMIT
            end = start + LIMIT
            pages = pages_qs.order_by("id")[start:end]

            filename = f"sitemap-{i+1}.xml"
            filepath = os.path.join(SITEMAP_DIR, filename)
            sitemap_files.append(filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write(
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                )
                for page in pages:
                    try:
                        url = page.full_url
                    except Exception:
                        continue
                    f.write("  <url>\n")
                    f.write(f"    <loc>{url}</loc>\n")
                    if page.latest_revision_created_at:
                        lastmod = page.latest_revision_created_at.strftime(
                            "%Y-%m-%d")
                        f.write(f"    <lastmod>{lastmod}</lastmod>\n")
                    f.write("  </url>\n")
                f.write("</urlset>\n")

            self.stdout.write(self.style.SUCCESS(f"Создан {filename}"))

        # sitemap index
        index_path = os.path.join(SITEMAP_DIR, "sitemap.xml")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            )
            now = timezone.now().strftime("%Y-%m-%d")
            for name in sitemap_files:
                f.write("  <sitemap>\n")
                f.write(f"    <loc>{SITEMAP_URL}/{name}</loc>\n")
                f.write(f"    <lastmod>{now}</lastmod>\n")
                f.write("  </sitemap>\n")
            f.write("</sitemapindex>\n")

        self.stdout.write(
            self.style.SUCCESS(f"✅ Sitemap успешно создан в {SITEMAP_DIR}")
        )
