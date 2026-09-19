"""
osrm_utils.py
-------------
OSRM (Open Source Routing Machine) public demo servisi uzerinden gercek
araba yolu mesafesi (km) ve tahmini surus suresi (dakika) hesaplar.

Public demo sunucusu (router.project-osrm.org) rate-limit uygulayabilir;
bu yuzden retry + exponential backoff eklenmistir. Yogun kullanimda
kendi OSRM sunucunuzu (Docker) kurup OSRM_BASE_URL'i degistirmeniz onerilir.
"""

import time

import requests

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
HEADERS = {"User-Agent": "yedas-gsm-saha-takip-app/1.0"}


def get_driving_distance(lat1, lon1, lat2, lon2, retries=3, timeout=10):
    """Donus: (distance_km, duration_min, error_message)"""
    url = f"{OSRM_BASE_URL}/{lon1},{lat1};{lon2},{lat2}"
    params = {"overview": "false", "alternatives": "false", "steps": "false"}

    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                distance_km = round(route["distance"] / 1000, 2)
                duration_min = round(route["duration"] / 60, 1)
                return distance_km, duration_min, None
            return None, None, data.get("message", "OSRM rota bulunamadi")
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
    return None, None, last_error or "Bilinmeyen OSRM hatasi"
