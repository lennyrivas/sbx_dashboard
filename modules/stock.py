# modules/stock.py
# Logic for the 'Stock Level' tab: filtering, aggregation, and historical analysis.
# Логика для вкладки 'Уровень запасов': фильтрация, агрегация и исторический анализ.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils import load_packaging_config, classify_pallet


# --- Filtering Logic ---
# --- Логика фильтрации ---

def filter_stock_df(df, selected_mandant, selected_artikel, selected_date):
    # Filters the DataFrame to show stock levels at the beginning of a specific date.
    # Фильтрует DataFrame для отображения уровня запасов на начало конкретной даты.
    # Logic: Pallet was received BEFORE the date AND (is still in stock OR was removed ON/AFTER the date).
    # Логика: Паллета была принята ДО даты И (все еще на складе ИЛИ была удалена В/ПОСЛЕ даты).
    
    if df is None or df.empty:
        return pd.DataFrame()

    # 🎯 STEP 1: Base mandant filter.
    # 🎯 ШАГ 1: Базовый фильтр по манданту.
    df_filtered = df[df["MANDANT"].astype(str) == selected_mandant].copy()

    # 🎯 STEP 2: STRICT DATE FILTRATION.
    # 🎯 ШАГ 2: СТРОГАЯ ФИЛЬТРАЦИЯ ПО ДАТЕ.
    
    # Condition 1: Received before the selected date.
    # Условие 1: Принято до выбранной даты.
    mask_in = df_filtered["IN_DATE"].dt.date < selected_date.date()
    
    # Condition 2: Currently in stock (401) OR removed on/after the selected date.
    # Условие 2: Текущий статус на складе (401) ИЛИ удалено в/после выбранной даты.
    mask_is_401 = df_filtered["ZUSTAND"].astype(str) == "401"
    mask_removed_later = df_filtered["OUT_DATE"].dt.date >= selected_date.date()
    
    mask_out_logic = mask_is_401 | mask_removed_later
    
    df_stock_raw = df_filtered[mask_in & mask_out_logic].copy()
        
    # 🎯 STEP 3: DEDUPLICATION BY LHMNR (PID).
    # 🎯 ШАГ 3: ДЕДУПЛИКАЦИЯ ПО LHMNR (PID).
    # Ensure each PID is counted only once (taking the latest entry if duplicates exist).
    # Гарантируем, что каждый PID считается только один раз (берем последнюю запись, если есть дубликаты).
    df_stock = df_stock_raw.sort_values("IN_DATE", ascending=False).drop_duplicates(
        subset=["LHMNR"], keep="first"
    )
    
    # 🎯 STEP 4: Article filter.
    # 🎯 ШАГ 4: Фильтр по артикулу.
    if selected_artikel:
        artikel_list = [a.strip().upper() for a in selected_artikel]
        df_stock = df_stock[df_stock["ARTIKELNR"].isin(artikel_list)].copy()

    # 🎯 STEP 5: Packaging classification (Cartons vs Others).
    # 🎯 ШАГ 5: Классификация упаковки (Картоны vs Остальные).
    kartony_prefixes, other_packaging_prefixes = load_packaging_config()
    pallets_frames_prefixes = st.session_state.get("pallets_frames", [])
    
    df_stock["Opakowanie"] = df_stock.apply(
        lambda row: classify_pallet(
            row["ARTIKELNR"], 
            kartony_prefixes, 
            pallets_frames_prefixes, 
            other_packaging_prefixes
        ),
        axis=1
    )
    
    return df_stock


# --- Aggregation Logic ---
# --- Логика агрегации ---

def aggregate_stock_df(df_stock, STR):
    # Aggregates stock data by article and packaging type.
    # Агрегирует данные о запасах по артикулу и типу упаковки.
    if df_stock.empty:
        return pd.DataFrame()
        
    # Group by Article, Description, and Packaging.
    # Группировка по Артикулу, Описанию и Упаковке.
    df_agg = df_stock.groupby(["ARTIKELNR", "ARTBEZ1", "Opakowanie"], dropna=False).agg(
        Ilość_palet=("LHMNR", "count"),
        Ilość_sztuk=("QUANTITY", "sum")
    ).reset_index()

    # Rename columns using localized strings.
    # Переименование колонок с использованием локализованных строк.
    df_agg.columns = [STR["col_article"], STR["col_description"], STR["col_packaging"], STR["col_pallet_count"], STR["col_quantity"]]
    return df_agg.sort_values(STR["col_pallet_count"], ascending=False)


@st.cache_data
def build_stock_history(
    df: pd.DataFrame,
    selected_mandant: str,
    selected_artikel: list[str],
    start_date: datetime,
    end_date: datetime,
    show_cartons_only: bool = False,
) -> pd.DataFrame:
    # Builds a historical dataset of stock levels day by day.
    # Строит исторический набор данных об уровнях запасов день за днем.
    # Cached for performance.
    # Кэшируется для производительности.
    
    if df is None or df.empty:
        return pd.DataFrame()

    # Normalize dates to start of day.
    # Нормализация дат на начало дня.
    start_date = datetime.combine(start_date.date(), datetime.min.time())
    end_date = datetime.combine(end_date.date(), datetime.min.time())

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    days = (end_date - start_date).days + 1
    history_rows = []

    # Iterate through each day in the range.
    # Перебираем каждый день в диапазоне.
    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        
        # Filter stock for the specific day.
        # Фильтруем запасы для конкретного дня.
        df_day = filter_stock_df(
            df=df,
            selected_mandant=selected_mandant,
            selected_artikel=selected_artikel,
            selected_date=current_date,
        )

        if df_day.empty:
            total_pallets = 0
            cartons_count = 0
            other_count = 0
        else:
            # Optional: Filter for cartons only if requested.
            # Опционально: Фильтр только для картонов, если запрошено.
            if show_cartons_only:
                df_for_count = df_day[df_day["Opakowanie"] == "Kartony"].copy()
            else:
                df_for_count = df_day

            # Calculate counts.
            # Вычисляем количество.
            total_pallets = len(df_for_count)
            cartons_count = df_for_count[df_for_count["Opakowanie"] == "Kartony"].shape[0]
            other_count = df_for_count[df_for_count["Opakowanie"] != "Kartony"].shape[0]

        history_rows.append({
            "DATE": current_date.date(),
            "TOTAL_PALLETS": total_pallets,
            "CARTONS": cartons_count,
            "OTHER": other_count,
        })

    return pd.DataFrame(history_rows)


# --- Tab Rendering ---
# --- Рендеринг вкладки ---

def render_stock_tab(df, selected_mandant, selected_artikel, STR):
    # Renders the 'Stock Level' tab content.
    # Рендерит содержимое вкладки 'Уровень запасов'.
    
    st.header(STR["stock_tab"])
    st.markdown("---")
    st.subheader(STR["stock_filters_title"])

    # --- Filters Section ---
    # --- Секция фильтров ---
    col_stock_mandant, col_stock_date, col_stock_artikel = st.columns([1, 1.5, 2])

    with col_stock_mandant:
        available_mandants_stock = sorted(df["MANDANT"].astype(str).unique())
        selected_mandant_stock = st.selectbox(STR["mandant"], options=available_mandants_stock, index=0, key="stock_mandant_filter")

    with col_stock_date:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        stock_date = st.date_input(STR["stock_date_check"], value=yesterday, max_value=datetime.now().date(), key="stock_date_only")
        selected_date_stock = datetime.combine(stock_date, datetime.min.time())

    with col_stock_artikel:
        artikel_stock_options = sorted(df[df["MANDANT"].astype(str) == selected_mandant_stock]["ARTIKELNR"].dropna().unique().tolist())
        selected_artikel_stock = st.multiselect(STR["stock_articles"], options=artikel_stock_options, default=[], key="stock_artikel_filter")

    # Checkbox for showing only cartons (only for Mandant 352).
    # Чекбокс для показа только картонов (только для Mandant 352).
    if str(selected_mandant_stock) == "351":
        show_cartons_only = False
    else:
        show_cartons_only = st.checkbox(f"📦 {STR['checkbox_cartons_only']}", key="stock_cartons_only_new")

    st.markdown("---")

    # --- Data Processing ---
    # --- Обработка данных ---
    df_stock = filter_stock_df(df, selected_mandant_stock, selected_artikel_stock, selected_date_stock)

    if df_stock.empty:
        st.warning(STR["stock_no_pallets"])
        return

    if show_cartons_only:
        df_stock = df_stock[df_stock["Opakowanie"] == "Kartony"].copy()
        
    total_pallets = len(df_stock)

    # --- Metrics Display ---
    # --- Отображение метрик ---
    if str(selected_mandant_stock) == "351":
        m1, _, _, _ = st.columns(4)
        m1.metric(STR["metric_total_pallets"], f"{total_pallets:,}")
    else:
        cartons_count = df_stock[df_stock["Opakowanie"] == "Kartony"].shape[0]
        other_pkg_count = df_stock[df_stock["Opakowanie"] != "Kartony"].shape[0]
        m1, m2, m3, _ = st.columns(4)
        m1.metric(STR["metric_total_pallets"], f"{total_pallets:,}")
        m2.metric(STR["metric_cartons"], f"{cartons_count:,}")
        m3.metric(STR["metric_other_pkg"], f"{other_pkg_count:,}")
    
    st.markdown("---")

    # --- Detailed Table (PIDs) ---
    # --- Детальная таблица (PID) ---
    with st.expander(f"**{STR['stock_table_pids']}** ({total_pallets:,} {STR['suffix_pallets']})"):
        cols_pids = {
            "ARTIKELNR": STR["col_article"],
            "ARTBEZ1": STR["col_description"],
            "QUANTITY": STR["col_qty_per_pallet"],
            "LHMNR": STR["col_pid"],
            "PLATZ": STR["col_place"]
        }
        st.dataframe(df_stock[list(cols_pids.keys())].rename(columns=cols_pids), width="stretch", height=400, hide_index=True)

    # --- Aggregated Table ---
    # --- Агрегированная таблица ---
    df_agg = aggregate_stock_df(df_stock, STR)
    with st.expander(f"**{STR['stock_table_agg']}** ({len(df_agg):,} {STR['suffix_rows']})"):
        st.dataframe(df_agg, width="stretch", height=400, hide_index=True)


def render_stock_history(df, selected_mandant_stock, selected_artikel_stock, history_start, history_end, show_cartons_only, STR, widget_prefix: str = ""):
    # Renders the stock history chart.
    # Рендерит график истории запасов.
    
    st.subheader(STR["history_header"])

    # 1. Get historical data.
    # 1. Получение исторических данных.
    history_df = build_stock_history(
        df=df,
        selected_mandant=selected_mandant_stock,
        selected_artikel=selected_artikel_stock or [],
        start_date=datetime.combine(history_start, datetime.min.time()),
        end_date=datetime.combine(history_end, datetime.min.time()),
        show_cartons_only=show_cartons_only,
    )

    if history_df is not None and not history_df.empty:
        # --- STRICT DATA CLEANING BEFORE PLOTTING ---
        # --- СТРОГАЯ ОЧИСТКА ДАННЫХ ПЕРЕД ПОСТРОЕНИЕМ ГРАФИКА ---
        plot_df = history_df.copy()
        
        for col in ["TOTAL_PALLETS", "CARTONS", "OTHER"]:
            if col in plot_df.columns:
                # Step A: Convert everything to string.
                # Шаг А: Конвертируем все в строку.
                # Step B: Remove commas (thousand separators).
                # Шаг Б: Удаляем запятые (разделители тысяч).
                # Step C: Convert to number (float).
                # Шаг В: Конвертируем в число (float).
                plot_df[col] = (
                    plot_df[col]
                    .astype(str)
                    .str.replace(',', '', regex=False)
                    .pipe(pd.to_numeric, errors='coerce')
                )
        
        # Ensure date format.
        # Обеспечиваем формат даты.
        plot_df["DATE"] = pd.to_datetime(plot_df["DATE"])
        plot_df = plot_df.sort_values("DATE")

        # 2. Series selection checkboxes.
        # 2. Чекбоксы выбора серий.
        col1, col2, col3 = st.columns(3)
        with col1:
            show_total = st.checkbox(STR["history_show_total"], value=True, key=f"{widget_prefix}h_total")
        
        show_cart = False
        show_other = False
        if str(selected_mandant_stock) != "351":
            with col2:
                show_cart = st.checkbox(STR["history_show_cartons"], value=True, key=f"{widget_prefix}h_cart")
            with col3:
                show_other = st.checkbox(STR["history_show_other"], value=False, key=f"{widget_prefix}h_other")

        # 3. Create chart via go.Figure.
        # 3. Создаем график через go.Figure.
        fig = go.Figure()

        if show_total and "TOTAL_PALLETS" in plot_df.columns:
            # Use .tolist() so Plotly doesn't read DataFrame indices.
            # Используем .tolist(), чтобы Plotly не читал индексы DataFrame.
            fig.add_trace(go.Scatter(
                x=plot_df["DATE"].tolist(),
                y=plot_df["TOTAL_PALLETS"].tolist(),
                name=STR["chart_total_label"],
                mode='lines+markers',
                line=dict(color='#0078D4', width=3),
                hovertemplate=f"{STR['chart_hover_date']}: %{{x}}<br>{STR['chart_hover_sum']}: %{{y:,.0f}}<extra></extra>"
            ))

        if show_cart and "CARTONS" in plot_df.columns:
            fig.add_trace(go.Scatter(
                x=plot_df["DATE"].tolist(),
                y=plot_df["CARTONS"].tolist(),
                name=STR["chart_cartons_label"],
                mode='lines+markers',
                line=dict(color='#E74C3C', width=2),
                hovertemplate=f"{STR['chart_hover_date']}: %{{x}}<br>{STR['chart_hover_cartons']}: %{{y:,.0f}}<extra></extra>"
            ))

        # 4. Axis configuration (important!).
        # 4. Настройка осей (важно!).
        fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            xaxis=dict(type='date', showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            yaxis=dict(
                title=STR["chart_y_axis"],
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                rangemode="tozero", # Y axis always from 0 / Ось Y всегда от 0
                tickformat=".0f"    # Remove decimals on axis / Убираем десятичные знаки на оси
            ),
            height=500,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, width="stretch")
    else:
        st.info(STR["history_no_data"])