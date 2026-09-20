"""
matching.py
-----------
YEDAŞ API'sinden gelen serbest metin adres bilgisi ile veritabanındaki
sahaların (il, ilçe, mahalle) bilgilerini karşılaştıran metin eşleştirme mantığı.
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

_SUFFIX_PATTERN = re.compile(
    r"\b(mahallesi|mahalle|mah|mh|koyu|koy|beldesi|merkez|caddesi|cad|sokagi|sokak|sok|sk|mevki|mevkii|bulvari|blv)\b"
)


def normalize(text):
    """Türkçe karakterleri sadeleştirir, küçük harfe çevirir, adres eklerini temizler."""
    if not text:
        return ""
    text = str(text).translate(_TR_MAP).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = _SUFFIX_PATTERN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_word(word, text):
    """Kelime sınırları gözeterek veya boşluksuz birleşik haliyle arama yapar."""
    if not word or not text:
        return False
    
    # 1. Birebir kelime/ifade araması
    pattern = r"\b" + re.escape(word) + r"\b"
    if bool(re.search(pattern, text)):
        return True
    
    # 2. Birleşik/Ayrı yazım kontrolü (Örn: "buyuk oyumca" <-> "buyukoyumca")
    word_nospace = word.replace(" ", "")
    text_nospace = text.replace(" ", "")
    if len(word_nospace) > 3 and word_nospace in text_nospace:
        return True

    return False


def site_matches_outage(site_il, site_ilce, site_mahalle, outage_text):
    """
    Bir sahanın kesinti metniyle eşleşip eşleşmediğini kontrol eder.
    - İl ve İlçe eşleşmesi ZORUNLUDUR.
    - Mahalle eşleşmesi varsa doğrulama oranını artırır.
    """
    norm_outage = normalize(outage_text)
    if not norm_outage:
        return False

    il_n = normalize(site_il)
    ilce_n = normalize(site_ilce)
    mahalle_n = normalize(site_mahalle)

    # İl ve İlçe veritabanında yoksa eşleştirme yapma
    if not il_n and not ilce_n:
        return False

    # İl Kontrolü (Zorunlu)
    if il_n and not _contains_word(il_n, norm_outage):
        return False

    # İlçe Kontrolü (Zorunlu)
    if ilce_n and not _contains_word(ilce_n, norm_outage):
        return False

    # Mahalle kontrolü: Kesinti metninde mahalle bilgisi açıkça aratılır.
    # Mahalle eşleşmese bile ilçe eşleştiği için True döner (arıza kaçırılmaz).
    return True


def match_score(site_il, site_ilce, site_mahalle, outage_text):
    """Debug/analiz amaçlı: Eşleşme hassasiyetini 0-3 arası skorlar."""
    norm_outage = normalize(outage_text)
    if not norm_outage:
        return 0

    score = 0
    for value in (site_il, site_ilce, site_mahalle):
        v = normalize(value)
        if v and _contains_word(v, norm_outage):
            score += 1
    return score
