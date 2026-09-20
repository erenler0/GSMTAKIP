"""
database.py
------------
Tum SQLite erisim katmani burada toplanmistir. Uygulamanin herhangi bir
yerinde dogrudan sqlite3 baglantisi acilmaz; her sey bu modul uzerinden yapilir.

ONEMLI (Streamlit Community Cloud notu):
Streamlit Cloud'un dosya sistemi, uygulama yeniden baslatildiginda (redeploy,
uzun sureli inaktivite sonrasi container yeniden ayaga kalkmasi, vb.) sifirlanir.
Yani buradaki SQLite dosyasi calisan container omru boyunca "kalicidir" fakat
sinirsiz/sonsuz kalicilik saglamaz. Duzenli disariya Excel/JPG export almak
veya ileride harici bir veritabanina (Postgres, Turso vb.) gecmek onerilir.
Bu detay README.md icinde de belirtilmistir.
"""

import os
import sqlite3
from contextlib import contextmanager
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    """Tum tablolari olusturur (varsa dokunmaz). ASLA ornek/test verisi eklemez."""
    with db_cursor(commit=True) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kml_dosyasi TEXT,
                placemark_adi TEXT NOT NULL UNIQUE, 
                aciklama TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                altitude REAL,
                koordinat_ham TEXT,
                il TEXT,
                ilce TEXT,
                mahalle TEXT,
                assigned_center_id INTEGER,
                center_is_manual INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assigned_center_id) REFERENCES district_centers(id) ON DELETE SET NULL
            )
        """)
        # Eski tablolarda placemark_adi UNIQUE olmayabileceği için tabloyu güvene alıyoruz.
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_placemark_adi ON sites(placemark_adi)")
        except sqlite3.OperationalError:
            pass
            
        cur.execute("""
            CREATE TABLE IF NOT EXISTS district_centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isim TEXT NOT NULL,
                il TEXT,
                ilce TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS site_distances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                center_id INTEGER NOT NULL,
                distance_km REAL,
                duration_min REAL,
                calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (center_id) REFERENCES district_centers(id) ON DELETE CASCADE,
                UNIQUE(site_id, center_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS outages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER,
                site_name TEXT NOT NULL,
                mains_time TEXT NOT NULL,
                down_time TEXT NOT NULL,
                restore_time TEXT,
                backup_duration_min REAL,
                outage_duration_min REAL,
                comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS yedas_outage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER,
                site_name TEXT,
                il TEXT,
                ilce TEXT,
                mahalle TEXT,
                start_time TEXT,
                end_time TEXT,
                description TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(site_name, start_time, end_time)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time TEXT DEFAULT CURRENT_TIMESTAMP,
                added_sites TEXT,
                removed_sites TEXT,
                added_count INTEGER,
                removed_count INTEGER
            )
        """)


# ---------------------------------------------------------------- SITES ----

def get_all_sites_df():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM sites", conn)
    finally:
        conn.close()
    return df


def bulk_insert_new_sites(rows):
    """rows: dict listesi. Hata veren bos (NaN) degerler temizlendi, INSERT OR REPLACE eklendi."""
    if not rows:
        return
    with db_cursor(commit=True) as cur:
        for r in rows:
            lat = r.get("Latitude")
            lon = r.get("Longitude")
            
            # Pandas'tan gelen NaN veya bos verileri yakala (NOT NULL hatasini onler)
            if pd.isna(lat) or pd.isna(lon) or lat == "" or lon == "":
                continue

            cur.execute("""
                INSERT OR REPLACE INTO sites
                    (kml_dosyasi, placemark_adi, aciklama, latitude, longitude,
                     altitude, koordinat_ham, il, ilce, mahalle)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get("KML Dosyası"), r.get("Placemark Adı"), r.get("Açıklama"),
                float(lat), float(lon), r.get("Altitude"),
                r.get("Koordinat (Ham)"), r.get("il", "Bekliyor"), r.get("ilce", "Bekliyor"), r.get("mahalle", "Bekliyor"),
            ))

def delete_sites_by_names(names):
    if not names:
        return
    with db_cursor(commit=True) as cur:
        cur.executemany("DELETE FROM sites WHERE placemark_adi = ?", [(n,) for n in names])


def diff_sites_for_sync(existing_df, new_df):
    existing_names = set(existing_df["placemark_adi"]) if not existing_df.empty else set()
    new_names = set(new_df["Placemark Adı"])

    added_names = new_names - existing_names
    removed_names = existing_names - new_names
    unchanged_names = existing_names & new_names

    added = new_df[new_df["Placemark Adı"].isin(added_names)].to_dict("records")
    removed = [{"Placemark Adı": n} for n in removed_names]
    unchanged = [{"Placemark Adı": n} for n in unchanged_names]
    return added, removed, unchanged


def log_sync(added_names, removed_names):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO sync_log (added_sites, removed_sites, added_count, removed_count) VALUES (?, ?, ?, ?)",
            (",".join(added_names), ",".join(removed_names), len(added_names), len(removed_names)),
        )

# --- YENİ EKLENEN REVERSE GEOCODING YARDIMCI FONKSİYONLARI ---

def get_sites_without_address():
    """Adresi eksik veya 'Bekliyor' olan sahalari getirir."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT id, placemark_adi, latitude, longitude FROM sites WHERE il IS NULL OR il = 'Bekliyor'", 
            conn
        )
    finally:
        conn.close()
    return df

def update_site_address(site_id, il, ilce, mahalle):
    """Admin panelindeki batch (parcali) adres cozme islemi sirasinda tekil sahayi gunceller."""
    with db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE sites 
            SET il = ?, ilce = ?, mahalle = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (il, ilce, mahalle, site_id))


# ------------------------------------------------------- DISTRICT CENTERS --

def get_all_centers_df():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM district_centers", conn)
    finally:
        conn.close()
    return df

def add_center(isim, il, ilce, lat, lon):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO district_centers (isim, il, ilce, latitude, longitude) VALUES (?,?,?,?,?)",
            (isim, il, ilce, lat, lon),
        )

def delete_center(center_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM district_centers WHERE id = ?", (center_id,))

def assign_center_to_site(site_id, center_id, manual=False):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE sites SET assigned_center_id = ?, center_is_manual = ? WHERE id = ?",
            (center_id, 1 if manual else 0, site_id),
        )


# ------------------------------------------------------------- DISTANCES ---

def get_cached_distance(site_id, center_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM site_distances WHERE site_id = ? AND center_id = ?",
            (site_id, center_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def upsert_distance(site_id, center_id, distance_km, duration_min):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO site_distances (site_id, center_id, distance_km, duration_min)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(site_id, center_id) DO UPDATE SET
                distance_km = excluded.distance_km,
                duration_min = excluded.duration_min,
                calculated_at = CURRENT_TIMESTAMP
        """, (site_id, center_id, distance_km, duration_min))


# --------------------------------------------------------------- OUTAGES ---

def add_outage(site_id, site_name, mains_time, down_time, restore_time,
               backup_duration_min, outage_duration_min, comment):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO outages
                (site_id, site_name, mains_time, down_time, restore_time,
                 backup_duration_min, outage_duration_min, comment)
            VALUES (?,?,?,?,?,?,?,?)
        """, (site_id, site_name, mains_time, down_time, restore_time,
              backup_duration_min, outage_duration_min, comment))


def get_outages_df():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM outages ORDER BY mains_time DESC", conn)
    finally:
        conn.close()
    return df


def delete_outage(outage_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM outages WHERE id = ?", (outage_id,))


# ----------------------------------------------------- YEDAS OUTAGE HISTORY

def save_outage_history(records):
    if not records:
        return
    with db_cursor(commit=True) as cur:
        for r in records:
            cur.execute("""
                INSERT OR IGNORE INTO yedas_outage_history
                    (site_id, site_name, il, ilce, mahalle, start_time, end_time, description)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                r.get("site_id"), r.get("site_name"), r.get("il"), r.get("ilce"),
                r.get("mahalle"), r.get("start_time"), r.get("end_time"), r.get("description"),
            ))


def get_outage_history_df():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM yedas_outage_history ORDER BY start_time DESC", conn)
    finally:
        conn.close()
    return df
