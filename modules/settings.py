# modules/settings.py
# Pallet type settings and configuration management.
# Настройки типов паллет и управление конфигурацией.

import streamlit as st
from utils import (
    load_excluded_articles,
    save_excluded_articles,
    load_packaging_config,
    save_packaging_config,
    load_packages_strategies,
    save_packages_strategies,
)

def init_settings():
    # Initialize default settings in session state if they don't exist.
    # Инициализация настроек по умолчанию в состоянии сессии, если они не существуют.
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

def render_settings_tab(STR):
    # Renders the 'Settings' tab with extended configuration for exceptions and packaging.
    # Рендерит вкладку 'Настройки' с расширенной конфигурацией для исключений и упаковки.
    
    st.header(STR["settings_header"])
    st.markdown("---")

    # --- 1. Article Exceptions ---
    # --- 1. Исключения артикулов ---
    st.subheader(STR["settings_sect1_header"])
    st.caption(STR["settings_sect1_caption"])
    st.caption(STR["settings_sect1_explanation"])
    
    # Load current exceptions from file.
    # Загрузка текущих исключений из файла.
    exact_list, prefix_list = load_excluded_articles()

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            # Exact match input area.
            # Поле ввода для точного совпадения.
            st.markdown(STR["settings_exact_match_header"])
            st.caption(STR["settings_exact_match_caption"])
            exact_input = st.text_area(
                label="exact_hidden",
                value="\n".join(exact_list),
                height=200,
                key="exact_input",
                label_visibility="collapsed"
            )
        with col2:
            # Prefix match input area.
            # Поле ввода для совпадения по префиксу.
            st.markdown(STR["settings_prefix_header"])
            st.caption(STR["settings_prefix_caption"])
            prefix_input = st.text_area(
                label="prefix_hidden",
                value="\n".join(prefix_list),
                height=200,
                key="prefix_input",
                label_visibility="collapsed"
            )
        
        # Save button for exceptions.
        # Кнопка сохранения исключений.
        if st.button(STR["settings_btn_save_exceptions"], type="primary", width="stretch"):
            new_exact = [x.strip() for x in exact_input.splitlines() if x.strip()]
            new_prefix = [x.strip() for x in prefix_input.splitlines() if x.strip()]
            if save_excluded_articles(new_exact, new_prefix):
                st.success(STR["settings_msg_exceptions_saved"])

    st.markdown("---")

    # --- 2. Packaging Configuration ---
    # --- 2. Конфигурация упаковки ---
    st.subheader(STR["settings_sect2_header"])
    st.caption(STR["settings_sect2_caption"])
    
    # Load current packaging config.
    # Загрузка текущей конфигурации упаковки.
    kartony_prefixes, other_prefixes = load_packaging_config()

    with st.container():
        col3, col4 = st.columns(2)
        with col3:
            # Cartons prefixes input.
            # Ввод префиксов картонов.
            st.markdown(STR["settings_cartons_header"])
            st.caption(STR["settings_cartons_caption"])
            kartony_input = st.text_area(
                label="kartony_hidden",
                value="\n".join(kartony_prefixes),
                height=200,
                key="kartony_input",
                label_visibility="collapsed"
            )
        with col4:
            # Other packaging prefixes input.
            # Ввод префиксов другой упаковки.
            st.markdown(STR["settings_other_pkg_header"])
            st.caption(STR["settings_other_pkg_caption"])
            other_input = st.text_area(
                label="other_hidden",
                value="\n".join(other_prefixes),
                height=200,
                key="other_input",
                label_visibility="collapsed"
            )

        # Save button for packaging config.
        # Кнопка сохранения конфигурации упаковки.
        if st.button(STR["settings_btn_save_packaging"], type="primary", width="stretch"):
            new_kartony = [x.strip() for x in kartony_input.splitlines() if x.strip()]
            new_other = [x.strip() for x in other_input.splitlines() if x.strip()]
            if save_packaging_config(new_kartony, new_other):
                st.success(STR["settings_msg_packaging_saved"])

    st.markdown("---")

    # --- 3. Strategies ---
    # --- 3. Стратегии ---
    st.subheader(STR["settings_sect3_header"])
    st.caption(STR["settings_sect3_caption"])
    
    # Load current strategies.
    # Загрузка текущих стратегий.
    strategies = load_packages_strategies()
    pallet_priority_prefixes = strategies.get("pallet_priority", {}).get("prefixes", [])
    
    with st.container():
        col5, col6 = st.columns([1, 1])
        with col5:
            # Pallet priority prefixes input.
            # Ввод префиксов приоритета паллет.
            st.markdown(STR["settings_strat_prefixes_header"])
            st.caption(STR["settings_strat_prefixes_caption"])
            strat_input = st.text_area(
                label="strat_hidden",
                value="\n".join(pallet_priority_prefixes),
                height=200,
                key="strat_input",
                label_visibility="collapsed"
            )
            
            # Save button for strategies.
            # Кнопка сохранения стратегий.
            if st.button(STR["settings_btn_save_strategies"], type="primary", width="stretch"):
                new_strat_prefixes = [x.strip() for x in strat_input.splitlines() if x.strip()]
                if save_packages_strategies(new_strat_prefixes):
                    st.success(STR["settings_msg_strategies_saved"])
        
        with col6:
            # Explanation of the strategy.
            # Объяснение стратегии.
            st.info(STR["settings_strat_explanation"])
