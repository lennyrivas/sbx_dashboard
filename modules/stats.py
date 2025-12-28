import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Импортируем функцию, которая уже есть в stock.py
from modules.stock import render_stock_history
from utils import load_packaging_config



def render_stats_tab(df, STR):
    """
    Рендеринг вкладки 'Statystyka'.

    Здесь сейчас показываем только историю liczby palet na magazynie:
    - заголовок,
    - выбор диапазона дат,
    - чекбоксы серий,
    - график.
    """

    # Заголовок вкладки статистики
    st.header("📊 Statystyka magazynu")

    # Пока делаем простый вариант:
    # - берём domyślny mandant: pierwszy z df["MANDANT"]
    # - nie filtrujemy po artykułach (pusta lista)
    # - domyślna data odniesienia: wczoraj
    available_mandants = sorted(df["MANDANT"].astype(str).unique())
    if not available_mandants:
        st.warning("Brak danych magazynowych do zbudowania statystyk.")
        return

    with st.expander("📈 Historia liczby palet na magazynie", expanded=False):
        # 🔹 Mandant, Data od, Data do w jednej linii
        col_mandant, col_from, col_to = st.columns([1, 1, 1])

        available_mandants = sorted(df["MANDANT"].astype(str).unique())
        if not available_mandants:
            st.warning("Brak danych magazynowych do zbudowania statystyk.")
            return

        with col_mandant:
            selected_mandant_stock = st.selectbox(
                "Mandant",
                options=available_mandants,
                index=0,
                key="stats_history_mandant",
            )

        # Domyślne wartości dat
        min_date = df["IN_DATE"].min().date()
        max_date = df["IN_DATE"].max().date()
        yesterday = (datetime.now() - timedelta(days=1)).date()

        # Domyślne: ostatnie 30 dni
        raw_default_start = (yesterday - timedelta(days=29))
        default_start = max(min_date, min(raw_default_start, max_date))
        default_end = max(min_date, min(yesterday, max_date))

        with col_from:
            history_start = st.date_input(
                "Data od",
                value=default_start,
                min_value=min_date,
                max_value=max_date,
                key="stats_history_start",
            )

        with col_to:
            history_end = st.date_input(
                "Data do",
                value=default_end,
                min_value=history_start,
                max_value=max_date,
                key="stats_history_end",
            )

        # 🔹 Lista artykułów tylko dla wybranego mandanta
        artikel_options = sorted(
            df[df["MANDANT"].astype(str) == selected_mandant_stock]["ARTIKELNR"]
            .dropna()
            .unique()
            .tolist()
        )

        selected_artikel_stock = st.multiselect(
            "Artykuły (filtr dla historii)",
            options=artikel_options,
            default=[],
            key="stats_history_artikel",
        )

        show_cartons_only = False

        render_stock_history(
            df=df,
            selected_mandant_stock=selected_mandant_stock,
            selected_artikel_stock=selected_artikel_stock,
            history_start=history_start,
            history_end=history_end,
            show_cartons_only=show_cartons_only,
            STR=STR,
            widget_prefix="stats_",
        )

    # --- NOWE METRYKI (1-5) ---
    st.markdown("---")
    st.header("📊 Raport miesięczny i rankingi")

    # Globalny wybór mandanta dla tych statystyk
    col_m_stats, _ = st.columns([1, 3])
    with col_m_stats:
        stats_mandant = st.selectbox(
            "Wybierz Mandant do analizy szczegółowej",
            options=available_mandants,
            index=0,
            key="stats_general_mandant"
        )

    df_stats = df[df["MANDANT"].astype(str) == stats_mandant].copy()

    # Konfiguracja opakowań
    kartony_prefixes, other_prefixes = load_packaging_config()

    # 1. Porównanie miesięcy
    st.subheader("Porównanie miesięcy (Obecny vs Poprzedni)")
    
    now = datetime.now()
    curr_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_end = curr_month_start - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Maski dat
    mask_curr_in = df_stats["IN_DATE"] >= curr_month_start
    mask_prev_in = (df_stats["IN_DATE"] >= prev_month_start) & (df_stats["IN_DATE"] < curr_month_start)

    mask_out_valid = (df_stats["ZUSTAND"] != "401") & (df_stats["OUT_DATE"].notna())
    mask_curr_out = mask_out_valid & (df_stats["OUT_DATE"] >= curr_month_start)
    mask_prev_out = mask_out_valid & (df_stats["OUT_DATE"] >= prev_month_start) & (df_stats["OUT_DATE"] < curr_month_start)

    # Klasyfikacja kartonów (tylko dla potrzebnych wierszy, optymalizacja)
    # Ale dla uproszczenia dodamy kolumnę tymczasową
    df_stats["IsCarton"] = df_stats["ARTIKELNR"].str.startswith(tuple(kartony_prefixes), na=False)

    # Obliczenia
    c1, c2, c3, c4 = st.columns(4)
    
    # Przyjęcia
    curr_in = mask_curr_in.sum()
    prev_in = mask_prev_in.sum()
    curr_in_cart = df_stats[mask_curr_in & df_stats["IsCarton"]].shape[0]
    prev_in_cart = df_stats[mask_prev_in & df_stats["IsCarton"]].shape[0]

    c1.metric("Przyjęte (Ten miesiąc)", f"{curr_in}", f"{curr_in - prev_in}")
    c2.metric("Przyjęte Kartony", f"{curr_in_cart}", f"{curr_in_cart - prev_in_cart}")

    # Wyjścia
    curr_out = mask_curr_out.sum()
    prev_out = mask_prev_out.sum()
    curr_out_cart = df_stats[mask_curr_out & df_stats["IsCarton"]].shape[0]
    prev_out_cart = df_stats[mask_prev_out & df_stats["IsCarton"]].shape[0]

    c3.metric("Usunięte (Ten miesiąc)", f"{curr_out}", f"{curr_out - prev_out}")
    c4.metric("Usunięte Kartony", f"{curr_out_cart}", f"{curr_out_cart - prev_out_cart}")

    st.markdown("---")

    # 2 & 3. Top 5 Artykułów
    st.subheader("Rankingi artykułów (Top 5)")
    
    period_opts = {
        "Ostatni tydzień": 7,
        "Ostatni miesiąc": 30,
        "Ostatnie 3 miesiące": 90,
        "Ostatni rok": 365
    }
    selected_period = st.selectbox("Wybierz okres", options=list(period_opts.keys()), index=1)
    days_back = period_opts[selected_period]
    cutoff_date = now - timedelta(days=days_back)

    col_top_out, col_top_in = st.columns(2)

    with col_top_out:
        st.markdown("**Najczęściej wysyłane (Top 5)**")
        mask_top_out = mask_out_valid & (df_stats["OUT_DATE"] >= cutoff_date)
        top_out = df_stats[mask_top_out]["ARTIKELNR"].value_counts().head(5).reset_index()
        top_out.columns = ["Artykuł", "Liczba palet"]
        st.dataframe(top_out, use_container_width=True, hide_index=True)

    with col_top_in:
        st.markdown("**Najczęściej przyjmowane (Top 5)**")
        mask_top_in = df_stats["IN_DATE"] >= cutoff_date
        top_in = df_stats[mask_top_in]["ARTIKELNR"].value_counts().head(5).reset_index()
        top_in.columns = ["Artykuł", "Liczba palet"]
        st.dataframe(top_in, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 4. Historyczne maksimum
    st.subheader("Historyczne maksimum magazynu")
    
    # Deduplikacja (ważne!): jeden LHMNR = jedna paleta.
    # Sortujemy po IN_DATE malejąco, aby zachować najnowszy wpis w razie duplikatów.
    df_stats_unique = df_stats.sort_values("IN_DATE", ascending=False).drop_duplicates(subset=["LHMNR"], keep="first")
    
    # Budujemy oś czasu zmian (+1 przyjęcie, -1 wyjście)
    events_in = df_stats_unique[["IN_DATE"]].dropna().rename(columns={"IN_DATE": "Date"})
    events_in["Change"] = 1
    
    # Wyjścia bierzemy z unikalnych danych
    mask_out_unique = (df_stats_unique["ZUSTAND"] != "401") & (df_stats_unique["OUT_DATE"].notna())
    events_out = df_stats_unique[mask_out_unique][["OUT_DATE"]].dropna().rename(columns={"OUT_DATE": "Date"})
    events_out["Change"] = -1
    
    timeline = pd.concat([events_in, events_out]).sort_values("Date").reset_index(drop=True)
    
    if not timeline.empty:
        timeline["Stock"] = timeline["Change"].cumsum()
        max_stock = timeline["Stock"].max()
        max_date_row = timeline.loc[timeline["Stock"].idxmax()]
        max_date_val = max_date_row["Date"]
        max_date_str = max_date_val.strftime('%d.%m.%Y')
        
        st.metric("Historyczny rekord liczby palet", f"{int(max_stock):,}", f"Data: {max_date_str}", delta_color="off")
        
        # --- DEBUG TABLE ---
        with st.expander("🔍 Debug: Analiza historycznego maksimum"):
            st.write("Poniższa tabela pomaga zrozumieć, skąd wzięła się maksymalna wartość.")
            
            c_d1, c_d2 = st.columns(2)
            c_d1.info(f"Liczba wierszy przed deduplikacją: {len(df_stats)}")
            c_d2.success(f"Liczba unikalnych palet (LHMNR): {len(df_stats_unique)}")
            
            st.markdown(f"**Szczegóły dla daty rekordu: {max_date_str}**")
            
            # Sprawdźmy, co się działo w okolicach tej daty (+/- 5 dni)
            window_days = 5
            d_start = max_date_val - timedelta(days=window_days)
            d_end = max_date_val + timedelta(days=window_days)
            
            mask_window = (timeline["Date"] >= d_start) & (timeline["Date"] <= d_end)
            timeline_window = timeline[mask_window].copy()
            
            if not timeline_window.empty:
                # Agregacja dziennych zmian
                daily_changes = timeline_window.groupby("Date")["Change"].sum().reset_index(name="Zmiana netto")
                # Stan na koniec dnia (ostatnia wartość Stock z danego dnia)
                daily_stock = timeline_window.groupby("Date")["Stock"].last().reset_index(name="Stan na koniec dnia")
                
                debug_df = pd.merge(daily_changes, daily_stock, on="Date", how="outer").sort_values("Date")
                debug_df["Date"] = debug_df["Date"].dt.date
                
                st.dataframe(debug_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("**Podsumowanie i lista palet w dniu rekordu**")
            
            # Odtwarzamy stan na dzień max_date_val
            # Paleta jest na stanie, jeśli: IN <= T  ORAZ  (nie wyszła w ogóle LUB wyszła po T)
            is_out = (df_stats_unique["ZUSTAND"] != "401") & (df_stats_unique["OUT_DATE"].notna())
            out_date = df_stats_unique["OUT_DATE"]
            
            mask_in_time = df_stats_unique["IN_DATE"] <= max_date_val
            mask_still_there = (~is_out) | (out_date > max_date_val)
            
            stock_at_max = df_stats_unique[mask_in_time & mask_still_there].copy()
            
            if not stock_at_max.empty:
                # Widok zagregowany
                agg_stock_at_max = stock_at_max.groupby(["ARTIKELNR", "ARTBEZ1"]).agg(
                    Liczba_palet=("LHMNR", "nunique"),
                    Suma_sztuk=("QUANTITY", "sum")
                ).reset_index().sort_values("Liczba_palet", ascending=False)
                
                st.write("Agregacja wg artykułów:")
                st.dataframe(agg_stock_at_max, use_container_width=True, height=400)

                # --- Przyciski do pobierania ---
                @st.cache_data
                def to_excel(df_to_convert):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_to_convert.to_excel(writer, index=False, sheet_name='Dane')
                    return output.getvalue()

                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    excel_agg_data = to_excel(agg_stock_at_max)
                    st.download_button(
                        label="📥 Pobierz podsumowanie (Excel)",
                        data=excel_agg_data,
                        file_name=f"podsumowanie_stanu_{max_date_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                with col_dl2:
                    raw_cols_to_show = [
                        "MANDANT", "ARTIKELNR", "ARTBEZ1", "QUANTITY", "LHMNR", 
                        "ZUSTAND", "PLATZ", "IN_DATE", "OUT_DATE", "CREATED_BY"
                    ]
                    raw_cols_exist = [col for col in raw_cols_to_show if col in stock_at_max.columns]
                    raw_data_to_download = stock_at_max[raw_cols_exist]

                    excel_raw_data = to_excel(raw_data_to_download)
                    st.download_button(
                        label="📥 Pobierz pełną listę palet (Excel)",
                        data=excel_raw_data,
                        file_name=f"lista_palet_{max_date_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.info("Brak palet na stanie w dniu rekordu.")
            
            if max_date_val > datetime.now() + timedelta(days=30):
                st.warning(f"⚠️ Data rekordu ({max_date_str}) jest w dalekiej przyszłości! Sprawdź poprawność dat w pliku źródłowym (kolumny ANGELEGT AM / IN_DATE).")

    else:
        st.info("Brak danych do obliczenia historii.")

    st.markdown("---")

    # 5. Zalegające palety (> 1 rok)
    st.subheader("Palety składowane powyżej 1 roku")
    
    stock_now = df_stats[df_stats["ZUSTAND"] == "401"].copy()
    if not stock_now.empty:
        one_year_ago = now - timedelta(days=365)
        old_stock = stock_now[stock_now["IN_DATE"] < one_year_ago].copy()
        
        count_old = len(old_stock)
        total_stock = len(stock_now)
        pct_old = (count_old / total_stock * 100) if total_stock > 0 else 0
        
        c_old1, c_old2 = st.columns(2)
        c_old1.metric("Liczba starych palet (>1 rok)", f"{count_old}", f"{pct_old:.1f}% całości")
        
        if count_old > 0:
            with st.expander("Pokaż listę zalegających palet"):
                old_stock["Dni na magazynie"] = (now - old_stock["IN_DATE"]).dt.days
                show_cols = ["ARTIKELNR", "ARTBEZ1", "LHMNR", "IN_DATE", "Dni na magazynie", "PLATZ"]
                st.dataframe(
                    old_stock[show_cols].sort_values("IN_DATE"),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.info("Brak palet na stanie.")


        show_cartons_only = False
