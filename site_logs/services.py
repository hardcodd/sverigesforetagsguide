"""Read and securely expose bounded application log data to administrators."""

from __future__ import annotations

import os
import stat
from typing import BinaryIO
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from site_logs.logging import LOG_FILE_PATTERN, LOG_LEVEL_NAMES, LOG_RECORD_SEPARATOR


@dataclass(frozen=True)
class LogRecords:
    """Return bounded log records together with the number of files consulted."""

    records: tuple[str, ...]
    files_read: int


@dataclass(frozen=True)
class DownloadableLogFile:
    """Describe a validated log file available for download."""

    name: str
    size: int
    modified_at: datetime


def _current_log_files(
    log_dir: Path,
    level_name: str,
    file_limit: int,
) -> list[Path]:
    candidates: list[tuple[int, Path]] = []
    for path in log_dir.glob(f"{level_name}.*.log"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            modified_at = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
        candidates.append((modified_at, path))

    candidates.sort(reverse=True)
    return [path for _, path in candidates[:file_limit]]


def _read_tail(path: Path, byte_limit: int) -> list[str]:
    with path.open("rb") as log_file:
        log_file.seek(0, 2)
        file_size = log_file.tell()
        offset = max(file_size - byte_limit, 0)
        log_file.seek(offset)
        content = log_file.read(byte_limit).decode("utf-8", errors="replace")

    has_complete_final_record = content.rstrip().endswith(LOG_RECORD_SEPARATOR)
    parts = content.split(LOG_RECORD_SEPARATOR)
    if offset:
        parts = parts[1:]
    if not has_complete_final_record:
        parts = parts[:-1]
    return [part.strip() for part in parts if part.strip()]


def read_recent_log_records(
    log_dir: str | Path,
    level_name: str,
    *,
    record_limit: int,
    file_limit: int,
    bytes_per_file: int,
) -> LogRecords:
    """Read the newest complete log records within explicit resource limits."""
    if level_name not in LOG_LEVEL_NAMES:
        raise ValueError(f"Unsupported log level group: {level_name}")
    if min(record_limit, file_limit, bytes_per_file) <= 0:
        raise ValueError("Log reading limits must be greater than zero.")

    log_dir = Path(log_dir)
    if not log_dir.is_dir():
        return LogRecords(records=(), files_read=0)

    log_files = _current_log_files(log_dir, level_name, file_limit)
    records: list[str] = []
    files_read = 0
    for path in log_files:
        try:
            records.extend(_read_tail(path, bytes_per_file))
        except FileNotFoundError:
            continue
        files_read += 1

    records.sort(key=lambda record: record.split(" | ", 1)[0], reverse=True)
    return LogRecords(
        records=tuple(records[:record_limit]),
        files_read=files_read,
    )


def list_downloadable_log_files(
    log_dir: str | Path,
    level_name: str,
    file_limit: int,
) -> tuple[DownloadableLogFile, ...]:
    """List recent regular log files from one validated severity group."""
    if level_name not in LOG_LEVEL_NAMES:
        raise ValueError(f"Unsupported log level group: {level_name}")
    if file_limit <= 0:
        raise ValueError("The file limit must be greater than zero.")

    log_dir = Path(log_dir)
    if not log_dir.is_dir():
        return ()

    files: list[DownloadableLogFile] = []
    for path in log_dir.iterdir():
        match = LOG_FILE_PATTERN.fullmatch(path.name)
        if (
            match is None
            or match.group(1) != level_name
            or path.is_symlink()
            or not path.is_file()
        ):
            continue
        try:
            file_stat = path.stat()
        except FileNotFoundError:
            continue
        files.append(
            DownloadableLogFile(
                name=path.name,
                size=file_stat.st_size,
                modified_at=datetime.fromtimestamp(file_stat.st_mtime, UTC),
            )
        )

    files.sort(key=lambda log_file: log_file.modified_at, reverse=True)
    return tuple(files[:file_limit])


def open_log_file(log_dir: str | Path, filename: str) -> BinaryIO:
    """Open a named regular log file without following symbolic links."""
    if LOG_FILE_PATTERN.fullmatch(filename) is None:
        raise FileNotFoundError(filename)

    path = Path(log_dir) / filename
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    file_descriptor = os.open(path, flags)
    if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
        os.close(file_descriptor)
        raise FileNotFoundError(filename)
    return os.fdopen(file_descriptor, "rb")
