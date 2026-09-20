"""
yedas_api.py
------------
YEDAS canli planli kesinti API'sini ceker.
Geçici olarak hata ayıklama (debug) modundadır.
"""

import requests
import streamlit as st

YEDAS_API_URL = "https://www.yedas.com/api/planli-kesinti-harita"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 yedas-gsm-takip/1.0",
    "Accept": "application/json, text/plain, */*",
}


# Hata ayıklama süresince Streamlit'in eski hatalı veriyi hafızada tutmaması için
# st.cache_data satırını geçici olarak devre dışı bıraktık.
# @st.cache_data(ttl=300, show_spinner=False)
def fetch_yedas_outages():
    """Donus: (normalized_records: list[dict], error: str|None)"""
    try:
        resp = requests.get(YEDAS_API_URL, headers=HEADERS, timeout=20)
        
        # --- HATA AYIKLAMA (DEBUG) BLOĞU ---
        if resp.status_code != 200:
            hata_mesaji = f"🚨 SUNUCU HATASI: {resp.status_code}\n📄 Dönen Cevap Özeti: {resp.text[:400]}"
            return [], hata_mesaji
        
        data = resp.json()
        
    except requests.exceptions.RequestException as e:
        return [], f"🌐 İSTEK HATASI: {e}"
    except ValueError as e: 
        # İstek 200 döner ama JSON yerine HTML (Captcha/Cloudflare) dönerse yakalayacak
        hata_mesaji = f"🧩 JSON DÖNÜŞTÜRME HATASI (Muhtemel Bot Koruması): {e}\n📄 Dönen Metin: {resp.text[:400]}"
        return [], hata_mesaji
    except Exception as e:
        return [], f"⚠️ BEKLENMEYEN HATA: {e}"

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
