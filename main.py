"""Command-line orchestration for a complete local Wi-Fi Vision scan."""
from scripts.discovery import run as discover
from scripts.device_intelligence import run as intelligence
from scripts.device_classifier import run as classify
from scripts.device_history import run as history
from scripts.behavior_analysis import run as behavior
from scripts.network_topology import run as topology
from scripts.network_monitor import run as monitor
from scripts.ap_client_intelligence import run as ap_client_run
from scripts.network_intelligence import run as infrastructure_run
from scripts.wifi_signal_intelligence import run as signal_run
from scripts.scan_events import emit_progress


def run_step(stage, start, finish, callback, optional=False):
    emit_progress(stage, start, "Başlatılıyor")
    try:
        result = callback()
    except Exception as exc:
        if not optional:
            emit_progress(stage, start, f"Hata: {type(exc).__name__}")
            raise
        print(f"{stage} modülü uyarısı: {exc}", flush=True)
        emit_progress(stage, finish, "Atlandı; uyarı kaydedildi")
        return None
    emit_progress(stage, finish, "Tamamlandı")
    return result


def main():
    emit_progress("Ağ keşfi", 0.02, "Yerel ağ ve cihazlar keşfediliyor")
    net, devices = discover()
    emit_progress("Ağ keşfi", 0.30, f"{len(devices)} cihaz gözlemlendi")

    steps = [
        ("Cihaz zekâsı", 0.34, 0.40, intelligence, False),
        ("Cihaz sınıflandırma", 0.42, 0.48, classify, False),
        ("Cihaz geçmişi", 0.50, 0.56, history, False),
        ("Davranış analizi", 0.58, 0.64, behavior, False),
        ("Ağ topolojisi", 0.66, 0.72, topology, False),
        ("Ağ izleme", 0.74, 0.80, monitor, False),
        ("AP-istemci analizi", 0.82, 0.86, ap_client_run, True),
        ("Ağ altyapısı analizi", 0.88, 0.93, infrastructure_run, True),
        ("Wi-Fi sinyal analizi", 0.95, 0.99, signal_run, True),
    ]
    for stage, start, finish, callback, optional in steps:
        run_step(stage, start, finish, callback, optional=optional)

    print(
        f"Scan complete: {len(devices)} observed devices on {net['network']}",
        flush=True,
    )
    emit_progress("Tamamlandı", 1.0, "Tarama ve analiz adımları tamamlandı")


if __name__ == "__main__":
    main()
