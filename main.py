# main.py
# Entry point for the Streamlit application.
# Handles session management, data loading, language selection, and tab rendering.

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid
import os

from modules.orders import render_orders_tab
from modules.ui_strings import get_translations
from utils import (
    load_excluded_articles,
    save_excluded_articles,
    load_packaging_config,
    save_packaging_config,
)
from modules.settings import render_settings_tab
from modules.stock import render_stock_tab
from modules.stats import render_stats_tab
from modules.data_loader import load_main_csv, save_session_to_disk, load_session_from_disk, clear_session_state
from modules.filters import render_analysis_filters
from modules.removal import render_removal_tab
from modules.downloader import run_ihka_downloader, cleanup_temp_downloads, create_standalone_package


# ==============================
# Page Configuration
# ==============================
st.set_page_config(
    page_title="Sprintbox — Raport palet",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================
# Language Selection
# ==============================
if "lang" not in st.session_state:
    st.session_state["lang"] = "PL"

lang_choice = st.sidebar.selectbox(
    "Language / Język", 
    ["PL", "EN"], 
    index=0 if st.session_state["lang"] == "PL" else 1
)
if lang_choice != st.session_state["lang"]:
    st.session_state["lang"] = lang_choice
    st.rerun()

STR = get_translations(st.session_state["lang"])
st.title(STR["title"])

# ==============================
# Session Management (UUID)
# ==============================
try:
    if "session_id" not in st.query_params:
        st.query_params["session_id"] = str(uuid.uuid4())
    session_id = st.query_params["session_id"]
except AttributeError:
    # Fallback for older Streamlit versions (< 1.30.0)
    params = st.experimental_get_query_params()
    if "session_id" not in params:
        session_id = str(uuid.uuid4())
        params["session_id"] = session_id
        st.experimental_set_query_params(**params)
    else:
        session_id = params["session_id"][0]

# ==============================
# Data Loading and Preparation
# ==============================

# --- AUTO DOWNLOAD (IHKA) ---
st.sidebar.markdown(f"### {STR['import_data']}")

if st.sidebar.button(STR["btn_auto_download"], type="primary"):
    # Status container
    status_box = st.sidebar.status("Łączenie z IHKA...", expanded=True)
    
    # Run downloader process
    file_path = run_ihka_downloader(status_box, STR)
    
    if file_path:
        # If file downloaded successfully, load it
        try:
            with open(file_path, "rb") as f:
                # Create in-memory file object to pass to load_main_csv
                from io import BytesIO
                mem_file = BytesIO(f.read())
                # Use full path to avoid [WinError 2] during caching
                mem_file.name = file_path 
                
                # Load into DataFrame
                df = load_main_csv(mem_file, STR)
                if df is not None:
                    save_session_to_disk(df, session_id)
                    st.session_state["restored_df"] = df
                    status_box.update(label="Done!", state="complete", expanded=False)
                    st.rerun()
                else:
                    status_box.update(label=STR["err_format"], state="error")
        except Exception as e:
            # Hide raw system error and show localized message
            st.sidebar.error(STR["err_process_download"])
            print(f"Auto-download error: {e}")
        finally:
            # Cleanup temp files
            cleanup_temp_downloads()
    else:
        status_box.update(label="Błąd", state="error")

# Manual link button if auto-download fails
st.sidebar.link_button(STR["btn_open_ihka"], "http://ihka.schaeflein.de/WebAccess/Auth/Login")

# --- OFFLINE TOOL DOWNLOAD ---
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {STR['offline_tool']}")
st.sidebar.caption(STR["offline_desc"])

zip_file = create_standalone_package()
st.sidebar.download_button(
    label=STR["download_script"],
    data=zip_file,
    file_name="ihka_downloader_tool.zip",
    mime="application/zip"
)

st.sidebar.caption(STR["wifi_warning"])
st.sidebar.markdown("---")

uploaded = st.sidebar.file_uploader(
    STR["upload_csv"],
    type=["csv", "txt"],
    key="main_csv",
)

df = None

# 1. Try loading from upload (priority)
if uploaded is not None:
    df = load_main_csv(uploaded, STR)
    if df is not None:
        # Save session to disk to persist across refreshes
        save_session_to_disk(df, session_id)
        if "restored_df" in st.session_state:
            del st.session_state["restored_df"]

# 2. If no upload, try restoring session from disk
if df is None:
    if "restored_df" not in st.session_state:
        saved_df = load_session_from_disk(session_id)
        if saved_df is not None:
            st.session_state["restored_df"] = saved_df
    
    if "restored_df" in st.session_state:
        df = st.session_state["restored_df"]
        st.sidebar.warning(STR["restore_session"])
        if st.sidebar.button(STR["clear_data"], key="clear_session_btn"):
            clear_session_state(session_id)
            del st.session_state["restored_df"]
            st.rerun()

if df is None:
    st.info(STR["no_file"])
    st.stop()

# --- Admin Login (Sidebar) ---
with st.sidebar:
    st.markdown("---")
    with st.expander(STR["admin_login"]):
        with st.form("admin_login_form"):
            admin_password = st.text_input(STR["password"], type="password", key="admin_pass", label_visibility="collapsed", placeholder=STR["password"])
            st.form_submit_button(STR["login"], width="stretch")

# ==============================
# Tabs
# ==============================
tabs_labels = [
    STR["tab_analysis"],
    STR["tab_stock"],
    STR["tab_stats"],
    STR["tab_removal"],
]

# Retrieve password from st.secrets (or default "admin" if secrets missing)
try:
    correct_password = st.secrets["ADMIN_PASSWORD"]
except Exception:
    correct_password = "admin"

if admin_password == correct_password:
    tabs_labels.append(STR["tab_settings"])

tabs = st.tabs(tabs_labels)

tab_analysis = tabs[0]
tab_stock = tabs[1]
tab_stats = tabs[2]
tab_removal = tabs[3]

with tab_analysis:
    st.header(STR["analysis_header"])

    # 👉 Filters are now rendered here, in this tab
    (
        selected_mandant,
        selected_artikel,
        mode,
        date_start,
        date_end,
        filtered_pallets_df,
        artikel_options,
        filtered_pallets_no_art_df,
    ) = render_analysis_filters(df, STR)

    # Calculate deleted_pallets and metrics after filtering
    kartony_prefixes, _ = load_packaging_config()

    if mode == STR["mode_received"]:
        # Received Mode: show received pallets and packaging breakdown
        total_received = len(filtered_pallets_df)
        
        if selected_mandant == "352":
            kartony_count = filtered_pallets_df[
                filtered_pallets_df["ARTIKELNR"].str.startswith(
                    tuple(kartony_prefixes),
                    na=False,
                )
            ].shape[0]
            inne_count = total_received - kartony_count
            
            col1, col2, col3 = st.columns(3)
            col1.metric(STR["received_pallets"], f"{total_received:,}")
            col2.metric(STR["received_cartons"], f"{kartony_count:,}")
            col3.metric(STR["received_other"], f"{inne_count:,}")
        else:
            # Mandant 351: only received pallets
            st.metric(STR["received_pallets"], f"{total_received:,}")

    else:
        # Output Mode: keep old logic (deleted)
        deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]]

        if selected_mandant == "352":
            col1, col2, col3 = st.columns(3)
            col1.metric(STR["deleted_pallets"], f"{len(deleted_pallets):,}")

            kartony_count = deleted_pallets[
                deleted_pallets["ARTIKELNR"].str.startswith(
                    tuple(kartony_prefixes),
                    na=False,
                )
            ].shape[0]
            inne_count = len(deleted_pallets) - kartony_count
            col2.metric(STR["deleted_cartons"], f"{kartony_count:,}")
            col3.metric(STR["deleted_other"], f"{inne_count:,}")
        else:
            # Mandant 351: only deleted pallets
            st.metric(STR["deleted_pallets"], f"{len(deleted_pallets):,}")

    render_orders_tab(
        artikel_options,
        filtered_pallets_df,
        selected_artikel,
        filtered_pallets_no_art_df=filtered_pallets_no_art_df,
        full_df=df,
        date_start=date_start,
        date_end=date_end,
        selected_mandant=selected_mandant,
        STR=STR
    )

with tab_stock:
    render_stock_tab(
        df,                # Full cleaned DataFrame
        selected_mandant,  # Current mandant from analysis filters
        selected_artikel,  # Current list of articles
        STR,
    )

with tab_stats:
    render_stats_tab(df, STR)

with tab_removal:
    render_removal_tab(df, STR)

if len(tabs) > 4:
    with tabs[4]:
        # Settings available only for admin
        render_settings_tab(STR)
