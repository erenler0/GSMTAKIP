"""
yedas_api.py
------------
YEDAŞ API yanıtındaki ID tabanlı adres verilerini (id_city, id_district vb.)
ve metinsel detayları ayrıştırarak eşleştirme motoruna hazır hale getirir.
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

# YEDAŞ Sorumluluk Bölgesi İl Kodları
CITY_MAP = {
    "55": "SAMSUN",
    "52": "ORDU",
    "28": "GİRESUN",
    "57": "SİNOP",
    "60": "TOKAT"
}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yedas_outages():
    """Dönüş: (normalized_records: list[dict], error: str|None)"""
    try:
        resp = requests.get(YEDAS_API_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        raw_json = resp.json()
    except Exception as e:
        return [], f"Bağlantı Hatası: {e}"

    try:
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
    aciklama = r.get("title", "Planlı Kesinti")
    details_text = r.get("details", "")
    baslangic, bitis = _parse_dates_from_details(details_text)

    address_list = r.get("address", [])
    adres_parcalari = []
    il, ilce, mahalle = None, None, None

    if isinstance(address_list, list):
        for addr in address_list:
            if isinstance(addr, dict):
                # İl ID'sinden İl İsmini Yakala (Örn: 55 -> SAMSUN)
                city_id = str(addr.get("id_city", ""))
                if city_id in CITY_MAP:
                    il = CITY_MAP[city_id]
                    adres_parcalari.append(il)

                # Metinsel il/ilçe/mahalle/sokak alanları varsa ekle
                for key in ("district_name", "ilce", "district", "mahalle_name", "mahalle", "street_name", "name", "text"):
                    val = addr.get(key)
                    if val and isinstance(val, str) and not val.isdigit():
                        adres_parcalari.append(val)
                        if not ilce and "district" in key:
                            ilce = val
                        if not mahalle and "mahalle" in key:
                            mahalle = val

    # Eğer ilçe adı ID olarak geldiyse veya adresten okunamadıysa varsayılan metinden ayıkla
    adres_metni = " ".join(dict.fromkeys(adres_parcalari)).strip()
    
    # Adres metni boş kaldıysa başlık ve detay bilgisini ekle
    if not adres_metni or len(adres_metni) < 5:
        adres_metni = f"{il or ''} {ilce or ''} {mahalle or ''} {aciklama} {details_text}".strip()

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
    if not text:
        return None, None
    dates = re.findall(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}", str(text))
    baslangic = dates[0] if len(dates) >= 1 else None
    bitis = dates[1] if len(dates) >= 2 else None
    return baslangic, bitis
