"""Shared result and error contract for local data collectors."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any, Callable


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _record_count(value: Any) -> int | None:
    """Count records for common collector return shapes without guessing."""
    if isinstance(value, list):
        return len(value)
    if isinstance(value, tuple) and len(value) >= 2 and isinstance(value[1], list):
        return len(value[1])
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        return len(value["records"])
    return None


@dataclass(frozen=True)
class CollectorError:
    source: str
    code: str
    message: str
    recoverable: bool
    occurred_at: str


@dataclass
class CollectorResult:
    collector: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: int
    records_count: int | None
    warnings: list[str] = field(default_factory=list)
    errors: list[CollectorError] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Kept in memory for orchestration; deliberately excluded from serialized output.
    exception: Exception | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("exception", None)
        return payload


def run_collector(
    collector: str,
    callback: Callable[[], Any],
    *,
    optional: bool = False,
) -> tuple[Any, CollectorResult]:
    """Run one collector and always return a normalized result envelope."""
    started_at = _timestamp()
    started_clock = perf_counter()
    try:
        value = callback()
        status = "no_data" if value is None or value == [] else "success"
        result = CollectorResult(
            collector=collector,
            status=status,
            started_at=started_at,
            finished_at=_timestamp(),
            duration_ms=max(0, round((perf_counter() - started_clock) * 1000)),
            records_count=_record_count(value),
            metadata={"return_type": type(value).__name__},
        )
        return value, result
    except Exception as exc:
        error = CollectorError(
            source=collector,
            code=type(exc).__name__,
            message=str(exc)[:500] or type(exc).__name__,
            recoverable=optional,
            occurred_at=_timestamp(),
        )
        result = CollectorResult(
            collector=collector,
            status="failed",
            started_at=started_at,
            finished_at=_timestamp(),
            duration_ms=max(0, round((perf_counter() - started_clock) * 1000)),
            records_count=None,
            errors=[error],
            metadata={"return_type": None},
            exception=exc,
        )
        return None, result
