import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.orders import render_orders_tab
from modules.ui_strings import STR
from utils import load_excluded_articles, save_excluded_articles, load_packaging_config, save_packaging_config
from modules.settings import render_settings_tab
from modules.stock import render_stock_tab
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "modules"))


st.set_page_config(page_title="Sprintbox — Raport palet", layout="wide", initial_sidebar_state="expanded")

# -------------------- 
# Dark theme CSS
# --------------------
# st.markdown("""
# <style>
#   :root { color-scheme: dark; }
#   .stApp { background-color: #0f1115; color: #d7dde5; }
#   [data-testid="stSidebar"] { background-color: #0b0c0e; color: #d7dde5; }
#   .stButton>button, .stDownloadButton>button { border-radius: 6px; }
#   .ag-theme-streamlit { --ag-background-color: #0f1115; --ag-odd-row-background-color: #111318; --ag-row-hover-color: #1a222a; --ag-header-background-color: #0c1013; --ag-foreground-color: #d7dde5; color: #d7dde5; }
#   .small-note { color:#9fb0c8; font-size:0.9em; }
# </style>
# """, unsafe_allow_html=True)

st.title(STR["title"])

# -------------------- 
# Sidebar - wspólne filtry dla wszystkich danych
# --------------------
st.sidebar.header(STR["filters"])

# Główny plik CSV z paletami
uploaded = st.sidebar.file_uploader(STR["upload_csv"], type=["csv", "txt"], key="main_csv")

# Filtry
available_mandants = ["351", "352"]
selected_mandant = st.sidebar.selectbox(STR["mandant"], options=available_mandants, index=0)

# Mode: usunięte vs przyjęte
mode = st.sidebar.radio(STR["mode"], (STR["mode_deleted"], STR["mode_received"]))

# Date mode
st.sidebar.markdown(STR["date_mode"])
yesterday = (datetime.now() - timedelta(days=1)).date()
date_mode = st.sidebar.radio(
    "Tryb daty", 
    (STR["single"], STR["range"]), 
    horizontal=True,
    label_visibility="visible"
)

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
    
    date_start = datetime.combine(start, datetime.min.time())
    date_end = datetime.combine(end, datetime.max.time())


if uploaded is None:
    st.info(STR["no_file"])
    st.stop()

# -------------------- 
# Ładowanie i filtrowanie palet (wspólne dla całej analizy)
# --------------------
try:
    if uploaded.name.lower().endswith(".csv") or uploaded.name.lower().endswith(".txt"):
        df_raw = pd.read_csv(uploaded, sep=';', dtype=str, encoding='utf-8')
    else:
        df_raw = pd.read_csv(uploaded, sep=';', dtype=str, encoding='utf-8')
except Exception:
    try:
        uploaded.seek(0)
        df_raw = pd.read_csv(uploaded, sep=';', dtype=str, encoding='latin-1')
    except Exception as e:
        st.error(f"Błąd wczytywania pliku: {e}")
        st.stop()

df_raw.columns = [c.strip() for c in df_raw.columns]
cols_map = {c.upper(): c for c in df_raw.columns}
required = ["MANDANT","ARTIKELNR","ARTBEZ1","QUANTITY","LHMNR","ZUSTAND","PLATZ","IN_DATE","OUT_DATE","GEANDERT_UM", "CHARGE1"]
missing = [r for r in required if r not in cols_map]
if missing:
    st.error(f"Plik nie zawiera wymaganych kolumn: {', '.join(missing)}")
    st.stop()

df = df_raw[[cols_map[c] for c in required]].copy()
df.columns = required

# Tylko mandanty 351/352
df = df[df["MANDANT"].astype(str).isin(["351","352"])].copy()

# Normalizacja i typy
df["ARTIKELNR"] = df["ARTIKELNR"].astype(str).str.strip().str.upper()
df["ARTBEZ1"] = df["ARTBEZ1"].astype(str).str.strip()
df["QUANTITY"] = pd.to_numeric(df["QUANTITY"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
df["IN_DATE"] = pd.to_datetime(df["IN_DATE"], dayfirst=True, errors='coerce')
df["OUT_DATE"] = pd.to_datetime(df["OUT_DATE"], dayfirst=True, errors='coerce')
df["GEANDERT_UM"] = pd.to_datetime(df["GEANDERT_UM"], dayfirst=True, errors='coerce') 
df["CHARGE1"] = df["CHARGE1"].fillna("").astype(str).str.strip()
df["LHMNR"] = df["LHMNR"].astype(str).str.strip()

# Artykuły dla filtrów
artikel_options = sorted(df[df["MANDANT"].astype(str) == selected_mandant]["ARTIKELNR"].dropna().unique().tolist())
selected_artikel = st.sidebar.multiselect(STR["artikel"], options=artikel_options, default=[])

# Filtrowanie
date_field = "OUT_DATE" if mode == STR["mode_deleted"] else "IN_DATE"

mask = (df["MANDANT"].astype(str) == selected_mandant)
if selected_artikel:
    mask &= df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])
mask &= df[date_field].between(pd.Timestamp(date_start), pd.Timestamp(date_end))

filtered_pallets_df = df[mask].copy()
filtered_pallets_df["IS_DELETED"] = filtered_pallets_df["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA")

# DEBUG INFO
st.sidebar.markdown("### 🔍 Debug filtrów")
st.sidebar.write(f"Mandant: **{selected_mandant}**")
st.sidebar.write(f"Artykuły: **{selected_artikel}**")
st.sidebar.write(f"Pole daty: **{date_field}**")
st.sidebar.write(f"Zakres: **{date_start.date()} → {date_end.date()}**")
st.sidebar.write(f"Wynik: **{len(filtered_pallets_df)} wierszy**")

def render_settings_tab():
    """Расширенные настройки исключений + упаковка"""
    st.header("⚙️ Ustawienia")
    
    # Исключения артикулов
    st.subheader("1. Artykuły wykluczone z porównań")
    exact_list, prefix_list = load_excluded_articles()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Artykuły dokładne**")
        exact_input = st.text_area(
            label="Artykuły dokładne", 
            value="\n".join(exact_list), 
            height=150, 
            key="exact_input"
        )
    with col2:
        st.markdown("**Prefiksy**")
        prefix_input = st.text_area(
            label="Prefiksy artykułów", 
            value="\n".join(prefix_list), 
            height=150, 
            key="prefix_input"
        )
    
    # Конфигурация упаковки (картоны)
    st.subheader("2. Konfiguracja opakowań (Mandant 352)")
    kartony_prefixes, other_prefixes = load_packaging_config()
    
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Prefiksy kartonów**")
        kartony_input = st.text_area(
            label="Prefiksy kartonów", 
            value="\n".join(kartony_prefixes), 
            height=150, 
            key="kartony_input"
        )
    with col4:
        st.markdown("**Inne opakowania**")
        other_input = st.text_area(
            label="Inne opakowania", 
            value="\n".join(other_prefixes), 
            height=150, 
            key="other_input"
        )
    
    # Кнопки сохранения
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


# Создание вкладок (ПОСЛЕ определения функции!)
tab_analysis, tab_stock, tab_settings = st.tabs([
    "Analiza zamówień vs palet",
    "Stany magazynowe",
    "⚙️ Ustawienia"
])

with tab_analysis:
    st.header("⚖️ Analiza dodanych i usuniętych palet")
    # Metrics
    col1, col2, col3 = st.columns([1,1,2])
    deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]]

    if selected_mandant == "352":
        col1, col2, col3, col4 = st.columns(4)
        deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]]
        col1.metric("Wybrane palety", f"{len(filtered_pallets_df):,}")
        col2.metric("Usunięte palety", f"{len(deleted_pallets):,}")

        from utils import load_packaging_config
        kartony_prefixes, _ = load_packaging_config()
        kartony_count = deleted_pallets[
            deleted_pallets["ARTIKELNR"].str.startswith(tuple(kartony_prefixes), na=False)
        ].shape[0]
        inne_count = len(deleted_pallets) - kartony_count
        col3.metric("Usunięte kartony", f"{kartony_count:,}")
        col4.metric("Inne opakowania", f"{inne_count:,}")
    else:
        col1, col2 = st.columns(2)
        deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]]
        col1.metric("Wybrane palety", f"{len(filtered_pallets_df):,}")
        col2.metric("Usunięte palety", f"{len(deleted_pallets):,}")

    render_orders_tab(artikel_options, filtered_pallets_df, selected_artikel)

with tab_stock:
    # 👉 новая вкладка складских остатков
    render_stock_tab(
        df,                 # полный очищенный DataFrame (база данных)
        selected_mandant,   # выбранный mandant из sidebar
        selected_artikel,   # список выбранных artykułów из sidebar
        STR                 # словарь строк UI
    )

with tab_settings:
    render_settings_tab()

