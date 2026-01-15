import streamlit as st
import pandas as pd
from datetime import datetime
from utils import load_packages_strategies, load_packaging_config

def get_platz_priority(platz):
    """
    Location priority:
    0: Starts with WE or BL
    1: Starts with 2 or 02
    2: Rest
    """
    p = str(platz).strip().upper()
    if p.startswith(('WE', 'BL')): return 0
    if p.startswith(('2', '02')): return 1
    return 2

def render_removal_tab(df, STR):
    
    # --- OPTIMIZATION: Initialize working stock base (only ZUSTAND 401) ---
    # Create unique data signature (e.g., shape) to detect source file change
    df_signature = df.shape
    
    if "removal_stock_df" not in st.session_state or st.session_state.get("removal_df_signature") != df_signature:
        # Create light copy with only available pallets
        stock_401 = df[df["ZUSTAND"] == "401"].copy()
        # Calculate location priority immediately (once and for all)
        stock_401["PLATZ_PRIORITY"] = stock_401["PLATZ"].apply(get_platz_priority)
        
        st.session_state["removal_stock_df"] = stock_401
        st.session_state["removal_df_signature"] = df_signature
        st.session_state["removed_pids"] = set()

    st.header(STR["removal_header"])
    st.info(STR["removal_info"])

    # 1. Check order availability
    if "orders_cache" not in st.session_state or st.session_state["orders_cache"].get("orders_all") is None:
        st.warning(STR["removal_warn_no_orders"])
        return

    orders_all = st.session_state["orders_cache"]["orders_all"]
    if orders_all.empty:
        st.warning(STR["removal_warn_empty_orders"])
        return

    # 2. File selection
    files = sorted(orders_all["SOURCE_FILE"].unique())
    selected_file = st.selectbox(STR["removal_select_file"], options=files)

    if selected_file:
        # Pass our optimized base from session state
        render_removal_tool(st.session_state["removal_stock_df"], orders_all, selected_file, STR)


def render_removal_tool(stock_df, orders_all, filename, STR):
    # CSS hack: wider tags in multiselect (attempt at 2-column layout / full width)
    # Change: tags wider (min 45%) and text wrapping
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

    # Display success message (if exists in session)
    if "removal_msg" in st.session_state:
        st.success(st.session_state.pop("removal_msg"))

    # Filter order data
    order_data = orders_all[orders_all["SOURCE_FILE"] == filename].copy()
    
    # Preserve original order (sort by first occurrence in file)
    order_data = order_data.reset_index()
    
    # Aggregate by article
    order_agg = order_data.groupby("ARTIKELNR", as_index=False).agg(
        Total_Qty=("ORDER_QTY", "sum"),
        Total_Pallets=("ORDER_PALLETS", "sum")
    )
    
    # Restore order
    first_occurrence = order_data.groupby("ARTIKELNR")['index'].min()
    order_agg['orig_idx'] = order_agg['ARTIKELNR'].map(first_occurrence)
    order_agg = order_agg.sort_values('orig_idx').drop(columns=['orig_idx'])
    
    # Calculate average quantity per pallet (for matching)
    order_agg["Qty_Per_Pallet"] = order_agg.apply(
        lambda r: r["Total_Qty"] / r["Total_Pallets"] if r["Total_Pallets"] > 0 else 0, axis=1
    )

    # Use already filtered and optimized base (stock_df is now st.session_state["removal_stock_df"])
    stock_active = stock_df.copy()

    final_pids = []

    st.markdown(STR["removal_list_header"])
    st.markdown("---")

    # Collecting data for summary
    summary_rows = []
    empty_pids_arts = []

    # Load strategy config (e.g., for articles with pallet priority)
    strategies_config = load_packages_strategies()
    pallet_priority_prefixes = strategies_config.get("pallet_priority", {}).get("prefixes", ["202671"])

    # Load packaging config (for marking cartons)
    kartony_prefixes_raw, _ = load_packaging_config()
    kartony_prefixes = [k for k in kartony_prefixes_raw if k and str(k).strip()]

    # Helper to format PLATZ (mask for 02...)
    def format_platz_display(p_val):
        p_str = str(p_val).strip()
        if p_str.startswith("02"):
            clean = p_str[2:]
            # Mask: XX-XXX-XX... (e.g. 1234567 -> 12-345-67)
            if len(clean) > 5:
                return f"{clean[:2]}-{clean[2:5]}-{clean[5:]}"
            elif len(clean) > 2:
                return f"{clean[:2]}-{clean[2:]}"
            return clean
        return p_str

    # Use form to minimize page reloads on every click
    with st.form("removal_form"):
        # Split into two columns: Others (left) | Cartons (right)
        col_others, col_cartons = st.columns(2)
        with col_others:
            st.markdown(STR["removal_col_others"])
        with col_cartons:
            st.markdown(STR["removal_col_cartons"])

        for index, row in order_agg.iterrows():
            art = row["ARTIKELNR"]
            qty_needed = row["Total_Qty"]
            pallets_needed = int(row["Total_Pallets"])
            qty_per_pal = row["Qty_Per_Pallet"]

            # Check if carton
            is_carton = str(art).startswith(tuple(kartony_prefixes))

            # Get available pallets for article
            art_stock = stock_active[stock_active["ARTIKELNR"] == art].copy()
            
            # Special logic for articles defined in packages_strategies.json (pallet count priority)
            # Check if article starts with one of defined prefixes
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
                # --- STRATEGY 1: Structural matching (by quantity per pallet) ---
                # Try to find pallets matching exactly "pieces per pallet" from order
                art_stock["Qty_Diff"] = art_stock["QUANTITY"].apply(lambda q: abs(q - qty_per_pal))
                
                df_strat1 = art_stock.sort_values(
                    by=["Qty_Diff", "PLATZ_PRIORITY", "IN_DATE"], 
                    ascending=[True, True, True]
                )
                pids_strat1 = df_strat1["LHMNR"].head(pallets_needed).tolist()
                qty_strat1 = df_strat1[df_strat1["LHMNR"].isin(pids_strat1)]["QUANTITY"].sum()
                diff_strat1 = abs(qty_strat1 - qty_needed)

                # --- STRATEGY 2: Quantitative matching (FIFO / Location Priority) ---
                # Ignore pallet division, try to collect required quantity (e.g., 11 pallets of 1 piece instead of 1 of 11)
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
                        
                        # Remember best set (closest quantitatively)
                        if curr_diff < best_strat2_diff:
                            best_strat2_diff = curr_diff
                            pids_strat2 = list(temp_pids)
                        
                        # If collected enough, stop (don't take excess pallets)
                        if temp_qty >= qty_needed:
                            break
                
                # If strategy 2 selected nothing (e.g., no stock), set error to max
                if not pids_strat2:
                    best_strat2_diff = qty_needed

                # --- DECISION ---
                # If Strategy 2 gives better quantitative match (smaller error), choose it.
                # Otherwise (tie or Strategy 1 better) stick to order structure.
                if best_strat2_diff < diff_strat1:
                    suggested_pids = pids_strat2
                else:
                    suggested_pids = pids_strat1
            
            # Target column selection
            target_col = col_cartons if is_carton else col_others

            # Display row
            with target_col:
                # Compact layout: Info left (1), Selection right (2) - adapted for narrower column
                col_info, col_select = st.columns([1, 2])
                
                # Map for multiselect display: PID (Qty) [Location]
                # Format: PID | Qty pcs | Location
                pid_map = {
                    r["LHMNR"]: f"{r['LHMNR']} | {int(r['QUANTITY'])} szt. | {format_platz_display(r['PLATZ'])}" 
                    for _, r in art_stock.iterrows()
                }
                
                # Ensure suggested PIDs are in available options
                valid_defaults = [p for p in suggested_pids if p in pid_map]
                
                with col_info:
                    st.markdown(f"**{art}**")
                    if is_carton:
                        st.markdown(f"<span style='background-color: #fff8e1; color: #5d4037; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; border: 1px solid #ffe0b2;'>{STR['removal_tag_carton']}</span>", unsafe_allow_html=True)
                    st.caption(STR["removal_target_pal"].format(val=int(pallets_needed)))
                    st.caption(STR["removal_target_qty"].format(val=int(qty_needed)))

                with col_select:
                    selected = st.multiselect(
                        STR["removal_select_pid_label"].format(art=art),
                        options=art_stock["LHMNR"].tolist(),
                        default=valid_defaults,
                        format_func=lambda x: pid_map.get(x, x),
                        key=f"sel_{filename}_{art}",
                        label_visibility="collapsed"
                    )
                    
                    # Calculate selection stats
                    sel_count = len(selected)
                    sel_qty = art_stock[art_stock["LHMNR"].isin(selected)]["QUANTITY"].sum()
                    
                    # Check compliance
                    match_pal = (sel_count == pallets_needed)
                    # Float tolerance for quantity comparison
                    match_qty = abs(sel_qty - qty_needed) < 0.1
                    
                    # Text coloring
                    if is_pallet_priority:
                        color_class = "green" if match_pal else "red"
                    else:
                        color_class = "green" if match_qty else "red"
                    
                    summary_text = STR["removal_summary_text"].format(p1=int(pallets_needed), q1=int(qty_needed), p2=sel_count, q2=int(sel_qty))
                    st.markdown(f":{color_class}[{summary_text}]")
                
                final_pids.extend(selected)
                st.divider()

                # Collecting data for summary
                if sel_count == 0:
                    empty_pids_arts.append(art)
                
                summary_rows.append({
                    "Artykuł": f"*{art}" if is_pallet_priority else art,
                    "Zamówiono (szt)": int(qty_needed),
                    "Wybrano (szt)": int(sel_qty),
                    "Różnica (szt)": int(sel_qty - qty_needed)
                })

        submit_btn = st.form_submit_button(STR["removal_submit_btn"], type="primary")

    # --- Summary Section (outside form) ---
    if summary_rows:
        st.markdown(STR["removal_summary_diff_header"])
        col_empty, col_diff = st.columns([1, 2])
        
        with col_empty:
            st.markdown(STR["removal_no_pid_header"])
            if empty_pids_arts:
                st.error(", ".join(empty_pids_arts))
            else:
                st.success(STR["removal_all_assigned"])
        
        with col_diff:
            st.markdown(STR["removal_diff_table_header"])
            df_summary = pd.DataFrame(summary_rows)
            # Show only those with difference
            df_diff = df_summary[df_summary["Różnica (szt)"] != 0]
            if not df_diff.empty:
                st.dataframe(df_diff, width="stretch", hide_index=True)
            else:
                st.success(STR["removal_no_diff"])
            st.caption(STR["removal_strategy_caption"])

    st.markdown(STR["removal_result_header"])
    if final_pids:
        # Remove duplicates (just in case)
        final_pids = list(dict.fromkeys(final_pids))
        
        # Layout: Result (left, ~35%), Button (right)
        col_res, col_btn = st.columns([0.35, 0.65])
        
        with col_res:
            # Compact result in expander
            with st.expander(STR["removal_pid_list_expander"].format(count=len(final_pids)), expanded=False):
                st.markdown("""
                <style>
                div[data-testid="stCodeBlock"] pre {
                    max-height: 300px;
                    overflow-y: auto;
                }
                </style>
                """, unsafe_allow_html=True)
                st.code("\n".join(final_pids), language="text")
                st.caption(STR["removal_copy_caption"])
        
        with col_btn:
            # Confirm removal button
            def confirm_removal():
                st.session_state["removed_pids"].update(final_pids)
                st.session_state["removal_stock_df"] = st.session_state["removal_stock_df"][~st.session_state["removal_stock_df"]["LHMNR"].isin(final_pids)]
                st.session_state["removal_msg"] = STR["removal_msg_removed"].format(count=len(final_pids))

            st.button(STR["removal_btn_confirm"], type="primary", help=STR["removal_help_confirm"], on_click=confirm_removal)
            
        if submit_btn:
            st.toast(STR["removal_toast_generated"], icon="📋")
    else:
        st.info(STR["removal_no_selection"])