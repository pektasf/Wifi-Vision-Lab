
import ipaddress
import subprocess
import re
import concurrent.futures
import json
import platform

from scripts.common import DATA, stamp, overwrite_rows


def get_network():
    if platform.system() != "Windows":
        raise RuntimeError("Bu paket Windows içindir.")

    ps = (
        "$c=Get-NetIPConfiguration | "
        "Where-Object {$_.IPv4DefaultGateway -and $_.IPv4Address} | "
        "Select-Object -First 1; "
        "if($c){[pscustomobject]@{"
        "IP=$c.IPv4Address[0].IPAddress; "
        "Prefix=$c.IPv4Address[0].PrefixLength; "
        "Gateway=$c.IPv4DefaultGateway.NextHop; "
        "Adapter=$c.InterfaceAlias"
        "}|ConvertTo-Json -Compress}"
    )

    p = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=15
    )

    if p.returncode or not p.stdout.strip():
        raise RuntimeError(
            "Aktif IPv4 ağı bulunamadı. Wi-Fi/Ethernet bağlantısını kontrol edin."
        )

    d = json.loads(p.stdout.strip().splitlines()[-1])
    iface = ipaddress.ip_interface(f"{d['IP']}/{d['Prefix']}")

    return {
        "ip": d["IP"],
        "gateway": d["Gateway"],
        "adapter": d["Adapter"],
        "network": str(iface.network)
    }


def ping_one(ip):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "600", str(ip)],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def arp_map():
    p = subprocess.run(
        ["arp", "-a"],
        capture_output=True,
        text=True,
        errors="ignore",
        timeout=10
    )

    out = {}

    for line in p.stdout.splitlines():
        m = re.search(
            r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F-]{17})",
            line
        )

        if m:
            out[m.group(1)] = m.group(2).replace("-", ":").upper()

    return out



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


def scan():
    print("[1/4] Aktif ağ algılanıyor...", flush=True)
    net = get_network()

    hosts = [
        str(x)
        for x in ipaddress.ip_network(
            net["network"], strict=False
        ).hosts()
    ]

    if len(hosts) > 1024:
        hosts = hosts[:1024]

    print(
        f"[2/4] {len(hosts)} IP adresi taranıyor: {net['network']}",
        flush=True
    )

    alive = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
        futures = {
            executor.submit(ping_one, ip): ip
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
                print(
                    f"    Tarama: {completed}/{len(hosts)}",
                    flush=True
                )

    print("[3/4] ARP tablosu okunuyor...", flush=True)
    arp = arp_map()

    infrastructure_prefixes = (
        "48:81:D4",
        "E0:5D:54",
        "9C:CE:88"
    )

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
        ok = alive.get(ip, False)

        if ok or ip in arp or ip == net["gateway"]:
            rows.append({
                "timestamp": stamp(),
                "ip": ip,
                "mac": arp.get(ip, ""),
                "hostname": hostnames.get(ip, ""),
                "status": "responding" if ok else "arp_seen",
                "gateway": net["gateway"],
                "adapter": net["adapter"],
                "subnet": net["network"]
            })

    print("[4/4] Sonuçlar kaydediliyor...", flush=True)

    overwrite_rows(
        DATA / "device_inventory.csv",
        rows,
        [
            "timestamp",
            "ip",
            "mac",
            "hostname",
            "status",
            "gateway",
            "adapter",
            "subnet"
        ]
    )

    print(f"Tarama tamamlandı. Bulunan cihaz: {len(rows)}", flush=True)

    return net, rows


if __name__ == "__main__":
    n, r = scan()

    print(f"Network: {n['network']}")
    print(f"Gateway: {n['gateway']}")
    print(f"Adapter: {n['adapter']}")
    print(f"Observed devices: {len(r)}")
