import pandas as pd
from scripts.common import DATA, stamp, overwrite_rows


def _score(value):
    """Parse one confidence score without affecting the other score."""
    try:
        return int(float(value))
    except (ValueError, TypeError, OverflowError):
        return 0


def run():
    source = DATA / "device_intelligence.csv"
    if not source.exists():
        print("device_intelligence.csv bulunamadı.")
        return []

    df = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    rows = []

    for _, r in df.iterrows():
        vendor_score = _score(r.get("vendor_confidence", 0))
        device_score = _score(r.get("device_confidence", 0))

        if device_score >= 75:
            confidence = "high"
        elif device_score >= 50:
            confidence = "medium"
        else:
            confidence = "low"

        rows.append({
            "timestamp": stamp(),
            "ip": r.get("ip", ""),
            "identity_hint": r.get("hostname") or r.get("vendor") or r.get("mac") or r.get("ip", ""),
            "category": r.get("classification", ""),
            "vendor": r.get("vendor", ""),
            "vendor_role": r.get("vendor_role", ""),
            "device_role": r.get("device_role", "Unknown"),
            "role_confidence": _score(r.get("role_confidence", 0)),
            "role_evidence_type": r.get("role_evidence_type", "insufficient_evidence"),
            "model": r.get("model", ""),
            "model_confidence": _score(r.get("model_confidence", 0)),
            "model_status": r.get("model_status", "unknown"),
            "model_source": r.get("model_source", "not_available"),
            "firmware_version": r.get("firmware_version", ""),
            "firmware_confidence": _score(r.get("firmware_confidence", 0)),
            "firmware_status": r.get("firmware_status", "unknown"),
            "firmware_source": r.get("firmware_source", "not_available"),
            "fingerprint_evidence": r.get("fingerprint_evidence", "no_model_or_firmware_evidence"),
            "mac_type": r.get("mac_type", ""),
            "vendor_confidence": vendor_score,
            "device_confidence": device_score,
            "confidence": confidence,
            "note": r.get("evidence", "")
        })

    fields = [
        "timestamp", "ip", "identity_hint", "category", "vendor",
        "vendor_role", "device_role", "role_confidence",
        "role_evidence_type", "model", "model_confidence", "model_status",
        "model_source", "firmware_version", "firmware_confidence",
        "firmware_status", "firmware_source", "fingerprint_evidence",
        "mac_type", "vendor_confidence",
        "device_confidence", "confidence", "note"
    ]
    overwrite_rows(DATA / "device_classification.csv", rows, fields)
    print(f"Cihaz sınıflandırması tamamlandı: {len(rows)} kayıt")
    return rows


if __name__ == "__main__":
    run()
