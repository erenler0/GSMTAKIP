# geocoding.py
import pandas as pd
from geopy.geocoders import ArcGIS
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# ArcGIS, Nominatim'e göre çok daha hızlıdır ve 1 saniye kısıtlaması yoktur.
geolocator = ArcGIS(timeout=10)

def reverse_geocode(lat, lon):
    if pd.isna(lat) or pd.isna(lon):
        return "", "", ""
    
    try:
        # Koordinatları ArcGIS'e gönderiyoruz
        location = geolocator.reverse(f"{lat}, {lon}")
        
        if location and location.raw:
            address = location.raw.get('address', {})
            
            # ArcGIS Türkiye verisinde genel yapı şöyledir:
            il = address.get('Region', '')
            ilce = address.get('City', '') 
            mahalle = address.get('Neighborhood', '')
            
            return il, ilce, mahalle
            
    except (GeocoderTimedOut, GeocoderServiceError):
        # API yanıt vermezse boş dönsün, kod çökmesin
        return "", "", ""
        
    return "", "", ""
