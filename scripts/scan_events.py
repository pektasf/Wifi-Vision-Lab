"""Small JSON-lines protocol for scan progress events.

Events are written to stdout with a stable prefix so the background runner can
consume progress without coupling the UI to collector log wording.
"""
from __future__ import annotations

import json
import math
import sys
from typing import Any

EVENT_PREFIX = "WIFI_VISION_EVENT "


def emit_progress(stage: str, progress: float, message: str = "") -> None:
    """Emit one bounded progress event for the parent process."""
    numeric_progress = float(progress)
    if not math.isfinite(numeric_progress):
        raise ValueError("progress must be a finite number")
    event = {
        "type": "progress",
        "stage": str(stage)[:120],
        "progress": max(0.0, min(1.0, numeric_progress)),
        "message": str(message)[:500],
    }
    sys.stdout.write(EVENT_PREFIX + json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def parse_event_line(line: str) -> dict[str, Any] | None:
    """Parse a supported event line; return None for ordinary or invalid logs."""
    if not line.startswith(EVENT_PREFIX):
        return None
    try:
        event = json.loads(line[len(EVENT_PREFIX):])
    except (TypeError, ValueError):
        return None
    if not isinstance(event, dict) or event.get("type") != "progress":
        return None
    stage = event.get("stage")
    progress = event.get("progress")
    if not isinstance(stage, str) or not isinstance(progress, (int, float)):
        return None
    if isinstance(progress, bool) or not math.isfinite(float(progress)):
        return None
    return {
        "stage": stage[:120],
        "progress": max(0.0, min(1.0, float(progress))),
        "message": str(event.get("message", ""))[:500],
    }
