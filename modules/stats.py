import streamlit as st
from datetime import datetime, timedelta

# Импортируем функцию, которая уже есть в stock.py
from modules.stock import render_stock_history



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


        show_cartons_only = False




