"""
geocoding.py
------------
Saha koordinatlarindan (Lat/Lon) Il/Ilce/Mahalle bilgisini cikarmak icin
Nominatim (OpenStreetMap) Reverse Geocoding kullanir.

Nominatim kullanim politikasi geregi saniyede en fazla 1 istek onerilir,
bu yuzden RateLimiter ile min_delay_seconds=1.1 uygulanmistir. User-Agent
zorunludur, aksi halde Nominatim istekleri reddedebilir.
"""

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

USER_AGENT = "yedas-gsm-saha-takip-app/1.0 (streamlit-cloud-deployment)"

_geolocator = Nominatim(user_agent=USER_AGENT, timeout=10)
_reverse = RateLimiter(
    _geolocator.reverse,
    min_delay_seconds=1.1,
    max_retries=3,
    error_wait_seconds=5.0,
    swallow_exceptions=True,
)


def _first_present(addr: dict, keys):
    for k in keys:
        if k in addr and addr[k]:
            return addr[k]
    return None


def reverse_geocode(lat, lon):
    """Verilen koordinat icin (il, ilce, mahalle) tuple'i doner.
    Herhangi bir alan bulunamazsa None olarak kalir; hata durumunda da
    (None, None, None) doner - uygulama akisini kesmez."""
    if lat is None or lon is None:
        return None, None, None
    try:
        location = _reverse((lat, lon), language="tr", addressdetails=True, zoom=18)
    except Exception:
        location = None

    if not location or not getattr(location, "raw", None) or "address" not in location.raw:
        return None, None, None

    addr = location.raw["address"]
    il = _first_present(addr, ["province", "state"])
    ilce = _first_present(addr, ["county", "town", "district", "municipality", "city_district"])
    mahalle = _first_present(addr, ["suburb", "neighbourhood", "quarter", "village", "hamlet"])
    return il, ilce, mahalle


def batch_reverse_geocode(rows, progress_callback=None):
    """rows: 'Latitude'/'Longitude' anahtarlarina sahip dict listesi.
    progress_callback(fraction: float) -> None, ilerleme cubugu icin kullanilabilir."""
    results = []
    total = len(rows) or 1
    for i, row in enumerate(rows):
        il, ilce, mahalle = reverse_geocode(row.get("Latitude"), row.get("Longitude"))
        results.append({"il": il, "ilce": ilce, "mahalle": mahalle})
        if progress_callback:
            progress_callback((i + 1) / total)
    return results
