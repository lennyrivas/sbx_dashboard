# modules/stock.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta # timedelta для yesterday
import numpy as np
from modules.ui_strings import STR
from modules.display_main import classify_pallet 
from utils import load_packaging_config

# --- Логика фильтрации ---

def filter_stock_df(df, selected_mandant, selected_artikel, selected_date, debug=False):
    """
    ✅ СТРОГАЯ ФИЛЬТРАЦИЯ складских остатков на начало дня
    Логика: IN_DATE < дата И (OUT_DATE пустой ИЛИ OUT_DATE >= дата)
    + ДЕДУПЛИКАЦИЯ по LHMNR (каждый PID только 1 раз)
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    if debug:
        st.markdown(f"### 🐞 DEBUG: Analiza na dzień {selected_date.strftime('%d.%m.%Y')}")
        st.info(f"**START**: Całkowita liczba wierszy w pliku: {len(df)}")

    # 🎯 ШАГ 1: Базовый фильтр mandant
    df_filtered = df[df["MANDANT"].astype(str) == selected_mandant].copy()
    
    if debug:
        st.write(f"1️⃣ **Filtr Mandant ({selected_mandant})**: {len(df_filtered)} wierszy")

    # 🎯 ШАГ 2: СТРОГАЯ ФИЛЬТРАЦИЯ ПО ДАТЕ
    # 1. IN_DATE < дата (Strictly less: принята ДО начала дня 00:00)
    mask_in = df_filtered["IN_DATE"].dt.date < selected_date.date()
    
    # 2. Логика присутствия (mask_out)
    # Пользователь: "Статус на складе = zustand 401. Если Zustand отличается, значит паллеты уже нет."
    # "Если zustand != 401, то дата удаления вписана в ячейке Bewegung am (OUT_DATE)."
    
    # A) Паллета имеет статус 401 (она на складе). OUT_DATE игнорируем (это дата движения).
    mask_is_401 = df_filtered["ZUSTAND"].astype(str) == "401"
    
    # B) Паллета имеет другой статус (удалена), НО дата удаления >= selected_date.
    mask_removed_later = df_filtered["OUT_DATE"].dt.date >= selected_date.date()
    
    mask_out_logic = mask_is_401 | mask_removed_later
    
    df_stock_raw = df_filtered[mask_in & mask_out_logic].copy()
    
    if debug:
        st.write(f"2️⃣ **Filtr Daty**: {len(df_stock_raw)} wierszy")
        st.caption(f"Warunek: IN_DATE < {selected_date.date()} ORAZ (ZUSTAND == 401 LUB OUT_DATE >= {selected_date.date()})")
        
        dropped = df_filtered[~(mask_in & mask_out_logic)]
        if not dropped.empty:
            with st.expander("❌ Przykłady odrzuconych wierszy (krok 2)"):
                st.dataframe(dropped[["LHMNR", "IN_DATE", "OUT_DATE", "ZUSTAND"]].head(10))

    # 🎯 ШАГ 3: ✅ ДЕДУПЛИКАЦИЯ ПО LHMNR (каждый PID только 1 раз!)
    # Берем САМУЮ ПОЗДНЮЮ запись для каждого PID
    df_stock = df_stock_raw.sort_values("IN_DATE", ascending=False).drop_duplicates(
        subset=["LHMNR"], keep="first"
    )
    
    if debug:
        st.write(f"3️⃣ **Deduplikacja LHMNR**: {len(df_stock)} wierszy")
        st.caption("Zostawiamy tylko najnowszy wpis (wg IN_DATE) dla każdego LHMNR.")

    # 🎯 ШАГ 4: Фильтр артикулов (после дедупликации)
    if selected_artikel:
        artikel_list = [a.strip().upper() for a in selected_artikel]
        df_stock = df_stock[df_stock["ARTIKELNR"].isin(artikel_list)].copy()
        if debug:
            st.write(f"4️⃣ **Filtr Artykułów**: {len(df_stock)} wierszy")

    
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


@st.cache_data
def build_stock_history(
    df: pd.DataFrame,
    selected_mandant: str,
    selected_artikel: list[str],
    start_date: datetime,
    end_date: datetime,
    show_cartons_only: bool = False,
) -> pd.DataFrame:
    """
    Строит историю количества палет на складе по дням.

    На каждый день в диапазоне [start_date, end_date] применяет
    уже существующую логику filter_stock_df и считает:
    - общее количество палет
    - количество картонных палет
    - количество прочих палет

    Возвращает DataFrame с колонками:
    - DATE
    - TOTAL_PALLETS
    - CARTONS
    - OTHER
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Нормализуем даты (обнуляем время)
    start_date = datetime.combine(start_date.date(), datetime.min.time())
    end_date = datetime.combine(end_date.date(), datetime.min.time())

    # На всякий случай гарантируем, что start_date <= end_date
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    days = (end_date - start_date).days + 1
    history_rows = []

    for offset in range(days):
        current_date = start_date + timedelta(days=offset)

        # Используем твою готовую функцию фильтрации
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

        history_rows.append(
            {
                "DATE": current_date.date(),
                "TOTAL_PALLETS": total_pallets,
                "CARTONS": cartons_count,
                "OTHER": other_count,
            }
        )

    history_df = pd.DataFrame(history_rows)
    return history_df





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

# Чекбокс "tylko kartony" – tylko dla mandanta != 351
    if str(selected_mandant_stock) == "351":
        show_cartons_only = False
    else:
        show_cartons_only = st.checkbox(
            "📦 Pokaż tylko kartony",
            key="stock_cartons_only_new"
        )

    # Checkbox for debug
    debug_mode = st.checkbox("🐞 Tryb debugowania (pokaż szczegóły filtracji)", value=False)

    st.markdown("---")

    # ✅ Теперь используем НАШИ локальные фильтры
    df_stock = filter_stock_df(
        df,                          # полный df
        selected_mandant_stock,      # 👉 наш mandant
        selected_artikel_stock,      # 👉 наши статьи  
        selected_date_stock,         # 👉 наша дата
        debug=debug_mode             # 👉 debug
    )

    if df_stock.empty:
        st.warning(f"Brak palet na magazynie zgodnie z filtrem Mandant={selected_mandant_stock}, Artykuł={selected_artikel_stock if selected_artikel_stock else 'Wszystkie'} i datą {selected_date_stock.strftime('%d.%m.%Y')}.")
        return

    # Применение фильтра "только картоны"
    if show_cartons_only:
        df_stock = df_stock[df_stock["Opakowanie"] == "Kartony"].copy()
        
    # 4. Вывод Метрик
    total_pallets = len(df_stock)

    # st.markdown("---")
    if str(selected_mandant_stock) == "351":
        # Tylko jedna metryka – łączna liczba palet
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
            "IN_TIME": "IN_TIME",
            "OUT_DATE": "OUT_DATE",
            "OUT_TIME": "OUT_TIME",
            "CREATED_BY": "CREATED_BY",
            "CHANGED_DATE": "CHANGED_DATE",
            "CHANGED_TIME": "CHANGED_TIME",
            "ZUSTAND": "ZUSTAND",
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


def render_stock_history(
    df,
    selected_mandant_stock,
    selected_artikel_stock,
    history_start,
    history_end,
    show_cartons_only,
    STR,
    widget_prefix: str = "",
):

    """
    Рисует блок '📈 Historia liczby palet na magazynie':
    - выбор диапазона дат,
    - чекбоксы серий,
    - сам график.
    """

    st.subheader("📈 Historia liczby palet na magazynie")

    history_df = build_stock_history(
        df=df,
        selected_mandant=selected_mandant_stock,
        selected_artikel=selected_artikel_stock or [],
        start_date=datetime.combine(history_start, datetime.min.time()),
        end_date=datetime.combine(history_end, datetime.min.time()),
        show_cartons_only=show_cartons_only,
    )


    if not history_df.empty:
        # 🔹 Wybór serii na wykresie – zależnie od mandanta
        if str(selected_mandant_stock) == "351":
            show_total = st.checkbox(
                "Pokaż łączną liczbę palet",
                value=True,
                key=f"{widget_prefix}hist_show_total",
            )
            show_cart = False
            show_other = False
        else:
            show_total = st.checkbox(
                "Pokaż łączną liczbę palet",
                value=True,
                key=f"{widget_prefix}hist_show_total",
            )
            show_cart = st.checkbox(
                "Pokaż kartony",
                value=True,
                key=f"{widget_prefix}hist_show_cartons",
            )
            show_other = st.checkbox(
                "Pokaż inne opakowania",
                value=False,
                key=f"{widget_prefix}hist_show_other",
            )


        # Формируем DataFrame для графика
        plot_df = history_df.set_index("DATE").copy()
        cols_to_plot = []
        if show_total:
            cols_to_plot.append("TOTAL_PALLETS")
        if show_cart:
            cols_to_plot.append("CARTONS")
        if show_other:
            cols_to_plot.append("OTHER")

        if cols_to_plot:
            st.line_chart(
                plot_df[cols_to_plot],
                use_container_width=True,
            )
        else:
            st.info("Zaznacz przynajmniej jedną opcję do wyświetlenia na wykresie.")
    else:
        st.info("Brak danych do zbudowania historii w wybranym zakresie dat.")
