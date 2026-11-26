import pandas as pd

from scripts.network_monitor import compare_inventories


def test_dhcp_address_change_is_reported_for_same_mac_not_as_new_device():
    previous = pd.DataFrame([{"ip": "192.168.1.20", "mac": "aa:bb:cc:dd:ee:ff"}])
    current = pd.DataFrame([{"ip": "192.168.1.35", "mac": "AA:BB:CC:DD:EE:FF"}])

    events = compare_inventories(previous, current)

    assert len(events) == 1
    assert events[0]["event"] == "IP_CHANGED"
    assert events[0]["ip"] == "192.168.1.35"


def test_new_and_missing_devices_are_compared_by_mac():
    previous = pd.DataFrame([
        {"ip": "192.168.1.10", "mac": "00:00:00:00:00:01"},
        {"ip": "192.168.1.11", "mac": "00:00:00:00:00:02"},
    ])
    current = pd.DataFrame([
        {"ip": "192.168.1.10", "mac": "00:00:00:00:00:01"},
        {"ip": "192.168.1.12", "mac": "00:00:00:00:00:03"},
    ])

    events = compare_inventories(previous, current)

    assert {(event["event"], event["ip"]) for event in events} == {
        ("FIRST_OBSERVED", "192.168.1.12"),
        ("NOT_IN_LATEST_SCAN", "192.168.1.11"),
    }


def test_missing_mac_falls_back_to_ip_identity():
    previous = pd.DataFrame([{"ip": "192.168.1.5", "mac": ""}])
    current = pd.DataFrame([{"ip": "192.168.1.5", "mac": ""}])

    assert compare_inventories(previous, current) == []


def test_empty_inventory_does_not_create_phantom_identity():
    previous = pd.DataFrame([{"ip": "", "mac": ""}])
    current = pd.DataFrame([{"ip": "", "mac": ""}])

    assert compare_inventories(previous, current) == []
