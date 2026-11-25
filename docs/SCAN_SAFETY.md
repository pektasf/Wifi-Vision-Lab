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
