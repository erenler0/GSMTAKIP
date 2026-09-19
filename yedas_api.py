"""
yedas_api.py
------------
YEDAS canli planli kesinti API'sini ceker ve st.cache_data(ttl=300) ile
5 dakikada bir arka planda gunceller.

ONEMLI NOT: YEDAS bu endpoint icin resmi/genel bir API dokumantasyonu
yayinlamamaktadir. Bu yuzden donen JSON'un olasi birkac farkli sema
varyasyonunu (liste, {"data": [...]}atasi, GeoJSON {"features": [...]}
seklinde vb.) deneyerek normallestiren esnek bir parser yazilmistir.
Gercek canli yanit farkli alan isimleri iceriyorsa, sadece asagidaki
`_normalize_record` fonksiyonundaki `g(...)` cagrilarina gercek alan
adini eklemeniz yeterlidir - uygulamanin geri kalani degismez.
"""

import requests
import streamlit as st

YEDAS_API_URL = "https://www.yedas.com/api/planli-kesinti-harita"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 yedas-gsm-takip/1.0",
    "Accept": "application/json, text/plain, */*",
}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yedas_outages():
    """Donus: (normalized_records: list[dict], error: str|None)
    Her kayit: {il, ilce, mahalle, baslangic, bitis, aciklama, adres_metni, raw}"""
    try:
        resp = requests.get(YEDAS_API_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [], f"Baglanti/istek hatasi: {e}"

    try:
        raw_records = _extract_records(data)
        normalized = [_normalize_record(r) for r in raw_records]
        return normalized, None
    except Exception as e:
        return [], f"Veri ayristirma hatasi: {e}"


def _extract_records(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "result", "results", "kesintiler", "items", "features", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _normalize_record(r):
    # GeoJSON tarzi kayitlarda gercek alanlar "properties" altinda olabilir
    props = r.get("properties", r) if isinstance(r, dict) else {}

    def g(*keys):
        for k in keys:
            v = props.get(k)
            if v:
                return v
        return None

    il = g("il", "İl", "province", "IL", "sehir")
    ilce = g("ilce", "İlçe", "district", "ILCE", "ilceAdi")
    mahalle = g("mahalle", "Mahalle", "mevki", "Mevki", "neighbourhood", "mahalleAdi")
    baslangic = g("baslangic", "baslangicTarihi", "start", "startDate", "kesintiBaslangic", "baslangicSaati")
    bitis = g("bitis", "bitisTarihi", "end", "endDate", "kesintiBitis", "bitisSaati")
    aciklama = g("aciklama", "isAciklamasi", "description", "not", "sebep", "aciklamaMetni")

    adres_parcalari = [str(x) for x in (il, ilce, mahalle) if x]
    adres_metni = " ".join(adres_parcalari)
    if aciklama:
        adres_metni = f"{adres_metni} {aciklama}".strip()

    return {
        "il": il,
        "ilce": ilce,
        "mahalle": mahalle,
        "baslangic": baslangic,
        "bitis": bitis,
        "aciklama": aciklama,
        "adres_metni": adres_metni.strip(),
        "raw": r,
    }
