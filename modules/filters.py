# modules/filters.py
# Data filtration by mandant, article, mode, and dates + date validation.

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from utils import load_packaging_config

def render_sidebar_filters(df, STR):
    """
    Renders sidebar filters and returns filtration parameters.
    Returns: selected_mandant, selected_artikel, mode, date_start, date_end
    """
    st.sidebar.header(STR["filters"])
    
    # Mandant selection
    available_mandants = ["351", "352"]
    selected_mandant = st.sidebar.selectbox(
        STR["mandant"], 
        options=available_mandants, 
        index=0
    )
    
    # Mode selection (deleted or received)
    mode = st.sidebar.radio(
        STR["mode"], 
        (STR["mode_deleted"], STR["mode_received"])
    )
    
    # Date mode selection
    st.sidebar.markdown(STR["date_mode"])
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_mode = st.sidebar.radio(
        "Date mode", 
        (STR["single"], STR["range"]), 
        label_visibility="collapsed"
    )
    
    # Date picker logic
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
        # Default values if dates are empty
        if start and end:
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())
        else:
            date_start = datetime.combine(yesterday - timedelta(days=6), datetime.min.time())
            date_end = datetime.combine(yesterday, datetime.max.time())
    
    # ✅ NEW CHECK: Date range validation
    if date_start > date_end:
        st.sidebar.error("❌ Błąd: Data 'Od' nie może być późniejsza niż 'Do'")
        st.sidebar.stop()
    
    # Article selection (after data load)
    artikel_options = sorted(
        df.loc[df["MANDANT"] == selected_mandant, "ARTIKELNR"]
        .dropna().unique().tolist()
    )
    selected_artikel = st.sidebar.multiselect(
        STR["artikel"], 
        options=artikel_options, 
        default=[]
    )
    
    return selected_mandant, selected_artikel, mode, date_start, date_end

def apply_filters(df, mandant, artikel, mode, date_start, date_end, STR):
    """
    Applies filters to the DataFrame.
    """
    # Select date field based on mode
    date_field = "OUT_DATE" if mode == STR["mode_deleted"] else "IN_DATE"
    
    # Base mandant filter
    mask = (df["MANDANT"] == mandant)
    
    # Article filter
    if artikel:
        mask &= df["ARTIKELNR"].isin([a.strip().upper() for a in artikel])
    
    # Date filter
    mask &= df[date_field].between(
        pd.Timestamp(date_start), 
        pd.Timestamp(date_end)
    )
    
    filtered_df = df[mask].copy()

    # IS_DELETED is already calculated during df preparation (ZUSTAND != 401)
    # Here we only extract the subset of deleted pallets:
    if "IS_DELETED" in filtered_df.columns:
        deleted_df = filtered_df[filtered_df["IS_DELETED"]].copy()
    else:
        # Fallback: if for some reason the column is missing
        deleted_df = filtered_df.iloc[0:0].copy()

    return filtered_df, deleted_df


def render_analysis_filters(df: pd.DataFrame, STR):
    """
    Very compact filters for the 'Orders vs Pallets Analysis' tab
    in a single line.
    """

    st.subheader(STR["analysis_filters_title"])
    
    # Generate time options (every 1h from 6:00 to 22:00)
    time_options = [""]
    t_curr = datetime(2000, 1, 1, 6, 0)
    t_end_limit = datetime(2000, 1, 1, 22, 0)
    while t_curr < t_end_limit:
        t_next = t_curr + timedelta(hours=1)
        label = f"{t_curr.strftime('%H:%M')} - {t_next.strftime('%H:%M')}"
        time_options.append(label)
        t_curr = t_next

    # Single line: Mandant | Mode | Dates (mode + from + to) | Time | Article
    col_mandant, col_mode, col_dates, col_time, col_artikel = st.columns(
        [0.6, 1.2, 2.8, 1.0, 1.4]
    )

    yesterday = (datetime.now() - timedelta(days=1)).date()

    # Mandant – very narrow column, 3 digits
    with col_mandant:
        selected_mandant = st.selectbox(
            STR["mandant"],
            options=["351", "352"],
            index=1,
            key="analysis_mandant",
        )

    # Mode: two radios – Output (OUT_DATE) / Input (IN_DATE)
    with col_mode:
        options_mode = [STR["opt_mode_out"], STR["opt_mode_in"]]
        mode_label = st.radio(
            STR["lbl_mode"],
            options=options_mode,
            index=0,
            horizontal=True,           # horizontal
            key="analysis_mode",
        )
        date_field = "OUT_DATE" if mode_label == STR["opt_mode_out"] else "IN_DATE"
        mode = STR["mode_deleted"] if date_field == "OUT_DATE" else STR["mode_received"]

    # Dates: Day / Range + Date From + Date To
    with col_dates:
        # 3 columns inside: [date mode] [from] [to]
        c_mode, c_from, c_to = st.columns([1.1, 1.1, 1.1])

        with c_mode:
            options_date_mode = [STR["opt_date_day"], STR["range"]]
            date_mode_label = st.radio(
                STR["lbl_dates"],
                options=options_date_mode,
                index=0,
                horizontal=True,        # now horizontal
                key="analysis_date_mode",
            )

        if date_mode_label == STR["opt_date_day"]:
            with c_from:
                sel_date = st.date_input(
                    STR["lbl_date"],
                    value=yesterday,
                    key="analysis_date_single",
                )
            date_start = datetime.combine(sel_date, datetime.min.time())
            date_end = datetime.combine(sel_date, datetime.max.time())
            # Reserve space for "To", but without field in "Day" mode
            with c_to:
                st.write("")  # empty placeholder
                st.write("")
        else:
            with c_from:
                start = st.date_input(
                    STR["from"],
                    value=yesterday - timedelta(days=6),
                    key="analysis_date_from",
                )
            with c_to:
                end = st.date_input(
                    STR["to"],
                    value=yesterday,
                    key="analysis_date_to",
                )
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())

    # Time (1h)
    with col_time:
        if date_mode_label == STR["opt_date_day"]:
            selected_time_range = st.selectbox(
                STR["lbl_time"],
                options=time_options,
                index=0,
                key="analysis_time_range",
            )
        else:
            selected_time_range = None

    # Article – back to multiselect, but in a slightly narrower column
    with col_artikel:
        all_artikel_options = sorted(
            df.loc[df["MANDANT"] == selected_mandant, "ARTIKELNR"]
            .dropna()
            .unique()
            .tolist()
        )
        selected_artikel = st.multiselect(
            STR["artikel"],
            options=all_artikel_options,
            default=[],
            key="analysis_artikel",
        )

    # Filter masks
    mask_global = (df["MANDANT"] == selected_mandant)

    # Filter by date (OUT_DATE or IN_DATE)
    mask_global &= df[date_field].between(
        pd.Timestamp(date_start),
        pd.Timestamp(date_end),
    )

    # 👉 Additionally: for Mode = Output, show only deleted pallets (ZUSTAND != 401)
    # This is part of the mode definition, so it goes into mask_global
    if date_field == "OUT_DATE":
        if "IS_DELETED" in df.columns:
            mask_global &= df["IS_DELETED"]
        else:
            mask_global &= df["ZUSTAND"] != "401"

    # 1. DataFrame without article filter AND WITHOUT TIME FILTER (for comparative statistics)
    # This ensures "Articles with discrepancy" metrics are independent of time and article filters.
    filtered_pallets_no_art_df = df[mask_global].copy()

    # Now create mask for view (with time and articles)
    mask_view = mask_global.copy()

    # Time filter (IN_TIME or OUT_TIME) - only for main view
    if selected_time_range:
        t_start_str, t_end_str = selected_time_range.split(" - ")
        t_start = datetime.strptime(t_start_str, "%H:%M").time()
        t_end = datetime.strptime(t_end_str, "%H:%M").time()
        
        time_col = "OUT_TIME" if date_field == "OUT_DATE" else "IN_TIME"
        
        # Vectorized time filtering - much faster than .apply()
        # First ensure column has no NaT, as it breaks comparisons
        valid_time_mask = df[time_col].notna()
        # Now actual filtering on valid data
        mask_view &= valid_time_mask & (df[time_col] >= t_start) & (df[time_col] < t_end)

    # Article filter - only for main view
    if selected_artikel:
        mask_view &= df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])

    filtered_pallets_df = df[mask_view].copy()
    

    # Here we DO NOT recalculate IS_DELETED – it is already calculated during df loading
    # and based on ZUSTAND != 401.

    # Return full list of articles for mandant (for manual orders), not just filtered ones
    # artikel_options = sorted(filtered_pallets_df["ARTIKELNR"].unique().tolist())


    return (
        selected_mandant,
        selected_artikel,
        mode,
        date_start,
        date_end,
        filtered_pallets_df,
        all_artikel_options,
        filtered_pallets_no_art_df,
    )
