"""Normalize local network observations into one searchable event timeline."""
from __future__ import annotations

import hashlib
import json

import pandas as pd

EVENT_SOURCES = {
    "device_events.csv": "Cihaz olayları",
    "network_events.csv": "Ağ olayları",
    "live_events.csv": "Canlı izleme",
    "behavior_findings.csv": "Davranış analizi",
}

TIME_FIELDS = ("event_time", "timestamp", "observed_at", "time")
TYPE_FIELDS = ("event_type", "event", "type", "event_name")
DETAIL_FIELDS = ("details", "detail", "description", "message")

EVENT_SEVERITY = {
    "ip_changed": "warning",
    "not_in_latest_scan": "warning",
    "ping_not_responding": "warning",
    "multiple_ips_same_mac": "review",
    "multiple_macs_same_ip": "review",
}


def _value(row: pd.Series, fields: tuple[str, ...], default: str = "") -> str:
    for field in fields:
        value = row.get(field, "")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return default


def _severity(row: pd.Series, event_type: str) -> str:
    explicit = _value(row, ("severity",))
    if explicit:
        return explicit
    return EVENT_SEVERITY.get(event_type.strip().lower(), "info")


def summarize_event_severity(frame: pd.DataFrame) -> dict[str, int]:
    """Count normalized severity levels, including any custom explicit levels."""
    if frame is None or frame.empty or "severity" not in frame.columns:
        return {}
    values = frame["severity"].fillna("").astype(str).str.strip().str.lower()
    values = values[values != ""]
    counts = values.value_counts()
    return {str(level): int(count) for level, count in counts.items()}


def normalize_event_frames(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a stable, newest-first timeline without discarding source context."""
    records: list[dict[str, str]] = []
    for filename, frame in frames.items():
        if frame is None or frame.empty:
            continue
        source = EVENT_SOURCES.get(filename, filename)
        for _, row in frame.fillna("").iterrows():
            subject = _value(
                row, ("identity_key", "subject", "mac", "client_mac", "ip"),
                "Genel ağ olayı",
            )
            records.append({
                "event_time": _value(row, TIME_FIELDS),
                "event_type": _value(row, TYPE_FIELDS, "unknown_event"),
                "subject": subject,
                "identity_key": _value(row, ("identity_key",)),
                "ip": _value(row, ("ip", "client_ip")),
                "severity": _severity(row, _value(row, TYPE_FIELDS, "unknown_event")),
                "old_value": _value(row, ("old_value",)),
                "new_value": _value(row, ("new_value",)),
                "details": _value(row, DETAIL_FIELDS),
                "source": source,
            })

    columns = [
        "event_time", "event_type", "subject", "identity_key", "ip", "severity",
        "old_value", "new_value", "details", "source",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(records, columns=columns)
    result["_parsed_time"] = pd.to_datetime(
        result["event_time"], format="mixed", utc=True, errors="coerce"
    )
    result["_order"] = range(len(result))
    result = result.sort_values(
        ["_parsed_time", "_order"],
        ascending=[False, True],
        na_position="last",
        kind="stable",
    )
    return result.drop(columns=["_parsed_time", "_order"]).reset_index(drop=True)



def filter_event_timeline(
    frame: pd.DataFrame,
    *,
    search: str = "",
    source: str = "",
    severity: str = "",
    event_type: str = "",
) -> pd.DataFrame:
    """Apply exact category filters and a literal, case-insensitive text search."""
    if frame is None:
        return pd.DataFrame()
    result = frame.copy()
    sentinels = {"source": "Tüm kaynaklar", "severity": "Tüm seviyeler", "event_type": "Tüm olay türleri"}
    for column, selected in (("source", source), ("severity", severity), ("event_type", event_type)):
        if selected and selected != sentinels[column]:
            if column not in result.columns:
                return result.iloc[0:0].copy()
            result = result[result[column].fillna("").astype(str) == str(selected)]
    term = str(search or "").strip()
    if term:
        mask = result.astype(str).apply(
            lambda column: column.str.contains(term, case=False, na=False, regex=False)
        ).any(axis=1)
        result = result[mask]
    return result.reset_index(drop=True)


def related_event_context(
    frame: pd.DataFrame,
    selected_event: pd.Series,
    window_minutes: float = 15,
) -> pd.DataFrame:
    """Return nearby events for the same stable device identity.

    Legacy rows without an identity key are intentionally not correlated by IP
    or subject because those values can change or be reused.
    """
    try:
        window = float(window_minutes)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("window_minutes must be a non-negative number")
    if pd.isna(window) or window < 0:
        raise ValueError("window_minutes must be a non-negative number")
    if frame is None or frame.empty or selected_event is None:
        return pd.DataFrame(columns=frame.columns if frame is not None else [])
    if "identity_key" not in frame.columns or "event_time" not in frame.columns:
        return frame.iloc[0:0].copy()

    identity = str(selected_event.get("identity_key", "") or "").strip()
    selected_time = pd.to_datetime(
        selected_event.get("event_time", ""), format="mixed", utc=True, errors="coerce"
    )
    if not identity or pd.isna(selected_time):
        return frame.iloc[0:0].copy()

    identities = frame["identity_key"].fillna("").astype(str).str.strip()
    times = pd.to_datetime(
        frame["event_time"], format="mixed", utc=True, errors="coerce"
    )
    mask = identities.eq(identity) & times.notna()
    mask &= (times - selected_time).abs() <= pd.Timedelta(minutes=window)
    result = frame.loc[mask].copy()
    result["_context_time"] = times.loc[mask]
    result = result.sort_values(
        "_context_time", ascending=False, kind="stable"
    ).drop(columns=["_context_time"])
    return result.reset_index(drop=True)


EVENT_REVIEW_STATUSES = ("new", "reviewed", "action_required", "resolved")
EVENT_REVIEW_PRIORITIES = ("low", "normal", "high", "critical")
EVENT_REVIEW_COLUMNS = (
    "event_key", "status", "note", "updated_at", "priority", "assignee",
)
EVENT_REVIEW_HISTORY_COLUMNS = (
    "action_id", "event_key", "updated_at", "changes", "status",
    "priority", "assignee", "note",
)


def event_review_key(event: pd.Series | dict) -> str:
    """Build a deterministic local review key from normalized event evidence."""
    import hashlib
    import json

    values = [
        str(event.get(field, "") or "").strip()
        for field in (
            "source", "event_time", "event_type", "identity_key",
            "ip", "old_value", "new_value", "details", "subject",
        )
    ]
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def merge_event_review_states(
    events: pd.DataFrame,
    states: pd.DataFrame | None,
) -> pd.DataFrame:
    """Attach persisted review metadata without mutating normalized evidence."""
    result = events.copy() if events is not None else pd.DataFrame()
    review_fields = {
        "event_key": "",
        "review_status": "new",
        "review_note": "",
        "review_updated_at": "",
        "review_priority": "normal",
        "review_assignee": "",
    }
    if result.empty:
        for column, default in review_fields.items():
            result[column] = pd.Series(dtype="object")
        return result
    result["event_key"] = result.apply(event_review_key, axis=1)
    if states is None or states.empty or not {"event_key", "status"}.issubset(states.columns):
        for column, default in review_fields.items():
            if column != "event_key":
                result[column] = default
        return result

    valid = states.copy()
    valid["event_key"] = valid["event_key"].fillna("").astype(str)
    valid = valid.drop_duplicates("event_key", keep="last").set_index("event_key")
    result["review_status"] = result["event_key"].map(valid["status"]).fillna("new")
    result["review_note"] = (
        result["event_key"].map(valid["note"]).fillna("")
        if "note" in valid.columns else ""
    )
    result["review_updated_at"] = (
        result["event_key"].map(valid["updated_at"]).fillna("")
        if "updated_at" in valid.columns else ""
    )
    result["review_priority"] = (
        result["event_key"].map(valid["priority"]).fillna("normal")
        if "priority" in valid.columns else "normal"
    )
    result["review_assignee"] = (
        result["event_key"].map(valid["assignee"]).fillna("")
        if "assignee" in valid.columns else ""
    )
    invalid = ~result["review_status"].isin(EVENT_REVIEW_STATUSES)
    result.loc[invalid, "review_status"] = "new"
    invalid_priority = ~result["review_priority"].isin(EVENT_REVIEW_PRIORITIES)
    result.loc[invalid_priority, "review_priority"] = "normal"
    return result


def upsert_event_review_state(
    states: pd.DataFrame | None,
    event: pd.Series | dict,
    status: str,
    note: str = "",
    updated_at: str = "",
    priority: str = "normal",
    assignee: str = "",
) -> pd.DataFrame:
    """Return a complete replacement snapshot with one event review state updated."""
    if status not in EVENT_REVIEW_STATUSES:
        raise ValueError(f"Unsupported event review status: {status}")
    if priority not in EVENT_REVIEW_PRIORITIES:
        raise ValueError(f"Unsupported event review priority: {priority}")
    if states is None or states.empty:
        current = pd.DataFrame(columns=EVENT_REVIEW_COLUMNS)
    else:
        current = states.copy()
        for column in EVENT_REVIEW_COLUMNS:
            if column not in current.columns:
                current[column] = ""
        current = current[list(EVENT_REVIEW_COLUMNS)]
    key = event_review_key(event)
    current = current[current["event_key"].astype(str) != key]
    row = {
        "event_key": key,
        "status": status,
        "note": str(note or "").strip(),
        "updated_at": str(updated_at or ""),
        "priority": priority,
        "assignee": str(assignee or "").strip(),
    }
    return pd.concat([current, pd.DataFrame([row])], ignore_index=True)



def bulk_update_event_review(
    states: pd.DataFrame | None,
    history: pd.DataFrame | None,
    events: pd.DataFrame | None,
    *,
    updated_at: str,
    status: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Apply selected review fields to unique events and append per-event audit rows.

    None means leave a field unchanged; an empty assignee string explicitly
    clears the assignment. Source event rows are read-only throughout this flow.
    Returns updated state snapshot, append-only history, and changed-event count.
    """
    if status is None and priority is None and assignee is None:
        raise ValueError("At least one review field must be selected for update")
    if status is not None and status not in EVENT_REVIEW_STATUSES:
        raise ValueError(f"Unsupported event review status: {status}")
    if priority is not None and priority not in EVENT_REVIEW_PRIORITIES:
        raise ValueError(f"Unsupported event review priority: {priority}")

    current_states = states.copy() if states is not None else pd.DataFrame(columns=EVENT_REVIEW_COLUMNS)
    current_history = history.copy() if history is not None else pd.DataFrame(columns=EVENT_REVIEW_HISTORY_COLUMNS)
    if events is None or events.empty:
        return current_states, current_history, 0

    changed_count = 0
    seen_keys: set[str] = set()
    for _, event in events.iterrows():
        key = event_review_key(event)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if not current_states.empty and "event_key" in current_states.columns:
            matches = current_states[current_states["event_key"].fillna("").astype(str).eq(key)]
            previous = matches.iloc[-1].to_dict() if not matches.empty else {}
        else:
            previous = {}
        old_status = str(previous.get("status", "new") or "new")
        old_priority = str(previous.get("priority", "normal") or "normal")
        old_assignee = str(previous.get("assignee", "") or "").strip()
        old_note = str(previous.get("note", "") or "").strip()
        new_status = status if status is not None else old_status
        new_priority = priority if priority is not None else old_priority
        new_assignee = str(assignee).strip() if assignee is not None else old_assignee
        if (
            new_status == old_status
            and new_priority == old_priority
            and new_assignee == old_assignee
        ):
            continue

        updated = upsert_event_review_state(
            current_states, event, new_status, old_note, updated_at,
            priority=new_priority, assignee=new_assignee,
        )
        before_history_count = len(current_history)
        current_history = append_event_review_history(
            current_history, event, previous,
            status=new_status, priority=new_priority, assignee=new_assignee,
            note=old_note, updated_at=updated_at,
        )
        if len(current_history) > before_history_count:
            changed_count += 1
        current_states = updated

    return current_states, current_history, changed_count


def append_event_review_history(
    history: pd.DataFrame | None,
    event: pd.Series | dict,
    previous_state: pd.Series | dict | None,
    *,
    status: str,
    priority: str,
    assignee: str,
    note: str,
    updated_at: str,
) -> pd.DataFrame:
    """Append one deduplicated audit entry describing changed review fields."""
    if status not in EVENT_REVIEW_STATUSES:
        raise ValueError(f"Unsupported event review status: {status}")
    if priority not in EVENT_REVIEW_PRIORITIES:
        raise ValueError(f"Unsupported event review priority: {priority}")

    previous = previous_state.to_dict() if isinstance(previous_state, pd.Series) else dict(previous_state or {})
    old_values = {
        "status": str(previous.get("status", previous.get("review_status", "new")) or "new"),
        "priority": str(previous.get("priority", previous.get("review_priority", "normal")) or "normal"),
        "assignee": str(previous.get("assignee", previous.get("review_assignee", "")) or "").strip(),
        "note": str(previous.get("note", previous.get("review_note", "")) or "").strip(),
    }
    new_values = {
        "status": status,
        "priority": priority,
        "assignee": str(assignee or "").strip(),
        "note": str(note or "").strip(),
    }
    changes = {
        field: {"from": old_values[field], "to": new_values[field]}
        for field in new_values if old_values[field] != new_values[field]
    }
    if not changes:
        if history is None:
            return pd.DataFrame(columns=EVENT_REVIEW_HISTORY_COLUMNS)
        return history.copy()

    key = event_review_key(event)
    timestamp = str(updated_at or "")
    changes_json = json.dumps(changes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    action_id = hashlib.sha256(
        f"{key}\\0{timestamp}\\0{changes_json}".encode("utf-8")
    ).hexdigest()
    current = history.copy() if history is not None else pd.DataFrame()
    for column in EVENT_REVIEW_HISTORY_COLUMNS:
        if column not in current.columns:
            current[column] = ""
    current = current[list(EVENT_REVIEW_HISTORY_COLUMNS)]
    if current["action_id"].astype(str).eq(action_id).any():
        return current
    row = {
        "action_id": action_id,
        "event_key": key,
        "updated_at": timestamp,
        "changes": changes_json,
        "status": status,
        "priority": priority,
        "assignee": new_values["assignee"],
        "note": new_values["note"],
    }
    return pd.concat([current, pd.DataFrame([row])], ignore_index=True)


def filter_event_review_history(
    history: pd.DataFrame | None,
    event_key: str,
) -> pd.DataFrame:
    """Return newest-first audit entries for one event key."""
    if history is None or history.empty or "event_key" not in history.columns:
        return pd.DataFrame(columns=EVENT_REVIEW_HISTORY_COLUMNS)
    result = history[history["event_key"].fillna("").astype(str).eq(str(event_key))].copy()
    if "updated_at" in result.columns:
        result["_parsed_time"] = pd.to_datetime(
            result["updated_at"], format="mixed", utc=True, errors="coerce"
        )
        result["_order"] = range(len(result))
        result = result.sort_values(
            ["_parsed_time", "_order"], ascending=[False, False],
            na_position="last", kind="stable",
        ).drop(columns=["_parsed_time", "_order"])
    return result.reset_index(drop=True)




def filter_event_review_history_for_events(
    history: pd.DataFrame | None,
    event_keys: list[str] | tuple[str, ...] | set[str],
) -> pd.DataFrame:
    """Return newest-first audit entries limited to an explicit event-key set."""
    if history is None or history.empty or "event_key" not in history.columns:
        return pd.DataFrame(columns=EVENT_REVIEW_HISTORY_COLUMNS)
    keys = {str(key).strip() for key in event_keys if str(key).strip()}
    if not keys:
        return pd.DataFrame(columns=EVENT_REVIEW_HISTORY_COLUMNS)
    result = history[
        history["event_key"].fillna("").astype(str).isin(keys)
    ].copy()
    if "updated_at" in result.columns:
        result["_parsed_time"] = pd.to_datetime(
            result["updated_at"], format="mixed", utc=True, errors="coerce"
        )
        result["_order"] = range(len(result))
        result = result.sort_values(
            ["_parsed_time", "_order"], ascending=[False, False],
            na_position="last", kind="stable",
        ).drop(columns=["_parsed_time", "_order"])
    return result.reset_index(drop=True)


def format_event_review_changes(value: object) -> str:
    """Render stored audit JSON as concise, readable Turkish change summaries."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    try:
        changes = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if not isinstance(changes, dict):
        return raw

    field_labels = {
        "status": "Durum", "priority": "Öncelik",
        "assignee": "Sorumlu", "note": "Not",
    }
    status_labels = {
        "new": "Yeni", "reviewed": "İncelendi",
        "action_required": "İşlem gerekli", "resolved": "Çözüldü",
    }
    priority_labels = {
        "low": "Düşük", "normal": "Normal",
        "high": "Yüksek", "critical": "Kritik",
    }
    summaries = []
    for field, transition in changes.items():
        if not isinstance(transition, dict) or not {"from", "to"}.issubset(transition):
            continue
        old_value = str(transition.get("from", "") or "").strip()
        new_value = str(transition.get("to", "") or "").strip()
        if field == "status":
            old_value = status_labels.get(old_value, old_value)
            new_value = status_labels.get(new_value, new_value)
        elif field == "priority":
            old_value = priority_labels.get(old_value, old_value)
            new_value = priority_labels.get(new_value, new_value)
        label = field_labels.get(str(field), str(field).replace("_", " ").title())
        summaries.append(f"{label}: {old_value or '—'} → {new_value or '—'}")
    return " · ".join(summaries) if summaries else raw


def filter_event_review_assignment(
    frame: pd.DataFrame,
    *,
    priority: str = "",
    assignee: str = "",
) -> pd.DataFrame:
    """Filter review metadata by exact priority and literal assignee substring."""
    if frame is None:
        return pd.DataFrame()
    result = frame.copy()
    selected_priority = str(priority or "").strip().lower()
    if selected_priority and selected_priority != "all":
        if selected_priority not in EVENT_REVIEW_PRIORITIES or "review_priority" not in result.columns:
            return result.iloc[0:0].copy()
        result = result[
            result["review_priority"].fillna("normal").astype(str).str.lower()
            .eq(selected_priority)
        ]
    term = str(assignee or "").strip()
    if term:
        if "review_assignee" not in result.columns:
            return result.iloc[0:0].copy()
        result = result[
            result["review_assignee"].fillna("").astype(str).str.contains(
                term, case=False, regex=False, na=False
            )
        ]
    return result.reset_index(drop=True)



def summarize_event_review_workload(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Summarize persisted review workload by assignee without inventing SLA or risk scores."""
    columns = [
        "assignee", "total_events", "open_events", "new_events",
        "action_required_events", "high_priority_open", "resolved_events",
    ]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=columns)

    data = frame.copy()
    data["_assignee"] = (
        data["review_assignee"].fillna("").astype(str).str.strip()
        if "review_assignee" in data.columns else ""
    )
    data["_assignee"] = data["_assignee"].replace("", "Atanmamış")
    data["_status"] = (
        data["review_status"].fillna("new").astype(str)
        if "review_status" in data.columns else "new"
    )
    data["_priority"] = (
        data["review_priority"].fillna("normal").astype(str)
        if "review_priority" in data.columns else "normal"
    )
    data["_open"] = data["_status"].ne("resolved")
    data["_high_open"] = data["_open"] & data["_priority"].isin(("high", "critical"))

    rows = []
    for assignee, group in data.groupby("_assignee", sort=True, dropna=False):
        rows.append({
            "assignee": str(assignee),
            "total_events": int(len(group)),
            "open_events": int(group["_open"].sum()),
            "new_events": int(group["_status"].eq("new").sum()),
            "action_required_events": int(group["_status"].eq("action_required").sum()),
            "high_priority_open": int(group["_high_open"].sum()),
            "resolved_events": int(group["_status"].eq("resolved").sum()),
        })
    result = pd.DataFrame(rows, columns=columns)
    return result.sort_values(
        ["open_events", "high_priority_open", "assignee"],
        ascending=[False, False, True], kind="stable",
    ).reset_index(drop=True)


def sort_event_review_queue(frame: pd.DataFrame | None, sort_by: str = "priority", *, unassigned_first: bool = False) -> pd.DataFrame:
    """Sort review rows into a deterministic operator queue without changing source data."""
    if frame is None: return pd.DataFrame()
    result = frame.copy()
    if result.empty: return result
    if sort_by not in {"priority", "newest", "open"}: raise ValueError(f"Unsupported event review queue sort: {sort_by}")
    status = result.get("review_status", pd.Series("new", index=result.index)).fillna("new").astype(str)
    priority = result.get("review_priority", pd.Series("normal", index=result.index)).fillna("normal").astype(str)
    assignee = result.get("review_assignee", pd.Series("", index=result.index)).fillna("").astype(str).str.strip()
    result["_queue_resolved"] = status.eq("resolved").astype(int)
    result["_queue_priority"] = priority.map({"critical": 0, "high": 1, "normal": 2, "low": 3}).fillna(4)
    result["_queue_unassigned"] = assignee.eq("").astype(int)
    time_col = next((col for col in ("event_time", "timestamp") if col in result.columns), None)
    result["_queue_time"] = pd.to_datetime(result[time_col], utc=True, errors="coerce") if time_col else pd.NaT
    if sort_by == "newest":
        cols, asc = ["_queue_resolved", "_queue_time"], [True, False]
    else:
        cols, asc = ["_queue_resolved", "_queue_priority", "_queue_time"], [True, True, False]
    if unassigned_first:
        insert_at = 1 if sort_by != "newest" else 1
        cols.insert(insert_at, "_queue_unassigned")
        asc.insert(insert_at, False)
    result = result.sort_values(cols, ascending=asc, na_position="last", kind="stable")
    return result.drop(columns=[c for c in result.columns if c.startswith("_queue_")]).reset_index(drop=True)


def add_event_review_history_summary(frame: pd.DataFrame | None, history: pd.DataFrame | None) -> pd.DataFrame:
    """Attach audit count and latest review timestamp to event rows using event_key only."""
    if frame is None: return pd.DataFrame()
    result = frame.copy()
    result["review_history_count"] = 0
    result["review_last_updated"] = ""
    if result.empty or history is None or history.empty or "event_key" not in history.columns or "event_key" not in result.columns: return result
    audit = history.copy()
    audit["event_key"] = audit["event_key"].fillna("").astype(str)
    audit = audit[audit["event_key"].ne("")]
    if audit.empty: return result
    counts = audit.groupby("event_key", sort=False).size()
    keys = result["event_key"].fillna("").astype(str)
    result["review_history_count"] = keys.map(counts).fillna(0).astype(int)
    if "updated_at" in audit.columns:
        audit["_parsed"] = pd.to_datetime(audit["updated_at"], utc=True, errors="coerce")
        latest = audit.sort_values("_parsed", ascending=False, na_position="last", kind="stable").drop_duplicates("event_key")
        values = latest.set_index("event_key")["updated_at"].fillna("").astype(str)
        result["review_last_updated"] = keys.map(values).fillna("")
    return result

def filter_event_review_status(
    frame: pd.DataFrame,
    status: str = "",
) -> pd.DataFrame:
    """Filter normalized events by their persisted review workflow status."""
    if frame is None:
        return pd.DataFrame()
    result = frame.copy()
    selected = str(status or "").strip()
    if not selected or selected == "all":
        return result.reset_index(drop=True)
    if selected not in EVENT_REVIEW_STATUSES or "review_status" not in result.columns:
        return result.iloc[0:0].copy()
    return result[
        result["review_status"].fillna("new").astype(str).eq(selected)
    ].reset_index(drop=True)
