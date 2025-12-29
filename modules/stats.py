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
    available_mandants = sorted(df["MANDANT"].unique())
    if not available_mandants:
        st.warning("Brak danych magazynowych do zbudowania statystyk.")
        return

    with st.expander("📈 Historia liczby palet na magazynie", expanded=False):
        # 🔹 Mandant, Data od, Data do w jednej linii
        col_mandant, col_from, col_to = st.columns([1, 1, 1])

        # available_mandants = sorted(df["MANDANT"].unique()) # Już pobrane wyżej
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
        # Optymalizacja pamięci: używamy loc i unikamy astype(str), bo MANDANT jest już str
        mask_mandant = df["MANDANT"] == selected_mandant_stock
        artikel_options = sorted(
            df.loc[mask_mandant, "ARTIKELNR"]
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

    df_stats = df[df["MANDANT"] == stats_mandant].copy()

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

    # Maski wyjść
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
        st.dataframe(
            top_out,
            use_container_width=True,
            hide_index=True,
            height=250,
            column_config={
                "Artykuł": st.column_config.TextColumn(width="medium"),
                "Liczba palet": st.column_config.NumberColumn(width="small"),
            }
        )

    with col_top_in:
        st.markdown("**Najczęściej przyjmowane (Top 5)**")
        mask_top_in = df_stats["IN_DATE"] >= cutoff_date
        top_in = df_stats[mask_top_in]["ARTIKELNR"].value_counts().head(5).reset_index()
        top_in.columns = ["Artykuł", "Liczba palet"]
        st.dataframe(
            top_in,
            use_container_width=True,
            hide_index=True,
            height=250,
            column_config={
                "Artykuł": st.column_config.TextColumn(width="medium"),
                "Liczba palet": st.column_config.NumberColumn(width="small"),
            }
        )

    st.markdown("---")

    # 5. Zalegające palety (> 1 rok)
    col_h_old, col_sel_old, _ = st.columns([0.25, 0.15, 0.6])
    with col_h_old:
        st.subheader("Palety składowane powyżej")
    with col_sel_old:
        period_options = {
            "5 lat": 365 * 5,
            "3 lat": 365 * 3,
            "1 roku": 365,
            "6 miesięcy": 180
        }
        selected_period_label = st.selectbox(
            "Wybierz okres",
            options=list(period_options.keys()),
            index=2,  # Default "1 rok"
            label_visibility="collapsed",
            key="stats_old_stock_period"
        )

    days_threshold = period_options[selected_period_label]
    
    stock_now = df_stats[df_stats["ZUSTAND"] == "401"].copy()
    if not stock_now.empty:
        threshold_date = now - timedelta(days=days_threshold)
        old_stock = stock_now[stock_now["IN_DATE"] < threshold_date].copy()
        
        count_old = len(old_stock)
        total_stock = len(stock_now)
        pct_old = (count_old / total_stock * 100) if total_stock > 0 else 0
        
        c_old1, c_old2 = st.columns(2)
        c_old1.metric(f"Liczba starych palet (>{selected_period_label})", f"{count_old}", f"{pct_old:.1f}% całości")
        
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