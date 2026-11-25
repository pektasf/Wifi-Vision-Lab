import pytest

from scripts.contracts import CollectorError, CollectorResult, run_collector


def test_list_result_has_record_count_and_timing():
    value, result = run_collector("inventory", lambda: [{"ip": "192.168.1.2"}])

    assert value == [{"ip": "192.168.1.2"}]
    assert isinstance(result, CollectorResult)
    assert result.status == "success"
    assert result.records_count == 1
    assert result.duration_ms >= 0
    assert result.started_at
    assert result.finished_at


def test_discovery_tuple_counts_device_list():
    value, result = run_collector(
        "discovery", lambda: ({"network": "192.168.1.0/24"}, [{"ip": "192.168.1.2"}])
    )

    assert len(value[1]) == 1
    assert result.records_count == 1


def test_none_is_reported_as_no_data():
    value, result = run_collector("wlan", lambda: None)

    assert value is None
    assert result.status == "no_data"
    assert result.records_count is None


def test_empty_list_is_reported_as_no_data():
    _, result = run_collector("inventory", lambda: [])

    assert result.status == "no_data"
    assert result.records_count == 0


def test_failure_is_structured_and_preserves_exception():
    original = RuntimeError("collector unavailable")
    value, result = run_collector(
        "wlan", lambda: (_ for _ in ()).throw(original), optional=True
    )

    assert value is None
    assert result.status == "failed"
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], CollectorError)
    assert result.errors[0].source == "wlan"
    assert result.errors[0].code == "RuntimeError"
    assert result.errors[0].recoverable is True
    assert result.exception is original


def test_serialized_result_does_not_include_exception_object():
    _, result = run_collector(
        "inventory", lambda: (_ for _ in ()).throw(ValueError("bad input"))
    )

    payload = result.to_dict()
    assert "exception" not in payload
    assert payload["errors"][0]["message"] == "bad input"
