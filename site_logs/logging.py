"""Configure process-safe Loguru sinks and bridge standard-library logging."""

from __future__ import annotations

import gzip
import inspect
import logging
import os
import re
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from collections.abc import Callable, Mapping
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from loguru import logger

LOG_RECORD_SEPARATOR = "--- END LOG RECORD ---"
LOG_LEVEL_NAMES = ("warnings", "errors")

LOG_FILE_PATTERN = re.compile(
    r"^(warnings|errors)\.(\d+)\.\d{8}T\d{12}Z(?:\..+)?\.log(?:\.gz)?$"
)
_configured_process_id: int | None = None


def _validate_positive_setting(name: str) -> int:
    value = getattr(settings, name)
    if value <= 0:
        raise ImproperlyConfigured(f"{name} must be greater than zero.")
    return value


def _secure_file_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


def _secure_gzip_compression(path: str) -> None:
    source = Path(path)
    destination = Path(f"{path}.gz")
    try:
        with source.open("rb") as source_file:
            file_descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(file_descriptor, "wb") as destination_file:
                with gzip.GzipFile(fileobj=destination_file, mode="wb") as archive:
                    shutil.copyfileobj(source_file, archive)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    source.unlink()


def _log_format(record: Mapping[str, Any]) -> str:
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS ZZ} | {level: <8} | "
        "pid={process.id} | {name}:{function}:{line} | {message}\n"
        "{exception}\n"
        f"{LOG_RECORD_SEPARATOR}\n"
    )


def _is_level_range(
    minimum: int,
    maximum: int | None = None,
) -> Callable[[Mapping[str, Any]], bool]:
    def filter_record(record: Mapping[str, Any]) -> bool:
        severity = record["level"].no
        return severity >= minimum and (maximum is None or severity < maximum)

    return filter_record


def _process_is_running(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def clean_old_log_files(
    log_dir: Path,
    retention_days: Mapping[str, int],
    now: datetime | None = None,
) -> None:
    """Delete expired logs while preserving files owned by live processes."""
    now = now or datetime.now(UTC)

    for path in log_dir.iterdir():
        match = LOG_FILE_PATTERN.fullmatch(path.name)
        if match is None or path.is_symlink() or not path.is_file():
            continue

        level_name, process_id = match.groups()
        current_file = path.name.endswith("Z.log")
        if current_file and _process_is_running(int(process_id)):
            continue

        modified_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if now - modified_at <= timedelta(days=retention_days[level_name]):
            continue

        try:
            path.unlink()
        except FileNotFoundError:
            pass


def configure_loguru() -> None:
    """Configure per-process console, warning, and error Loguru sinks once."""
    global _configured_process_id

    process_id = os.getpid()
    if _configured_process_id == process_id:
        return

    rotation_mb = _validate_positive_setting("SITE_LOG_ROTATION_MB")
    warning_retention_days = _validate_positive_setting(
        "SITE_LOG_WARNING_RETENTION_DAYS"
    )
    error_retention_days = _validate_positive_setting("SITE_LOG_ERROR_RETENTION_DAYS")
    log_dir = Path(settings.SITE_LOG_DIR)
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.SITE_LOG_CONSOLE_LEVEL,
        format=_log_format,
        backtrace=False,
        diagnose=False,
    )

    retention_days = {
        "warnings": warning_retention_days,
        "errors": error_retention_days,
    }
    try:
        clean_old_log_files(log_dir, retention_days)
    except OSError:
        logger.exception("Old application log files could not be cleaned up")

    started_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    common_options = {
        "rotation": f"{rotation_mb} MB",
        "compression": _secure_gzip_compression,
        "format": _log_format,
        "backtrace": False,
        "diagnose": False,
        "delay": True,
        "encoding": "utf-8",
        "errors": "backslashreplace",
        "opener": _secure_file_opener,
    }
    logger.add(
        log_dir / f"warnings.{process_id}.{started_at}.log",
        level="WARNING",
        filter=_is_level_range(30, 40),
        retention=f"{warning_retention_days} days",
        **common_options,
    )
    logger.add(
        log_dir / f"errors.{process_id}.{started_at}.log",
        level="ERROR",
        filter=_is_level_range(40),
        retention=f"{error_retention_days} days",
        **common_options,
    )
    _configured_process_id = process_id


class InterceptHandler(logging.Handler):
    """Forward standard-library log records to the configured Loguru sinks."""

    def emit(self, record: logging.LogRecord) -> None:
        """Forward a log record while preserving level and exception context."""
        configure_loguru()

        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = inspect.currentframe()
        depth = 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )
