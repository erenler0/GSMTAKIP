"""
yedas_api.py
------------
YEDAŞ canlı planlı kesinti API'sini çeker ve gerçek JSON şemasına göre ayrıştırır.
Şema: result -> data -> [ {address: [...], title: "...", details: "...", ...} ]
"""

import re
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
    """Dönüş: (normalized_records: list[dict], error: str|None)"""
    try:
        resp = requests.get(YEDAS_API_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        raw_json = resp.json()
    except Exception as e:
        return [], f"Bağlantı/İstek Hatası: {e}"

    try:
        # YEDAŞ Gerçek JSON Yapısı: result -> data
        result_obj = raw_json.get("result", {})
        if isinstance(result_obj, dict):
            items = result_obj.get("data", [])
        elif isinstance(result_obj, list):
            items = result_obj
        else:
            items = raw_json.get("data", [])

        normalized = [_normalize_record(item) for item in items if isinstance(item, dict)]
        return normalized, None
    except Exception as e:
        return [], f"Veri Ayrıştırma Hatası: {e}"


def _normalize_record(r):
    # 1. Başlık / Çalışma Nedeni
    aciklama = r.get("title", "Planlı Kesinti")

    # 2. Tarih ve Zaman Bilgisi (details metni içerisinden çekilir)
    details_text = r.get("details", "")
    baslangic, bitis = _parse_dates_from_details(details_text)

    # 3. Adres Metni & İl / İlçe / Mahalle Çıkarımı
    address_list = r.get("address", [])
    adres_parcalari = []
    il, ilce, mahalle = None, None, None

    if isinstance(address_list, list):
        for addr in address_list:
            if isinstance(addr, dict):
                # Olası alan isimleri
                il = il or addr.get("city_name") or addr.get("city") or addr.get("il")
                ilce = ilce or addr.get("district_name") or addr.get("district") or addr.get("ilce")
                mahalle = mahalle or addr.get("mahalle_name") or addr.get("mahalle") or addr.get("name")
                
                # Obje içerisindeki metinsel değerleri adres metnine ekle
                for key, val in addr.items():
                    if isinstance(val, str) and not val.isdigit() and len(val) > 1:
                        adres_parcalari.append(val)
            elif isinstance(addr, str):
                adres_parcalari.append(addr)
    elif isinstance(address_list, str):
        adres_parcalari.append(address_list)

    # Adres metnini birleştir
    adres_metni = " ".join(adres_parcalari).strip()
    if not adres_metni:
        adres_metni = f"{il or ''} {ilce or ''} {mahalle or ''} {aciklama}".strip()

    return {
        "il": il,
        "ilce": ilce,
        "mahalle": mahalle,
        "baslangic": baslangic,
        "bitis": bitis,
        "aciklama": aciklama,
        "adres_metni": adres_metni,
        "raw": r,
    }


def _parse_dates_from_details(text):
    """details string'i içerisindeki Başlangıç ve Bitiş zamanlarını yakalar."""
    if not text:
        return None, None
    
    # Regex ile tarih formatlarını yakala (Örn: 30.09.2026 09:00:00)
    dates = re.findall(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}", str(text))
    baslangic = dates[0] if len(dates) >= 1 else None
    bitis = dates[1] if len(dates) >= 2 else None
    
    return baslangic, bitis
