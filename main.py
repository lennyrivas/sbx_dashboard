import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

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

# Чтобы можно было импортировать из папки modules
sys.path.append(str(Path(__file__).parent / "modules"))


# ==============================
# Функция фильтров для вкладки Analiza
# ==============================

def render_analysis_filters(df: pd.DataFrame):
    """
    Bardzo kompaktowe filtry dla zakładki 'Analiza zamówień vs palet'
    w jednej linii.
    """

    st.subheader("🔍 Filtry analizy")
    

    # Jedna linia: Mandant | Tryb | Daty (tryb + od + do) | Artykuł
    col_mandant, col_mode, col_dates, col_artikel = st.columns(
        [0.4, 1.4, 3.2, 1.6]  # ostatnią kolumnę trochę skracamy względem poprzedniej wersji
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

try:
    if uploaded.name.lower().endswith(".csv") or uploaded.name.lower().endswith(".txt"):
        df_raw = pd.read_csv(uploaded, sep=";", dtype=str, encoding="utf-8")
    else:
        df_raw = pd.read_csv(uploaded, sep=";", dtype=str, encoding="utf-8")
except Exception:
    try:
        uploaded.seek(0)
        df_raw = pd.read_csv(uploaded, sep=";", dtype=str, encoding="latin-1")
    except Exception as e:
        st.error(f"Błąd wczytywania pliku: {e}")
        st.stop()

# Приводим имена колонок к аккуратному виду
# 1. Заголовки и карта
df_raw.columns = [c.strip() for c in df_raw.columns]
cols_map = {c.upper(): c for c in df_raw.columns}

required_raw = [
    "MANDANT",
    "ARTIKELNR",
    "ARTBEZ1",
    "QUANTITY",
    "LHMNR",
    "ZUSTAND",
    "PLATZ",
    "CHARGE1",
    "ANGELEGT AM",
    "ANGELEGT UM",
    "ANGELEGT VON",
    "GEANDERT AM",
    "GEANDERT UM",
    "BEWEGUNG AM",
    "BEWEGUNG UM",
]

missing = [r for r in required_raw if r not in cols_map]
if missing:
    st.error(f"Plik nie zawiera wymaganych kolumn: {', '.join(missing)}")
    st.stop()

# 2. Берём нужные колонки из df_raw
df = df_raw[[cols_map[c] for c in required_raw]].copy()
df.columns = required_raw  # пока оставляем UPPER/немецкие

# 3. Переименовываем немецкие поля в программные имена
df = df.rename(
    columns={
        "ANGELEGT AM": "IN_DATE",
        "ANGELEGT UM": "IN_TIME",
        "BEWEGUNG AM": "OUT_DATE",
        "BEWEGUNG UM": "OUT_TIME",
        "GEANDERT AM": "CHANGED_DATE",
        "GEANDERT UM": "CHANGED_TIME",
        "ANGELEGT VON": "CREATED_BY",
    }
)

# 4. ТИПЫ
df["ARTIKELNR"] = df["ARTIKELNR"].astype(str).str.strip().str.upper()
df["ARTBEZ1"] = df["ARTBEZ1"].astype(str).str.strip()
df["QUANTITY"] = pd.to_numeric(
    df["QUANTITY"].astype(str).str.replace(",", "."),
    errors="coerce",
).fillna(0)
df["LHMNR"] = df["LHMNR"].astype(str).str.strip()
df["CHARGE1"] = df["CHARGE1"].fillna("").astype(str).str.strip()
df["ZUSTAND"] = df["ZUSTAND"].astype(str).str.strip()
df["PLATZ"] = df["PLATZ"].astype(str).str.strip()
df["CREATED_BY"] = df["CREATED_BY"].astype(str).str.strip()

df["IN_DATE"] = pd.to_datetime(df["IN_DATE"], dayfirst=True, errors="coerce")
df["OUT_DATE"] = pd.to_datetime(df["OUT_DATE"], dayfirst=True, errors="coerce")
df["CHANGED_DATE"] = pd.to_datetime(df["CHANGED_DATE"], dayfirst=True, errors="coerce")

df["IN_TIME"] = pd.to_datetime(df["IN_TIME"], format="%H:%M:%S", errors="coerce").dt.time
df["OUT_TIME"] = pd.to_datetime(df["OUT_TIME"], format="%H:%M:%S", errors="coerce").dt.time
df["CHANGED_TIME"] = pd.to_datetime(
    df["CHANGED_TIME"], format="%H:%M:%S", errors="coerce"
).dt.time

# 5. Логика удаления: ZUSTAND != 401
df["IS_DELETED"] = df["ZUSTAND"] != "401"


# Для паллет с ZUSTAND == 401 поля OUT_DATE/OUT_TIME игнорируются логически.
# (Физически остаются в df, но при фильтрации удалённых мы будем смотреть только на IS_DELETED)



# ==============================
# Локальная функция настроек (как у тебя было)
# ==============================
def render_local_settings_tab():
    """Расширенные настройки исключений + упаковка"""
    st.header("⚙️ Ustawienia")

    # 1. Исключения артикулов
    st.subheader("1. Artykuły wykluczone z porównań")
    exact_list, prefix_list = load_excluded_articles()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Artykuły dokładne**")
        exact_input = st.text_area(
            label="Artykuły dokładne",
            value="\n".join(exact_list),
            height=150,
            key="exact_input",
        )
    with col2:
        st.markdown("**Prefiksy**")
        prefix_input = st.text_area(
            label="Prefiksy artykułów",
            value="\n".join(prefix_list),
            height=150,
            key="prefix_input",
        )

    # 2. Конфигурация упаковки
    st.subheader("2. Konfiguracja opakowań (Mandant 352)")
    kartony_prefixes, other_prefixes = load_packaging_config()

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Prefiksy kartonów**")
        kartony_input = st.text_area(
            label="Prefiksy kartonów",
            value="\n".join(kartony_prefixes),
            height=150,
            key="kartony_input",
        )
    with col4:
        st.markdown("**Inne opakowania**")
        other_input = st.text_area(
            label="Inne opakowania",
            value="\n".join(other_prefixes),
            height=150,
            key="other_input",
        )

    col_save1, col_save2, _ = st.columns(3)
    with col_save1:
        if st.button("💾 Zapisz wyjątki", type="secondary"):
            new_exact = [x.strip() for x in exact_input.splitlines() if x.strip()]
            new_prefix = [x.strip() for x in prefix_input.splitlines() if x.strip()]
            if save_excluded_articles(new_exact, new_prefix):
                st.success("✅ Wyjątki zapisane pomyślnie")

    with col_save2:
        if st.button("📦 Zapisz opakowania", type="primary"):
            new_kartony = [x.strip() for x in kartony_input.splitlines() if x.strip()]
            new_other = [x.strip() for x in other_input.splitlines() if x.strip()]
            if save_packaging_config(new_kartony, new_other):
                st.success("✅ Konfiguracja opakowań zapisana pomyślnie")


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
    # Можно использовать либо render_settings_tab из modules.settings,
    # либо локальную реализацию выше; выбирай один вариант:
    # render_settings_tab(df, STR)  # если такая сигнатура есть
    render_local_settings_tab()
