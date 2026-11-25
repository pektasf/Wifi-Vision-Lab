"""Normalize device model and firmware evidence without guessing.

This module deliberately does not infer model or firmware from a vendor OUI
or hostname. It only accepts values accompanied by an explicit provenance.
"""
from __future__ import annotations


SOURCE_CONFIDENCE = {
    "management_api": 95,
    "snmp_sysdescr": 85,
    "lldp_system_description": 75,
    "manual_verified": 100,
    "unverified_input": 20,
}

VERIFIED_SOURCES = {"management_api", "manual_verified"}
OBSERVED_SOURCES = {"snmp_sysdescr", "lldp_system_description"}


def _clean(value):
    text = str(value or "").strip()
    if text.casefold() in {"nan", "none", "null", "unknown", "n/a"}:
        return ""
    return text


def _field(value, source):
    cleaned = _clean(value)
    if not cleaned:
        return "", 0, "unknown", "not_available"

    provenance = _clean(source).casefold()
    if provenance not in SOURCE_CONFIDENCE:
        provenance = "unverified_input"

    confidence = SOURCE_CONFIDENCE[provenance]
    if provenance in VERIFIED_SOURCES:
        status = "verified"
    elif provenance in OBSERVED_SOURCES:
        status = "observed_unverified"
    else:
        status = "unverified"

    return cleaned, confidence, status, provenance


def resolve_device_fingerprint(record):
    """Return model/firmware values with source, confidence and status.

    Expected optional input keys: model, model_source, firmware_version,
    firmware_source. Missing values remain explicitly unknown.
    """
    model, model_confidence, model_status, model_source = _field(
        record.get("model", ""), record.get("model_source", "")
    )
    firmware, firmware_confidence, firmware_status, firmware_source = _field(
        record.get("firmware_version", record.get("firmware", "")),
        record.get("firmware_source", ""),
    )

    evidence = []
    if model:
        evidence.append(f"model:{model_source}")
    if firmware:
        evidence.append(f"firmware:{firmware_source}")

    return {
        "model": model,
        "model_confidence": model_confidence,
        "model_status": model_status,
        "model_source": model_source,
        "firmware_version": firmware,
        "firmware_confidence": firmware_confidence,
        "firmware_status": firmware_status,
        "firmware_source": firmware_source,
        "fingerprint_evidence": "; ".join(evidence) if evidence else "no_model_or_firmware_evidence",
    }
