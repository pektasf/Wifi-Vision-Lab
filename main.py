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
from scripts.contracts import run_collector


def run_step(stage, start, finish, callback, optional=False):
    emit_progress(stage, start, "Başlatılıyor")
    value, result = run_collector(stage, callback, optional=optional)

    if result.status == "failed":
        error = result.errors[0]
        print(
            f"Collector failed: {stage} | {error.code} | {error.message}",
            flush=True,
        )
        emit_progress(stage, finish, "Uyarı: modül başarısız")
        if not optional:
            raise RuntimeError(f"Zorunlu modül başarısız: {stage}") from result.exception
        return None

    count = result.records_count
    summary = f"{count} kayıt" if count is not None else result.status
    print(
        f"Collector {result.status}: {stage} | {summary} | "
        f"{result.duration_ms} ms",
        flush=True,
    )
    emit_progress(
        stage,
        finish,
        "Kayıt bulunamadı" if result.status == "no_data" else "Tamamlandı",
    )
    return value


def main():
    net, devices = run_step(
        "Ağ keşfi", 0.02, 0.30, discover, optional=False
    )
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
