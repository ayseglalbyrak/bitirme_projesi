# Aktivite Simülatörü v3 — Sensör İzleme

## Kurulum

```bash
py -m pip install flask flask-cors flask-socketio
```

## Çalıştırma

```bash
# Eski DB varsa sil (şema değişti)
del simulasyon_v3.db   # Windows
rm simulasyon_v3.db    # Mac/Linux

py app.py
```

Tarayıcıda aç: http://localhost:5000

---

## Özellikler

### Biyometrik Sensörler
- Nabız (HR), SpO2, cilt sicakligi, HRV, stres skoru
- Aktiviteye gore gercekci degerler — Gaussian gurultu + ustel yumusatma
- Her kisi kartinda canli mini sensor grafigi (nabiz / SpO2 / stres secebilir)
- Biyometrik panel: tehlikeli degerlerde kirmizi, uyari icin sari, normal icin yesil

### Analiz & Grafik
- Gunluk saglik skoru 0-100 (uyku + aktif sure + stres + nabiz + SpO2 bilesimi)
- 7 gunluk trend oklari: adim / aktif sure / uyku / stres / nabiz icin yukari asagi
- Korelasyon analizi: "uyku az oldugunda ertesi gun stres yuksek" gibi iliskiler otomatik tespit
- En iyi / en kotu gun karsilastirmasi (saglik skoruna gore)
- Radar grafigi: uyku / aktif / stres / SpO2 / nabiz — 5 eksenli saglik profili
- Isi haritasi: saat x gun aktivite yogunlugu (24 saat x N gun)
- Nabiz min / ort / maks band grafigi
- Aktivite dagilimi yigin cubuk grafigi (aktif / dinlenme / yemek / uyku)

### Gunluk Profil & Tahmin
- Her gun icin tam profil: uyanis saati, uyku baslangici, ilk aktivite, adim, stres, nabiz, SpO2
- Gunler arasi delta karsilastirmasi: bir onceki gune gore yukari asagi renkli gosterim
- Anomali tespiti:
  - Uyanis saati giderek gecikiyor
  - Adim sayisi dusus trendi
  - Uyku duzensiziigi (uyanis saatleri arasindaki fark)
  - Stres surekli artiyor
  - Aktivite belirgin azaldi
- Gelecek 3 gun tahmini (hafta sonu duzeltmeli, guven seviyeli)

### WebSocket — Gercek Zamanli Veri
- Flask-SocketIO ile anlik push — polling yok
- Her sensor guncellemesi kart uzerinde aninda yansir
- Anomali tespit edilince aninda toast + bildirim merkezi
- Baglanti kesilince header'daki yesil nokta kirmiziya doner

### Harita
- Leaflet.js ile gercek haritada canli konum takibi (OpenStreetMap)
- Her kisi icin GPS koordinati (Istanbul bazli)
- Aktivite gecislerinde konum yumusak kayar

### Bildirim Merkezi
- Header'da can ikonu — okunmamis bildirim sayisi kirmizi badge
- Tum anomali ve akilli uyarilar arsivlenir, kaybetmez
- Sesli uyari: critical icin 880Hz, warning icin 550Hz

### Simulasyon Kontrolu
- 1x / 2x / 5x hiz butonu — header'da
- Uygulama ilk acilista son 14 gunluk gercekci fake data otomatik uretilir
- Her kisiye ozgu uyku / uyanis saati profili
- Yeni kisi eklendiginde de otomatik 14 gunluk gecmis uretilir
- Akilli uyarilar her ~1 saatte kontrol edilir

### Kisisel Ayarlar
- Kisi basina anomali esigi (nabiz ve stres icin ayri)
- Avatar rengi tiklatarak degistir
- Surukle-birak ile kart siralama

### Disa Aktarma
- PDF rapor: analiz + korelasyon + en iyi/kotu gun + gunluk tablo + akilli uyarilar
- Aktivite CSV: son 1000 aktivite kaydi
- Sensor CSV: son 2000 sensor olcumu
- Gunluk ozet CSV: son 30 gunun gunluk toplamlari

### Zaman Cizelgesi
- Gunluk aktiviteleri 24 saatlik renkli blok gorunumu
- Renk kodlamasi: mavi = aktif, yesil = dinlenme, sari = yemek, acik mavi = uyku
- Hover'da saat ve aktivite tipi tooltip

---

## Sekmeler

| Sekme | Icerik |
|---|---|
| Kisi Kartlari | Anlik durum, biyometrik panel, mini grafik, trend oklari |
| Canli Grafik | Kisi + metrik secip 60 olcumluk canli cizgi grafik |
| Harita | Gercek haritada tum kisilerin anlik konumu |
| Karsilastirma | Kisiler arasi tablo (adim, kalori, nabiz, SpO2, stres, HRV) |
| Anomaliler | Son 1 saatteki anomali listesi |
| Haftalik | 7 gunluk grafik + tablo + PDF indirme |
| Analiz | Saglik skoru, radar, uyku, nabiz, trend, korelasyon, isi haritasi |
| Akilli Uyarilar | Onleyici uyarilar (egzersiz yok, uyku borcu, stres trendi) |
| Zaman Cizelgesi | 24 saatlik aktivite blok gorunumu |

---

## API

| Endpoint | Method | Aciklama |
|---|---|---|
| /api/state | GET | Tum kisilerin anlik durumu |
| /api/persons | GET | Kisi listesi |
| /api/persons | POST | Yeni kisi ekle |
| /api/persons/:id | PATCH | Ayarlari guncelle |
| /api/persons/:id | DELETE | Kisiyi pasife al |
| /api/timeline/:id | GET | Son 7 gun aktivite gecmisi |
| /api/weekly/:id | GET | Haftalik ozet |
| /api/chart/:id | GET | Grafik verisi |
| /api/anomalies | GET | Son 50 anomali |
| /api/smart_alerts | GET | Akilli uyarilar |
| /api/compare | GET | Karsilastirma tablosu |
| /api/summary | GET | Ozet istatistikler + hava durumu |
| /api/analysis/:id | GET | Detayli analiz |
| /api/daily_profile/:id | GET | Gunluk profil + 3 gunluk tahmin |
| /api/sensors/:id | GET | Ham sensor logu |
| /api/location | GET | Tum kisilerin GPS koordinatlari |
| /api/trend/:id | GET | 7 gunluk trend verisi |
| /api/export/:id?type= | GET | CSV disa aktarma (activity/sensor/daily) |
| /api/sim_speed | GET/POST | Simulasyon hizi (1x/2x/5x) |
| /api/ai_analyze/:id | GET | AI saglik analizi (API key gerekli) |

---

## Veritabani Tablolari

| Tablo | Icerik |
|---|---|
| persons | Kisi bilgileri, anomali esikleri, avatar rengi |
| current_state | Her kisinin anlik durumu (aktivite, biyometrik, konum) |
| activity_log | Tamamlanan aktiviteler (baslangic/bitis saati, sure, adim, kalori) |
| sensor_log | Ham sensor olcumleri (her 15 saniyede bir) |
| anomalies | Tespit edilen anomaliler |
| smart_alerts | Akilli onleyici uyarilar |
| weather_log | Hava durumu gecmisi |