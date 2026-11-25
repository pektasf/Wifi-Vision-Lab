# WiFi Vision Lab — Windows taşınabilir paket

1. ZIP'i çıkarın.
2. Windows'ta Python 3.10+ kurulu olmalı.
3. `START.bat` dosyasına çift tıklayın.
4. İlk çalıştırmada klasör içinde `.venv` oluşturulur ve eksik paketler kurulur. İlk paket kurulumu internet gerektirir.
5. Uygulama `http://localhost:8501` adresinde açılır.

Klasörün tamamını başka Windows bilgisayara kopyalayıp orada da `START.bat` çalıştırabilirsiniz. Her bilgisayar kendi aktif IPv4 ağını otomatik algılar ve kendi CSV verilerini kendi klasöründe tutar. EXE/Docker/bulut gerekmez. Güncellemelerde `.py` dosyalarını değiştirmek yeterlidir.

**Özellikler:** ping/ARP tabanlı yerel cihaz keşfi, envanter, geçmiş, sezgisel sınıflandırma, davranış ipuçları, basit topoloji, canlı ping takibi ve Windows Wi-Fi kalite/kanal/hız kaydı.

**Sınırlar:** Ping yanıtı cihazın açık olduğunu kesin kanıtlamaz. MAC/IP eşleşmeleri fiziksel cihaz kimliğini garanti etmez. Wi-Fi kalite yüzdesi dBm veya mesafe değildir. CSI tabanlı insan/konum algılama bu sürümde yoktur. Yalnızca sahibi olduğunuz veya tarama izniniz olan ağlarda kullanın. Uygulama verileri buluta göndermez; ilk bağımlılık kurulumu internet kullanır.
