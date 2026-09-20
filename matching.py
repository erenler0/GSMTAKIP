"""
matching.py
-----------
YEDAŞ API'sinden gelen serbest metin adres bilgisi ile veritabanındaki
sahaların (il, ilçe, mahalle) bilgilerini karşılaştıran metin eşleştirme mantığı.
"""

import re

# Türkçe karakter dönüştürme tablosu
_TR_MAP = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})

# Adreslerde gereksiz kalabalık yapan ve eşleşmeyi bozan ek/kelimeler
_SUFFIX_PATTERN = re.compile(
    r"\b(mahallesi|mahalle|mah|mh|koyu|koy|beldesi|merkez|caddesi|cad|sokagi|sokak|sok|sk|mevki|mevkii|bulvari|blv)\b"
)


def normalize(text):
    """Türkçe karakterleri sadeleştirir, küçük harfe çevirir, adres eklerini
    temizler ve kelimeler arasındaki fazla boşlukları siler."""
    if not text:
        return ""
    text = str(text).translate(_TR_MAP).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = _SUFFIX_PATTERN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_word(word, text):
    """Bir kelimenin metin içinde bağımsız bir kelime olarak geçip geçmediğini
    kelime sınırlarıyla (word boundary) kontrol eder."""
    if not word or not text:
        return False
    pattern = r"\b" + re.escape(word) + r"\b"
    return bool(re.search(pattern, text))


def site_matches_outage(site_il, site_ilce, site_mahalle, outage_text):
    """
    Bir sahanın kesinti metniyle eşleşip eşleşmediğini kontrol eder.
    1. İl ve İlçe eşleşmesi ZORUNLUDUR.
    2. Saha kartında mahalle bilgisi mevcutsa, kesinti metninde de bu mahallenin
       geçmesi gerekir (Tüm ilçeyi yanlış alarm yapmamak için).
    """
    norm_outage = normalize(outage_text)
    if not norm_outage:
        return False

    il_n = normalize(site_il)
    ilce_n = normalize(site_ilce)
    mahalle_n = normalize(site_mahalle)

    # İl ve İlçe veritabanında boşsa eşleştirme yapma
    if not il_n and not ilce_n:
        return False

    # İl Kontrolü
    if il_n and not _contains_word(il_n, norm_outage):
        return False

    # İlçe Kontrolü
    if ilce_n and not _contains_word(ilce_n, norm_outage):
        return False

    # Mahalle Kontrolü
    if mahalle_n and not _contains_word(mahalle_n, norm_outage):
        return False

    return True


def match_score(site_il, site_ilce, site_mahalle, outage_text):
    """Debug/analiz amaçlı: Kaç alanın eşleştiğini 0-3 arasında skorlar."""
    norm_outage = normalize(outage_text)
    if not norm_outage:
        return 0

    score = 0
    for value in (site_il, site_ilce, site_mahalle):
        v = normalize(value)
        if v and _contains_word(v, norm_outage):
            score += 1
    return score
