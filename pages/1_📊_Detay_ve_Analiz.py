"""Ekran 2: Detay ve Analiz Ekranı."""

import io
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import init_db, get_outage_history_df
from image_export import generate_table_jpg

st.set_page_config(page_title="Detay ve Analiz", page_icon="📊", layout="wide")
init_db()

st.title("📊 Detay ve Analiz Ekranı")

history_df = get_outage_history_df()

if history_df.empty:
    st.info(
        "Henüz kayıtlı YEDAŞ kesinti geçmişi bulunmuyor. Ana Ekran açıldıkça "
        "eşleşen kesinti kayıtları otomatik olarak burada birikmeye başlayacaktır."
    )
    st.stop()

history_df["start_time_dt"] = pd.to_datetime(history_df["start_time"], errors="coerce", dayfirst=True)
history_df["end_time_dt"] = pd.to_datetime(history_df["end_time"], errors="coerce", dayfirst=True)

# --- Hizli ozet KPI'lar ------------------------------------------------------
st.subheader("Hızlı Özet")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Top 5 Saha**")
    st.dataframe(
        history_df["site_name"].value_counts().head(5)
        .rename_axis("Saha").reset_index(name="Kesinti Sayısı"),
        use_container_width=True,
    )
with c2:
    st.markdown("**Top 5 İl**")
    st.dataframe(
        history_df["il"].value_counts().head(5)
        .rename_axis("İl").reset_index(name="Kesinti Sayısı"),
        use_container_width=True,
    )
with c3:
    st.markdown("**Top 5 İlçe**")
    st.dataframe(
        history_df["ilce"].value_counts().head(5)
        .rename_axis("İlçe").reset_index(name="Kesinti Sayısı"),
        use_container_width=True,
    )

st.divider()

# --- Arama ve zaman filtresi --------------------------------------------------
st.subheader("Arama ve Zaman Filtresi")
colf1, colf2, colf3 = st.columns(3)
with colf1:
    site_options = ["(Tümü)"] + sorted(history_df["site_name"].dropna().unique().tolist())
    selected_site = st.selectbox("Saha / İl / İlçe Ara", site_options)
with colf2:
    default_start = (history_df["start_time_dt"].min() or (datetime.now() - timedelta(days=30))).date()
    start_date = st.date_input("Başlangıç Tarihi", value=default_start)
with colf3:
    default_end = (history_df["start_time_dt"].max() or datetime.now()).date()
    end_date = st.date_input("Bitiş Tarihi", value=default_end)

filtered = history_df[
    history_df["start_time_dt"].dt.date.between(start_date, end_date, inclusive="both")
    | history_df["start_time_dt"].isna()
]
if selected_site != "(Tümü)":
    filtered = filtered[
        (filtered["site_name"] == selected_site)
        | (filtered["il"] == selected_site)
        | (filtered["ilce"] == selected_site)
    ]

st.dataframe(
    filtered[["site_name", "il", "ilce", "mahalle", "start_time", "end_time", "description"]],
    use_container_width=True,
)

# --- Mum grafik (timeline) ----------------------------------------------------
st.subheader("Mum Grafik (Timeline)")
if selected_site != "(Tümü)" and not filtered.empty:
    fig = go.Figure()
    for _, row in filtered.iterrows():
        if pd.isna(row["start_time_dt"]) or pd.isna(row["end_time_dt"]):
            continue
        day = row["start_time_dt"].normalize()
        start_hour = row["start_time_dt"].hour + row["start_time_dt"].minute / 60
        end_hour = row["end_time_dt"].hour + row["end_time_dt"].minute / 60
        if row["end_time_dt"].date() != row["start_time_dt"].date():
            end_hour = 24
        duration = max(end_hour - start_hour, 0.15)
        fig.add_trace(go.Bar(
            x=[day], y=[duration], base=[start_hour],
            marker_color="#e68a00", width=0.4 * 86400000,
            hovertext=f"{row['start_time']} - {row['end_time']}<br>{row['description'] or ''}",
            hoverinfo="text", showlegend=False,
        ))
    fig.update_layout(
        yaxis=dict(title="Saat (0-24)", range=[0, 24]),
        xaxis=dict(title="Tarih"),
        height=500, barmode="overlay",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("Mum grafiğini görmek için yukarıdan tek bir saha seçin.")

# --- Ciktilar ------------------------------------------------------------------
st.subheader("Çıktılar")
export_df = filtered.drop(columns=["start_time_dt", "end_time_dt"], errors="ignore")

colo1, colo2 = st.columns(2)
with colo1:
    xlsx_buf = io.BytesIO()
    export_df.to_excel(xlsx_buf, index=False, engine="openpyxl")
    xlsx_buf.seek(0)
    st.download_button(
        "📥 Excel İndir", data=xlsx_buf, file_name="detay_analiz.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with colo2:
    if st.button("🖼️ JPG Rapor Oluştur"):
        jpg_buf = generate_table_jpg(
            export_df[["site_name", "il", "ilce", "start_time", "end_time"]].head(25),
            title="Detay ve Analiz Raporu",
        )
        st.download_button("📥 JPG İndir", data=jpg_buf, file_name="detay_analiz.jpg", mime="image/jpeg")
