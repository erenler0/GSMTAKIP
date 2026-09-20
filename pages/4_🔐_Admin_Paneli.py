"""Ekran 5: Admin Paneli & Yetkilendirme."""

import pandas as pd
import streamlit as st
import concurrent.futures # Hızlı (Paralel) adres bulma için eklendi

from database import (
    init_db, get_all_sites_df, bulk_insert_new_sites, diff_sites_for_sync,
    delete_sites_by_names, log_sync, get_all_centers_df, add_center,
    delete_center, assign_center_to_site,
)
from geocoding import reverse_geocode
from image_export import generate_diff_report_jpg
from utils import require_admin_login

st.set_page_config(page_title="Admin Paneli", page_icon="🔐", layout="wide")
init_db()

st.title("🔐 Admin Paneli & Yetkilendirme")

if not require_admin_login():
    st.stop()

st.divider()
st.subheader("📥 Saha Excel Yükleme (Otomatik Adres Bulma)")
st.caption(
    "Excel sütunları: KML Dosyası, Placemark Adı, Açıklama, Latitude, Longitude, "
    "Altitude, Koordinat (Ham). İl, ilçe, mahalle ArcGIS kullanılarak HIZLI şekilde bulunacaktır."
)

uploaded = st.file_uploader("Saha Excel Dosyası (.xlsx)", type=["xlsx"])

if uploaded is not None:
    try:
        new_df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Excel okunamadı: {e}")
        st.stop()

    required_cols = {"Placemark Adı", "Latitude", "Longitude"}
    if not required_cols.issubset(set(new_df.columns)):
        st.error(f"Excel'de şu sütunlar bulunmalı: {sorted(required_cols)}")
        st.stop()

    new_df = new_df.dropna(subset=["Latitude", "Longitude"])

    st.write(f"Excel'de {len(new_df)} satır okundu.")
    existing_df = get_all_sites_df()
    added, removed, unchanged = diff_sites_for_sync(existing_df, new_df)

    st.write(f"🟢 Yeni eklenecek saha sayısı: **{len(added)}**")
    st.write(f"🔴 Silinecek saha sayısı: **{len(removed)}**")
    st.write(f"⚪ Değişmeyen saha sayısı: **{len(unchanged)}**")

    if "fark_raporu_jpg" not in st.session_state:
        st.session_state.fark_raporu_jpg = None

    if st.button("✅ Senkronizasyonu Onayla ve Başlat"):
        progress = st.progress(0.0, text="Eşzamanlı (Hızlı) Adres Bulma başlatılıyor...")

        geocoded_rows = []
        total = len(added) or 1
        
        # Paralel adres bulma fonksiyonu (Worker)
        def fetch_address_for_row(row):
            il, ilce, mahalle = reverse_geocode(row.get("Latitude"), row.get("Longitude"))
            return {**row, "il": il, "ilce": ilce, "mahalle": mahalle}

        # Aynı anda 10 istek atarak işlemi yaklaşık 10 kat hızlandırıyoruz
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Tüm satırları iş kuyruğuna ekle
            futures = {executor.submit(fetch_address_for_row, row): row for row in added}
            
            # İşler bittikçe sonuçları topla
            for future in concurrent.futures.as_completed(futures):
                geocoded_rows.append(future.result())
                completed += 1
                progress.progress(min(completed / total, 1.0), text=f"Adresler bulunuyor: {completed} / {total}")

        if geocoded_rows:
            bulk_insert_new_sites(geocoded_rows)

        removed_names = [r["Placemark Adı"] for r in removed]
        if removed_names:
            delete_sites_by_names(removed_names)

        added_names = [r["Placemark Adı"] for r in added]
        log_sync(added_names, removed_names)

        progress.progress(1.0, text="Tamamlandı")
        st.success(f"Senkronizasyon tamamlandı: {len(added_names)} saha eklendi, {len(removed_names)} saha silindi.")

        st.session_state.fark_raporu_jpg = generate_diff_report_jpg(added_names, removed_names)

    if st.session_state.fark_raporu_jpg is not None:
        st.download_button(
            "🖼️ Fark Raporu Çıkart (JPG)", 
            data=st.session_state.fark_raporu_jpg,
            file_name="fark_raporu.jpg", 
            mime="image/jpeg",
        )

st.divider()
st.subheader("🏙️ İlçe Merkezleri Yönetimi")

centers_df = get_all_centers_df()
colc1, colc2 = st.columns(2)

with colc1:
    st.markdown("**Yeni İlçe Merkezi Ekle**")
    with st.form("add_center_form"):
        isim = st.text_input("Merkez Adı")
        il = st.text_input("İl")
        ilce = st.text_input("İlçe")
        lat = st.number_input("Latitude", format="%.6f")
        lon = st.number_input("Longitude", format="%.6f")
        submitted_c = st.form_submit_button("Ekle")
    if submitted_c:
        if isim:
            add_center(isim, il, ilce, lat, lon)
            st.success("İlçe merkezi eklendi.")
            st.rerun()
        else:
            st.error("Merkez adı zorunludur.")

with colc2:
    st.markdown("**Mevcut Merkezler**")
    search_c = st.text_input("Merkez Ara")
    show_df = centers_df
    if search_c and not centers_df.empty:
        show_df = centers_df[centers_df["isim"].str.contains(search_c, case=False, na=False)]
    if show_df.empty:
        st.caption("Henüz merkez tanımlanmamış.")
    else:
        for _, c in show_df.iterrows():
            cc1, cc2 = st.columns([4, 1])
            cc1.write(f"**{c['isim']}** ({c['il']}/{c['ilce']}) — {c['latitude']:.4f}, {c['longitude']:.4f}")
            if cc2.button("Sil", key=f"del_center_{c['id']}"):
                delete_center(int(c["id"]))
                st.rerun()

st.divider()
st.subheader("📌 Saha - İlçe Merkezi Manuel Atama (Override)")

sites_df = get_all_sites_df()
centers_df = get_all_centers_df()

if not sites_df.empty and not centers_df.empty:
    colo1, colo2, colo3 = st.columns(3)
    with colo1:
        site_sel = st.selectbox("Saha Seç", sorted(sites_df["placemark_adi"].unique()), key="override_site")
    with colo2:
        center_sel = st.selectbox("İlçe Merkezi Seç", sorted(centers_df["isim"].unique()), key="override_center")
    with colo3:
        st.write("")
        st.write("")
        if st.button("Atamayı Kaydet"):
            site_id = int(sites_df[sites_df["placemark_adi"] == site_sel].iloc[0]["id"])
            center_id = int(centers_df[centers_df["isim"] == center_sel].iloc[0]["id"])
            assign_center_to_site(site_id, center_id, manual=True)
            st.success(f"'{site_sel}' sahası artık manuel olarak '{center_sel}' merkezine bağlı.")
else:
    st.info("Manuel atama yapabilmek için hem saha hem de en az bir ilçe merkezi tanımlı olmalıdır.")
