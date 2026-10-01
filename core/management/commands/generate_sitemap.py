import multiprocessing as mp
import os
import re
import shutil
import stat
import tempfile
from argparse import ArgumentParser
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, TextIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import translation

# --------------------
# НАСТРОЙКИ
# --------------------

LIMIT = 10_000
MAX_UNCONFIRMED_SHRINK = 0.10
SITEMAP_FILENAME = re.compile(r"sitemap-([1-9][0-9]*)\.xml\Z")

SITEMAP_ROOT = os.path.join(
    settings.BASE_DIR,
    "app",
    "templates",
    "sitemaps",
)

LANGUAGES: list[str] = [code for code, _ in settings.LANGUAGES]

# имя sitemap -> app.Model
SITEMAP_PAGE_TYPES: dict[str, str] = {
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


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


@contextmanager
def atomic_xml_file(path: str) -> Iterator[TextIO]:
    """Replace an XML file only after its complete contents are written."""
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=os.path.dirname(path),
            prefix=f".{os.path.basename(path)}-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_path = output.name
            yield output
        try:
            mode = stat.S_IMODE(os.stat(path).st_mode)
        except FileNotFoundError:
            mode = 0o644
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def sitemap_files(directory: Path) -> list[Path]:
    """Return the generated section files in numeric order, without symlinks."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if SITEMAP_FILENAME.fullmatch(path.name)
            and path.is_file()
            and not path.is_symlink()
        ),
        key=lambda path: int(path.stem.removeprefix("sitemap-")),
    )


def remove_stale_files(directory: Path, current_files: set[str]) -> None:
    """Remove numbered files no longer produced by a completed section run."""
    for path in sitemap_files(directory):
        if path.name not in current_files:
            path.unlink()


def page_full_url(page: Any, *, lang: str, section: str) -> Optional[str]:
    """Resolve a page URL, reporting failures that must abort regeneration."""
    try:
        return page.full_url
    except Exception as exc:
        raise CommandError(
            f"Cannot resolve URL for {section} page "
            f"{getattr(page, 'pk', getattr(page, 'id', '?'))} [{lang}]: {exc}"
        ) from exc


def count_section_urls(directory: Path) -> int:
    """Count published URLs without loading large sitemap files into memory."""
    count = 0
    for path in sitemap_files(directory):
        try:
            for _, element in ElementTree.iterparse(path, events=("end",)):
                if element.tag.rsplit("}", 1)[-1] == "url":
                    count += 1
                element.clear()
        except ElementTree.ParseError as exc:
            raise CommandError(f"Invalid existing sitemap {path}: {exc}") from exc
    return count


def publish_section(staged_dir: Path, out_dir: Path, backup_dir: Path) -> None:
    """Publish a complete section and restore old files if publishing fails."""
    old_files = sitemap_files(out_dir)
    new_files = sitemap_files(staged_dir)
    old_names = {path.name for path in old_files}
    new_names = {path.name for path in new_files}
    backup_dir.mkdir()
    for path in old_files:
        backup_path = backup_dir / path.name
        try:
            os.link(path, backup_path)
        except OSError:
            shutil.copy2(path, backup_path)

    ensure_dir(str(out_dir))
    try:
        for path in new_files:
            old_path = out_dir / path.name
            if path.name in old_names:
                os.chmod(path, stat.S_IMODE(old_path.stat().st_mode))
            os.replace(path, old_path)
        remove_stale_files(out_dir, new_names)
    except Exception:
        for path in sitemap_files(out_dir):
            if path.name not in old_names:
                path.unlink()
        for path in old_files:
            os.replace(backup_dir / path.name, path)
        raise


def xml_text(value: str) -> str:
    return escape(value, entities={"'": "&apos;", '"': "&quot;"})


@dataclass(frozen=True)
class Job:
    sitemap_name: str
    model_path: str
    lang: str
    allow_large_shrink: bool = False


def _write_urlset_file(
    *,
    pages: Iterable,
    lang: str,
    out_dir: str,
    file_index: int,
    default_lang: str,
    languages: list[str],
    section: str | None = None,
) -> str:
    """
    Пишет urlset сразу в файл (потоково) и возвращает filename.
    Важно: предполагается, что снаружи уже активирован `lang`.
    """
    filename = f"sitemap-{file_index}.xml"
    filepath = os.path.join(out_dir, filename)
    section_name = section or os.path.basename(out_dir)

    with atomic_xml_file(filepath) as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        )

        for page in pages:
            # loc считаем в активном языке (lang) без лишних переключений
            loc_url = page_full_url(page, lang=lang, section=section_name)
            if not loc_url:
                raise CommandError(
                    f"Missing URL for {section_name} page "
                    f"{getattr(page, 'pk', getattr(page, 'id', '?'))} [{lang}]"
                )

            urls_by_lang: dict[str, Optional[str]] = {lang: loc_url}

            # hreflang (считаем остальные языки)
            for hreflang in languages:
                if hreflang == lang:
                    continue
                with activate_language(hreflang):
                    urls_by_lang[hreflang] = page_full_url(
                        page, lang=hreflang, section=section_name
                    )

            # x-default -> default_lang
            if default_lang not in urls_by_lang:
                with activate_language(default_lang):
                    urls_by_lang[default_lang] = page_full_url(
                        page, lang=default_lang, section=section_name
                    )

            f.write("  <url>\n")
            f.write(f"    <loc>{xml_text(loc_url)}</loc>\n")

            for hreflang in languages:
                href = urls_by_lang.get(hreflang)
                if not href:
                    continue
                f.write(
                    '    <xhtml:link rel="alternate" '
                    f'hreflang="{xml_text(hreflang)}" '
                    f'href="{xml_text(href)}" />\n'
                )

            default_url = urls_by_lang.get(default_lang)
            if default_url:
                f.write(
                    '    <xhtml:link rel="alternate" '
                    'hreflang="x-default" '
                    f'href="{xml_text(default_url)}" />\n'
                )

            lastmod = getattr(page, "latest_revision_created_at", None)
            if lastmod:
                f.write(f"    <lastmod>{lastmod:%Y-%m-%d}</lastmod>\n")

            f.write("  </url>\n")

        f.write("</urlset>\n")

    return filename


def _run_job(args: tuple[Job, str, list[str], int]) -> list[str]:
    """
    Воркер для multiprocessing (spawn-safe).
    Возвращает список <loc> (URL'ы sitemap-файлов) для sitemapindex.
    """
    job, sitemap_root, languages, limit = args

    # Важно: в spawn-процессе нужно инициировать Django ДО импортов моделей Wagtail
    import django  # noqa: WPS433 (локальный импорт намеренно)

    django.setup()

    close_old_connections()

    from django.apps import apps as dj_apps  # noqa: WPS433
    from django.conf import settings as dj_settings  # noqa: WPS433
    from wagtail.models import Site  # noqa: WPS433

    ensure_dir(sitemap_root)

    site = Site.objects.get(is_default_site=True)
    base_url = site.root_url.rstrip("/")

    default_lang = dj_settings.LANGUAGE_CODE

    model = dj_apps.get_model(job.model_path)
    base_qs = model.objects.live().exclude(depth=1).order_by("id")

    total = base_qs.count()
    out_dir = Path(sitemap_root, job.lang, job.sitemap_name)
    previous_count = count_section_urls(out_dir)
    index_entries: list[str] = []
    processed_count = 0

    try:
        with tempfile.TemporaryDirectory(
            dir=sitemap_root, prefix=f".{job.lang}-{job.sitemap_name}-"
        ) as temporary_root:
            staged_dir = Path(temporary_root, "staged")
            staged_dir.mkdir()
            backup_dir = Path(temporary_root, "backup")
            file_index = 1
            pages_buffer: list[Any] = []

            with activate_language(job.lang):
                page_iter = base_qs.iterator(chunk_size=min(limit, 5000))
                for page in page_iter:
                    processed_count += 1
                    pages_buffer.append(page)
                    if len(pages_buffer) >= limit:
                        filename = _write_urlset_file(
                            pages=pages_buffer,
                            lang=job.lang,
                            out_dir=str(staged_dir),
                            file_index=file_index,
                            default_lang=default_lang,
                            languages=languages,
                            section=job.sitemap_name,
                        )
                        index_entries.append(
                            f"{base_url}/sitemaps/{job.lang}/{job.sitemap_name}/{filename}"
                        )
                        file_index += 1
                        pages_buffer.clear()

                if pages_buffer:
                    filename = _write_urlset_file(
                        pages=pages_buffer,
                        lang=job.lang,
                        out_dir=str(staged_dir),
                        file_index=file_index,
                        default_lang=default_lang,
                        languages=languages,
                        section=job.sitemap_name,
                    )
                    index_entries.append(
                        f"{base_url}/sitemaps/{job.lang}/{job.sitemap_name}/{filename}"
                    )

            if processed_count != total:
                raise CommandError(
                    f"{job.sitemap_name} [{job.lang}]: selected {total} pages, "
                    f"processed {processed_count}; existing sitemap was preserved"
                )
            if (
                previous_count
                and processed_count < previous_count * (1 - MAX_UNCONFIRMED_SHRINK)
                and not job.allow_large_shrink
            ):
                raise CommandError(
                    f"{job.sitemap_name} [{job.lang}]: existing sitemap has "
                    f"{previous_count} URLs, new selection has {processed_count}; "
                    "use --allow-large-shrink only after verifying the reduction"
                )

            publish_section(staged_dir, out_dir, backup_dir)
    finally:
        close_old_connections()

    return index_entries


# --------------------
# COMMAND
# --------------------


class Command(BaseCommand):
    help = (
        "Генерирует sitemap для Wagtail + wagtail-modeltranslation "
        "(URL с языковым префиксом, hreflang). Поддерживает ускорение через multiprocessing."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--lang",
            action="append",
            dest="langs",
            help="Генерировать только для указанного языка. Можно указывать несколько раз.",
        )
        parser.add_argument(
            "--only",
            action="append",
            dest="only",
            help="Генерировать только указанные sitemap (ключ из SITEMAP_PAGE_TYPES). Можно указывать несколько раз.",
        )
        parser.add_argument(
            "--exclude",
            action="append",
            dest="exclude",
            help="Skip a sitemap section by its SITEMAP_PAGE_TYPES key. Repeat as needed.",
        )
        parser.add_argument(
            "--processes",
            type=int,
            default=1,
            help="Количество процессов для параллельной генерации (1 = без параллели).",
        )
        parser.add_argument(
            "--allow-large-shrink",
            action="store_true",
            help="Allow a section to lose more than 10%% of its existing URLs.",
        )

    def handle(self, *args: object, **options: Any) -> None:
        ensure_dir(SITEMAP_ROOT)

        requested_langs = options.get("langs") or None
        requested_only = options.get("only") or None
        excluded = set(options.get("exclude") or [])
        processes = int(options.get("processes") or 1)
        if processes < 1:
            processes = 1

        langs = [
            lang for lang in LANGUAGES if not requested_langs or lang in requested_langs
        ]
        if not langs:
            self.stdout.write(self.style.WARNING("ℹ️ Не найдено языков для генерации."))
            return

        sitemap_items = list(SITEMAP_PAGE_TYPES.items())
        if requested_only:
            sitemap_items = [(k, v) for k, v in sitemap_items if k in requested_only]
        if excluded:
            sitemap_items = [(k, v) for k, v in sitemap_items if k not in excluded]
        if not sitemap_items:
            self.stdout.write(self.style.WARNING("ℹ️ Не найдено sitemap для генерации."))
            return

        # Папки заранее
        for sitemap_name, _ in sitemap_items:
            for lang in langs:
                ensure_dir(os.path.join(SITEMAP_ROOT, lang, sitemap_name))

        # Собираем задания (lang x sitemap_name)
        jobs = [
            Job(
                sitemap_name=k,
                model_path=v,
                lang=lang,
                allow_large_shrink=bool(options.get("allow_large_shrink")),
            )
            for k, v in sitemap_items
            for lang in langs
        ]

        if processes == 1 or len(jobs) == 1:
            # Последовательно
            for job in jobs:
                self.stdout.write(f"→ {job.sitemap_name} [{job.lang}]")
                _run_job((job, SITEMAP_ROOT, LANGUAGES, LIMIT))
        else:
            # Параллельно (spawn-safe на macOS/Windows)
            ctx = mp.get_context("spawn")
            work = [(job, SITEMAP_ROOT, LANGUAGES, LIMIT) for job in jobs]

            with ctx.Pool(processes=processes) as pool:
                # Важно: imap_unordered возвращает результаты не по порядку — это нормально
                for _ in pool.imap_unordered(_run_job, work, chunksize=1):
                    pass

        from wagtail.models import Site

        base_url = Site.objects.get(is_default_site=True).root_url.rstrip("/")
        sitemap_index_entries = self.collect_index_entries(base_url)
        self.write_index(sitemap_index_entries)
        if sitemap_index_entries:
            self.stdout.write(self.style.SUCCESS("✅ Sitemap успешно сгенерированы"))
        else:
            self.stdout.write(self.style.WARNING("ℹ️ Нет данных для генерации sitemap."))

    def collect_index_entries(self, base_url: str) -> list[tuple[str, str]]:
        """Build the index from all existing generated sections, including skipped ones."""
        entries: list[tuple[str, str]] = []
        for section in SITEMAP_PAGE_TYPES:
            for lang in LANGUAGES:
                directory = Path(SITEMAP_ROOT, lang, section)
                for path in sitemap_files(directory):
                    modified = datetime.fromtimestamp(
                        path.stat().st_mtime, tz=datetime_timezone.utc
                    ).date()
                    loc = f"{base_url}/sitemaps/{lang}/{section}/{path.name}"
                    entries.append((loc, modified.isoformat()))
        return entries

    def write_index(self, entries: list[tuple[str, str]]) -> None:
        """Replace the index only after every selected section finished successfully."""
        index_path = os.path.join(SITEMAP_ROOT, "sitemap.xml")
        with atomic_xml_file(index_path) as output:
            output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            output.write(
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            )

            for loc, lastmod in entries:
                output.write("  <sitemap>\n")
                output.write(f"    <loc>{xml_text(loc)}</loc>\n")
                output.write(f"    <lastmod>{lastmod}</lastmod>\n")
                output.write("  </sitemap>\n")

            output.write("</sitemapindex>\n")
