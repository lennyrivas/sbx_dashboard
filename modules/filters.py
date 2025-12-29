# modules/filters.py
# Фильтрация данных по mandant, артикулу, режиму и датам + валидация дат

import streamlit as st
from modules.ui_strings import STR
from datetime import datetime, timedelta
import pandas as pd
from utils import load_packaging_config

def render_sidebar_filters(df):
    """
    Рендерит sidebar фильтры и возвращает параметры фильтрации
    Возвращает: selected_mandant, selected_artikel, mode, date_start, date_end
    """
    st.sidebar.header(STR["filters"])
    
    # Mandant выбор
    available_mandants = ["351", "352"]
    selected_mandant = st.sidebar.selectbox(
        STR["mandant"], 
        options=available_mandants, 
        index=0
    )
    
    # Mode выбор (удаленные или принятые)
    mode = st.sidebar.radio(
        STR["mode"], 
        (STR["mode_deleted"], STR["mode_received"])
    )
    
    # Date mode выбор
    st.sidebar.markdown(STR["date_mode"])
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_mode = st.sidebar.radio(
        "Date mode", 
        (STR["single"], STR["range"]), 
        label_visibility="collapsed"
    )
    
    # Date picker логика
    if date_mode == STR["single"]:
        sel_date = st.sidebar.date_input(
            STR["single"], 
            value=yesterday, 
            key="date_single"
        )
        date_start = datetime.combine(sel_date, datetime.min.time())
        date_end = datetime.combine(sel_date, datetime.max.time())
    else:
        start = st.sidebar.date_input(
            STR["from"], 
            value=yesterday - timedelta(days=6), 
            key="date_from"
        )
        end = st.sidebar.date_input(
            STR["to"], 
            value=yesterday, 
            key="date_to"
        )
        # Значения по умолчанию если даты пустые
        if start and end:
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())
        else:
            date_start = datetime.combine(yesterday - timedelta(days=6), datetime.min.time())
            date_end = datetime.combine(yesterday, datetime.max.time())
    
    # ✅ НОВАЯ ПРОВЕРКА: валидация диапазона дат
    if date_start > date_end:
        st.sidebar.error("❌ Błąd: Data 'Od' nie może być późniejsza niż 'Do'")
        st.sidebar.stop()
    
    # Artikel выбор (после загрузки данных)
    artikel_options = sorted(
        df.loc[df["MANDANT"] == selected_mandant, "ARTIKELNR"]
        .dropna().unique().tolist()
    )
    selected_artikel = st.sidebar.multiselect(
        STR["artikel"], 
        options=artikel_options, 
        default=[]
    )
    
    return selected_mandant, selected_artikel, mode, date_start, date_end

def apply_filters(df, mandant, artikel, mode, date_start, date_end):
    """
    Применяет фильтры к DataFrame
    """
    # Выбор поля даты по режиму
    date_field = "OUT_DATE" if mode == STR["mode_deleted"] else "IN_DATE"
    
    # Базовый фильтр mandant
    mask = (df["MANDANT"] == mandant)
    
    # Фильтр артикулов
    if artikel:
        mask &= df["ARTIKELNR"].isin([a.strip().upper() for a in artikel])
    
    # Фильтр даты
    mask &= df[date_field].between(
        pd.Timestamp(date_start), 
        pd.Timestamp(date_end)
    )
    
    filtered_df = df[mask].copy()

    # IS_DELETED уже посчитан при подготовке df (ZUSTAND != 401)
    # Здесь только выделяем podzbiór usuniętych palet:
    if "IS_DELETED" in filtered_df.columns:
        deleted_df = filtered_df[filtered_df["IS_DELETED"]].copy()
    else:
        # Fallback: jeśli z jakiegoś powodu kolumny нет
        deleted_df = filtered_df.iloc[0:0].copy()

    return filtered_df, deleted_df



# def render_debug_info(mandant, artikel, date_field, date_start, date_end, filtered_count):
#     """Отображает информацию о фильтрах в sidebar БЕЗ заголовка"""
#     st.sidebar.markdown("---")
#     st.sidebar.write(f"**Mandant:** {mandant}")
#     st.sidebar.write(f"**Artykuły:** {len(artikel) if artikel else 0}")
#     st.sidebar.write(f"**Data field:** {date_field}")
#     st.sidebar.write(f"**Date range:** {date_start.date()} - {date_end.date()}")
#     st.sidebar.write(f"**Wynik filtracji:** {filtered_count:,} wierszy")


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
        if date_mode_label == "Dzień":
            selected_time_range = st.selectbox(
                "Czas (1h)",
                options=time_options,
                index=0,
                key="analysis_time_range",
            )
        else:
            selected_time_range = None

    # Artykuł – z powrotem multiselect, ale w nieco węższej kolumnie
    with col_artikel:
        all_artikel_options = sorted(
            df.loc[df["MANDANT"] == selected_mandant, "ARTIKELNR"]
            .dropna()
            .unique()
            .tolist()
        )
        selected_artikel = st.multiselect(
            "Artykuł (ARTIKELNR)",
            options=all_artikel_options,
            default=[],
            key="analysis_artikel",
        )

    # Maski filtrów
    mask_global = (df["MANDANT"] == selected_mandant)

    # Filtr po dacie (OUT_DATE lub IN_DATE)
    mask_global &= df[date_field].between(
        pd.Timestamp(date_start),
        pd.Timestamp(date_end),
    )

    # 👉 Dodatkowo: przy Tryb = Wyjście pokazujemy tylko palety usunięte (ZUSTAND != 401)
    # To jest część definicji trybu, więc wchodzi do mask_global
    if date_field == "OUT_DATE":
        if "IS_DELETED" in df.columns:
            mask_global &= df["IS_DELETED"]
        else:
            mask_global &= df["ZUSTAND"] != "401"

    # 1. DataFrame bez filtra artykułów I BEZ FILTRA CZASU (do statystyk porównawczych)
    # Dzięki temu metryki "Artykuły z rozbieżnością" są niezależne od filtra czasu i artykułu.
    filtered_pallets_no_art_df = df[mask_global].copy()

    # Teraz tworzymy maskę dla widoku (z czasem i artykułami)
    mask_view = mask_global.copy()

    # Filtr czasu (IN_TIME lub OUT_TIME) - tylko dla głównego widoku
    if selected_time_range:
        t_start_str, t_end_str = selected_time_range.split(" - ")
        t_start = datetime.strptime(t_start_str, "%H:%M").time()
        t_end = datetime.strptime(t_end_str, "%H:%M").time()
        
        time_col = "OUT_TIME" if date_field == "OUT_DATE" else "IN_TIME"
        
        # Wektorowe filtrowanie czasu - znacznie szybsze niż .apply()
        # Najpierw upewniamy się, że kolumna nie ma NaT, bo to psuje porównania
        valid_time_mask = df[time_col].notna()
        # Teraz właściwe filtrowanie na poprawnych danych
        mask_view &= valid_time_mask & (df[time_col] >= t_start) & (df[time_col] < t_end)

    # Filtr artykułów - tylko dla głównego widoku
    if selected_artikel:
        mask_view &= df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])

    filtered_pallets_df = df[mask_view].copy()
    

    # Здесь НЕ пересчитываем IS_DELETED – он уже посчитан при загрузке df
    # и основан на ZUSTAND != 401.

    # Zwracamy pełną listę artykułów dla mandanta (do ręcznych zamówień), a nie tylko przefiltrowaną
    # artikel_options = sorted(filtered_pallets_df["ARTIKELNR"].unique().tolist())


    return (
        selected_mandant,
        selected_artikel,
        mode,
        date_start,
        date_end,
        filtered_pallets_df,
        all_artikel_options,
        filtered_pallets_no_art_df,
    )
