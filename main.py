import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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
from modules.data_loader import load_main_csv
from modules.filters import render_analysis_filters


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
# Загрузка файла и подготовка df
# ==============================
uploaded = st.sidebar.file_uploader(
    STR["upload_csv"],
    type=["csv", "txt"],
    key="main_csv",
)

if uploaded is None:
    st.info(STR["no_file"])
    st.stop()

df = load_main_csv(uploaded)
if df is None:
    st.stop()

# --- Admin Login (Sidebar) ---
with st.sidebar:
    st.markdown("---")
    with st.expander("🔐 Admin"):
        admin_password = st.text_input("Hasło", type="password", key="admin_pass")

# ==============================
# Вкладки
# ==============================
tabs_labels = [
    "Analiza zamówień vs palet",
    "Stany magazynowe",
    "📊 Statystyka",
    "⚙️ Ustawienia",
]

# Bezpieczne sprawdzanie hasła przez st.secrets
# Hasło nie jest przechowywane w kodzie na GitHubie
if "ADMIN_PASSWORD" in st.secrets and admin_password == st.secrets["ADMIN_PASSWORD"]:
    tabs_labels.append("🔐 Admin")

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
        # Tryb Wyjście: zachowujemy starą logikę (usunięte)
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
        st.header("🔐 Ukryty Panel Administratora")
        st.info("Witaj w panelu administratora!")
        st.write("Tutaj możesz dodać funkcje administracyjne.")
