# Proje durumu
Bu paket, önceki oturumdaki modüllerin temiz bir başlangıç sürümü olarak yeniden oluşturulmuştur; eski bilgisayardaki dosyaların birebir yedeği değildir.
Mevcut: dinamik IPv4 ağ algılama, ping/ARP envanteri, CSV geçmişi, sezgisel sınıflandırma, davranış ipuçları, topoloji, canlı ping, Windows Wi-Fi kalite kaydı.
Henüz yok: CSI yakalama, kalibre edilmiş iç mekân konumlandırma, insan/iskelet algılama, RF ısı haritası.


## Spatial Intelligence (FAZ 9)

Laptop-only Spatial Intelligence work has started.

- SI-0 capability audit module and Streamlit page are implemented.
- SI-1 local Spatial Core is implemented: SQLite floor, zone, and anchor records with coordinate validation.
- SI-1 Streamlit floor-plan editor is implemented for manual floor, zone, and anchor placement.
- SI-2 manual RSSI fingerprint survey, experimental zone matching, and leave-one-out validation metrics are implemented locally (schema v4).
- Windows RSSI collection has an initial read-only Native WLAN API BSS-list backend; it does not call WlanScan and pseudonymises BSSIDs locally.
- Linux has an initial read-only `iw` cached-BSS RSSI collector; macOS native RSSI collection is not implemented. Core app features remain platform-independent where their dependencies permit.
- Passive human/object sensing remains unimplemented and hardware-gated.
- The audit reads Windows Wi-Fi driver/interface metadata and physical adapter details.
- The audit is read-only: it does not scan nearby networks, capture packets, alter adapter settings, or store SSID/BSSID.
- CSI, monitor mode, and Wi-Fi RTT/FTM remain unknown until verified against the actual laptop adapter and driver.
- Calibrated indoor positioning and passive presence/motion sensing are not implemented yet.
- The Windows BSS collector is driver-dependent; the UI distinguishes missing interfaces, empty BSS results, permission/service/driver errors, and partial results rather than fabricating measurements.
- Per-adapter diagnostics show each local Wi-Fi interface description, Windows state, BSS-list status, and error code; adapter descriptions are not persisted with measurements.
- Windows and Linux RSSI results now include measurement-age metadata when the driver exposes timestamps; the UI warns when timestamped records are older than 120 seconds.
- The capability audit can export a JSON compatibility report without SSID/BSSID or network names for troubleshooting different laptop models.
- The app is not tied to one laptop model. Windows devices are evaluated at runtime; actual RSSI availability varies by Wi-Fi chipset, driver, Windows WLAN service, and cached BSS data.
- Capability reporting distinguishes backend implementation from per-device results. Windows and Linux have driver/tool-dependent RSSI backends; macOS is explicitly marked not implemented.

Roadmap: see SPATIAL_INTELLIGENCE.md.
