"""
matching.py
-----------
YEDAS API'sinden gelen serbest metin adres bilgisi ile veritabanindaki
sahalarin (reverse-geocoding ile bulunmus) il/ilce/mahalle bilgilerini
karsilastiran text-matching mantigi.

Poligon/harita alani bazli eslestirme KULLANILMAZ - talimat geregi sadece
string/metin karsilastirmasi yapilir.
"""

import re

_TR_MAP = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})

_SUFFIX_PATTERN = re.compile(r"\b(mahallesi|mahallesi|mahalle|mah|koyu|koy|beldesi|merkez)\b")


def normalize(text):
    """Turkce karakterleri sadelestirir, kucuk harfe cevirir, gereksiz
    ekleri (mahallesi, koyu, vb.) temizler, tekrarli bosluklari siler."""
    if text is None:
        return ""
    text = str(text).translate(_TR_MAP).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = _SUFFIX_PATTERN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def site_matches_outage(site_il, site_ilce, site_mahalle, outage_text):
    """Bir sahanin, verilen YEDAS kesinti metniyle eslesip eslesmedigini doner.
    Il ve ilce eslesmesi zorunludur (ikisi de bos degilse); mahalle bulunuyorsa
    ekstra dogrulama olarak kullanilir fakat zorunlu tutulmaz (Nominatim mahalle
    isimlendirmesi YEDAS'in kullandigi isimlendirmeyle her zaman birebir
    ortusmeyebilir)."""
    norm_outage = normalize(outage_text)
    if not norm_outage:
        return False

    il_n = normalize(site_il)
    ilce_n = normalize(site_ilce)

    if il_n and il_n not in norm_outage:
        return False
    if ilce_n and ilce_n not in norm_outage:
        return False
    # Il ve ilce her ikisi de bossa (geocoding basarisiz olduysa) eslestirme yapma
    if not il_n and not ilce_n:
        return False
    return True


def match_score(site_il, site_ilce, site_mahalle, outage_text):
    """Debug/analiz amacli: kac alanin eslesigini 0-3 arasinda skorlar."""
    norm_outage = normalize(outage_text)
    score = 0
    for value in (site_il, site_ilce, site_mahalle):
        v = normalize(value)
        if v and v in norm_outage:
            score += 1
    return score
