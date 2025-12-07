# modules/stock.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta # timedelta для yesterday
import numpy as np
from modules.ui_strings import STR
from modules.display_main import classify_pallet 
from utils import load_packaging_config

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

    # 🎯 ШАГ 1.5: ✅ ФИЛЬТР ZUSTAND (только паллеты НА СКЛАДЕ)
    zustand_stock = ["401", "460"]
    df_filtered = df_filtered[
        df_filtered["ZUSTAND"].astype(str).isin(zustand_stock)
    ].copy()

    # 🎯 ШАГ 1.7: ✅ ФИЛЬТР PLATZ (НАЧИНАЕТСЯ с BL*, WE*, WA01*, 02*, 2*)
    platz_prefixes = ["BL", "WE", "WA", "02", "2"]
    df_filtered["PLATZ_UPPER"] = df_filtered["PLATZ"].fillna("").astype(str).str.upper()

    # Создаём маску: PLATZ начинается с любого из префиксов
    mask_platz = False
    for prefix in platz_prefixes:
        mask_platz |= df_filtered["PLATZ_UPPER"].str.startswith(prefix)

    df_filtered = df_filtered[mask_platz].copy()
    df_filtered = df_filtered.drop("PLATZ_UPPER", axis=1)
    
    # 🎯 ШАГ 2: СТРОГАЯ ФИЛЬТРАЦИЯ ПО ДАТЕ
    # IN_DATE < дата (принята ДО начала дня)
    mask_in = df_filtered["IN_DATE"].dt.date < selected_date.date()
    
    # OUT_DATE пустой ИЛИ >= дата (не удалена К началу дня)
    mask_out = (
        df_filtered["OUT_DATE"].isnull() | 
        (df_filtered["OUT_DATE"].dt.date >= selected_date.date())
    )
    
    df_stock_raw = df_filtered[mask_in & mask_out].copy()

    # 🔍 Диагностика: сколько PID имеют >1 записи после фильтра по дате
    dup_lhmnr = df_stock_raw["LHMNR"].value_counts()
    multi_lhmnr_count = (dup_lhmnr > 1).sum()



    
    # 🎯 ШАГ 3: ✅ ДЕДУПЛИКАЦИЯ ПО LHMNR (каждый PID только 1 раз!)
    # Берем САМУЮ ПОЗДНЮЮ запись для каждого PID
    df_stock = df_stock_raw.sort_values("IN_DATE", ascending=False).drop_duplicates(
        subset=["LHMNR"], keep="first"
    )
    
    # 🎯 ШАГ 4: Фильтр артикулов (после дедупликации)
    if selected_artikel:
        artikel_list = [a.strip().upper() for a in selected_artikel]
        df_stock = df_stock[df_stock["ARTIKELNR"].isin(artikel_list)].copy()
        st.info(f"📊 После фильтра статьи: **{len(df_stock):,}** строк")
    
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
    """
    Группировка по артикулу, описанию и типу упаковки, подсчет паллет/штук.
    """
    if df_stock.empty:
        return pd.DataFrame()
        
    df_agg = df_stock.groupby(["ARTIKELNR", "ARTBEZ1", "Opakowanie"], dropna=False).agg(
        Ilość_palet=("LHMNR", "count"),
        Ilość_sztuk=("QUANTITY", "sum")
    ).reset_index()

    # Переименование для финальной таблицы
    df_agg.columns = [
        "Artykuł", 
        "Opis artykułu", 
        "Opakowanie",
        "Ilość palet", 
        "Ilość sztuk"
    ]
    
    # Сортировка по количеству паллет
    return df_agg.sort_values("Ilość palet", ascending=False)

# --- Рендеринг вкладки ---

def render_stock_tab(df, selected_mandant, selected_artikel, STR):
    """
    Основная функция рендеринга вкладки Stany magazynowe.
    """
    st.header(STR["stock_tab"])

    # =======================
    # 👉 НОВЫЕ НЕЗАВИСИМЫЕ ФИЛЬТРЫ ДЛЯ СКЛАДА
    # =======================
    st.markdown("---")
    st.subheader("🔍 Filtry dla stanów magazynowych")

    # Создаём 3 колонки для фильтров склада
    col_stock_mandant, col_stock_date, col_stock_artikel = st.columns([1, 1.5, 2])

    # 1. Mandant (независимый от sidebar)
    with col_stock_mandant:
        available_mandants_stock = sorted(df["MANDANT"].astype(str).unique())
        selected_mandant_stock = st.selectbox(
            "Mandant", 
            options=available_mandants_stock, 
            index=0,
            key="stock_mandant_filter"
        )

    # 2. Только дата (убрали zakres dat)
    with col_stock_date:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        stock_date = st.date_input(
            "Data sprawdzenia stanów", 
            value=yesterday,
            max_value=datetime.now().date(),
            key="stock_date_only"
        )
        selected_date_stock = datetime.combine(stock_date, datetime.min.time())

    # 3. Artikel фильтр (независимый)
    with col_stock_artikel:
        # Только статьи для выбранного mandant
        artikel_stock_options = sorted(
            df[df["MANDANT"].astype(str) == selected_mandant_stock]["ARTIKELNR"]
            .dropna().unique().tolist()
        )
        selected_artikel_stock = st.multiselect(
            "Artykuły", 
            options=artikel_stock_options,
            default=[],
            key="stock_artikel_filter"
        )

    # Чекбокс "только картоны" (остаётся)
    show_cartons_only = st.checkbox("📦 Pokaż tylko kartony", key="stock_cartons_only_new")

    st.markdown("---")

    # ✅ Теперь используем НАШИ локальные фильтры
    df_stock = filter_stock_df(
        df,                          # полный df
        selected_mandant_stock,      # 👉 наш mandant
        selected_artikel_stock,      # 👉 наши статьи  
        selected_date_stock          # 👉 наша дата
    )

    if df_stock.empty:
        st.warning(f"Brak palet na magazynie zgodnie z filtrem Mandant={selected_mandant}, Artykuł={selected_artikel if selected_artikel else 'Wszystkie'} i datą {selected_date.strftime('%d.%m.%Y')}.")
        return

    # Применение фильтра "только картоны"
    if show_cartons_only:
        df_stock = df_stock[df_stock["Opakowanie"] == "Kartony"].copy()
        
    # 4. Вывод Метрик
    total_pallets = len(df_stock)
    cartons_count = df_stock[df_stock["Opakowanie"] == "Kartony"].shape[0]
    # Используем `!= 'Kartony'` для подсчета всего остального, что не является картоном (включая Palety/ramy и Inne)
    other_pkg_count = df_stock[df_stock["Opakowanie"] != "Kartony"].shape[0]
    
    st.markdown("---")
    m1, m2, m3, _ = st.columns(4)
    m1.metric(STR["metric_total_pallets"], f"{total_pallets:,}")
    m2.metric(STR["metric_cartons"], f"{cartons_count:,}")
    m3.metric(STR["metric_other_pkg"], f"{other_pkg_count:,}")
    st.markdown("---")

    # 5. Первая таблица (детальная)
    with st.expander(f"**{STR['stock_table_pids']}** ({total_pallets:,} palet)"):
        cols_pids = {
            "ARTIKELNR": "Artykuł",
            "ARTBEZ1": "Opis artykułu",
            "QUANTITY": "Ilość na palecie",
            "LHMNR": "PID",
            "PLATZ": "Miejsce",
            "CHARGE1": "Dodatkowy opis",
            "IN_DATE": "IN_DATE",
            "Opakowanie": "Opakowanie"
        }
        
        # Выбираем и переименовываем колонки для отображения
        df_display_pids = df_stock[cols_pids.keys()].rename(columns=cols_pids)

        st.dataframe(
            df_display_pids,
            use_container_width=True,
            height=800, 
            hide_index=True
        )

    # 6. Вторая таблица (агрегат)
    df_agg = aggregate_stock_df(df_stock)

    with st.expander(f"**{STR['stock_table_agg']}** ({len(df_agg):,} wierszy)"):
        st.dataframe(
            df_agg,
            use_container_width=True,
            height=800,
            hide_index=True
        )

    # 7. Предупреждение
    st.markdown("---")
    st.markdown(f'<div class="small-note">{STR["stock_warning"]}</div>', unsafe_allow_html=True)