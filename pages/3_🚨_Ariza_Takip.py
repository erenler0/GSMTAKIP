"""Ekran 4: Arıza Takip & Şebeke/Kesinti Analizi."""

import io
from datetime import date, datetime, time as dtime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import init_db, get_all_sites_df, add_outage, get_outages_df
from image_export import generate_table_jpg

st.set_page_config(page_title="Arıza Takip", page_icon="🚨", layout="wide")
init_db()

st.title("🚨 Arıza Takip & Şebeke/Kesinti Analizi")

sites_df = get_all_sites_df()

with st.expander("➕ Yeni Arıza Kaydı Ekle", expanded=False):
    with st.form("outage_form"):
        col1, col2 = st.columns(2)
        with col1:
            if not sites_df.empty:
                site_name = st.selectbox("Saha Ara / Seç", sorted(sites_df["placemark_adi"].unique()))
            else:
                site_name = st.text_input("Saha Adı (veritabanında saha yok, manuel girin)")
            mains_date = st.date_input("Mains Tarihi (Elektrik Kesilme)", value=date.today())
            mains_time_v = st.time_input("Mains Saati", value=dtime(0, 0))
        with col2:
            down_date = st.date_input("Kesinti Tarihi (Saha Down Olma)", value=date.today())
            down_time_v = st.time_input("Kesinti Saati", value=dtime(0, 0))
            outage_duration = st.number_input("Kesinti Süresi (dakika)", min_value=0.0, step=1.0)
        comment = st.text_area("Yorum")
        submitted = st.form_submit_button("Kaydet")

    if submitted:
        if not site_name:
            st.error("Saha adı boş olamaz.")
        else:
            mains_dt = datetime.combine(mains_date, mains_time_v)
            down_dt = datetime.combine(down_date, down_time_v)
            backup_min = max((down_dt - mains_dt).total_seconds() / 60, 0)
            restore_dt = down_dt + timedelta(minutes=outage_duration)

            site_id = None
            if not sites_df.empty:
                match = sites_df[sites_df["placemark_adi"] == site_name]
                if not match.empty:
                    site_id = int(match.iloc[0]["id"])

            add_outage(
                site_id=site_id, site_name=site_name,
                mains_time=mains_dt.isoformat(), down_time=down_dt.isoformat(),
                restore_time=restore_dt.isoformat(),
                backup_duration_min=backup_min, outage_duration_min=outage_duration,
                comment=comment,
            )
            st.success("Arıza kaydı eklendi.")
            st.rerun()

outages_df = get_outages_df()

if outages_df.empty:
    st.info("Henüz arıza kaydı bulunmuyor. Yukarıdaki formdan yeni kayıt ekleyebilirsiniz.")
    st.stop()

outages_df["mains_dt"] = pd.to_datetime(outages_df["mains_time"])
outages_df["down_dt"] = pd.to_datetime(outages_df["down_time"])
outages_df["restore_dt"] = pd.to_datetime(outages_df["restore_time"])

colf1, colf2, colf3 = st.columns(3)
with colf1:
    site_filter = st.selectbox("Saha Filtrele", ["(Tümü)"] + sorted(outages_df["site_name"].unique()))
with colf2:
    start_d = st.date_input("Başlangıç", value=outages_df["mains_dt"].min().date(), key="af_start")
with colf3:
    end_d = st.date_input("Bitiş", value=outages_df["mains_dt"].max().date(), key="af_end")

filtered = outages_df[
    outages_df["mains_dt"].dt.date.between(start_d, end_d, inclusive="both")
]
if site_filter != "(Tümü)":
    filtered = filtered[filtered["site_name"] == site_filter]

st.subheader("Özel Mum / Gantt Grafiği")
st.caption("🟩 Yeşil: Mains kesilme → Saha down (akü/backup süresi)  |  🟥 Kırmızı: Saha down → Enerjilenme (kesinti süresi)")

fig = go.Figure()
for _, row in filtered.iterrows():
    if pd.isna(row["mains_dt"]) or pd.isna(row["down_dt"]) or pd.isna(row["restore_dt"]):
        continue
    day = row["mains_dt"].normalize()
    mains_h = row["mains_dt"].hour + row["mains_dt"].minute / 60
    down_h = row["down_dt"].hour + row["down_dt"].minute / 60
    restore_h = row["restore_dt"].hour + row["restore_dt"].minute / 60
    if row["down_dt"].date() != row["mains_dt"].date():
        down_h = 24
    if row["restore_dt"].date() != row["down_dt"].date():
        restore_h = 24

    fig.add_trace(go.Bar(
        x=[day], y=[max(down_h - mains_h, 0.08)], base=[mains_h],
        marker_color="#22a83b", width=0.35 * 86400000,
        hovertext=f"{row['site_name']}<br>Mains: {row['mains_time']}<br>Down: {row['down_time']}",
        hoverinfo="text", showlegend=False,
    ))
    fig.add_trace(go.Bar(
        x=[day], y=[max(restore_h - down_h, 0.08)], base=[down_h],
        marker_color="#d92727", width=0.35 * 86400000,
        hovertext=f"{row['site_name']}<br>Down: {row['down_time']}<br>Restore: {row['restore_time']}",
        hoverinfo="text", showlegend=False,
    ))

fig.update_layout(
    yaxis=dict(title="Saat (0-24)", range=[0, 24]),
    xaxis=dict(title="Tarih"),
    barmode="overlay", height=550,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Raporlama")
c1, c2, c3 = st.columns(3)
c1.metric("Ortalama Backup Süresi (dk)", round(filtered["backup_duration_min"].mean(), 1) if not filtered.empty else 0)
c2.metric("Ortalama Kesik Kalma Süresi (dk)", round(filtered["outage_duration_min"].mean(), 1) if not filtered.empty else 0)
c3.metric("Toplam Kesinti Saati", round(filtered["outage_duration_min"].sum() / 60, 1) if not filtered.empty else 0)

st.dataframe(
    filtered[["site_name", "mains_time", "down_time", "restore_time",
              "backup_duration_min", "outage_duration_min", "comment"]],
    use_container_width=True,
)

colo1, colo2 = st.columns(2)
with colo1:
    xlsx_buf = io.BytesIO()
    filtered.drop(columns=["mains_dt", "down_dt", "restore_dt"], errors="ignore").to_excel(
        xlsx_buf, index=False, engine="openpyxl",
    )
    xlsx_buf.seek(0)
    st.download_button(
        "📥 Excel İndir", data=xlsx_buf, file_name="ariza_takip.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with colo2:
    if st.button("🖼️ JPG Rapor Oluştur", key="ariza_jpg"):
        jpg_buf = generate_table_jpg(
            filtered[["site_name", "mains_time", "down_time", "outage_duration_min"]].head(25),
            "Arıza Takip Raporu",
        )
        st.download_button("📥 JPG İndir", data=jpg_buf, file_name="ariza_takip.jpg", mime="image/jpeg")
