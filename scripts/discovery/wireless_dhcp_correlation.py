"""Conservative temporal links between Kismet Wi-Fi and Zeek DHCP evidence.

A link means the same normalized MAC address was observed near the same time.
It does not prove a physical device or person identity. BSSID is AP context,
never a client identity key.
"""

from datetime import datetime, timezone

from scripts.discovery.identity_signals import normalize_mac

DEFAULT_WINDOW_SECONDS = 300
MAX_CORRELATION_PAIRS = 10000


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


def _scope(row):
    for field in ("network_id", "subnet", "network"):
        value = str(row.get(field, "") or "").strip()
        if value:
            return value
    return ""


def correlate_wireless_dhcp_observations(
    wireless_observations,
    dhcp_observations,
    window_seconds=DEFAULT_WINDOW_SECONDS,
    limit=MAX_CORRELATION_PAIRS,
):
    """Return exact-MAC, time-near cross-source pairs without merging records.

    Different explicitly supplied network scopes are excluded. Missing scope
    is retained as an uncertainty. Missing/invalid timestamps are not linked.
    Randomized MAC flags are preserved as a caution, not used to infer identity.
    """
    try:
        window = float(window_seconds)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Zaman penceresi sayısal olmalıdır.")
    if window <= 0 or window > 3600:
        raise ValueError("Zaman penceresi 1 ile 3600 saniye arasında olmalıdır.")

    try:
        max_pairs = max(1, min(int(limit), MAX_CORRELATION_PAIRS))
    except (TypeError, ValueError, OverflowError):
        max_pairs = MAX_CORRELATION_PAIRS

    wireless = []
    for index, source in enumerate(wireless_observations or []):
        row = dict(source)
        mac = normalize_mac(row.get("mac"))
        observed = _parse_time(row.get("observed_at") or row.get("ts"))
        if mac and observed is not None:
            wireless.append((index, row, mac, observed))

    dhcp = []
    for index, source in enumerate(dhcp_observations or []):
        row = dict(source)
        mac = normalize_mac(row.get("mac"))
        observed = _parse_time(row.get("observed_at") or row.get("ts"))
        if mac and observed is not None:
            dhcp.append((index, row, mac, observed))

    from bisect import bisect_left

    by_mac = {}
    for item in wireless:
        by_mac.setdefault(item[2], []).append(item)
    for items in by_mac.values():
        items.sort(key=lambda item: item[3])
        timestamps = [item[3].timestamp() for item in items]
        items[:] = (items, timestamps)

    pairs = []
    for dhcp_index, dhcp_row, mac, dhcp_time in dhcp:
        indexed = by_mac.get(mac)
        if not indexed:
            continue
        items, timestamps = indexed
        center = dhcp_time.timestamp()
        insertion = bisect_left(timestamps, center)
        left = insertion - 1
        right = insertion
        nearest = []
        # Keep work and memory bounded even when a MAC has many repeated observations.
        while len(nearest) < 20 and (left >= 0 or right < len(items)):
            left_delta = abs(center - timestamps[left]) if left >= 0 else float('inf')
            right_delta = abs(timestamps[right] - center) if right < len(items) else float('inf')
            if left_delta <= right_delta:
                if left_delta > window:
                    break
                nearest.append(items[left])
                left -= 1
            else:
                if right_delta > window:
                    break
                nearest.append(items[right])
                right += 1
        for wireless_index, wireless_row, wireless_mac, wireless_time in nearest:
            delta = abs((dhcp_time - wireless_time).total_seconds())
            wireless_scope = _scope(wireless_row)
            dhcp_scope = _scope(dhcp_row)
            if wireless_scope and dhcp_scope and wireless_scope != dhcp_scope:
                continue
            random_flag = str(wireless_row.get('randomized_mac', '')).strip().casefold()
            if random_flag not in {'true', 'false'}:
                random_flag = 'unknown'
            if random_flag == 'true':
                status = 'exact_mac_time_near_randomized_mac'
                interpretation = 'Randomized MAC işaretli adresin zaman yakınlığı; fiziksel cihaz kimliği doğrulanmaz'
            elif wireless_scope and dhcp_scope:
                status = 'exact_mac_time_near_scope_match'
                interpretation = 'MAC ve zaman yakın; açık ağ kapsamı da eşleşiyor'
            else:
                status = 'exact_mac_time_near_scope_unknown'
                interpretation = 'MAC ve zaman yakın; ağ kapsamı eksik'
            pairs.append({
                'wireless_observed_at': str(wireless_row.get('observed_at') or wireless_row.get('ts') or ''),
                'dhcp_observed_at': str(dhcp_row.get('observed_at') or dhcp_row.get('ts') or ''),
                'mac': mac,
                'time_delta_seconds': round(delta, 3),
                'wireless_bssid_context': normalize_mac(wireless_row.get('last_bssid')),
                'wireless_signal_dbm': str(wireless_row.get('signal_dbm', '') or ''),
                'dhcp_assigned_ip': str(dhcp_row.get('assigned_ip', '') or ''),
                'dhcp_server_ip': str(dhcp_row.get('server_ip', '') or ''),
                'wireless_network_scope': wireless_scope,
                'dhcp_network_scope': dhcp_scope,
                'randomized_mac': random_flag,
                'correlation_status': status,
                'interpretation': interpretation,
                'wireless_source_index': wireless_index,
                'dhcp_source_index': dhcp_index,
            })
            if len(pairs) >= max_pairs:
                break
        if len(pairs) >= max_pairs:
            break
    pairs.sort(key=lambda row: (row['time_delta_seconds'], row['dhcp_observed_at']))
    return pairs
