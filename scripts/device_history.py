import pandas as pd
from scripts.common import DATA, stamp, write_rows, overwrite_rows

HISTORY_FIELDS = [
    "observed_at", "ip", "mac", "hostname", "identity_key"
]

PROFILE_FIELDS = [
    "identity_key", "first_seen", "last_seen", "current_ip",
    "ip_history", "ip_change_count", "mac", "hostname",
    "vendor", "classification", "observation_count", "status"
]

EVENT_FIELDS = [
    "event_time", "identity_key", "event_type",
    "old_value", "new_value", "details"
]

def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

def identity_for(mac, ip):
    mac = str(mac).strip().upper()
    if mac:
        return mac
    return "IP:" + str(ip).strip()

def parse_time(value):
    try:
        return pd.to_datetime(value, utc=True)
    except Exception:
        return pd.NaT

def run():
    inventory_path = DATA / "device_inventory.csv"
    history_path = DATA / "device_history.csv"
    profiles_path = DATA / "device_profiles.csv"
    events_path = DATA / "device_events.csv"
    intelligence_path = DATA / "device_intelligence.csv"

    if not inventory_path.exists():
        print("device_inventory.csv bulunamadı.")
        return []

    inventory = read_csv(inventory_path)
    if inventory.empty:
        print("Envanter boş.")
        return []

    intelligence = read_csv(intelligence_path)
    history = read_csv(history_path)

    # Güncel cihaz analizlerini kimlik anahtarına bağla.
    intel_map = {}
    if not intelligence.empty:
        for _, row in intelligence.iterrows():
            key = identity_for(row.get("mac", ""), row.get("ip", ""))
            intel_map[key] = row.to_dict()

    # Mevcut geçmiş kayıtlarını tekilleştirme için kullan.
    known_observations = set()
    if not history.empty:
        for _, row in history.iterrows():
            known_observations.add((
                str(row.get("observed_at", "")),
                identity_for(row.get("mac", ""), row.get("ip", ""))
            ))

    old_profiles = read_csv(profiles_path)
    old_profile_map = {}

    if not old_profiles.empty:
        for _, row in old_profiles.iterrows():
            old_profile_map[str(row["identity_key"])] = row.to_dict()

    new_rows = []
    events = []
    current_keys = set()

    for _, row in inventory.iterrows():
        ip = str(row.get("ip", "")).strip()
        mac = str(row.get("mac", "")).strip().upper()
        hostname = str(row.get("hostname", "")).strip()
        observed_at = str(row.get("timestamp", "")).strip() or stamp()
        key = identity_for(mac, ip)

        current_keys.add(key)

        observation_id = (observed_at, key)
        if observation_id in known_observations:
            continue

        new_rows.append({
            "observed_at": observed_at,
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "identity_key": key
        })

        previous = old_profile_map.get(key)

        if not previous:
            events.append({
                "event_time": observed_at,
                "identity_key": key,
                "event_type": "new_device",
                "old_value": "",
                "new_value": ip,
                "details": "Bu kimlik ilk kez gözlemlendi."
            })
        else:
            old_ip = str(previous.get("current_ip", ""))
            if old_ip and ip and old_ip != ip:
                events.append({
                    "event_time": observed_at,
                    "identity_key": key,
                    "event_type": "ip_changed",
                    "old_value": old_ip,
                    "new_value": ip,
                    "details": "Aynı MAC kimliği farklı IP adresinde gözlemlendi."
                })

            previous_time = parse_time(previous.get("last_seen", ""))
            current_time = parse_time(observed_at)

            if pd.notna(previous_time) and pd.notna(current_time):
                gap_minutes = (current_time - previous_time).total_seconds() / 60
                if gap_minutes >= 10:
                    events.append({
                        "event_time": observed_at,
                        "identity_key": key,
                        "event_type": "seen_again",
                        "old_value": previous.get("last_seen", ""),
                        "new_value": observed_at,
                        "details": f"Cihaz en az {int(gap_minutes)} dakika sonra yeniden gözlemlendi."
                    })

    # Yalnızca yeni gözlemleri geçmişe ekle.
    if new_rows:
        write_rows(history_path, new_rows, HISTORY_FIELDS)

    # Tüm geçmişten cihaz profillerini yeniden oluştur.
    combined = read_csv(history_path)
    profiles = []

    if not combined.empty:
        combined["_time"] = combined["observed_at"].apply(parse_time)
        combined = combined.sort_values("_time")

        for key, group in combined.groupby("identity_key", sort=False):
            group = group.sort_values("_time")
            first = group.iloc[0]
            last = group.iloc[-1]

            ips = list(dict.fromkeys(
                ip for ip in group["ip"].tolist() if ip
            ))

            latest_intel = intel_map.get(key, {})
            profiles.append({
                "identity_key": key,
                "first_seen": first["observed_at"],
                "last_seen": last["observed_at"],
                "current_ip": last["ip"],
                "ip_history": "; ".join(ips),
                "ip_change_count": max(0, len(ips) - 1),
                "mac": last["mac"],
                "hostname": last["hostname"],
                "vendor": latest_intel.get("vendor", ""),
                "classification": latest_intel.get("classification", ""),
                "observation_count": len(group),
                "status": "seen_in_latest_scan" if key in current_keys else "not_seen_in_latest_scan"
            })

    overwrite_rows(profiles_path, profiles, PROFILE_FIELDS)

    # İlk kurulum: mevcut profilleri başlangıç envanteri olarak kaydet.
    existing_events = read_csv(events_path)

    if existing_events.empty and profiles:
        baseline_time = stamp()

        for profile in profiles:
            events.append({
                "event_time": baseline_time,
                "identity_key": profile["identity_key"],
                "event_type": "baseline_snapshot",
                "old_value": "",
                "new_value": profile["current_ip"],
                "details": "Mevcut cihaz başlangıç envanterine alındı. Bu kayıt geçmiş bağlantı olayı değildir."
            })
    # Olayları yalnızca yeni olaylar varsa ekle.
    if events:
        write_rows(events_path, events, EVENT_FIELDS)
    elif not events_path.exists():
        overwrite_rows(events_path, [], EVENT_FIELDS)

    print(f"Yeni gözlem: {len(new_rows)}")
    print(f"Cihaz profili: {len(profiles)}")
    print(f"Yeni olay: {len(events)}")
    print(f"Geçmiş dosyası: {history_path}")
    print(f"Profil dosyası: {profiles_path}")
    print(f"Olay dosyası: {events_path}")

    return profiles

if __name__ == "__main__":
    run()

