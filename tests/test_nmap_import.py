import pytest

from scripts.discovery.nmap_import import normalize_nmap_xml


def test_nmap_xml_import_extracts_host_mac_ip_and_arp_evidence():
    xml = """<?xml version="1.0"?>
    <nmaprun scanner="nmap" start="1795687200" version="7.98">
      <host starttime="1795687200" endtime="1795687201">
        <status state="up" reason="arp-response"/>
        <address addr="192.168.1.25" addrtype="ipv4"/>
        <address addr="02:11:22:33:44:55" addrtype="mac" vendor="Example Vendor"/>
        <hostnames><hostname name="test-client.local" type="PTR"/></hostnames>
        <ports><port protocol="tcp" portid="80"><state state="open"/></port></ports>
      </host>
    </nmaprun>"""

    rows = normalize_nmap_xml(
        xml,
        imported_at="2026-11-26T10:00:00+00:00",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "nmap_xml_import"
    assert row["ip"] == "192.168.1.25"
    assert row["mac"] == "02:11:22:33:44:55"
    assert row["hostname"] == "test-client.local"
    assert row["host_state"] == "up"
    assert row["host_reason"] == "arp-response"
    assert row["mac_vendor"] == "Example Vendor"
    assert row["mac_address_type"] == "locally_administered"
    assert row["evidence_status"] == "nmap_host_up;nmap_arp_response;locally_administered_mac"
    assert row["imported_at"] == "2026-11-26T10:00:00+00:00"


def test_nmap_xml_import_keeps_ip_only_host_without_inventing_mac():
    xml = """<nmaprun scanner="nmap" start="1795687200">
      <host><status state="up" reason="echo-reply"/>
        <address addr="192.168.1.30" addrtype="ipv4"/>
      </host>
    </nmaprun>"""
    rows = normalize_nmap_xml(xml)
    assert len(rows) == 1
    assert rows[0]["ip"] == "192.168.1.30"
    assert rows[0]["mac"] == ""
    assert rows[0]["evidence_status"] == "nmap_host_up"


def test_nmap_xml_import_does_not_extract_ports_or_services():
    xml = """<nmaprun scanner="nmap">
      <host><status state="up" reason="arp-response"/>
        <address addr="192.168.1.31" addrtype="ipv4"/>
        <ports><port protocol="tcp" portid="22">
          <state state="open"/><service name="ssh"/>
        </port></ports>
      </host>
    </nmaprun>"""
    row = normalize_nmap_xml(xml)[0]
    assert set(row) == {
        "imported_at", "scan_started_at", "observed_at", "source",
        "ip", "mac", "hostname", "host_state", "host_reason",
        "mac_vendor", "mac_address_type", "evidence_status",
    }


@pytest.mark.parametrize("xml", [
    "",
    "<not-nmap/>",
    "<nmaprun scanner='other'/>",
    "<nmaprun scanner='nmap'><host>",
])
def test_nmap_xml_import_rejects_invalid_or_unrelated_xml(xml):
    with pytest.raises(ValueError):
        normalize_nmap_xml(xml)


def test_nmap_xml_import_blocks_dtd_and_entity_expansion():
    xml = """<?xml version="1.0"?>
    <!DOCTYPE nmaprun [<!ENTITY x "expanded">]>
    <nmaprun scanner="nmap"><host><status state="&x;"/></host></nmaprun>"""
    with pytest.raises(ValueError, match="güvenli"):
        normalize_nmap_xml(xml)


def test_nmap_xml_import_ignores_hosts_without_ip_or_mac():
    xml = """<nmaprun scanner="nmap">
      <host><status state="up"/></host>
    </nmaprun>"""
    assert normalize_nmap_xml(xml) == []


def test_nmap_xml_import_rejects_files_over_size_limit():
    from scripts.discovery.nmap_import import MAX_NMAP_XML_BYTES

    with pytest.raises(ValueError, match="10 MB"):
        normalize_nmap_xml(b" " * (MAX_NMAP_XML_BYTES + 1))



def test_nmap_xml_import_ignores_malformed_ipv4_address():
    xml = """<nmaprun scanner="nmap">
      <host><status state="up"/>
        <address addr="999.999.1.1" addrtype="ipv4"/>
      </host>
    </nmaprun>"""
    assert normalize_nmap_xml(xml) == []
