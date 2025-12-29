# modules/settings.py
# Настройки типов паллет

import streamlit as st
from modules.ui_strings import STR
from utils import (
    load_excluded_articles,
    save_excluded_articles,
    load_packaging_config,
    save_packaging_config,
    load_packages_strategies,
    save_packages_strategies,
)

def init_settings():
    """Инициализация настроек по умолчанию"""
    defaults = {
        "cartons": ["83090", "676", "568", "ZC", "826", "3807486", 
                   "PRZEKLADKI CIETE", "RAMKA IPUV", "TCM-ECE", "TKAS"],
        "pallets_frames": [],
        "other_packaging": []
    }
    
    for key, default_list in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_list.copy()
    
    return defaults

def render_settings_tab():
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

    # 3. Strategie
    st.subheader("3. Strategie usuwania (Priorytet Palet)")
    strategies = load_packages_strategies()
    pallet_priority_prefixes = strategies.get("pallet_priority", {}).get("prefixes", [])
    
    col5, _ = st.columns(2)
    with col5:
        st.markdown("**Prefiksy (Priorytet Palet)**")
        st.caption("Artykuły, dla których ważniejsza jest liczba palet niż ilość sztuk.")
        strat_input = st.text_area(
            label="Prefiksy strategii",
            value="\n".join(pallet_priority_prefixes),
            height=150,
            key="strat_input",
        )
        
    if st.button("⚙️ Zapisz strategie", type="primary"):
        new_strat_prefixes = [x.strip() for x in strat_input.splitlines() if x.strip()]
        if save_packages_strategies(new_strat_prefixes):
            st.success("✅ Strategie zapisane pomyślnie")
