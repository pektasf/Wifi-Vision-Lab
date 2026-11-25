from __future__ import annotations

import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
LOGS = ROOT / "logs"
DATA.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write_rows(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    """Write a complete CSV snapshot and atomically replace the destination."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fields)
    if not fieldnames or len(set(fieldnames)) != len(fieldnames):
        raise ValueError("CSV fields must be non-empty and unique.")

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8-sig",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def write_rows(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    """Append rows by atomically replacing a validated complete CSV snapshot."""
    path = Path(path)
    new_rows = list(rows)
    existing_rows = []

    if path.exists() and path.stat().st_size:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(fields):
                raise ValueError(
                    f"CSV schema mismatch for {path}: "
                    f"expected {list(fields)!r}, found {reader.fieldnames!r}"
                )
            existing_rows = list(reader)

    snapshot = [*existing_rows, *new_rows]
    from scripts.storage import write_dataset_snapshot

    write_dataset_snapshot(path.name, snapshot)
    _atomic_write_rows(path, snapshot, fields)


def overwrite_rows(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    """Persist the active SQLite snapshot, then export its CSV compatibility copy."""
    path = Path(path)
    snapshot = list(rows)
    from scripts.storage import write_dataset_snapshot

    write_dataset_snapshot(path.name, snapshot)
    _atomic_write_rows(path, snapshot, fields)
