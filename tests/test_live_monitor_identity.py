import pandas as pd

from scripts.live_monitor import (
    LIVE_EVENT_FIELDS,
    build_ping_transition,
    load_identity_map,
    migrate_live_events_schema,
    normalize_mac_identity,
)


def test_normalize_mac_identity_prefers_valid_mac_and_normalizes_separators():
    assert normalize_mac_identity("aa-bb-cc-dd-ee-ff", "192.0.2.8") == (
        "AA:BB:CC:DD:EE:FF"
    )


def test_normalize_mac_identity_falls_back_to_explicit_ip_identity():
    assert normalize_mac_identity("not-a-mac", "192.0.2.8") == "IP:192.0.2.8"
    assert normalize_mac_identity("", "") == ""


def test_load_identity_map_uses_mac_when_available_and_ip_fallback(tmp_path):
    inventory = tmp_path / "device_inventory.csv"
    pd.DataFrame([
        {"ip": "192.0.2.8", "mac": "aa:bb:cc:dd:ee:ff"},
        {"ip": "192.0.2.9", "mac": ""},
    ]).to_csv(inventory, index=False)

    assert load_identity_map(inventory) == {
        "192.0.2.8": "AA:BB:CC:DD:EE:FF",
        "192.0.2.9": "IP:192.0.2.9",
    }


def test_load_identity_map_handles_missing_inventory(tmp_path):
    assert load_identity_map(tmp_path / "missing.csv") == {}


def test_ping_transition_preserves_identity_and_before_after_state():
    event = build_ping_transition(
        "192.0.2.8",
        was_responding=True,
        is_responding=False,
        identity_map={"192.0.2.8": "AA:BB:CC:DD:EE:FF"},
        timestamp="2026-11-26T09:00:00+03:00",
    )
    assert event == {
        "timestamp": "2026-11-26T09:00:00+03:00",
        "ip": "192.0.2.8",
        "event": "PING_NOT_RESPONDING",
        "identity_key": "AA:BB:CC:DD:EE:FF",
        "old_value": "responding",
        "new_value": "not_responding",
    }


def test_ping_transition_labels_ip_fallback_when_mac_is_unknown():
    event = build_ping_transition(
        "192.0.2.10", False, True, {}, timestamp="fixed"
    )
    assert event["identity_key"] == "IP:192.0.2.10"
    assert event["old_value"] == "not_responding"
    assert event["new_value"] == "responding"


def test_live_event_migration_preserves_legacy_rows_and_adds_context(tmp_path):
    path = tmp_path / "live_events.csv"
    path.write_text(
        "timestamp,ip,event\n"
        "2026-11-25T09:00:00+03:00,192.0.2.8,PING_NOT_RESPONDING\n",
        encoding="utf-8",
    )

    migrate_live_events_schema(path)
    saved = pd.read_csv(path, dtype=str).fillna("")

    assert list(saved.columns) == LIVE_EVENT_FIELDS
    assert len(saved) == 1
    assert saved.loc[0, "event"] == "PING_NOT_RESPONDING"
    assert saved.loc[0, "ip"] == "192.0.2.8"
    assert saved.loc[0, "identity_key"] == ""
    assert saved.loc[0, "old_value"] == ""
    assert saved.loc[0, "new_value"] == ""


def test_live_event_migration_is_idempotent(tmp_path):
    path = tmp_path / "live_events.csv"
    pd.DataFrame([{
        "timestamp": "fixed",
        "ip": "192.0.2.8",
        "event": "PING_RESPONDING",
        "identity_key": "AA:BB:CC:DD:EE:FF",
        "old_value": "not_responding",
        "new_value": "responding",
    }], columns=LIVE_EVENT_FIELDS).to_csv(path, index=False)

    migrate_live_events_schema(path)
    saved = pd.read_csv(path, dtype=str).fillna("")
    assert len(saved) == 1
    assert saved.loc[0, "identity_key"] == "AA:BB:CC:DD:EE:FF"
