
import ipaddress
import subprocess
import re
import concurrent.futures
import json
import os
import platform

from scripts.common import DATA, stamp, overwrite_rows
from scripts.scan_policy import build_scan_targets, load_scan_settings


def classify_network_adapter(hardware_interface, adapter="", description=""):
    """Classify a local Windows interface without inferring remote endpoints."""
    if hardware_interface is True:
        return "physical"
    if hardware_interface is not False:
        return "unknown"
    text = f"{adapter} {description}".casefold()
    markers = (
        "wi-fi direct", "wifi direct", "hosted network",
        "wireless virtual", "virtual wi-fi", "virtual wifi",
    )
    return "virtual_wlan" if any(marker in text for marker in markers) else "virtual_or_software"


def list_network_interfaces():
    """Return local IPv4 interfaces, including Windows hosted-network adapters."""
    if platform.system() != "Windows":
        raise RuntimeError("Bu ağ adaptörü şu anda Windows içindir.")

    ps = (
        "$dhcp=@{}; "
        "Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "
        "\"IPEnabled=True\" | ForEach-Object { "
        "$key=($_.MACAddress -replace '[:-]','').ToUpperInvariant(); "
        "if($key){$dhcp[$key]=$_} }; "
        "$items = @(Get-NetIPConfiguration | "
        "Where-Object {$_.IPv4Address} | ForEach-Object { "
        "$gateway = ''; "
        "if($_.IPv4DefaultGateway){$gateway=$_.IPv4DefaultGateway.NextHop}; "
        "$key=($_.NetAdapter.MacAddress -replace '[:-]','').ToUpperInvariant(); "
        "$cfg=$dhcp[$key]; "
        "$dhcpEnabled=''; $dhcpServer=''; $leaseObtained=''; $leaseExpires=''; "
        "if($cfg){ "
        "$dhcpEnabled=[string][bool]$cfg.DHCPEnabled; "
        "$dhcpServer=[string]$cfg.DHCPServer; "
        "if($cfg.DHCPLeaseObtained){$leaseObtained=$cfg.DHCPLeaseObtained.ToUniversalTime().ToString('o')}; "
        "if($cfg.DHCPLeaseExpires){$leaseExpires=$cfg.DHCPLeaseExpires.ToUniversalTime().ToString('o')} "
        "}; "
        "[pscustomobject]@{"
        "IP=$_.IPv4Address[0].IPAddress; "
        "Prefix=$_.IPv4Address[0].PrefixLength; "
        "Gateway=$gateway; "
        "Adapter=$_.InterfaceAlias; "
        "InterfaceIndex=$_.InterfaceIndex; "
        "HardwareInterface=[string]$_.NetAdapter.HardwareInterface; "
        "InterfaceDescription=$_.NetAdapter.InterfaceDescription; "
        "DHCPEnabled=$dhcpEnabled; "
        "DHCPServer=$dhcpServer; "
        "DHCPLeaseObtained=$leaseObtained; "
        "DHCPLeaseExpires=$leaseExpires"
        "} }); "
        "if($items.Count -gt 0){$items | ConvertTo-Json -Compress}"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=15
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(f"Windows ağ arayüzleri sorgulanamadı: {exc}") from exc

    if result.returncode or not result.stdout.strip():
        detail = result.stderr.strip() or "IPv4 arayüzü bulunamadı."
        raise RuntimeError(detail[:300])

    try:
        data = json.loads(result.stdout.strip().splitlines()[-1])
        if isinstance(data, dict):
            data = [data]
        interfaces = []
        for row in data:
            interface = ipaddress.ip_interface(
                f"{row['IP']}/{row['Prefix']}"
            )
            gateway = str(row.get("Gateway") or "").strip()
            if gateway:
                gateway = str(ipaddress.ip_address(gateway))
            hardware_text = str(row.get("HardwareInterface") or "").strip().casefold()
            hardware_interface = True if hardware_text == "true" else False if hardware_text == "false" else None
            adapter = str(row.get("Adapter") or "Unknown")
            description = str(row.get("InterfaceDescription") or "")
            interfaces.append({
                "ip": str(interface.ip),
                "gateway": gateway,
                "adapter": adapter,
                "adapter_description": description,
                "hardware_interface": hardware_interface,
                "adapter_kind": classify_network_adapter(hardware_interface, adapter, description),
                "interface_index": int(row.get("InterfaceIndex") or 0),
                "network": str(interface.network),
                "has_default_gateway": bool(gateway),
                "dhcp_enabled": (
                    str(row.get("DHCPEnabled") or "").strip().casefold() == "true"
                    if str(row.get("DHCPEnabled") or "").strip().casefold()
                    in {"true", "false"} else None
                ),
                "dhcp_server": str(row.get("DHCPServer") or "").strip(),
                "dhcp_lease_obtained": str(row.get("DHCPLeaseObtained") or "").strip(),
                "dhcp_lease_expires": str(row.get("DHCPLeaseExpires") or "").strip(),
            })
    except (KeyError, ValueError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Windows IPv4 arayüz bilgisi okunamadı.") from exc

    return interfaces


def get_network(interface_alias=None):
    """Select an explicit local interface, or retain the default-route fallback."""
    interfaces = list_network_interfaces()
    if interface_alias:
        matches = [
            item for item in interfaces
            if item["adapter"] == str(interface_alias).strip()
        ]
        if not matches:
            raise RuntimeError(
                f"Seçilen ağ adaptörü artık mevcut değil: {interface_alias}"
            )
        selected = matches[0]
    else:
        selected = next(
            (item for item in interfaces if item["has_default_gateway"]),
            interfaces[0] if interfaces else None,
        )

    if selected is None:
        raise RuntimeError("Etkin IPv4 ağ arayüzü bulunamadı.")
    return {
        "ip": selected["ip"],
        "gateway": selected["gateway"],
        "adapter": selected["adapter"],
        "adapter_description": selected.get("adapter_description", ""),
        "hardware_interface": selected.get("hardware_interface"),
        "adapter_kind": selected.get("adapter_kind", "unknown"),
        "network": selected["network"],
        "interface_index": selected["interface_index"],
        "has_default_gateway": selected["has_default_gateway"],
        "dhcp_enabled": selected.get("dhcp_enabled"),
        "dhcp_server": selected.get("dhcp_server", ""),
        "dhcp_lease_obtained": selected.get("dhcp_lease_obtained", ""),
        "dhcp_lease_expires": selected.get("dhcp_lease_expires", ""),
    }

def ping_one(ip, timeout_ms=600):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), str(ip)],
            capture_output=True,
            timeout=(timeout_ms / 1000) + 2
        )
        return result.returncode == 0
    except Exception:
        return False


def arp_map():
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Windows ARP komutu bulunamadi.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ARP tablosu sorgusu 10 saniyede tamamlanamadi.") from exc
    except OSError as exc:
        raise RuntimeError(f"ARP tablosu okunamadi: {exc}") from exc

    if result.returncode and not result.stdout.strip():
        detail = result.stderr.strip() or "ARP komutu sonuc dondurmedi."
        raise RuntimeError(f"ARP tablosu okunamadi: {detail[:300]}")

    output = {}
    for line in result.stdout.splitlines():
        match = re.search(
            r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F-]{17})",
            line
        )
        if match:
            output[match.group(1)] = match.group(2).replace("-", ":").upper()
    return output


def resolve_hostnames(ips):
    """Bulunan cihazlar icin yerel ters DNS kayitlarini sorgular."""
    ips = [str(ip) for ip in ips if ip]
    if not ips:
        return {}

    values = ",".join("'" + ip + "'" for ip in ips)
    ps = (
        "$ips = @(" + values + "); "
        "$out = foreach($ip in $ips){ "
        "try { "
        "$r=Resolve-DnsName -Name $ip -Type PTR -QuickTimeout "
        "-ErrorAction Stop | Select-Object -First 1; "
        "if($r.NameHost){"
        "[pscustomobject]@{IP=$ip;Hostname=$r.NameHost}"
        "} "
        "} catch {} }; "
        "if($out){$out | ConvertTo-Json -Compress}"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=35
        )
        if result.returncode or not result.stdout.strip():
            return {}

        data = json.loads(result.stdout.strip())
        if isinstance(data, dict):
            data = [data]

        return {
            str(row.get("IP", "")): str(row.get("Hostname", "")).strip()
            for row in data
            if row.get("IP") and row.get("Hostname")
        }
    except Exception as exc:
        print("DNS isim sorgusu tamamlanamadi:", exc)
        return {}


NETWORK_CONTEXT_FIELDS = [
    "captured_at", "adapter", "adapter_description", "adapter_kind", "interface_index", "local_ipv4",
    "network_cidr", "gateway", "dhcp_enabled", "dhcp_server",
    "dhcp_lease_obtained", "dhcp_lease_expires", "evidence_source"
]


def build_network_context_row(net, captured_at=None):
    """Build a local-only snapshot of the selected adapter's network context."""
    dhcp_enabled = net.get("dhcp_enabled")
    dhcp_state = (
        "enabled" if dhcp_enabled is True
        else "disabled" if dhcp_enabled is False
        else "unknown"
    )
    return {
        "captured_at": captured_at or stamp(),
        "adapter": str(net.get("adapter") or ""),
        "adapter_description": str(net.get("adapter_description") or ""),
        "adapter_kind": str(net.get("adapter_kind") or "unknown"),
        "interface_index": str(net.get("interface_index") or ""),
        "local_ipv4": str(net.get("ip") or ""),
        "network_cidr": str(net.get("network") or ""),
        "gateway": str(net.get("gateway") or ""),
        "dhcp_enabled": dhcp_state,
        "dhcp_server": str(net.get("dhcp_server") or ""),
        "dhcp_lease_obtained": str(net.get("dhcp_lease_obtained") or ""),
        "dhcp_lease_expires": str(net.get("dhcp_lease_expires") or ""),
        "evidence_source": "windows_ip_configuration",
    }


def format_network_diagnostics(net):
    """Format selected local adapter context for the scan's local output."""
    gateway = str(net.get("gateway") or "").strip() or "yok (varsayılan ağ geçidi yok)"
    dhcp_enabled = net.get("dhcp_enabled")
    dhcp_status = (
        "etkin" if dhcp_enabled is True
        else "devre dışı" if dhcp_enabled is False
        else "bilinmiyor"
    )
    return (
        "Tarama ağ bağlamı: "
        f"adaptör={str(net.get('adapter') or 'bilinmiyor')}; "
        f"adaptör türü={str(net.get('adapter_kind') or 'unknown')}; "
        f"donanım açıklaması={str(net.get('adapter_description') or 'bilinmiyor')}; "
        f"IPv4={str(net.get('ip') or 'bilinmiyor')}; "
        f"alt ağ={str(net.get('network') or 'bilinmiyor')}; "
        f"ağ geçidi={gateway}; "
        f"arayüz indeksi={str(net.get('interface_index') or 'bilinmiyor')}; "
        f"DHCP={dhcp_status}; "
        f"DHCP sunucusu={str(net.get('dhcp_server') or 'bilinmiyor')}; "
        f"kira başlangıcı={str(net.get('dhcp_lease_obtained') or 'bilinmiyor')}; "
        f"kira bitişi={str(net.get('dhcp_lease_expires') or 'bilinmiyor')}"
    )


def scan(scan_cidr=None, approved=False, confirmation=None, interface_alias=None):
    print("[1/4] Aktif ag algilaniyor...", flush=True)
    selected_alias = interface_alias or os.getenv("WIFI_VISION_INTERFACE_ALIAS", "").strip() or None
    net = get_network(selected_alias)
    print(format_network_diagnostics(net), flush=True)
    overwrite_rows(
        DATA / "network_context.csv",
        [build_network_context_row(net)],
        NETWORK_CONTEXT_FIELDS,
    )
    active_network = net["network"]

    requested_cidr = (
        str(scan_cidr or os.getenv("WIFI_VISION_SCAN_CIDR", "")).strip()
        or active_network
    )
    approved = approved or os.getenv("WIFI_VISION_SCAN_APPROVED") == "1"
    confirmation = (
        confirmation
        if confirmation is not None
        else os.getenv("WIFI_VISION_SCAN_CONFIRMATION", "")
    )

    settings = load_scan_settings()
    hosts, truncated = build_scan_targets(
        requested_cidr,
        net["ip"],
        net["gateway"],
        max_hosts=settings["max_hosts"],
        active_network_cidr=active_network,
        approved=approved,
        confirmation=confirmation,
    )
    selected_network = str(ipaddress.ip_network(requested_cidr, strict=True))
    net["active_network"] = active_network
    net["network"] = selected_network

    if truncated:
        network_size = ipaddress.ip_network(selected_network).num_addresses
        print(
            f"[UYARI] Alt agda {network_size} adres alani var; "
            f"guvenlik siniri nedeniyle ilk {len(hosts)} hedef taranacak. "
            "WIFI_VISION_MAX_SCAN_HOSTS ile siniri kontrollu artirabilirsiniz.",
            flush=True,
        )

    print(
        f"[2/4] {len(hosts)} IP adresi taraniyor: {selected_network} "
        f"(eszamanli isci: {settings['workers']}, "
        f"ping: {settings['ping_timeout_ms']} ms)",
        flush=True
    )

    alive = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=settings["workers"]
    ) as executor:
        futures = {
            executor.submit(ping_one, ip, settings["ping_timeout_ms"]): ip
            for ip in hosts
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            ip = futures[future]
            try:
                alive[ip] = future.result()
            except Exception:
                alive[ip] = False
            completed += 1
            if completed % 25 == 0 or completed == len(hosts):
                print(f"    Tarama: {completed}/{len(hosts)}", flush=True)

    print("[3/4] ARP tablosu okunuyor...", flush=True)
    arp = arp_map()

    infrastructure_prefixes = ("48:81:D4", "E0:5D:54", "9C:CE:88")
    discovered_ips = [
        ip for ip in hosts
        if ip == net["gateway"]
        or any(
            arp.get(ip, "").upper().startswith(prefix)
            for prefix in infrastructure_prefixes
        )
    ]
    print("[DNS] Bulunan cihazlarin isimleri sorgulaniyor...", flush=True)
    hostnames = resolve_hostnames(discovered_ips)

    rows = []
    for ip in hosts:
        responding = alive.get(ip, False)
        if responding or ip in arp or ip == net["gateway"]:
            rows.append({
                "timestamp": stamp(),
                "ip": ip,
                "mac": arp.get(ip, ""),
                "hostname": hostnames.get(ip, ""),
                "status": "responding" if responding else "arp_seen",
                "gateway": net["gateway"],
                "adapter": net["adapter"],
                "subnet": selected_network
            })

    print("[4/4] Sonuclar kaydediliyor...", flush=True)
    overwrite_rows(
        DATA / "device_inventory.csv",
        rows,
        [
            "timestamp", "ip", "mac", "hostname",
            "status", "gateway", "adapter", "subnet"
        ]
    )
    print(f"Tarama tamamlandi. Bulunan cihaz: {len(rows)}", flush=True)
    return net, rows


if __name__ == "__main__":
    n, r = scan()

    print(f"Network: {n['network']}")
    print(f"Gateway: {n['gateway']}")
    print(f"Adapter: {n['adapter']}")
    print(f"Observed devices: {len(r)}")
