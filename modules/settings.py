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
    st.markdown("---")

    # 1. Исключения артикулов
    st.subheader("1. Wykluczenia z porównań")
    st.caption("Zdefiniuj artykuły, które mają być ignorowane w tabelach różnic (np. opakowania zwrotne).")
    
    exact_list, prefix_list = load_excluded_articles()

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 🎯 Artykuły (dokładne dopasowanie)")
            st.caption("Wpisz pełne numery artykułów, jeden pod drugim.")
            exact_input = st.text_area(
                label="exact_hidden",
                value="\n".join(exact_list),
                height=200,
                key="exact_input",
                label_visibility="collapsed"
            )
        with col2:
            st.markdown("##### 🔤 Prefiksy (początek numeru)")
            st.caption("Wpisz ciągi znaków, od których zaczynają się wykluczone artykuły.")
            prefix_input = st.text_area(
                label="prefix_hidden",
                value="\n".join(prefix_list),
                height=200,
                key="prefix_input",
                label_visibility="collapsed"
            )
        
        if st.button("💾 Zapisz wyjątki", type="primary", use_container_width=True):
            new_exact = [x.strip() for x in exact_input.splitlines() if x.strip()]
            new_prefix = [x.strip() for x in prefix_input.splitlines() if x.strip()]
            if save_excluded_articles(new_exact, new_prefix):
                st.success("✅ Wyjątki zapisane pomyślnie")

    st.markdown("---")

    # 2. Конфигурация упаковки
    st.subheader("2. Konfiguracja opakowań (Mandant 352)")
    st.caption("Określ, które artykuły są kartonami, a które innymi opakowaniami, na podstawie ich prefiksów.")
    
    kartony_prefixes, other_prefixes = load_packaging_config()

    with st.container():
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("##### 📦 Prefiksy Kartonów")
            st.caption("Artykuły zaczynające się od tych znaków będą zliczane jako kartony.")
            kartony_input = st.text_area(
                label="kartony_hidden",
                value="\n".join(kartony_prefixes),
                height=200,
                key="kartony_input",
                label_visibility="collapsed"
            )
        with col4:
            st.markdown("##### 🏷️ Inne opakowania")
            st.caption("Prefiksy dla pozostałych typów opakowań (nie-paletowych).")
            other_input = st.text_area(
                label="other_hidden",
                value="\n".join(other_prefixes),
                height=200,
                key="other_input",
                label_visibility="collapsed"
            )

        if st.button("💾 Zapisz konfigurację opakowań", type="primary", use_container_width=True):
            new_kartony = [x.strip() for x in kartony_input.splitlines() if x.strip()]
            new_other = [x.strip() for x in other_input.splitlines() if x.strip()]
            if save_packaging_config(new_kartony, new_other):
                st.success("✅ Konfiguracja opakowań zapisana pomyślnie")

    st.markdown("---")

    # 3. Strategie
    st.subheader("3. Strategie usuwania (Priorytet Palet)")
    st.caption("Dla poniższych artykułów system będzie dobierał palety do usunięcia kierując się liczbą palet, a nie sumą sztuk.")
    
    strategies = load_packages_strategies()
    pallet_priority_prefixes = strategies.get("pallet_priority", {}).get("prefixes", [])
    
    with st.container():
        col5, col6 = st.columns([1, 1])
        with col5:
            st.markdown("##### 🔢 Prefiksy artykułów")
            st.caption("Wpisz prefiksy artykułów (np. '202671'), dla których 1 szt. w zamówieniu = 1 paleta fizyczna.")
            strat_input = st.text_area(
                label="strat_hidden",
                value="\n".join(pallet_priority_prefixes),
                height=200,
                key="strat_input",
                label_visibility="collapsed"
            )
            
            if st.button("💾 Zapisz strategie", type="primary", use_container_width=True):
                new_strat_prefixes = [x.strip() for x in strat_input.splitlines() if x.strip()]
                if save_packages_strategies(new_strat_prefixes):
                    st.success("✅ Strategie zapisane pomyślnie")
        
        with col6:
            st.info("""
            ℹ️ **Jak to działa?**
            
            Jeśli artykuł znajduje się na tej liście, algorytm w zakładce **Usuwanie palet** zignoruje ilość sztuk na palecie i spróbuje dobrać dokładnie tyle palet, ile wynika z zamówienia.
            
            **Przykład:**
            Zamówienie: 1 szt. (co oznacza 1 paletę).
            Stan: Paleta ma 4 sztuki.
            
            Bez tej strategii: System szukałby palety z 1 sztuką.
            Z tą strategią: System weźmie paletę z 4 sztukami, bo liczy się 1 paleta.
            """)
