"""Ekran 3: Sahalar & İlçe Merkezleri (Mesafe & Rota)."""

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from geopy.distance import geodesic

from database import (
    init_db, get_all_sites_df, get_all_centers_df,
    get_cached_distance, upsert_distance,
)
from image_export import generate_table_jpg
from osrm_utils import get_driving_distance
from utils import KAPSAM_ILLER

st.set_page_config(page_title="Sahalar ve İlçe Merkezleri", page_icon="🗺️", layout="wide")
init_db()

st.title("🗺️ Sahalar & İlçe Merkezleri (Mesafe & Rota)")
st.caption(f"Kapsam: {', '.join(KAPSAM_ILLER)}")

sites_df = get_all_sites_df()
centers_df = get_all_centers_df()

sites_df = sites_df[sites_df["il"].isin(KAPSAM_ILLER)] if not sites_df.empty else sites_df

if sites_df.empty:
    st.warning(f"Kapsam dahilindeki illerde ({', '.join(KAPSAM_ILLER)}) saha bulunamadı.")
    st.stop()
if centers_df.empty:
    st.warning("Henüz ilçe merkezi tanımlanmamış. 🔐 Admin Paneli'nden ekleyin.")
    st.stop()


def nearest_center(site_row):
    if site_row.get("assigned_center_id") and site_row.get("center_is_manual"):
        c = centers_df[centers_df["id"] == site_row["assigned_center_id"]]
        if not c.empty:
            return c.iloc[0]
    best, best_dist = None, None
    for _, c in centers_df.iterrows():
        d = geodesic((site_row["latitude"], site_row["longitude"]), (c["latitude"], c["longitude"])).km
        if best_dist is None or d < best_dist:
            best, best_dist = c, d
    return best


rows = []
with st.spinner("Mesafeler hesaplanıyor (ilk çalıştırmada zaman alabilir, sonrası SQLite'tan gelir)..."):
    for _, site in sites_df.iterrows():
        center = nearest_center(site)
        if center is None:
            continue
        cached = get_cached_distance(int(site["id"]), int(center["id"]))
        if cached:
            dist_km, dur_min = cached["distance_km"], cached["duration_min"]
        else:
            dist_km, dur_min, err = get_driving_distance(
                site["latitude"], site["longitude"], center["latitude"], center["longitude"],
            )
            if dist_km is not None:
                upsert_distance(int(site["id"]), int(center["id"]), dist_km, dur_min)
        rows.append({
            "Saha Adı": site["placemark_adi"], "İl": site["il"], "İlçe": site["ilce"],
            "Merkez": center["isim"], "Mesafe (km)": dist_km, "Süre (dk)": dur_min,
            "site_lat": site["latitude"], "site_lon": site["longitude"],
        })

result_df = pd.DataFrame(rows)

if result_df.empty:
    st.info("Gösterilecek saha/merkez eşleşmesi bulunamadı.")
    st.stop()

# --- Filtreler ----------------------------------------------------------------
colf1, colf2, colf3 = st.columns(3)
with colf1:
    il_secim = st.multiselect("İl Filtresi", sorted(result_df["İl"].dropna().unique()))
with colf2:
    ilce_secim = st.multiselect("İlçe Filtresi", sorted(result_df["İlçe"].dropna().unique()))
with colf3:
    arama = st.text_input("Saha Ara")

filtered = result_df.copy()
if il_secim:
    filtered = filtered[filtered["İl"].isin(il_secim)]
if ilce_secim:
    filtered = filtered[filtered["İlçe"].isin(ilce_secim)]
if arama:
    filtered = filtered[filtered["Saha Adı"].str.contains(arama, case=False, na=False)]

# --- Harita --------------------------------------------------------------------
fig = go.Figure()
fig.add_trace(go.Scattermapbox(
    lat=filtered["site_lat"], lon=filtered["site_lon"], mode="markers",
    marker=dict(size=10, color="blue"), name="GSM Sahaları",
    text=[
        f"{r['Saha Adı']}<br>Merkez: {r['Merkez']}<br>Mesafe: {r['Mesafe (km)']} km<br>Süre: {r['Süre (dk)']} dk"
        for _, r in filtered.iterrows()
    ],
    hoverinfo="text",
))
fig.add_trace(go.Scattermapbox(
    lat=centers_df["latitude"], lon=centers_df["longitude"], mode="markers",
    marker=dict(size=14, color="red"), name="İlçe Merkezleri",
    text=centers_df["isim"], hoverinfo="text",
))
fig.update_layout(
    mapbox_style="open-street-map",
    mapbox=dict(center=dict(lat=41.2, lon=36.3), zoom=6.5),
    height=600, margin={"r": 0, "t": 0, "l": 0, "b": 0},
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# --- Tablo ----------------------------------------------------------------------
st.subheader("Saha Listesi")
st.dataframe(
    filtered[["Saha Adı", "İl", "İlçe", "Merkez", "Mesafe (km)", "Süre (dk)"]].sort_values("Saha Adı"),
    use_container_width=True,
)

colo1, colo2 = st.columns(2)
with colo1:
    xlsx_buf = io.BytesIO()
    filtered[["Saha Adı", "İl", "İlçe", "Merkez", "Mesafe (km)", "Süre (dk)"]].to_excel(
        xlsx_buf, index=False, engine="openpyxl",
    )
    xlsx_buf.seek(0)
    st.download_button(
        "📥 Excel İndir", data=xlsx_buf, file_name="sahalar_mesafe.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with colo2:
    if st.button("🖼️ JPG Rapor Oluştur"):
        jpg_buf = generate_table_jpg(
            filtered[["Saha Adı", "İl", "İlçe", "Merkez", "Mesafe (km)", "Süre (dk)"]].head(30),
            "Saha - Mesafe Raporu",
        )
        st.download_button("📥 JPG İndir", data=jpg_buf, file_name="sahalar_mesafe.jpg", mime="image/jpeg")
