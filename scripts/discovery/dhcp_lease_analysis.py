"""Conservative analysis of Zeek DHCP lease windows.

Zeek's DHCP log timestamp is the earliest message in a transaction and
duration spans the transaction. The lease start below is an estimate at
ts + duration, not an authoritative DHCP-server lease database.
"""

import heapq
import ipaddress
from datetime import datetime, timedelta, timezone
from math import isfinite

from scripts.discovery.identity_signals import normalize_mac


def _parse_time(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _seconds(value, allow_zero=False):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        return None
    return number


def _ip(value):
    try:
        return str(ipaddress.IPv4Address(str(value or "").strip()))
    except (TypeError, ValueError):
        return ""


def _scope(row):
    for field in ("network_id", "subnet", "network"):
        value = str(row.get(field, "") or "").strip()
        if value:
            return value
    return ""


def _iso(value):
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _has_ack(value):
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = str(value or "").replace(",", ";").split(";")
    return any(str(item).strip().upper() == "ACK" for item in items)


def analyze_dhcp_lease_windows(observations):
    """Add estimated lease windows and conservative address-reuse findings.

    Comparisons are scoped by DHCP server + assigned IPv4. When both rows
    provide an explicit network scope, different scopes are never compared.
    Missing scope downgrades overlapping different-MAC findings to a
    review-only candidate.
    """
    rows = [dict(row) for row in (observations or [])]
    results = []
    leases = []

    for index, row in enumerate(rows):
        row.update({
            "lease_start_estimate": "",
            "lease_expiry_estimate": "",
            "lease_window_seconds": "",
            "lease_timing_quality": "",
            "lease_analysis": "Karşılaştırma yapılamadı",
            "lease_related_observation": "",
        })
        results.append(row)

        if not _has_ack(row.get("message_types")):
            row["lease_analysis"] = "ACK yok · kira başlangıcı doğrulanamadı"
            continue

        assigned_ip = _ip(row.get("assigned_ip"))
        if not assigned_ip:
            row["lease_analysis"] = "Atanmış IP yok"
            continue

        lease_seconds = _seconds(row.get("lease_time_seconds"))
        if lease_seconds is None or lease_seconds > 4294967295:
            row["lease_analysis"] = "Geçerli kira süresi yok"
            continue

        observed = _parse_time(row.get("observed_at"))
        if observed is None:
            row["lease_analysis"] = "Geçerli zaman damgası yok"
            continue

        duration = _seconds(row.get("duration_seconds"), allow_zero=True)
        if duration is not None and duration > 86400:
            duration = None
        timing_quality = "transaction_end_estimate" if duration is not None else "first_message_estimate"
        try:
            start = observed + timedelta(seconds=duration or 0)
            expiry = start + timedelta(seconds=lease_seconds)
        except (OverflowError, ValueError):
            row["lease_analysis"] = "Kira zaman aralığı hesaplanamadı"
            continue

        row["lease_start_estimate"] = _iso(start)
        row["lease_expiry_estimate"] = _iso(expiry)
        row["lease_window_seconds"] = str(int(lease_seconds) if lease_seconds.is_integer() else lease_seconds)
        row["lease_timing_quality"] = timing_quality
        row["lease_analysis"] = "Kira penceresi hesaplandı"

        server_ip = _ip(row.get("server_ip"))
        mac = normalize_mac(row.get("mac"))
        if not server_ip or not mac:
            row["lease_analysis"] = "Kira hesaplandı · sunucu veya MAC eksik"
            continue

        leases.append({
            "index": index,
            "server": server_ip,
            "ip": assigned_ip,
            "mac": mac,
            "scope": _scope(row),
            "start": start,
            "end": expiry,
        })

    groups = {}
    for lease in leases:
        groups.setdefault((lease["server"], lease["ip"]), []).append(lease)

    for group in groups.values():
        group.sort(key=lambda item: (item["start"], item["index"]))
        active = {}
        by_scope = {}
        unknown_scope = {}
        all_macs = {}
        expiry_heap = []
        seen_by_scope = {}
        seen_unknown = set()

        def add_bucket(bucket, mac, lease_index):
            bucket.setdefault(mac, set()).add(lease_index)

        def remove_bucket(bucket, mac, lease_index):
            values = bucket.get(mac)
            if values is not None:
                values.discard(lease_index)
                if not values:
                    bucket.pop(mac, None)

        for lease in group:
            while expiry_heap and expiry_heap[0][0] <= lease["start"].timestamp():
                _, expired_index = heapq.heappop(expiry_heap)
                expired = active.pop(expired_index, None)
                if expired is None:
                    continue
                remove_bucket(all_macs, expired["mac"], expired_index)
                if expired["scope"]:
                    scope_bucket = by_scope.get(expired["scope"], {})
                    remove_bucket(scope_bucket, expired["mac"], expired_index)
                    if not scope_bucket:
                        by_scope.pop(expired["scope"], None)
                else:
                    remove_bucket(unknown_scope, expired["mac"], expired_index)

            current_mac = lease["mac"]
            current_scope = lease["scope"]
            if current_scope:
                candidate_buckets = [
                    by_scope.get(current_scope, {}),
                    unknown_scope,
                ]
                prior_same_scope = set(seen_by_scope.get(current_scope, set()))
                prior_unknown_scope = set(seen_unknown)
            else:
                candidate_buckets = [all_macs]
                prior_same_scope = set()
                prior_unknown_scope = set(seen_unknown)
                for macs in seen_by_scope.values():
                    prior_unknown_scope.update(macs)

            overlapping_mac = ""
            for bucket in candidate_buckets:
                for candidate_mac, indexes in bucket.items():
                    if candidate_mac != current_mac and indexes:
                        overlapping_mac = candidate_mac
                        break
                if overlapping_mac:
                    break

            row = results[lease["index"]]
            if overlapping_mac:
                same_scope_match = bool(
                    current_scope
                    and overlapping_mac in by_scope.get(current_scope, {})
                )
                row["lease_analysis"] = (
                    "Çakışan kira adayı · ağ kapsamı doğrulandı"
                    if same_scope_match
                    else "Olası çakışma · ağ kapsamı bilinmiyor"
                )
                row["lease_related_observation"] = overlapping_mac
            elif any(mac != current_mac for mac in prior_same_scope):
                row["lease_analysis"] = "Önceki farklı MAC kirası sona ermiş · sıralı yeniden kullanım"
            elif any(mac != current_mac for mac in prior_unknown_scope):
                row["lease_analysis"] = "Farklı MAC sonrası yeniden kullanım · ağ kapsamı bilinmiyor"

            active[lease["index"]] = lease
            add_bucket(all_macs, current_mac, lease["index"])
            if current_scope:
                add_bucket(by_scope.setdefault(current_scope, {}), current_mac, lease["index"])
                seen_by_scope.setdefault(current_scope, set()).add(current_mac)
            else:
                add_bucket(unknown_scope, current_mac, lease["index"])
                seen_unknown.add(current_mac)
            heapq.heappush(expiry_heap, (lease["end"].timestamp(), lease["index"]))

    return results
