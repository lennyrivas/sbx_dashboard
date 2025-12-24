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

# ==============================
# Функция фильтров для вкладки Analiza
# ==============================

def render_analysis_filters(df: pd.DataFrame):
    """
    Bardzo kompaktowe filtry dla zakładki 'Analiza zamówień vs palet'
    w jednej linii.
    """

    st.subheader("🔍 Filtry analizy")
    
    # Generowanie opcji czasu (co 1h od 6:00 do 22:00)
    time_options = [""]
    t_curr = datetime(2000, 1, 1, 6, 0)
    t_end_limit = datetime(2000, 1, 1, 22, 0)
    while t_curr < t_end_limit:
        t_next = t_curr + timedelta(hours=1)
        label = f"{t_curr.strftime('%H:%M')} - {t_next.strftime('%H:%M')}"
        time_options.append(label)
        t_curr = t_next

    # Jedna linia: Mandant | Tryb | Daty (tryb + od + do) | Czas | Artykuł
    col_mandant, col_mode, col_dates, col_time, col_artikel = st.columns(
        [0.4, 1.2, 2.8, 1.0, 1.4]
    )

    yesterday = (datetime.now() - timedelta(days=1)).date()

    # Mandant – bardzo wąska kolumna, 3 cyfry
    with col_mandant:
        selected_mandant = st.selectbox(
            "Mandant",
            options=["351", "352"],
            index=0,
            key="analysis_mandant",
        )

    # Tryb: dwa radio – Wyjście (OUT_DATE) / Wejście (IN_DATE)
    with col_mode:
        mode_label = st.radio(
            "Tryb",
            options=["Wyjście", "Wejście"],
            index=0,
            horizontal=True,           # poziomo
            key="analysis_mode",
        )
        date_field = "OUT_DATE" if mode_label == "Wyjście" else "IN_DATE"
        mode = STR["mode_deleted"] if date_field == "OUT_DATE" else STR["mode_received"]

    # Daty: Dzień / Zakres + Data od + Data do
    with col_dates:
        # 3 kolumny wewnątrz: [tryb daty] [od] [do]
        c_mode, c_from, c_to = st.columns([1.1, 1.1, 1.1])

        with c_mode:
            date_mode_label = st.radio(
                "Daty",
                options=["Dzień", "Zakres"],
                index=0,
                horizontal=True,        # teraz poziomo
                key="analysis_date_mode",
            )

        if date_mode_label == "Dzień":
            with c_from:
                sel_date = st.date_input(
                    "Data",
                    value=yesterday,
                    key="analysis_date_single",
                )
            date_start = datetime.combine(sel_date, datetime.min.time())
            date_end = datetime.combine(sel_date, datetime.max.time())
            # Rezerwujemy miejsce na "Do", ale bez pola przy trybie "Dzień"
            with c_to:
                st.write("")  # pusty placeholder
                st.write("")
        else:
            with c_from:
                start = st.date_input(
                    "Od",
                    value=yesterday - timedelta(days=6),
                    key="analysis_date_from",
                )
            with c_to:
                end = st.date_input(
                    "Do",
                    value=yesterday,
                    key="analysis_date_to",
                )
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())

    # Czas (1h)
    with col_time:
        selected_time_range = st.selectbox(
            "Czas (1h)",
            options=time_options,
            index=0,
            key="analysis_time_range",
        )

    # Artykuł – z powrotem multiselect, ale w nieco węższej kolumnie
    with col_artikel:
        artikel_options = sorted(
            df[df["MANDANT"].astype(str) == selected_mandant]["ARTIKELNR"]
            .dropna()
            .unique()
            .tolist()
        )
        selected_artikel = st.multiselect(
            "Artykuł (ARTIKELNR)",
            options=artikel_options,
            default=[],
            key="analysis_artikel",
        )

    # Maski filtrów
    mask = (df["MANDANT"].astype(str) == selected_mandant)

    if selected_artikel:
        mask &= df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])

    # Filtr po dacie (OUT_DATE lub IN_DATE)
    mask &= df[date_field].between(
        pd.Timestamp(date_start),
        pd.Timestamp(date_end),
    )

    # Filtr czasu (IN_TIME lub OUT_TIME)
    if selected_time_range:
        t_start_str, t_end_str = selected_time_range.split(" - ")
        t_start = datetime.strptime(t_start_str, "%H:%M").time()
        t_end = datetime.strptime(t_end_str, "%H:%M").time()
        
        time_col = "OUT_TIME" if date_field == "OUT_DATE" else "IN_TIME"
        
        def filter_time_range(val):
            if val is None or pd.isna(val):
                return False
            return t_start <= val < t_end
            
        mask &= df[time_col].apply(filter_time_range)

    # 👉 Dodatkowo: przy Tryb = Wyjście pokazujemy tylko palety usunięte (ZUSTAND != 401)
    if date_field == "OUT_DATE":
        # Możesz użyć albo IS_DELETED, albo bezpośrednio ZUSTAND != 401
        if "IS_DELETED" in df.columns:
            mask &= df["IS_DELETED"]
        else:
            mask &= df["ZUSTAND"].astype(str).str.strip() != "401"

    filtered_pallets_df = df[mask].copy()


    # Здесь НЕ пересчитываем IS_DELETED – он уже посчитан при загрузке df
    # и основан на ZUSTAND != 401.

    # Lista dostępnych artykułów po filtrach
    artikel_options = sorted(filtered_pallets_df["ARTIKELNR"].unique().tolist())


    return (
        selected_mandant,
        selected_artikel,
        mode,
        date_start,
        date_end,
        filtered_pallets_df,
        artikel_options,
    )


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

# ==============================
# Вкладки
# ==============================
tab_analysis, tab_stock, tab_stats, tab_settings = st.tabs(
    [
        "Analiza zamówień vs palet",
        "Stany magazynowe",
        "📊 Statystyka",
        "⚙️ Ustawienia",
    ]
)

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
    ) = render_analysis_filters(df)

    # После фильтров считаем deleted_pallets и метрики
    deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]]

    if selected_mandant == "352":
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Wybrane palety", f"{len(filtered_pallets_df):,}")
        col2.metric("Usunięte palety", f"{len(deleted_pallets):,}")

        kartony_prefixes, _ = load_packaging_config()
        kartony_count = deleted_pallets[
            deleted_pallets["ARTIKELNR"].str.startswith(
                tuple(kartony_prefixes),
                na=False,
            )
        ].shape[0]
        inne_count = len(deleted_pallets) - kartony_count
        col3.metric("Usunięte kartony", f"{kartony_count:,}")
        col4.metric("Inne opakowania", f"{inne_count:,}")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Wybrane palety", f"{len(filtered_pallets_df):,}")
        col2.metric("Usunięte palety", f"{len(deleted_pallets):,}")

    render_orders_tab(
        artikel_options,
        filtered_pallets_df,
        selected_artikel,
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
