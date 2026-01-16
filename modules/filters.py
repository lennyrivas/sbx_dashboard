# modules/filters.py
# Data filtration by mandant, article, mode, and dates + date validation.
# Фильтрация данных по манданту, артикулу, режиму и датам + валидация дат.

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from utils import load_packaging_config

def render_sidebar_filters(df, STR):
    # Renders sidebar filters and returns filtration parameters.
    # Рендерит фильтры в боковой панели и возвращает параметры фильтрации.
    # Returns: selected_mandant, selected_artikel, mode, date_start, date_end
    # Возвращает: selected_mandant, selected_artikel, mode, date_start, date_end
    
    st.sidebar.header(STR["filters"])
    
    # Mandant selection dropdown.
    # Выбор манданта (клиента) из выпадающего списка.
    available_mandants = ["351", "352"]
    selected_mandant = st.sidebar.selectbox(
        STR["mandant"], 
        options=available_mandants, 
        index=0
    )
    
    # Mode selection: Deleted (Output) or Received (Input).
    # Выбор режима: Удаленные (Выход) или Принятые (Вход).
    mode = st.sidebar.radio(
        STR["mode"], 
        (STR["mode_deleted"], STR["mode_received"])
    )
    
    # Date selection mode: Single day or Date range.
    # Режим выбора даты: Один день или Диапазон дат.
    st.sidebar.markdown(STR["date_mode"])
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_mode = st.sidebar.radio(
        "Date mode", 
        (STR["single"], STR["range"]), 
        label_visibility="collapsed"
    )
    
    # Logic for date pickers based on the selected mode.
    # Логика выбора дат в зависимости от выбранного режима.
    if date_mode == STR["single"]:
        # Single date picker.
        # Выбор одной даты.
        sel_date = st.sidebar.date_input(
            STR["single"], 
            value=yesterday, 
            key="date_single"
        )
        # Set start and end to the beginning and end of the selected day.
        # Устанавливаем начало и конец на начало и конец выбранного дня.
        date_start = datetime.combine(sel_date, datetime.min.time())
        date_end = datetime.combine(sel_date, datetime.max.time())
    else:
        # Date range pickers (From and To).
        # Выбор диапазона дат (От и До).
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
        # Set default values if dates are not selected.
        # Устанавливаем значения по умолчанию, если даты не выбраны.
        if start and end:
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())
        else:
            date_start = datetime.combine(yesterday - timedelta(days=6), datetime.min.time())
            date_end = datetime.combine(yesterday, datetime.max.time())
    
    # Validate that the start date is not after the end date.
    # Проверяем, что начальная дата не позже конечной.
    if date_start > date_end:
        st.sidebar.error("❌ Błąd: Data 'Od' nie może być późniejsza niż 'Do'")
        st.sidebar.stop()
    
    # Article selection multiselect (populated based on selected mandant).
    # Мультивыбор артикулов (заполняется на основе выбранного манданта).
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

def apply_filters(df, mandant, artikel, mode, date_start, date_end, STR):
    # Applies the selected filters to the DataFrame.
    # Применяет выбранные фильтры к DataFrame.
    
    # Determine which date column to use based on the mode.
    # Определяем, какую колонку даты использовать в зависимости от режима.
    date_field = "OUT_DATE" if mode == STR["mode_deleted"] else "IN_DATE"
    
    # Create a mask for the mandant.
    # Создаем маску для манданта.
    mask = (df["MANDANT"] == mandant)
    
    # Add article filter to the mask if articles are selected.
    # Добавляем фильтр по артикулам в маску, если артикулы выбраны.
    if artikel:
        mask &= df["ARTIKELNR"].isin([a.strip().upper() for a in artikel])
    
    # Add date range filter to the mask.
    # Добавляем фильтр по диапазону дат в маску.
    mask &= df[date_field].between(
        pd.Timestamp(date_start), 
        pd.Timestamp(date_end)
    )
    
    # Apply the mask to create the filtered DataFrame.
    # Применяем маску для создания отфильтрованного DataFrame.
    filtered_df = df[mask].copy()

    # Extract the subset of deleted pallets if the column exists.
    # IS_DELETED is pre-calculated during data loading (ZUSTAND != 401).
    # Извлекаем подмножество удаленных паллет, если колонка существует.
    # IS_DELETED предварительно вычисляется при загрузке данных (ZUSTAND != 401).
    if "IS_DELETED" in filtered_df.columns:
        deleted_df = filtered_df[filtered_df["IS_DELETED"]].copy()
    else:
        # Fallback: return an empty DataFrame if the column is missing.
        # Резервный вариант: возвращаем пустой DataFrame, если колонка отсутствует.
        deleted_df = filtered_df.iloc[0:0].copy()

    return filtered_df, deleted_df


def render_analysis_filters(df: pd.DataFrame, STR):
    # Renders compact filters for the 'Orders vs Pallets Analysis' tab in a single line.
    # Рендерит компактные фильтры для вкладки 'Анализ заказов vs паллет' в одну строку.

    st.subheader(STR["analysis_filters_title"])
    
    # Generate time range options (every 1 hour from 6:00 to 22:00).
    # Генерируем опции временных диапазонов (каждый час с 6:00 до 22:00).
    time_options = [""]
    t_curr = datetime(2000, 1, 1, 6, 0)
    t_end_limit = datetime(2000, 1, 1, 22, 0)
    while t_curr < t_end_limit:
        t_next = t_curr + timedelta(hours=1)
        label = f"{t_curr.strftime('%H:%M')} - {t_next.strftime('%H:%M')}"
        time_options.append(label)
        t_curr = t_next

    # Layout: Mandant | Mode | Dates (mode + from + to) | Time | Article
    # Макет: Мандант | Режим | Даты (режим + от + до) | Время | Артикул
    col_mandant, col_mode, col_dates, col_time, col_artikel = st.columns(
        [0.6, 1.2, 2.8, 1.0, 1.4]
    )

    yesterday = (datetime.now() - timedelta(days=1)).date()

    # Mandant selection (narrow column).
    # Выбор манданта (узкая колонка).
    with col_mandant:
        selected_mandant = st.selectbox(
            STR["mandant"],
            options=["351", "352"],
            index=1,
            key="analysis_mandant",
        )

    # Mode selection: Output (OUT_DATE) or Input (IN_DATE).
    # Выбор режима: Выход (OUT_DATE) или Вход (IN_DATE).
    with col_mode:
        options_mode = [STR["opt_mode_out"], STR["opt_mode_in"]]
        mode_label = st.radio(
            STR["lbl_mode"],
            options=options_mode,
            index=0,
            horizontal=True,           # Horizontal layout / Горизонтальное расположение
            key="analysis_mode",
        )
        date_field = "OUT_DATE" if mode_label == STR["opt_mode_out"] else "IN_DATE"
        mode = STR["mode_deleted"] if date_field == "OUT_DATE" else STR["mode_received"]

    # Date selection: Day or Range.
    # Выбор даты: День или Диапазон.
    with col_dates:
        # Nested columns: [Date Mode] [From/Date] [To/Empty]
        # Вложенные колонки: [Режим даты] [От/Дата] [До/Пусто]
        c_mode, c_from, c_to = st.columns([1.1, 1.1, 1.1])

        with c_mode:
            options_date_mode = [STR["opt_date_day"], STR["range"]]
            date_mode_label = st.radio(
                STR["lbl_dates"],
                options=options_date_mode,
                index=0,
                horizontal=True,        # Horizontal layout / Горизонтальное расположение
                key="analysis_date_mode",
            )

        if date_mode_label == STR["opt_date_day"]:
            # Single day selection.
            # Выбор одного дня.
            with c_from:
                sel_date = st.date_input(
                    STR["lbl_date"],
                    value=yesterday,
                    key="analysis_date_single",
                )
            date_start = datetime.combine(sel_date, datetime.min.time())
            date_end = datetime.combine(sel_date, datetime.max.time())
            # Placeholder for the third column to maintain alignment.
            # Заполнитель для третьей колонки для сохранения выравнивания.
            with c_to:
                st.write("")  
                st.write("")
        else:
            # Date range selection.
            # Выбор диапазона дат.
            with c_from:
                start = st.date_input(
                    STR["from"],
                    value=yesterday - timedelta(days=6),
                    key="analysis_date_from",
                )
            with c_to:
                end = st.date_input(
                    STR["to"],
                    value=yesterday,
                    key="analysis_date_to",
                )
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())

    # Time range selection (1 hour intervals).
    # Выбор временного диапазона (интервалы по 1 часу).
    with col_time:
        if date_mode_label == STR["opt_date_day"]:
            selected_time_range = st.selectbox(
                STR["lbl_time"],
                options=time_options,
                index=0,
                key="analysis_time_range",
            )
        else:
            selected_time_range = None

    # Article selection (multiselect).
    # Выбор артикула (мультивыбор).
    with col_artikel:
        all_artikel_options = sorted(
            df.loc[df["MANDANT"] == selected_mandant, "ARTIKELNR"]
            .dropna()
            .unique()
            .tolist()
        )
        selected_artikel = st.multiselect(
            STR["artikel"],
            options=all_artikel_options,
            default=[],
            key="analysis_artikel",
        )

    # --- Apply Filters ---
    # --- Применение фильтров ---
    
    # Global mask for Mandant.
    # Глобальная маска для манданта.
    mask_global = (df["MANDANT"] == selected_mandant)

    # Filter by date (OUT_DATE or IN_DATE).
    # Фильтр по дате (OUT_DATE или IN_DATE).
    mask_global &= df[date_field].between(
        pd.Timestamp(date_start),
        pd.Timestamp(date_end),
    )

    # Additional logic for Output mode: show only deleted pallets (ZUSTAND != 401).
    # Дополнительная логика для режима Выход: показывать только удаленные паллеты (ZUSTAND != 401).
    if date_field == "OUT_DATE":
        if "IS_DELETED" in df.columns:
            mask_global &= df["IS_DELETED"]
        else:
            mask_global &= df["ZUSTAND"] != "401"

    # Create a DataFrame without article and time filters (for comparative statistics).
    # This ensures metrics like "Articles with discrepancy" are calculated globally for the selected period.
    # Создаем DataFrame без фильтров по артикулу и времени (для сравнительной статистики).
    # Это гарантирует, что метрики, такие как "Артикулы с расхождениями", рассчитываются глобально для выбранного периода.
    filtered_pallets_no_art_df = df[mask_global].copy()

    # Create a mask for the main view (including time and article filters).
    # Создаем маску для основного вида (включая фильтры по времени и артикулу).
    mask_view = mask_global.copy()

    # Apply time filter if selected (only for the main view).
    # Применяем фильтр по времени, если выбран (только для основного вида).
    if selected_time_range:
        t_start_str, t_end_str = selected_time_range.split(" - ")
        t_start = datetime.strptime(t_start_str, "%H:%M").time()
        t_end = datetime.strptime(t_end_str, "%H:%M").time()
        
        time_col = "OUT_TIME" if date_field == "OUT_DATE" else "IN_TIME"
        
        # Use vectorized filtering for performance.
        # Ensure the time column is not NaT before comparison.
        # Используем векторизованную фильтрацию для производительности.
        # Убеждаемся, что колонка времени не содержит NaT перед сравнением.
        valid_time_mask = df[time_col].notna()
        mask_view &= valid_time_mask & (df[time_col] >= t_start) & (df[time_col] < t_end)

    # Apply article filter if selected (only for the main view).
    # Применяем фильтр по артикулу, если выбран (только для основного вида).
    if selected_artikel:
        mask_view &= df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])

    # Create the final filtered DataFrame for the view.
    # Создаем итоговый отфильтрованный DataFrame для отображения.
    filtered_pallets_df = df[mask_view].copy()
    
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
