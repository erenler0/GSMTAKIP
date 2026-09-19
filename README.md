# YEDAŞ Planlı Kesinti - GSM Saha Takip Sistemi

Streamlit tabanlı, YEDAŞ planlı kesintileri ile ~1300 GSM baz istasyonunu
**text-matching** (poligon/harita alanı bazlı değil) yöntemiyle eşleştiren,
haritada gösteren, OSRM ile gerçek sürüş mesafesi hesaplayan, arıza kayıtlarını
özel mum/Gantt grafiği ile sunan ve admin yönetimi barındıran uygulama.

## Klasör Yapısı

```
yedas_gsm_app/
├── app.py                                  # Ekran 1: Ana Ekran (giriş noktası)
├── pages/
│   ├── 1_📊_Detay_ve_Analiz.py             # Ekran 2
│   ├── 2_🗺️_Sahalar_ve_Ilce_Merkezleri.py  # Ekran 3
│   ├── 3_🚨_Ariza_Takip.py                 # Ekran 4
│   └── 4_🔐_Admin_Paneli.py                # Ekran 5
├── database.py       # SQLite şema + tüm CRUD fonksiyonları
├── geocoding.py       # Geopy/Nominatim reverse geocoding
├── matching.py         # YEDAŞ metni <-> saha adresi text-matching
├── yedas_api.py         # YEDAŞ API çekme + 5 dk cache
├── osrm_utils.py         # OSRM sürüş mesafesi/süresi
├── image_export.py       # Pillow/Matplotlib ile JPG rapor üretimi
├── utils.py               # Sabitler + admin oturum yönetimi
├── requirements.txt
├── .streamlit/config.toml
└── .gitignore
```

## Kurulum (Yerel)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud Dağıtımı

1. Bu klasörü bir GitHub reposuna yükleyin (kök dizinde `app.py` olmalı).
2. [share.streamlit.io](https://share.streamlit.io) üzerinden repoyu bağlayın,
   ana dosya olarak `app.py`'yi seçin.
3. `requirements.txt` otomatik algılanır, ek bir yapılandırma gerekmez.
4. İlk açılışta veritabanı boştur — Admin Paneli'nden (`admin5555`) saha
   Excel'inizi yükleyerek sistemi başlatın.

## Admin Şifresi

```
admin5555
```

Oturum `st.session_state` üzerinden yönetilir; sayfa/sekme kapatılınca veya
tarayıcı oturumu bitince otomatik sıfırlanır.

## ÖNEMLİ KISITLAR VE DİKKAT EDİLMESİ GEREKENLER

### 1) YEDAŞ API şeması doğrulanmadı
`https://www.yedas.com/api/planli-kesinti-harita` uç noktası için resmi/genel
bir JSON şeması yayınlanmamıştır. `yedas_api.py` içindeki `_normalize_record`
fonksiyonu, olası birkaç farklı alan adını (`il`/`İl`/`province` vb.) otomatik
dener; ancak canlı yanıtın gerçek alan adları farklıysa **tek yapmanız gereken
bu fonksiyondaki `g(...)` çağrılarına gerçek alan adını eklemektir** — uygulamanın
geri kalanı değişmeden çalışır. Sorun yaşarsanız Ana Ekran'da "Teknik Detay"
alanına bakıp API'nin ham yanıtını (`raw` alanı) inceleyebilirsiniz.

### 2) SQLite kalıcılığı (Streamlit Community Cloud)
Streamlit Community Cloud'un dosya sistemi, uygulama yeniden başlatıldığında
(redeploy, uzun süreli inaktivite sonrası container yeniden ayağa kalkması vb.)
**sıfırlanır**. `database.db` dosyası çalışan container ömrü boyunca kalıcıdır
ancak sınırsız kalıcılık garanti etmez. Öneriler:
- Düzenli olarak Admin Paneli / Detay Analiz ekranlarından Excel yedeği alın.
- Kritik/uzun vadeli veri için ileride harici bir veritabanına (Postgres,
  Turso, Supabase vb.) geçiş yapılması önerilir — `database.py` bu geçişi
  kolaylaştıracak şekilde tüm SQL erişimini tek dosyada toplar.

### 3) OSRM public demo sunucusu
`router.project-osrm.org` genel demo sunucusudur, yoğun/çok sayıda istek
altında rate-limit uygulayabilir. `osrm_utils.py` retry + backoff içerir ve
hesaplanan mesafeler `site_distances` tablosunda kalıcı olarak önbelleğe
alınır, böylece her sayfa yüklemesinde tekrar hesaplanmaz. Üretimde yoğun
kullanım bekleniyorsa kendi OSRM sunucunuzu (Docker) kurup `OSRM_BASE_URL`
değişkenini güncelleyin.

### 4) Nominatim (Geopy) kullanım kısıtları
Nominatim politikası gereği saniyede en fazla ~1 istek önerilir. `geocoding.py`
`RateLimiter` ile bunu otomatik uygular (yaklaşık 1.1 sn/istek). ~1300 sahalık
ilk yükleme bu nedenle birkaç dakika sürebilir; ilerleme çubuğu gösterilir.
Bu işlem sadece **yeni eklenen** sahalar için, **bir kez** çalışır.

### 5) "Mum Grafik" uygulaması
Gerçek finansal candlestick (OHLC) grafiği açık/yüksek/düşük/kapanış
gerektirir ve bir zaman aralığını (başlangıç-bitiş) görselleştirmeye uygun
değildir. Bunun yerine, istenen görsel sonucu (X ekseninde tarih, Y ekseninde
00:00-24:00 saat aralığında renkli çubuklar) birebir sağlayan bir
**"floating bar" (yüzen çubuk) grafiği** kullanılmıştır — Ekran 2'de tek renk,
Ekran 4'te istenen yeşil/kırmızı renklendirmeyle.

## Dummy/Test Verisi

Bu projede **hiçbir** test/örnek veri eklenmemiştir. `init_db()` yalnızca boş
tabloları oluşturur; tüm veriler yalnızca Admin Paneli üzerinden yüklenen
gerçek Excel dosyasından ve kullanıcı girişlerinden gelir.
