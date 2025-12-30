# modules/stock.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from modules.ui_strings import STR
from utils import load_packaging_config, classify_pallet


# --- Логика фильтрации ---

def filter_stock_df(df, selected_mandant, selected_artikel, selected_date):
    """
    ✅ СТРОГАЯ ФИЛЬТРАЦИЯ складских остатков на начало дня
    Логика: IN_DATE < дата И (OUT_DATE пустой ИЛИ OUT_DATE >= дата)
    + ДЕДУПЛИКАЦИЯ по LHMNR (каждый PID только 1 раз)
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # 🎯 ШАГ 1: Базовый фильтр mandant
    df_filtered = df[df["MANDANT"].astype(str) == selected_mandant].copy()

    # 🎯 ШАГ 2: СТРОГАЯ ФИЛЬТРАЦИЯ ПО ДАТЕ
    mask_in = df_filtered["IN_DATE"].dt.date < selected_date.date()
    
    # Статус 401 (на складе) или удалена позже выбранной даты
    mask_is_401 = df_filtered["ZUSTAND"].astype(str) == "401"
    mask_removed_later = df_filtered["OUT_DATE"].dt.date >= selected_date.date()
    
    mask_out_logic = mask_is_401 | mask_removed_later
    
    df_stock_raw = df_filtered[mask_in & mask_out_logic].copy()
        
    # 🎯 ШАГ 3: ДЕДУПЛИКАЦИЯ ПО LHMNR
    df_stock = df_stock_raw.sort_values("IN_DATE", ascending=False).drop_duplicates(
        subset=["LHMNR"], keep="first"
    )
    
    # 🎯 ШАГ 4: Фильтр артикулов
    if selected_artikel:
        artikel_list = [a.strip().upper() for a in selected_artikel]
        df_stock = df_stock[df_stock["ARTIKELNR"].isin(artikel_list)].copy()

    # 🎯 ШАГ 5: Классификация упаковки
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


# --- Логика агрегации ---

def aggregate_stock_df(df_stock):
    if df_stock.empty:
        return pd.DataFrame()
        
    df_agg = df_stock.groupby(["ARTIKELNR", "ARTBEZ1", "Opakowanie"], dropna=False).agg(
        Ilość_palet=("LHMNR", "count"),
        Ilość_sztuk=("QUANTITY", "sum")
    ).reset_index()

    df_agg.columns = ["Artykuł", "Opis artykułu", "Opakowanie", "Ilość palet", "Ilość sztuk"]
    return df_agg.sort_values("Ilość palet", ascending=False)


@st.cache_data
def build_stock_history(
    df: pd.DataFrame,
    selected_mandant: str,
    selected_artikel: list[str],
    start_date: datetime,
    end_date: datetime,
    show_cartons_only: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    start_date = datetime.combine(start_date.date(), datetime.min.time())
    end_date = datetime.combine(end_date.date(), datetime.min.time())

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    days = (end_date - start_date).days + 1
    history_rows = []

    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
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
            if show_cartons_only:
                df_for_count = df_day[df_day["Opakowanie"] == "Kartony"].copy()
            else:
                df_for_count = df_day

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


# --- Рендеринг вкладки ---

def render_stock_tab(df, selected_mandant, selected_artikel, STR):
    st.header(STR["stock_tab"])
    st.markdown("---")
    st.subheader("🔍 Filtry dla stanów magazynowych")

    col_stock_mandant, col_stock_date, col_stock_artikel = st.columns([1, 1.5, 2])

    with col_stock_mandant:
        available_mandants_stock = sorted(df["MANDANT"].astype(str).unique())
        selected_mandant_stock = st.selectbox("Mandant", options=available_mandants_stock, index=0, key="stock_mandant_filter")

    with col_stock_date:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        stock_date = st.date_input("Data sprawdzenia stanów", value=yesterday, max_value=datetime.now().date(), key="stock_date_only")
        selected_date_stock = datetime.combine(stock_date, datetime.min.time())

    with col_stock_artikel:
        artikel_stock_options = sorted(df[df["MANDANT"].astype(str) == selected_mandant_stock]["ARTIKELNR"].dropna().unique().tolist())
        selected_artikel_stock = st.multiselect("Artykuły", options=artikel_stock_options, default=[], key="stock_artikel_filter")

    if str(selected_mandant_stock) == "351":
        show_cartons_only = False
    else:
        show_cartons_only = st.checkbox("📦 Pokaż tylko kartony", key="stock_cartons_only_new")

    st.markdown("---")

    df_stock = filter_stock_df(df, selected_mandant_stock, selected_artikel_stock, selected_date_stock)

    if df_stock.empty:
        st.warning(f"Brak palet na magazynie.")
        return

    if show_cartons_only:
        df_stock = df_stock[df_stock["Opakowanie"] == "Kartony"].copy()
        
    total_pallets = len(df_stock)

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

    with st.expander(f"**{STR['stock_table_pids']}** ({total_pallets:,} palet)"):
        cols_pids = {"ARTIKELNR": "Artykuł", "ARTBEZ1": "Opis artykułu", "QUANTITY": "Ilość na palecie", "LHMNR": "PID", "PLATZ": "Miejsce"}
        st.dataframe(df_stock[list(cols_pids.keys())].rename(columns=cols_pids), width="stretch", height=400, hide_index=True)

    df_agg = aggregate_stock_df(df_stock)
    with st.expander(f"**{STR['stock_table_agg']}** ({len(df_agg):,} wierszy)"):
        st.dataframe(df_agg, width="stretch", height=400, hide_index=True)


def render_stock_history(df, selected_mandant_stock, selected_artikel_stock, history_start, history_end, show_cartons_only, STR, widget_prefix: str = ""):
    st.subheader("📈 Historia liczby palet na magazynie")

    # 1. Получаем данные
    history_df = build_stock_history(
        df=df,
        selected_mandant=selected_mandant_stock,
        selected_artikel=selected_artikel_stock or [],
        start_date=datetime.combine(history_start, datetime.min.time()),
        end_date=datetime.combine(history_end, datetime.min.time()),
        show_cartons_only=show_cartons_only,
    )

    if history_df is not None and not history_df.empty:
        # --- ЖЕСТКАЯ ОЧИСТКА ДАННЫХ ПЕРЕД ГРАФИКОМ ---
        plot_df = history_df.copy()
        
        for col in ["TOTAL_PALLETS", "CARTONS", "OTHER"]:
            if col in plot_df.columns:
                # Шаг А: Превращаем всё в строку
                # Шаг Б: Убираем запятые (разделители тысяч)
                # Шаг В: Превращаем в число (float)
                plot_df[col] = (
                    plot_df[col]
                    .astype(str)
                    .str.replace(',', '', regex=False)
                    .pipe(pd.to_numeric, errors='coerce')
                )
        
        # Гарантируем формат даты
        plot_df["DATE"] = pd.to_datetime(plot_df["DATE"])
        plot_df = plot_df.sort_values("DATE")

        # 2. Выбор серий
        col1, col2, col3 = st.columns(3)
        with col1:
            show_total = st.checkbox("Pokaż łączną liczbę palet", value=True, key=f"{widget_prefix}h_total")
        
        show_cart = False
        show_other = False
        if str(selected_mandant_stock) != "351":
            with col2:
                show_cart = st.checkbox("Pokaż kartony", value=True, key=f"{widget_prefix}h_cart")
            with col3:
                show_other = st.checkbox("Pokaż inne opakowania", value=False, key=f"{widget_prefix}h_other")

        # 3. Создаем график через go.Figure
        fig = go.Figure()

        if show_total and "TOTAL_PALLETS" in plot_df.columns:
            # Используем .tolist(), чтобы Plotly не мог прочитать индексы DataFrame
            fig.add_trace(go.Scatter(
                x=plot_df["DATE"].tolist(),
                y=plot_df["TOTAL_PALLETS"].tolist(),
                name="Suma wszystkich palet",
                mode='lines+markers',
                line=dict(color='#0078D4', width=3),
                hovertemplate="Data: %{x}<br>Suma: %{y:,.0f}<extra></extra>"
            ))

        if show_cart and "CARTONS" in plot_df.columns:
            fig.add_trace(go.Scatter(
                x=plot_df["DATE"].tolist(),
                y=plot_df["CARTONS"].tolist(),
                name="Tylko kartony",
                mode='lines+markers',
                line=dict(color='#E74C3C', width=2),
                hovertemplate="Data: %{x}<br>Kartony: %{y:,.0f}<extra></extra>"
            ))

        # 4. Настройка осей (важно!)
        fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            xaxis=dict(type='date', showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            yaxis=dict(
                title="Liczba palet",
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                rangemode="tozero", # Ось Y всегда от 0
                tickformat=".0f"    # Убираем дробные значения на оси
            ),
            height=500,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Brak danych do wyświetlenia historii.")