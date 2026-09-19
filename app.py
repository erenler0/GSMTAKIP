"""
app.py
------
Ekran 1: Ana Ekran (YEDAS Canli Kesintiler & Anlik Takip)
Bu dosya Streamlit multi-page uygulamasinin giris noktasidir; diger ekranlar
pages/ klasorunde otomatik olarak sidebar'a eklenir.
"""

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from dateutil import parser as dateparser

from database import init_db, get_all_sites_df, save_outage_history
from image_export import generate_info_card_jpg
from matching import site_matches_outage
from yedas_api import fetch_yedas_outages

st.set_page_config(page_title="YEDAŞ GSM Kesinti Takip", page_icon="📡", layout="wide")
init_db()

st.title("📡 YEDAŞ Planlı Kesinti - GSM Saha Takip Sistemi")


def parse_dt(value):
    if not value:
        return None
    try:
        return dateparser.parse(str(value), dayfirst=True, fuzzy=True)
    except Exception:
        return None


sites_df = get_all_sites_df()

if sites_df.empty:
    st.warning(
        "Veritabanında henüz saha verisi bulunmuyor. Lütfen 🔐 Admin Paneli'nden "
        "saha Excel dosyasını yükleyin."
    )
    st.stop()

with st.spinner("YEDAŞ canlı kesinti verisi alınıyor..."):
    outages, error = fetch_yedas_outages()

if error:
    st.error(f"YEDAŞ verisi alınamadı: {error}")
    st.caption(
        "Not: YEDAŞ API'sinin JSON alan isimleri değişmiş olabilir. "
        "`yedas_api.py` içindeki alan eşleştirmelerini kontrol edin."
    )
    st.stop()

if not outages:
    st.info("Şu anda YEDAŞ tarafında planlı kesinti verisi bulunamadı.")
    st.stop()

# --- Filtre butonlari -------------------------------------------------------
if "date_filter" not in st.session_state:
    st.session_state.date_filter = 1

col1, col2, col3, _ = st.columns([1, 1, 1, 3])
with col1:
    if st.button("Günlük", use_container_width=True):
        st.session_state.date_filter = 1
with col2:
    if st.button("3 Günlük", use_container_width=True):
        st.session_state.date_filter = 3
with col3:
    if st.button("7 Günlük", use_container_width=True):
        st.session_state.date_filter = 7

gun = st.session_state.date_filter
st.caption(f"Görünüm: Önümüzdeki {gun} gün içindeki planlı kesintiler")

now = datetime.now()
horizon = now + timedelta(days=gun)

# --- Eslestirme --------------------------------------------------------------
affected_rows = []
history_records = []

for outage in outages:
    start_dt = parse_dt(outage.get("baslangic"))
    end_dt = parse_dt(outage.get("bitis"))

    if start_dt and start_dt > horizon:
        continue
    if end_dt and end_dt < now - timedelta(days=1):
        continue

    mask = sites_df.apply(
        lambda row: site_matches_outage(row["il"], row["ilce"], row["mahalle"], outage["adres_metni"]),
        axis=1,
    )
    matched_sites = sites_df[mask]

    for _, site in matched_sites.iterrows():
        affected_rows.append({
            "site_id": int(site["id"]),
            "Saha Adı": site["placemark_adi"],
            "İl": site["il"], "İlçe": site["ilce"], "Mahalle": site["mahalle"],
            "Latitude": site["latitude"], "Longitude": site["longitude"],
            "Başlangıç": outage.get("baslangic"), "Bitiş": outage.get("bitis"),
            "İş Açıklaması": outage.get("aciklama"),
        })
        history_records.append({
            "site_id": int(site["id"]), "site_name": site["placemark_adi"],
            "il": site["il"], "ilce": site["ilce"], "mahalle": site["mahalle"],
            "start_time": outage.get("baslangic"), "end_time": outage.get("bitis"),
            "description": outage.get("aciklama"),
        })

save_outage_history(history_records)

affected_df = pd.DataFrame(affected_rows)

if affected_df.empty:
    st.success("Seçili zaman aralığında etkilenen saha bulunamadı.")
    st.stop()

st.metric("Etkilenen Saha Sayısı", len(affected_df))

fig = px.scatter_mapbox(
    affected_df, lat="Latitude", lon="Longitude", hover_name="Saha Adı",
    hover_data=["İl", "İlçe", "Başlangıç", "Bitiş"],
    zoom=6, height=550,
)
fig.update_traces(marker=dict(size=12, color="blue"))
fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
st.plotly_chart(fig, use_container_width=True)

st.subheader("Etkilenen Sahalar - Detay Listesi")
for i, row in affected_df.iterrows():
    with st.expander(f"📍 {row['Saha Adı']} — {row['İl']} / {row['İlçe']}"):
        st.write(f"**Başlangıç:** {row['Başlangıç']}")
        st.write(f"**Bitiş:** {row['Bitiş']}")
        st.write(f"**İş Açıklaması:** {row['İş Açıklaması']}")
        buf = generate_info_card_jpg(
            title=row["Saha Adı"],
            subtitle=f"{row['İl']} / {row['İlçe']} / {row['Mahalle']}",
            fields={
                "Çalışma Başlangıç": row["Başlangıç"],
                "Çalışma Bitiş": row["Bitiş"],
                "İş Açıklaması": row["İş Açıklaması"],
            },
        )
        st.download_button(
            "🖼️ Görsel Olarak İndir (JPG)", data=buf,
            file_name=f"{row['Saha Adı']}_kesinti.jpg", mime="image/jpeg",
            key=f"dl_{i}",
        )
