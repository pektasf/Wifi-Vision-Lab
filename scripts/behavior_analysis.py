"""Evidence-based review findings from the current local device inventory."""
from __future__ import annotations

import pandas as pd

from scripts.common import DATA, overwrite_rows, stamp


FINDING_FIELDS = ["timestamp", "severity", "type", "subject", "detail"]


def analyze_inventory(inventory: pd.DataFrame) -> list[dict[str, str]]:
    """Find duplicate address mappings in one inventory snapshot.

    These are review signals only. They do not establish spoofing, compromise,
    or malicious behavior.
    """
    if inventory is None or inventory.empty:
        return []
    if "ip" not in inventory.columns or "mac" not in inventory.columns:
        return []

    frame = inventory.copy()
    frame["ip"] = frame["ip"].fillna("").astype(str).str.strip()
    frame["mac"] = (
        frame["mac"].fillna("").astype(str).str.strip().str.upper()
    )
    frame = frame[(frame["ip"] != "") | (frame["mac"] != "")]
    timestamp = stamp()
    findings: list[dict[str, str]] = []

    with_mac = frame[frame["mac"] != ""]
    for mac, group in with_mac.groupby("mac", sort=True):
        ips = sorted(value for value in group["ip"].unique().tolist() if value)
        if len(ips) > 1:
            findings.append({
                "timestamp": timestamp,
                "severity": "review",
                "type": "MULTIPLE_IPS_SAME_MAC",
                "subject": mac,
                "detail": (
                    "Aynı MAC adresi tek envanter anlık görüntüsünde birden fazla "
                    "IP ile eşleşti: " + ", ".join(ips)
                ),
            })

    with_ip = frame[frame["ip"] != ""]
    for ip, group in with_ip.groupby("ip", sort=True):
        macs = sorted(value for value in group["mac"].unique().tolist() if value)
        if len(macs) > 1:
            findings.append({
                "timestamp": timestamp,
                "severity": "review",
                "type": "MULTIPLE_MACS_SAME_IP",
                "subject": ip,
                "detail": (
                    "Aynı IP adresi tek envanter anlık görüntüsünde birden fazla "
                    "MAC ile eşleşti: " + ", ".join(macs)
                ),
            })

    return findings


def run(
    inventory_path=None,
    output_path=None,
) -> list[dict[str, str]]:
    """Analyze the current local inventory and persist the resulting findings."""
    source = inventory_path or DATA / "device_inventory.csv"
    destination = output_path or DATA / "behavior_findings.csv"
    source = pd.io.common.stringify_path(source)
    destination = pd.io.common.stringify_path(destination)
    try:
        inventory = pd.read_csv(
            source, dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, pd.errors.ParserError):
        return []

    findings = analyze_inventory(inventory)
    overwrite_rows(destination, findings, FINDING_FIELDS)
    return findings


if __name__ == "__main__":
    print(len(run()))
