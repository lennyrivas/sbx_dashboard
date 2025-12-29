import streamlit as st
import pandas as pd
from datetime import datetime

def get_platz_priority(platz):
    """
    Priorytet miejsc:
    0: Zaczyna się od WE lub BL
    1: Zaczyna się od 2 lub 02
    2: Reszta
    """
    p = str(platz).upper()
    if p.startswith(('WE', 'BL')): return 0
    if p.startswith(('2', '02')): return 1
    return 2

def render_admin_tab(df):
    st.header("🔐 Panel Administratora")
    
    # --- OPTYMALIZACJA: Inicjalizacja roboczej bazy stanów (tylko ZUSTAND 401) ---
    # Tworzymy unikalny podpis danych (np. rozmiar), aby wykryć zmianę pliku źródłowego
    df_signature = df.shape
    
    if "admin_stock_df" not in st.session_state or st.session_state.get("admin_df_signature") != df_signature:
        # Tworzymy lekką kopię tylko z dostępnymi paletami
        stock_401 = df[df["ZUSTAND"] == "401"].copy()
        # Od razu wyliczamy priorytet miejsc (raz na zawsze)
        stock_401["PLATZ_PRIORITY"] = stock_401["PLATZ"].apply(get_platz_priority)
        
        st.session_state["admin_stock_df"] = stock_401
        st.session_state["admin_df_signature"] = df_signature
        st.session_state["removed_pids"] = set()

    st.header("🗑️ Usuwanie palet (Generator PID)")
    st.info("Narzędzie pomaga dobrać palety do usunięcia na podstawie zamówienia, uwzględniając priorytet miejsc (WE/BL -> 2/02) oraz dopasowanie ilości.")

    # 1. Sprawdzenie dostępności zamówień
    if "orders_cache" not in st.session_state or st.session_state["orders_cache"].get("orders_all") is None:
        st.warning("⚠️ Brak załadowanych plików zamówień. Przejdź do zakładki 'Analiza zamówień' i załaduj pliki.")
        return

    orders_all = st.session_state["orders_cache"]["orders_all"]
    if orders_all.empty:
        st.warning("⚠️ Brak danych zamówień.")
        return

    # 2. Wybór pliku
    files = sorted(orders_all["SOURCE_FILE"].unique())
    selected_file = st.selectbox("Wybierz plik zamówienia:", options=files)

    if selected_file:
        # Przekazujemy naszą zoptymalizowaną bazę ze stanu sesji
        render_removal_tool(st.session_state["admin_stock_df"], orders_all, selected_file)

    # --- Narzędzia deweloperskie (na dole) ---
    st.markdown("---")
    with st.expander("🛠 Narzędzia deweloperskie i podgląd", expanded=False):
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("Zarządzanie aplikacją")
            if st.button("🧹 Wyczyść pamięć podręczną (st.cache_data)", type="primary"):
                st.cache_data.clear()
                st.success("Pamięć podręczna została wyczyszczona.")
                
            st.subheader("Stan sesji")
            session_summary = {k: str(v)[:200] + "..." if len(str(v)) > 200 else v for k, v in st.session_state.items()}
            st.json(session_summary)

        with col_a2:
            st.subheader("Podgląd danych (Top 100)")
            st.dataframe(df.head(100), use_container_width=True)
            st.write(f"Wymiary: {df.shape}")


def render_removal_tool(stock_df, orders_all, filename):
    # CSS hack: szersze tagi w multiselect (próba układu 2-kolumnowego / pełna szerokość)
    # Zmiana: tagi szersze (min 45%) i zawijanie tekstu
    st.markdown("""
    <style>
    /* Zwiększenie czytelności tagów w multiselect */
    .stMultiSelect span[data-baseweb="tag"] {
        min-width: 30% !important;
        max-width: 100% !important;
        white-space: normal !important;
        display: flex !important;
        justify-content: flex-start !important;
    }
    .stMultiSelect span[data-baseweb="tag"] span {
        white-space: normal !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Filtrowanie danych zamówienia
    order_data = orders_all[orders_all["SOURCE_FILE"] == filename].copy()
    
    # Zachowanie oryginalnej kolejności (sortowanie wg pierwszego wystąpienia w pliku)
    order_data = order_data.reset_index()
    
    # Agregacja po artykule
    order_agg = order_data.groupby("ARTIKELNR", as_index=False).agg(
        Total_Qty=("ORDER_QTY", "sum"),
        Total_Pallets=("ORDER_PALLETS", "sum")
    )
    
    # Przywracanie kolejności
    first_occurrence = order_data.groupby("ARTIKELNR")['index'].min()
    order_agg['orig_idx'] = order_agg['ARTIKELNR'].map(first_occurrence)
    order_agg = order_agg.sort_values('orig_idx').drop(columns=['orig_idx'])
    
    # Wyliczenie średniej ilości na paletę (do dopasowania)
    order_agg["Qty_Per_Pallet"] = order_agg.apply(
        lambda r: r["Total_Qty"] / r["Total_Pallets"] if r["Total_Pallets"] > 0 else 0, axis=1
    )

    # Używamy już przefiltrowanej i zoptymalizowanej bazy (stock_df to teraz st.session_state["admin_stock_df"])
    stock_active = stock_df.copy()

    final_pids = []

    st.markdown("### Lista pozycji do usunięcia")
    st.markdown("---")

    # Zbieranie danych do podsumowania
    summary_rows = []
    empty_pids_arts = []

    # Używamy formularza, aby zminimalizować przeładowania strony przy każdym kliknięciu
    with st.form("removal_form"):
        for index, row in order_agg.iterrows():
            art = row["ARTIKELNR"]
            qty_needed = row["Total_Qty"]
            pallets_needed = int(row["Total_Pallets"])
            qty_per_pal = row["Qty_Per_Pallet"]

            # Pobranie dostępnych palet dla artykułu
            art_stock = stock_active[stock_active["ARTIKELNR"] == art].copy()
            
            # Logika sortowania:
            # 1. Dopasowanie ilości (+/- 10 sztuk) - Najpierw pasujące
            # 2. Priorytet miejsca (WE/BL -> 2/02 -> inne) - Rosnąco
            # 3. Data przyjęcia (IN_DATE) - Najstarsze (FIFO)
            art_stock["Is_Match"] = art_stock["QUANTITY"].apply(lambda q: abs(q - qty_per_pal) <= 10)
            
            art_stock = art_stock.sort_values(
                by=["Is_Match", "PLATZ_PRIORITY", "IN_DATE"], 
                ascending=[False, True, True]
            )

            # Automatyczny wybór PID (bierzemy tyle, ile potrzeba w zamówieniu)
            suggested_pids = art_stock["LHMNR"].head(pallets_needed).tolist()
            
            # Wyświetlanie wiersza
            with st.container():
                # Kompaktowy układ: Info po lewej (1), Wybór po prawej (4) - więcej miejsca na PID
                col_info, col_select = st.columns([1, 4])
                
                # Mapa do wyświetlania w multiselect: PID (Ilość) [Miejsce]
                # Format: PID | Ilość szt. | Miejsce
                pid_map = {
                    r["LHMNR"]: f"{r['LHMNR']} | {int(r['QUANTITY'])} szt. | {r['PLATZ']}" 
                    for _, r in art_stock.iterrows()
                }
                
                # Upewniamy się, że sugerowane PID są w dostępnych opcjach
                valid_defaults = [p for p in suggested_pids if p in pid_map]
                
                with col_info:
                    st.markdown(f"**{art}**")
                    st.caption(f"Cel: {int(pallets_needed)} pal.")
                    st.caption(f"Cel: {int(qty_needed)} szt.")

                with col_select:
                    selected = st.multiselect(
                        f"Wybierz PID dla {art}",
                        options=art_stock["LHMNR"].tolist(),
                        default=valid_defaults,
                        format_func=lambda x: pid_map.get(x, x),
                        key=f"sel_{filename}_{art}",
                        label_visibility="collapsed"
                    )
                    
                    # Obliczanie statystyk wyboru
                    sel_count = len(selected)
                    sel_qty = art_stock[art_stock["LHMNR"].isin(selected)]["QUANTITY"].sum()
                    
                    # Sprawdzenie zgodności
                    match_pal = (sel_count == pallets_needed)
                    # Tolerancja dla float przy porównaniu ilości
                    match_qty = abs(sel_qty - qty_needed) < 0.1
                    
                    # Kolorowanie tekstu
                    color_class = "green" if (match_pal and match_qty) else "red"
                    
                    summary_text = f"Zamówiono: {int(pallets_needed)} pal. / {int(qty_needed)} szt. | Wybrano: {sel_count} pal. / {int(sel_qty)} szt."
                    st.markdown(f":{color_class}[{summary_text}]")
                
                final_pids.extend(selected)
                st.divider()

                # Zbieranie danych do podsumowania
                if sel_count == 0:
                    empty_pids_arts.append(art)
                
                summary_rows.append({
                    "Artykuł": art,
                    "Zamówiono (szt)": int(qty_needed),
                    "Wybrano (szt)": int(sel_qty),
                    "Różnica (szt)": int(sel_qty - qty_needed)
                })

        submit_btn = st.form_submit_button("Przelicz / Zatwierdź wybór", type="primary")

    # --- Sekcja podsumowania (poza formularzem) ---
    if summary_rows:
        st.markdown("### 📊 Podsumowanie różnic")
        col_empty, col_diff = st.columns([1, 2])
        
        with col_empty:
            st.markdown("**Artykuły bez wybranych PID (do usunięcia):**")
            if empty_pids_arts:
                st.error(", ".join(empty_pids_arts))
            else:
                st.success("Wszystkie artykuły mają przypisane PID.")
        
        with col_diff:
            st.markdown("**Tabela różnic (Zamówienie vs Wybór):**")
            df_summary = pd.DataFrame(summary_rows)
            # Pokaż tylko te z różnicą
            df_diff = df_summary[df_summary["Różnica (szt)"] != 0]
            if not df_diff.empty:
                st.dataframe(df_diff, use_container_width=True, hide_index=True)
            else:
                st.success("Brak różnic ilościowych!")

    st.markdown("### 📋 Wynik")
    if final_pids:
        # Usuwanie duplikatów (na wszelki wypadek)
        final_pids = list(dict.fromkeys(final_pids))
        
        # Layout: Wynik (lewo, ~35%), Przycisk (prawo)
        col_res, col_btn = st.columns([0.35, 0.65])
        
        with col_res:
            # Kompaktowy wynik w expanderze
            with st.expander(f"Lista PID ({len(final_pids)} szt.)", expanded=False):
                st.markdown("""
                <style>
                div[data-testid="stCodeBlock"] pre {
                    max-height: 300px;
                    overflow-y: auto;
                }
                </style>
                """, unsafe_allow_html=True)
                st.code("\n".join(final_pids), language="text")
        
        with col_btn:
            # Przycisk zatwierdzania usunięcia
            if st.button("✅ Zatwierdź usunięcie (Ukryj te PIDy)", type="primary", help="Kliknij po skopiowaniu, aby oznaczyć te palety jako usunięte w bieżącej sesji."):
                # 1. Dodajemy do listy usuniętych (dla historii/logów)
                st.session_state["removed_pids"].update(final_pids)
                
                # 2. Fizycznie usuwamy wiersze z naszej roboczej bazy danych w sesji
                # Dzięki temu przy kolejnym odświeżeniu nie musimy nic filtrować - tych palet już tam nie będzie.
                st.session_state["admin_stock_df"] = st.session_state["admin_stock_df"][~st.session_state["admin_stock_df"]["LHMNR"].isin(final_pids)]
                
                st.success(f"Oznaczono {len(final_pids)} palet jako usunięte. Nie będą one sugerowane przy kolejnych analizach.")
                
                # DEBUG: Komunikat przed rerun
                st.toast("🐞 ADMIN: Wywołano `st.rerun()`")
                st.rerun()
    else:
        st.info("Brak wybranych palet.")