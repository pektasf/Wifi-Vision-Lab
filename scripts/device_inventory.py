
import ipaddress
import subprocess
import re
import concurrent.futures
import json
import os
import platform

from scripts.common import DATA, stamp, overwrite_rows
from scripts.scan_policy import build_scan_targets, load_scan_settings


def list_network_interfaces():
    """Return local IPv4 interfaces, including Windows hosted-network adapters."""
    if platform.system() != "Windows":
        raise RuntimeError("Bu ağ adaptörü şu anda Windows içindir.")

    ps = (
        "$items = @(Get-NetIPConfiguration | "
        "Where-Object {$_.IPv4Address} | ForEach-Object { "
        "$gateway = ''; "
        "if($_.IPv4DefaultGateway){$gateway=$_.IPv4DefaultGateway.NextHop}; "
        "[pscustomobject]@{"
        "IP=$_.IPv4Address[0].IPAddress; "
        "Prefix=$_.IPv4Address[0].PrefixLength; "
        "Gateway=$gateway; "
        "Adapter=$_.InterfaceAlias; "
        "InterfaceIndex=$_.InterfaceIndex"
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
            interfaces.append({
                "ip": str(interface.ip),
                "gateway": gateway,
                "adapter": str(row.get("Adapter") or "Unknown"),
                "interface_index": int(row.get("InterfaceIndex") or 0),
                "network": str(interface.network),
                "has_default_gateway": bool(gateway),
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
        "network": selected["network"],
        "interface_index": selected["interface_index"],
        "has_default_gateway": selected["has_default_gateway"],
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


def scan(scan_cidr=None, approved=False, confirmation=None, interface_alias=None):
    print("[1/4] Aktif ag algilaniyor...", flush=True)
    selected_alias = interface_alias or os.getenv("WIFI_VISION_INTERFACE_ALIAS", "").strip() or None
    net = get_network(selected_alias)
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
