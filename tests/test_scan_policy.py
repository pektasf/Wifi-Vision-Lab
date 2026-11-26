import pytest

from scripts.scan_policy import build_scan_targets, load_scan_settings


def test_private_subnet_targets_are_bounded_and_report_truncation():
    targets, truncated = build_scan_targets(
        "192.168.10.0/24", "192.168.10.20", "192.168.10.1", max_hosts=10
    )

    assert len(targets) == 10
    assert targets[0] == "192.168.10.1"
    assert truncated is True


def test_small_private_subnet_is_not_marked_truncated():
    targets, truncated = build_scan_targets(
        "192.168.10.0/29", "192.168.10.2", "192.168.10.1", max_hosts=10
    )

    assert len(targets) == 6
    assert truncated is False


@pytest.mark.parametrize(
    "network,local,gateway",
    [
        ("8.8.8.0/24", "8.8.8.10", "8.8.8.1"),
        ("127.0.0.0/8", "127.0.0.2", "127.0.0.1"),
        ("169.254.1.0/24", "169.254.1.2", "169.254.1.1"),
        ("192.168.10.0/24", "192.168.11.2", "192.168.10.1"),
        ("192.168.10.0/24", "192.168.10.2", "192.168.11.1"),
    ],
)
def test_rejects_nonlocal_or_unsafe_networks(network, local, gateway):
    with pytest.raises(ValueError):
        build_scan_targets(network, local, gateway)


def test_rejects_invalid_scan_limit():
    with pytest.raises(ValueError):
        build_scan_targets(
            "192.168.10.0/24", "192.168.10.2", "192.168.10.1", max_hosts=5000
        )


def test_scan_settings_have_safe_defaults(monkeypatch):
    for key in (
        "WIFI_VISION_MAX_SCAN_HOSTS",
        "WIFI_VISION_SCAN_WORKERS",
        "WIFI_VISION_PING_TIMEOUT_MS",
    ):
        monkeypatch.delenv(key, raising=False)

    assert load_scan_settings() == {
        "max_hosts": 1024,
        "workers": 32,
        "ping_timeout_ms": 600,
    }


def test_scan_settings_reject_unbounded_worker_count(monkeypatch):
    monkeypatch.setenv("WIFI_VISION_SCAN_WORKERS", "1000")
    with pytest.raises(ValueError):
        load_scan_settings()


def test_custom_private_subnet_requires_explicit_approval():
    with pytest.raises(ValueError, match="explicit authorization"):
        build_scan_targets(
            "10.20.30.0/24", "192.168.10.20", "192.168.10.1",
            active_network_cidr="192.168.10.0/24",
        )


def test_custom_private_subnet_requires_exact_cidr_confirmation():
    with pytest.raises(ValueError, match="canonical CIDR"):
        build_scan_targets(
            "10.20.30.0/24", "192.168.10.20", "192.168.10.1",
            active_network_cidr="192.168.10.0/24",
            approved=True,
            confirmation="10.20.30.0/25",
        )


def test_approved_custom_private_subnet_is_bounded():
    targets, truncated = build_scan_targets(
        "10.20.30.0/24", "192.168.10.20", "192.168.10.1",
        max_hosts=12,
        active_network_cidr="192.168.10.0/24",
        approved=True,
        confirmation="10.20.30.0/24",
    )
    assert len(targets) == 12
    assert targets[0] == "10.20.30.1"
    assert truncated is True


@pytest.mark.parametrize("network", ["8.8.8.0/24", "127.0.0.0/8", "169.254.0.0/16", "100.64.0.0/10"])
def test_approved_custom_scope_still_rejects_non_rfc1918(network):
    with pytest.raises(ValueError, match="RFC1918"):
        build_scan_targets(
            network, "192.168.10.20", "192.168.10.1",
            active_network_cidr="192.168.10.0/24",
            approved=True,
            confirmation=network,
        )


def test_active_interface_must_be_rfc1918_private():
    with pytest.raises(ValueError, match="active interface"):
        build_scan_targets(
            "192.168.10.0/24", "100.64.10.20", "100.64.10.1",
            active_network_cidr="100.64.10.0/24",
        )



def test_hosted_network_interface_without_gateway_is_allowed():
    targets, truncated = build_scan_targets(
        "192.168.137.0/24",
        "192.168.137.1",
        "",
        max_hosts=20,
        active_network_cidr="192.168.137.0/24",
    )

    assert len(targets) == 20
    assert targets[0] == "192.168.137.1"
    assert truncated is True


def test_gateway_is_validated_when_present():
    with pytest.raises(ValueError, match="default gateway"):
        build_scan_targets(
            "192.168.137.0/24",
            "192.168.137.1",
            "192.168.138.1",
            active_network_cidr="192.168.137.0/24",
        )



def test_windows_interface_listing_includes_hosted_network_without_gateway(monkeypatch):
    import json
    from types import SimpleNamespace

    from scripts import device_inventory

    payload = [
        {
            "IP": "192.168.1.20", "Prefix": 24, "Gateway": "192.168.1.1",
            "Adapter": "Wi-Fi", "InterfaceIndex": 7,
            "DHCPEnabled": "True", "DHCPServer": "192.168.1.1",
            "DHCPLeaseObtained": "2026-11-26T06:00:00.0000000Z",
            "DHCPLeaseExpires": "2026-11-27T06:00:00.0000000Z",
        },
        {
            "IP": "192.168.137.1", "Prefix": 24, "Gateway": "",
            "Adapter": "Local Area Connection* 12", "InterfaceIndex": 19,
            "DHCPEnabled": "False", "DHCPServer": "",
            "DHCPLeaseObtained": "", "DHCPLeaseExpires": "",
        },
    ]
    monkeypatch.setattr(device_inventory.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        device_inventory.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )

    interfaces = device_inventory.list_network_interfaces()

    assert len(interfaces) == 2
    assert interfaces[0]["adapter"] == "Wi-Fi"
    hosted = interfaces[1]
    assert hosted["adapter"] == "Local Area Connection* 12"
    assert hosted["ip"] == "192.168.137.1"
    assert hosted["network"] == "192.168.137.0/24"
    assert hosted["gateway"] == ""
    assert hosted["has_default_gateway"] is False
    assert hosted["dhcp_enabled"] is False
    assert hosted["dhcp_server"] == ""
    assert hosted["dhcp_lease_obtained"] == ""
    assert hosted["dhcp_lease_expires"] == ""
    wifi = interfaces[0]
    assert wifi["dhcp_enabled"] is True
    assert wifi["dhcp_server"] == "192.168.1.1"
    assert wifi["dhcp_lease_obtained"] == "2026-11-26T06:00:00.0000000Z"
    assert wifi["dhcp_lease_expires"] == "2026-11-27T06:00:00.0000000Z"


def test_get_network_can_select_hosted_network_adapter(monkeypatch):
    from scripts import device_inventory

    interfaces = [
        {
            "ip": "192.168.1.20", "gateway": "192.168.1.1",
            "adapter": "Wi-Fi", "interface_index": 7,
            "network": "192.168.1.0/24", "has_default_gateway": True,
        },
        {
            "ip": "192.168.137.1", "gateway": "",
            "adapter": "Local Area Connection* 12", "interface_index": 19,
            "network": "192.168.137.0/24", "has_default_gateway": False,
        },
    ]
    monkeypatch.setattr(device_inventory, "list_network_interfaces", lambda: interfaces)

    selected = device_inventory.get_network("Local Area Connection* 12")

    assert selected["adapter"] == "Local Area Connection* 12"
    assert selected["ip"] == "192.168.137.1"
    assert selected["network"] == "192.168.137.0/24"
    assert selected["gateway"] == ""
    assert selected["has_default_gateway"] is False
    assert selected["dhcp_enabled"] is False
    assert selected["dhcp_server"] == ""


def test_get_network_rejects_stale_adapter_selection(monkeypatch):
    from scripts import device_inventory

    monkeypatch.setattr(device_inventory, "list_network_interfaces", lambda: [])
    with pytest.raises(RuntimeError, match="no longer|mevcut değil"):
        device_inventory.get_network("Old hosted adapter")



def test_scan_network_diagnostics_show_selected_adapter_and_gateway():
    from scripts.device_inventory import format_network_diagnostics

    message = format_network_diagnostics({
        "adapter": "Local Area Connection* 12",
        "ip": "192.168.137.1",
        "network": "192.168.137.0/24",
        "gateway": "",
        "interface_index": 19,
    })

    assert "Local Area Connection* 12" in message
    assert "192.168.137.1" in message
    assert "192.168.137.0/24" in message
    assert "ağ geçidi=yok" in message
    assert "arayüz indeksi=19" in message
    assert "DHCP=bilinmiyor" in message
    assert "DHCP sunucusu=bilinmiyor" in message


def test_scan_network_diagnostics_show_gateway_when_present():
    from scripts.device_inventory import format_network_diagnostics

    message = format_network_diagnostics({
        "adapter": "Wi-Fi",
        "ip": "192.168.1.20",
        "network": "192.168.1.0/24",
        "gateway": "192.168.1.1",
        "interface_index": 7,
    })

    assert "ağ geçidi=192.168.1.1" in message
    assert "DHCP=bilinmiyor" in message
    assert "yok" not in message



def test_scan_network_diagnostics_show_dhcp_lease_context():
    from scripts.device_inventory import format_network_diagnostics

    message = format_network_diagnostics({
        "adapter": "Wi-Fi",
        "ip": "192.168.1.20",
        "network": "192.168.1.0/24",
        "gateway": "192.168.1.1",
        "interface_index": 7,
        "dhcp_enabled": True,
        "dhcp_server": "192.168.1.1",
        "dhcp_lease_obtained": "2026-11-26T06:00:00Z",
        "dhcp_lease_expires": "2026-11-27T06:00:00Z",
    })

    assert "DHCP=etkin" in message
    assert "DHCP sunucusu=192.168.1.1" in message
    assert "kira başlangıcı=2026-11-26T06:00:00Z" in message
    assert "kira bitişi=2026-11-27T06:00:00Z" in message



def test_scan_network_diagnostics_distinguish_disabled_dhcp():
    from scripts.device_inventory import format_network_diagnostics

    message = format_network_diagnostics({
        "adapter": "Virtual adapter",
        "ip": "192.168.137.1",
        "network": "192.168.137.0/24",
        "gateway": "",
        "interface_index": 19,
        "dhcp_enabled": False,
    })

    assert "DHCP=devre dışı" in message
