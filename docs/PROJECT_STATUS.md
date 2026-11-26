# Proje durumu
Bu paket, önceki oturumdaki modüllerin temiz bir başlangıç sürümü olarak yeniden oluşturulmuştur; eski bilgisayardaki dosyaların birebir yedeği değildir.
Mevcut: dinamik IPv4 ağ algılama, ping/ARP envanteri, CSV geçmişi, sezgisel sınıflandırma, davranış ipuçları, topoloji, canlı ping, Windows Wi-Fi kalite kaydı.
Henüz yok: CSI yakalama, kalibre edilmiş iç mekân konumlandırma, insan/iskelet algılama, RF ısı haritası.


## Spatial Intelligence (FAZ 9)

Laptop-only Spatial Intelligence work has started.

- SI-0 capability audit module and Streamlit page are implemented.
- The audit reads Windows Wi-Fi driver/interface metadata and physical adapter details.
- The audit is read-only: it does not scan nearby networks, capture packets, alter adapter settings, or store SSID/BSSID.
- CSI, monitor mode, and Wi-Fi RTT/FTM remain unknown until verified against the actual laptop adapter and driver.
- Calibrated indoor positioning and passive presence/motion sensing are not implemented yet.

Roadmap: see SPATIAL_INTELLIGENCE.md.
