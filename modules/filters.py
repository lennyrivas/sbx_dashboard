# modules/filters.py
# Фильтрация данных по mandant, артикулу, режиму и датам + валидация дат

import streamlit as st
from modules.ui_strings import STR
from datetime import datetime, timedelta
import pandas as pd

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
        df[df["MANDANT"].astype(str) == selected_mandant]["ARTIKELNR"]
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
    mask = (df["MANDANT"].astype(str) == mandant)
    
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



def render_debug_info(mandant, artikel, date_field, date_start, date_end, filtered_count):
    """Отображает информацию о фильтрах в sidebar БЕЗ заголовка"""
    st.sidebar.markdown("---")
    st.sidebar.write(f"**Mandant:** {mandant}")
    st.sidebar.write(f"**Artykuły:** {len(artikel) if artikel else 0}")
    st.sidebar.write(f"**Data field:** {date_field}")
    st.sidebar.write(f"**Date range:** {date_start.date()} - {date_end.date()}")
    st.sidebar.write(f"**Wynik filtracji:** {filtered_count:,} wierszy")

