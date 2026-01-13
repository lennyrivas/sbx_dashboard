import streamlit as st
import pandas as pd
from datetime import datetime
from utils import load_packages_strategies, load_packaging_config

def get_platz_priority(platz):
    """
    Priorytet miejsc:
    0: Zaczyna się od WE lub BL
    1: Zaczyna się od 2 lub 02
    2: Reszta
    """
    p = str(platz).strip().upper()
    if p.startswith(('WE', 'BL')): return 0
    if p.startswith(('2', '02')): return 1
    return 2

def render_removal_tab(df):
    
    # --- OPTYMALIZACJA: Inicjalizacja roboczej bazy stanów (tylko ZUSTAND 401) ---
    # Tworzymy unikalny podpis danych (np. rozmiar), aby wykryć zmianę pliku źródłowego
    df_signature = df.shape
    
    if "removal_stock_df" not in st.session_state or st.session_state.get("removal_df_signature") != df_signature:
        # Tworzymy lekką kopię tylko z dostępnymi paletami
        stock_401 = df[df["ZUSTAND"] == "401"].copy()
        # Od razu wyliczamy priorytet miejsc (raz na zawsze)
        stock_401["PLATZ_PRIORITY"] = stock_401["PLATZ"].apply(get_platz_priority)
        
        st.session_state["removal_stock_df"] = stock_401
        st.session_state["removal_df_signature"] = df_signature
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
        render_removal_tool(st.session_state["removal_stock_df"], orders_all, selected_file)


def render_removal_tool(stock_df, orders_all, filename):
    # CSS hack: szersze tagi w multiselect (próba układu 2-kolumnowego / pełna szerokość)
    # Zmiana: tagi szersze (min 45%) i zawijanie tekstu
    st.markdown("""
    <style>
    /* Zwiększenie czytelności tagów w multiselect */
    .stMultiSelect span[data-baseweb="tag"] {
        min-width: 100% !important;
        max-width: 100% !important;
        white-space: nowrap !important;
        display: flex !important;
        justify-content: flex-start !important;
    }
    .stMultiSelect span[data-baseweb="tag"] span {
        white-space: nowrap !important;
        max-width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Wyświetlanie komunikatu o sukcesie (jeśli istnieje w sesji)
    if "removal_msg" in st.session_state:
        st.success(st.session_state.pop("removal_msg"))

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

    # Używamy już przefiltrowanej i zoptymalizowanej bazy (stock_df to teraz st.session_state["removal_stock_df"])
    stock_active = stock_df.copy()

    final_pids = []

    st.markdown("### Lista pozycji do usunięcia")
    st.markdown("---")

    # Zbieranie danych do podsumowania
    summary_rows = []
    empty_pids_arts = []

    # Ładowanie konfiguracji strategii (np. dla artykułów z priorytetem palet)
    strategies_config = load_packages_strategies()
    pallet_priority_prefixes = strategies_config.get("pallet_priority", {}).get("prefixes", ["202671"])

    # Ładowanie konfiguracji opakowań (dla oznaczenia kartonów)
    kartony_prefixes_raw, _ = load_packaging_config()
    kartony_prefixes = [k for k in kartony_prefixes_raw if k and str(k).strip()]

    # Helper do formatowania PLATZ (maska dla 02...)
    def format_platz_display(p_val):
        p_str = str(p_val).strip()
        if p_str.startswith("02"):
            clean = p_str[2:]
            # Maska: XX-XXX-XX... (np. 1234567 -> 12-345-67)
            if len(clean) > 5:
                return f"{clean[:2]}-{clean[2:5]}-{clean[5:]}"
            elif len(clean) > 2:
                return f"{clean[:2]}-{clean[2:]}"
            return clean
        return p_str

    # Używamy formularza, aby zminimalizować przeładowania strony przy każdym kliknięciu
    with st.form("removal_form"):
        # Podział na dwie kolumny: Pozostałe (lewo) | Kartony (prawo)
        col_others, col_cartons = st.columns(2)
        with col_others:
            st.markdown("##### 🏷️ Pozostałe")
        with col_cartons:
            st.markdown("##### 📦 Kartony")

        for index, row in order_agg.iterrows():
            art = row["ARTIKELNR"]
            qty_needed = row["Total_Qty"]
            pallets_needed = int(row["Total_Pallets"])
            qty_per_pal = row["Qty_Per_Pallet"]

            # Sprawdzenie czy to karton
            is_carton = str(art).startswith(tuple(kartony_prefixes))

            # Pobranie dostępnych palet dla artykułu
            art_stock = stock_active[stock_active["ARTIKELNR"] == art].copy()
            
            # Specjalna logika dla artykułów zdefiniowanych w packages_strategies.json (priorytet liczby palet)
            # Sprawdzamy, czy artykuł zaczyna się od jednego ze zdefiniowanych prefiksów
            is_pallet_priority = str(art).startswith(tuple(pallet_priority_prefixes))
            
            if is_carton:
                suggested_pids = []
            elif is_pallet_priority:
                df_special = art_stock.sort_values(
                    by=["PLATZ_PRIORITY", "IN_DATE"], 
                    ascending=[True, True]
                )
                suggested_pids = df_special["LHMNR"].head(pallets_needed).tolist()
            else:
                # --- STRATEGIA 1: Dopasowanie strukturalne (wg ilości na palecie) ---
                # Próbujemy znaleźć palety pasujące idealnie do "sztuk na paletę" z zamówienia
                art_stock["Qty_Diff"] = art_stock["QUANTITY"].apply(lambda q: abs(q - qty_per_pal))
                
                df_strat1 = art_stock.sort_values(
                    by=["Qty_Diff", "PLATZ_PRIORITY", "IN_DATE"], 
                    ascending=[True, True, True]
                )
                pids_strat1 = df_strat1["LHMNR"].head(pallets_needed).tolist()
                qty_strat1 = df_strat1[df_strat1["LHMNR"].isin(pids_strat1)]["QUANTITY"].sum()
                diff_strat1 = abs(qty_strat1 - qty_needed)

                # --- STRATEGIA 2: Dopasowanie ilościowe (FIFO / Priorytet miejsca) ---
                # Ignorujemy podział na palety, próbujemy uzbierać zadaną ilość sztuk (np. 11 palet po 1 sztuce zamiast 1 po 11)
                df_strat2 = art_stock.sort_values(
                    by=["PLATZ_PRIORITY", "IN_DATE"], 
                    ascending=[True, True]
                )
                
                pids_strat2 = []
                best_strat2_diff = float('inf')
                
                if not df_strat2.empty and qty_needed > 0:
                    temp_pids = []
                    temp_qty = 0
                    
                    for _, row_s in df_strat2.iterrows():
                        temp_pids.append(row_s["LHMNR"])
                        temp_qty += row_s["QUANTITY"]
                        
                        curr_diff = abs(temp_qty - qty_needed)
                        
                        # Zapamiętujemy najlepszy zestaw (najbliższy ilościowo)
                        if curr_diff < best_strat2_diff:
                            best_strat2_diff = curr_diff
                            pids_strat2 = list(temp_pids)
                        
                        # Jeśli już uzbieraliśmy wystarczająco, przerywamy (nie bierzemy nadmiarowych palet)
                        if temp_qty >= qty_needed:
                            break
                
                # Jeśli strategia 2 nic nie wybrała (np. brak towaru), ustawiamy błąd na max
                if not pids_strat2:
                    best_strat2_diff = qty_needed

                # --- DECYZJA ---
                # Jeśli Strategia 2 daje lepsze dopasowanie ilościowe (mniejszy błąd), wybieramy ją.
                # W przeciwnym razie (remis lub Strategia 1 lepsza) trzymamy się struktury zamówienia.
                if best_strat2_diff < diff_strat1:
                    suggested_pids = pids_strat2
                else:
                    suggested_pids = pids_strat1
            
            # Wybór kolumny docelowej
            target_col = col_cartons if is_carton else col_others

            # Wyświetlanie wiersza
            with target_col:
                # Kompaktowy układ: Info po lewej (1), Wybór po prawej (2) - dostosowane do węższej kolumny
                col_info, col_select = st.columns([1, 2])
                
                # Mapa do wyświetlania w multiselect: PID (Ilość) [Miejsce]
                # Format: PID | Ilość szt. | Miejsce
                pid_map = {
                    r["LHMNR"]: f"{r['LHMNR']} | {int(r['QUANTITY'])} szt. | {format_platz_display(r['PLATZ'])}" 
                    for _, r in art_stock.iterrows()
                }
                
                # Upewniamy się, że sugerowane PID są w dostępnych opcjach
                valid_defaults = [p for p in suggested_pids if p in pid_map]
                
                with col_info:
                    st.markdown(f"**{art}**")
                    if is_carton:
                        st.markdown("<span style='background-color: #fff8e1; color: #5d4037; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; border: 1px solid #ffe0b2;'>📦 Karton</span>", unsafe_allow_html=True)
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
                    if is_pallet_priority:
                        color_class = "green" if match_pal else "red"
                    else:
                        color_class = "green" if match_qty else "red"
                    
                    summary_text = f"Zamówiono: {int(pallets_needed)} pal. / {int(qty_needed)} szt. | Wybrano: {sel_count} pal. / {int(sel_qty)} szt."
                    st.markdown(f":{color_class}[{summary_text}]")
                
                final_pids.extend(selected)
                st.divider()

                # Zbieranie danych do podsumowania
                if sel_count == 0:
                    empty_pids_arts.append(art)
                
                summary_rows.append({
                    "Artykuł": f"*{art}" if is_pallet_priority else art,
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
                st.dataframe(df_diff, width="stretch", hide_index=True)
            else:
                st.success("Brak różnic ilościowych!")
            st.caption("\\* - Artykuł obsługiwany strategią 'Priorytet Palet' (ignorowanie ilości sztuk)")

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
                st.caption("✅ Skopiuj listę (ikona w rogu), a następnie zatwierdź usunięcie.")
        
        with col_btn:
            # Przycisk zatwierdzania usunięcia
            def confirm_removal():
                st.session_state["removed_pids"].update(final_pids)
                st.session_state["removal_stock_df"] = st.session_state["removal_stock_df"][~st.session_state["removal_stock_df"]["LHMNR"].isin(final_pids)]
                st.session_state["removal_msg"] = f"Oznaczono {len(final_pids)} palet jako usunięte. Nie będą one sugerowane przy kolejnych analizach."

            st.button("✅ Zatwierdź usunięcie (Ukryj te PIDy)", type="primary", help="Kliknij po skopiowaniu, aby oznaczyć te palety jako usunięte w bieżącej sesji.", on_click=confirm_removal)
            
        if submit_btn:
            st.toast("Lista PID została wygenerowana. Skopiuj dane i zatwierdź usunięcie.", icon="📋")
    else:
        st.info("Brak wybranych palet.")