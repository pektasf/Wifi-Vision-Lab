# WiFi Vision Lab

Windows icin yerel ag kesfi, cihaz envanteri, ag topolojisi ve Wi-Fi sinyal analizi.

## Kurulum ve baslatma

1. Python 3.10 veya daha yenisini kurun.
2. GitHub reposunu ZIP olarak indirin ve cikartin.
3. `START.bat` dosyasina cift tiklayin.
4. Ilk calistirmada izole `.venv` ortami olusturulur ve gerekli paketler kurulur.
5. Uygulama `http://127.0.0.1:8501` adresinde acilir.

Ilk kurulum veya `requirements.txt` degistiginde internet baglantisi gerekir.
Baslatici bagimlilik dosyasinin SHA-256 ozetini kontrol eder; dosya degismediyse
her acilista paketleri yeniden kurmaz. Streamlit kullanim istatistikleri
gonderimi kapali tutulur ve sunucu yalnizca bu bilgisayarin loopback adresinde
dinler.

## Yerel veri ve yedekleme

Tarama verileri `data/processed/` altinda SQLite ve CSV uyumluluk kopyalariyla
yerel olarak saklanir. Veritabani ve ag envanteri Git'e eklenmez.

SQLite yedegi olusturmak icin:

```powershell
python -m scripts.storage --backup-to .\backups\wifi-vision-backup.db
```

Geri yukleme mevcut bir veritabaninin uzerine yazmaz; yeni bir hedef yol verin.
Ayrintilar icin `docs/SQLITE_STORAGE.md` dosyasina bakin.

## Proje yapisi

- `app.py`: Streamlit arayuzu
- `main.py`: Tarama ve analiz orkestrasyonu
- `scripts/`: Kesif, analiz, depolama ve arka plan isleri
- `pages/`: Ek arayuz sayfalari
- `data/reference/`: OUI uretici verileri
- `data/processed/`: Yerel tarama verileri

Yalnizca yetkili oldugunuz aglarda kullanin. Gercek ag verilerini, veritabani
dosyalarini veya yedekleri GitHub'a yuklemeyin.
