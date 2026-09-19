"""
utils.py
--------
Ortak sabitler ve admin oturum yonetimi (session-based auth).
"""

import streamlit as st

ADMIN_PASSWORD = "admin5555"

# Ekran 3 kapsamindaki 6 il
KAPSAM_ILLER = ["Samsun", "Sinop", "Ordu", "Amasya", "Tokat", "Çorum"]


def is_admin():
    return bool(st.session_state.get("is_admin", False))


def require_admin_login():
    """Admin girisini yonetir. Giris yapilmissa True doner ve cikis butonu gosterir.
    Giris yapilmamissa sifre formu gosterir ve False doner."""
    if is_admin():
        col1, col2 = st.columns([4, 1])
        col1.success("Admin oturumu aktif.")
        if col2.button("Çıkış Yap"):
            st.session_state.is_admin = False
            st.rerun()
        return True

    with st.form("admin_login_form"):
        pwd = st.text_input("Admin Şifresi", type="password")
        submitted = st.form_submit_button("Giriş Yap")

    if submitted:
        if pwd == ADMIN_PASSWORD:
            st.session_state.is_admin = True
            st.rerun()
        else:
            st.error("Hatalı şifre.")
    return False
