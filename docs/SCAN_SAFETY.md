# Local network scan safety

WiFi Vision Lab discovery is intentionally limited to the IPv4 subnet reported by
the active Windows interface. The scanner does not accept arbitrary target IPs,
CIDR ranges, or public Internet ranges.

## Safe defaults

| Setting | Default | Allowed range |
|---|---:|---:|
| `WIFI_VISION_MAX_SCAN_HOSTS` | 1024 | 1–4096 |
| `WIFI_VISION_SCAN_WORKERS` | 32 | 1–64 |
| `WIFI_VISION_PING_TIMEOUT_MS` | 600 | 100–3000 |

If the local subnet contains more hosts than the configured limit, the scanner
uses only the first bounded set of host addresses and prints a warning. Increase
the limit only on a network you own or are explicitly authorized to assess.

## Windows PowerShell example

Set these variables in the same PowerShell session before launching the app:

```powershell
$env:WIFI_VISION_MAX_SCAN_HOSTS = "512"
$env:WIFI_VISION_SCAN_WORKERS = "32"
$env:WIFI_VISION_PING_TIMEOUT_MS = "600"
.START.bat
```

Invalid values stop the scan with a clear configuration error instead of
silently applying an unexpected limit. These controls bound the existing ICMP
and local ARP-based discovery; they do not turn the application into a
vulnerability scanner or guarantee that every device will respond.


## Explicit custom scan scope

The default remains the active IPv4 subnet reported by Windows. A custom
target is optional and must be a canonical IPv4 CIDR inside one of the RFC1918
private ranges: 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16.

In the Streamlit sidebar, expand **Tarama kapsamı**, enter the target CIDR,
confirm that you are authorized to scan it, and type the same CIDR again.
The application rejects the request if the confirmation is missing or does
not exactly match the canonical CIDR. Public, loopback, link-local, multicast,
reserved, and CGNAT ranges remain rejected even after approval.

The active interface and its default gateway are independently validated.
A custom target does not need to be the active interface subnet, because it
may be a separately routed private subnet; however, the user is responsible
for ensuring that the target is reachable and that they have permission to
scan it. The scanner does not discover routes or prove ownership.

The existing limits still apply to custom scopes:
- maximum 4,096 target addresses per run;
- maximum 64 concurrent workers;
- ping timeout between 100 and 3,000 ms;
- defaults remain 1,024 targets, 32 workers, and 600 ms.

Custom scope is passed to the scan subprocess only for that run. The app
removes inherited custom-scope environment variables for ordinary scans so
an old setting cannot silently widen the next scan.
