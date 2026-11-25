import json

from scripts.scan_events import EVENT_PREFIX, emit_progress, parse_event_line


def test_emit_progress_writes_machine_readable_event(capsys):
    emit_progress("Ağ keşfi", 0.35, "3 cihaz bulundu")
    output = capsys.readouterr().out.strip()

    assert output.startswith(EVENT_PREFIX)
    event = json.loads(output[len(EVENT_PREFIX):])
    assert event == {
        "type": "progress",
        "stage": "Ağ keşfi",
        "progress": 0.35,
        "message": "3 cihaz bulundu",
    }


def test_parse_progress_event_clamps_progress():
    line = EVENT_PREFIX + json.dumps({
        "type": "progress",
        "stage": "Ağ keşfi",
        "progress": 1.5,
        "message": "Tamamlandı",
    })

    assert parse_event_line(line) == {
        "stage": "Ağ keşfi",
        "progress": 1.0,
        "message": "Tamamlandı",
    }


def test_parse_ignores_non_events_and_invalid_events():
    assert parse_event_line("ordinary console output") is None
    assert parse_event_line(EVENT_PREFIX + "{invalid") is None
    assert parse_event_line(EVENT_PREFIX + json.dumps({
        "type": "other",
        "stage": "Ağ keşfi",
        "progress": 0.5,
    })) is None


def test_parse_rejects_non_finite_progress():
    line = EVENT_PREFIX + '{"type":"progress","stage":"Ağ keşfi","progress":NaN}'
    assert parse_event_line(line) is None
