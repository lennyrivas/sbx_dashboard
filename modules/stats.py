# modules/stats.py
# Logic for the 'Statistics' tab: historical charts and monthly reports.
# Логика для вкладки 'Статистика': исторические графики и ежемесячные отчеты.

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Import function already present in stock.py to reuse chart rendering logic.
# Импортируем функцию, уже присутствующую в stock.py, для повторного использования логики отрисовки графиков.
from modules.stock import render_stock_history
from utils import load_packaging_config



def render_stats_tab(df, STR):
    # Renders the 'Statistics' tab content.
    # Рендерит содержимое вкладки 'Статистика'.
    # Includes: Stock history chart, Monthly report, Top 5 rankings, Stagnant stock.
    # Включает: График истории запасов, Ежемесячный отчет, Рейтинги Топ-5, Залежавшиеся запасы.
    
    # --- Header ---
    # --- Заголовок ---
    st.header(STR["stats_header"])

    # Get available mandants (clients) from the data.
    # Получаем доступных мандантов (клиентов) из данных.
    available_mandants = sorted(df["MANDANT"].unique())
    if not available_mandants:
        st.warning(STR["stats_no_data_warning"])
        return

    # --- Section 1: Stock History Chart ---
    # --- Секция 1: График истории запасов ---
    with st.expander(STR["history_header"], expanded=False):
        # Layout: Mandant | Date From | Date To (in one row).
        # Макет: Мандант | Дата От | Дата До (в одной строке).
        col_mandant, col_from, col_to = st.columns([1, 1, 1])

        # Check again if mandants exist (defensive programming).
        # Еще раз проверяем, существуют ли манданты (защитное программирование).
        if not available_mandants:
            st.warning(STR["stats_no_data_warning"])
            return

        # Mandant selector for the chart.
        # Селектор манданта для графика.
        with col_mandant:
            selected_mandant_stock = st.selectbox(
                STR["mandant"],
                options=available_mandants,
                index=0,
                key="stats_history_mandant",
            )

        # Calculate default date range (last 30 days).
        # Вычисляем диапазон дат по умолчанию (последние 30 дней).
        min_date = df["IN_DATE"].min().date()
        max_date = df["IN_DATE"].max().date()
        yesterday = (datetime.now() - timedelta(days=1)).date()

        raw_default_start = (yesterday - timedelta(days=29))
        default_start = max(min_date, min(raw_default_start, max_date))
        default_end = max(min_date, min(yesterday, max_date))

        # Date pickers.
        # Выбор дат.
        with col_from:
            history_start = st.date_input(
                STR["from"],
                value=default_start,
                min_value=min_date,
                max_value=max_date,
                key="stats_history_start",
            )

        with col_to:
            history_end = st.date_input(
                STR["to"],
                value=default_end,
                min_value=history_start,
                max_value=max_date,
                key="stats_history_end",
            )

        # Filter article options based on the selected mandant.
        # Фильтруем опции артикулов на основе выбранного манданта.
        # Optimization: use .loc for faster filtering.
        mask_mandant = df["MANDANT"] == selected_mandant_stock
        artikel_options = sorted(
            df.loc[mask_mandant, "ARTIKELNR"]
            .dropna()
            .unique()
            .tolist()
        )

        # Article multiselect for chart filtering.
        # Мультивыбор артикулов для фильтрации графика.
        selected_artikel_stock = st.multiselect(
            STR["stats_history_articles_filter"],
            options=artikel_options,
            default=[],
            key="stats_history_artikel",
        )

        show_cartons_only = False

        # Render the chart using the shared function from stock.py.
        # Рендерим график, используя общую функцию из stock.py.
        render_stock_history(
            df=df,
            selected_mandant_stock=selected_mandant_stock,
            selected_artikel_stock=selected_artikel_stock,
            history_start=history_start,
            history_end=history_end,
            show_cartons_only=show_cartons_only,
            STR=STR,
            widget_prefix="stats_",
        )

    # --- Section 2: Monthly Report & Rankings ---
    # --- Секция 2: Ежемесячный отчет и рейтинги ---
    st.markdown("---")
    st.header(STR["stats_monthly_report_header"])

    # Global mandant selection for the statistics below.
    # Глобальный выбор манданта для статистики ниже.
    col_m_stats, _ = st.columns([1, 3])
    with col_m_stats:
        stats_mandant = st.selectbox(
            STR["stats_select_mandant_detail"],
            options=available_mandants,
            index=0,
            key="stats_general_mandant"
        )

    # Filter data for the selected mandant.
    # Фильтруем данные для выбранного манданта.
    df_stats = df[df["MANDANT"] == stats_mandant].copy()

    # Load packaging configuration (to identify cartons).
    # Загружаем конфигурацию упаковки (для идентификации картонов).
    kartony_prefixes, other_prefixes = load_packaging_config()

    # --- Subsection 2.1: Month Comparison ---
    # --- Подсекция 2.1: Сравнение месяцев ---
    st.subheader(STR["stats_month_comparison_header"])
    
    # Calculate date ranges for current and previous month.
    # Вычисляем диапазоны дат для текущего и предыдущего месяца.
    now = datetime.now()
    curr_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_end = curr_month_start - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Create masks for IN_DATE (Receipts).
    # Создаем маски для IN_DATE (Поступления).
    mask_curr_in = df_stats["IN_DATE"] >= curr_month_start
    mask_prev_in = (df_stats["IN_DATE"] >= prev_month_start) & (df_stats["IN_DATE"] < curr_month_start)

    # Create masks for OUT_DATE (Removals).
    # Valid removal: ZUSTAND != 401 (not in stock) and OUT_DATE exists.
    # Создаем маски для OUT_DATE (Удаления).
    # Валидное удаление: ZUSTAND != 401 (не на складе) и OUT_DATE существует.
    mask_out_valid = (df_stats["ZUSTAND"] != "401") & (df_stats["OUT_DATE"].notna())
    mask_curr_out = mask_out_valid & (df_stats["OUT_DATE"] >= curr_month_start)
    mask_prev_out = mask_out_valid & (df_stats["OUT_DATE"] >= prev_month_start) & (df_stats["OUT_DATE"] < curr_month_start)

    # Add a helper column to identify cartons.
    # Добавляем вспомогательную колонку для идентификации картонов.
    df_stats["IsCarton"] = df_stats["ARTIKELNR"].str.startswith(tuple(kartony_prefixes), na=False)

    # Calculate metrics.
    # Вычисляем метрики.
    c1, c2, c3, c4 = st.columns(4)
    
    # Receipts metrics.
    # Метрики поступлений.
    curr_in = mask_curr_in.sum()
    prev_in = mask_prev_in.sum()
    curr_in_cart = df_stats[mask_curr_in & df_stats["IsCarton"]].shape[0]
    prev_in_cart = df_stats[mask_prev_in & df_stats["IsCarton"]].shape[0]

    c1.metric(STR["stats_metric_received_month"], f"{curr_in}", f"{curr_in - prev_in}")
    c2.metric(STR["stats_metric_received_cartons"], f"{curr_in_cart}", f"{curr_in_cart - prev_in_cart}")

    # Removals metrics.
    # Метрики удалений.
    curr_out = mask_curr_out.sum()
    prev_out = mask_prev_out.sum()
    curr_out_cart = df_stats[mask_curr_out & df_stats["IsCarton"]].shape[0]
    prev_out_cart = df_stats[mask_prev_out & df_stats["IsCarton"]].shape[0]

    c3.metric(STR["stats_metric_deleted_month"], f"{curr_out}", f"{curr_out - prev_out}")
    c4.metric(STR["stats_metric_deleted_cartons"], f"{curr_out_cart}", f"{curr_out_cart - prev_out_cart}")

    st.markdown("---")

    # --- Subsection 2.2: Top 5 Rankings ---
    # --- Подсекция 2.2: Рейтинги Топ-5 ---
    st.subheader(STR["stats_top5_header"])
    
    # Period selector for rankings.
    # Селектор периода для рейтингов.
    period_opts = {
        STR["period_last_week"]: 7,
        STR["period_last_month"]: 30,
        STR["period_last_3_months"]: 90,
        STR["period_last_year"]: 365
    }
    selected_period = st.selectbox(STR["stats_select_period"], options=list(period_opts.keys()), index=1)
    days_back = period_opts[selected_period]
    cutoff_date = now - timedelta(days=days_back)

    col_top_out, col_top_in = st.columns(2)

    with col_top_out:
        # Top 5 Sent (Removed).
        # Топ-5 Отправленных (Удаленных).
        st.markdown(f"**{STR['stats_top_sent']}**")
        mask_top_out = mask_out_valid & (df_stats["OUT_DATE"] >= cutoff_date)
        top_out = df_stats[mask_top_out]["ARTIKELNR"].value_counts().head(5).reset_index()
        top_out.columns = [STR["col_article"], STR["col_pallet_count"]]
        st.dataframe(
            top_out,
            width="stretch",
            hide_index=True,
            height=250,
            column_config={
                STR["col_article"]: st.column_config.TextColumn(width="medium"),
                STR["col_pallet_count"]: st.column_config.NumberColumn(width="small"),
            }
        )

    with col_top_in:
        # Top 5 Received.
        # Топ-5 Принятых.
        st.markdown(f"**{STR['stats_top_received']}**")
        mask_top_in = df_stats["IN_DATE"] >= cutoff_date
        top_in = df_stats[mask_top_in]["ARTIKELNR"].value_counts().head(5).reset_index()
        top_in.columns = [STR["col_article"], STR["col_pallet_count"]]
        st.dataframe(
            top_in,
            width="stretch",
            hide_index=True,
            height=250,
            column_config={
                STR["col_article"]: st.column_config.TextColumn(width="medium"),
                STR["col_pallet_count"]: st.column_config.NumberColumn(width="small"),
            }
        )

    st.markdown("---")

    # --- Subsection 2.3: Stagnant Stock ---
    # --- Подсекция 2.3: Залежавшиеся запасы ---
    col_h_old, col_sel_old, _ = st.columns([0.25, 0.15, 0.6])
    with col_h_old:
        st.subheader(STR["stats_stagnant_header"])
    with col_sel_old:
        period_options = {
            STR["period_5_years"]: 365 * 5,
            STR["period_3_years"]: 365 * 3,
            STR["period_1_year"]: 365,
            STR["period_6_months"]: 180
        }
        selected_period_label = st.selectbox(
            STR["stats_select_period"],
            options=list(period_options.keys()),
            index=2,  # Default "1 rok"
            label_visibility="collapsed",
            key="stats_old_stock_period"
        )

    days_threshold = period_options[selected_period_label]
    
    # Filter current stock (ZUSTAND 401).
    # Фильтруем текущие запасы (ZUSTAND 401).
    stock_now = df_stats[df_stats["ZUSTAND"] == "401"].copy()
    if not stock_now.empty:
        # Identify old stock based on IN_DATE.
        # Идентифицируем старые запасы на основе IN_DATE.
        threshold_date = now - timedelta(days=days_threshold)
        old_stock = stock_now[stock_now["IN_DATE"] < threshold_date].copy()
        
        count_old = len(old_stock)
        total_stock = len(stock_now)
        pct_old = (count_old / total_stock * 100) if total_stock > 0 else 0
        
        # Display metric.
        # Отображаем метрику.
        c_old1, c_old2 = st.columns(2)
        c_old1.metric(STR["stats_metric_old_pallets"].format(period=selected_period_label), f"{count_old}", f"{pct_old:.1f}{STR['stats_suffix_total']}")
        
        if count_old > 0:
            # Show detailed list of stagnant pallets.
            # Показываем подробный список залежавшихся паллет.
            with st.expander(STR["stats_show_stagnant_list"]):
                old_stock[STR["col_days_in_stock"]] = (now - old_stock["IN_DATE"]).dt.days
                show_cols = ["ARTIKELNR", "ARTBEZ1", "LHMNR", "IN_DATE", STR["col_days_in_stock"], "PLATZ"]
                
                # Rename columns for display.
                # Переименовываем колонки для отображения.
                rename_map = {
                    "ARTIKELNR": STR["col_article"],
                    "ARTBEZ1": STR["col_description"],
                    "LHMNR": STR["col_pid"],
                    "IN_DATE": STR["col_in_date"],
                    "PLATZ": STR["col_place"]
                }
                
                st.dataframe(
                    old_stock[show_cols].rename(columns=rename_map).sort_values(STR["col_in_date"]),
                    width="stretch",
                    hide_index=True
                )
    else:
        st.info(STR["stats_no_stock"])


    show_cartons_only = False