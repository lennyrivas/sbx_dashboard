import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid

from modules.orders import render_orders_tab
from modules.ui_strings import STR
from utils import (
    load_excluded_articles,
    save_excluded_articles,
    load_packaging_config,
    save_packaging_config,
)
from modules.settings import render_settings_tab
from modules.stock import render_stock_tab
from modules.stats import render_stats_tab
from modules.data_loader import load_main_csv, save_session_to_disk, load_session_from_disk, clear_session_state
from modules.filters import render_analysis_filters
from modules.admin import render_admin_tab


# ==============================
# Основная конфигурация страницы
# ==============================
st.set_page_config(
    page_title="Sprintbox — Raport palet",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title(STR["title"])

# ==============================
# Zarządzanie sesją użytkownika (UUID)
# ==============================
if "session_id" not in st.query_params:
    st.query_params["session_id"] = str(uuid.uuid4())

session_id = st.query_params["session_id"]

# ==============================
# Загрузка файла и подготовка df
# ==============================
uploaded = st.sidebar.file_uploader(
    STR["upload_csv"],
    type=["csv", "txt"],
    key="main_csv",
)

df = None

# 1. Próba załadowania z uploadu (priorytet)
if uploaded is not None:
    df = load_main_csv(uploaded)
    if df is not None:
        # Zapisujemy sesję na dysk, aby przetrwała odświeżenie strony
        save_session_to_disk(df, session_id)
        if "restored_df" in st.session_state:
            del st.session_state["restored_df"]

# 2. Jeśli brak uploadu, próba przywrócenia sesji z dysku
if df is None:
    if "restored_df" not in st.session_state:
        saved_df = load_session_from_disk(session_id)
        if saved_df is not None:
            st.session_state["restored_df"] = saved_df
    
    if "restored_df" in st.session_state:
        df = st.session_state["restored_df"]
        st.sidebar.warning("⚠️ Przywrócono dane z ostatniej sesji.")
        if st.sidebar.button("🗑️ Wyczyść dane", key="clear_session_btn"):
            clear_session_state(session_id)
            del st.session_state["restored_df"]
            st.rerun()

if df is None:
    st.info(STR["no_file"])
    st.stop()

# --- Admin Login (Sidebar) ---
with st.sidebar:
    st.markdown("---")
    with st.expander("🔐 Admin"):
        with st.form("admin_login_form"):
            admin_password = st.text_input("Hasło", type="password", key="admin_pass", label_visibility="collapsed", placeholder="Hasło")
            st.form_submit_button("Login", use_container_width=True)

# ==============================
# Вкладки
# ==============================
tabs_labels = [
    "Analiza zamówień vs palet",
    "Stany magazynowe",
    "📊 Statystyka",
    "⚙️ Ustawienia",
]

# Pobieranie hasła z st.secrets (lub domyślne "admin" jeśli brak pliku secrets)
try:
    correct_password = st.secrets["ADMIN_PASSWORD"]
except Exception:
    correct_password = "admin"

if admin_password == correct_password:
    tabs_labels.append("🔐 Usuwanie palet")

tabs = st.tabs(tabs_labels)

tab_analysis = tabs[0]
tab_stock = tabs[1]
tab_stats = tabs[2]
tab_settings = tabs[3]

with tab_analysis:
    st.header("⚖️ Analiza dodanych i usuniętych palet")

    # 👉 Фильтры теперь рисуются здесь, в этой вкладке
    (
        selected_mandant,
        selected_artikel,
        mode,
        date_start,
        date_end,
        filtered_pallets_df,
        artikel_options,
        filtered_pallets_no_art_df,
    ) = render_analysis_filters(df)

    # После фильтров считаем deleted_pallets и метрики
    kartony_prefixes, _ = load_packaging_config()

    if mode == STR["mode_received"]:
        # Tryb Wejście: pokazujemy przyjęte palety i podział na opakowania
        total_received = len(filtered_pallets_df)
        
        if selected_mandant == "352":
            kartony_count = filtered_pallets_df[
                filtered_pallets_df["ARTIKELNR"].str.startswith(
                    tuple(kartony_prefixes),
                    na=False,
                )
            ].shape[0]
            inne_count = total_received - kartony_count
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Przyjęte palety", f"{total_received:,}")
            col2.metric("Kartony (przyjęte)", f"{kartony_count:,}")
            col3.metric("Inne opakowania (przyjęte)", f"{inne_count:,}")
        else:
            # Mandant 351: tylko przyjęte palety
            st.metric("Przyjęte palety", f"{total_received:,}")

    else:
        # Tryb Wyjście: zachowujemy starą логику (usunięte)
        deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]]

        if selected_mandant == "352":
            col1, col2, col3 = st.columns(3)
            col1.metric("Usunięte palety", f"{len(deleted_pallets):,}")

            kartony_count = deleted_pallets[
                deleted_pallets["ARTIKELNR"].str.startswith(
                    tuple(kartony_prefixes),
                    na=False,
                )
            ].shape[0]
            inne_count = len(deleted_pallets) - kartony_count
            col2.metric("Usunięte kartony", f"{kartony_count:,}")
            col3.metric("Inne opakowania", f"{inne_count:,}")
        else:
            # Mandant 351: tylko usunięte palety
            st.metric("Usunięte palety", f"{len(deleted_pallets):,}")

    render_orders_tab(
        artikel_options,
        filtered_pallets_df,
        selected_artikel,
        filtered_pallets_no_art_df=filtered_pallets_no_art_df,
        full_df=df,
        date_start=date_start,
        date_end=date_end,
        selected_mandant=selected_mandant,
    )

with tab_stock:
    render_stock_tab(
        df,                # полный очищенный DataFrame
        selected_mandant,  # текущий mandant из фильтров анализа
        selected_artikel,  # текущий список artykułów (можно потом отделить)
        STR,
    )

with tab_stats:
    render_stats_tab(df, STR)


with tab_settings:
    # Используем функцию из модуля
    render_settings_tab()

if len(tabs) > 4:
    with tabs[4]:
        render_admin_tab(df)
