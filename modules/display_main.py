# modules/display_main.py
# Display of tables with filters and pallet statistics.

import streamlit as st
import pandas as pd
import numpy as np
from utils import classify_pallet, load_packaging_config


def show_main_display(filtered_df, deleted_df, STR):
    """
    Main display:
    - in 'Deleted Pallets' mode, there is a right block with pallet types and summary,
      article filter applies to deleted pallets;
    - in 'Received Pallets' mode, right side only has article summary,
      top left has header/filter for received pallets.
    Also changes the set of displayed columns.
    """

    # Determine mode by localized string
    mode_deleted = STR["mode_deleted"]
    mode_received = STR["mode_received"]

    # In main.py filters.apply_filters uses the same STR, so
    # we can restore current mode from sidebar via session_state
    # or by data characteristics. More reliable — pass mode explicitly,
    # but now using simple heuristic: if OUT_DATE != NaT,
    # then it was deleted mode. For clarity add selection button.
    # However, mode is already selected in sidebar, so
    # better to pass mode from main.py here.
    # Here assuming main.py passes st.session_state["current_mode"].

    current_mode = st.session_state.get("current_mode", mode_deleted)

    # ---------------- Metrics ----------------
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.metric("Wybrane wiersze", f"{len(filtered_df):,}")
    with col2:
        st.metric("Usunięte palety (wg PLATZ)", f"{len(deleted_df):,}")
    total_qty = deleted_df["QUANTITY"].sum() if len(deleted_df) else 0
    with col3:
        st.metric(
            "Suma sztuk na wybranych paletach",
            f"{int(total_qty):,}" if not np.isnan(total_qty) else "0"
        )

    # ---------------- General layout: two columns ----------------
    col_left, col_right = st.columns([1, 1])

    mandant = filtered_df["MANDANT"].iloc[0] if not filtered_df.empty else "351"

    # ---------- Row 1: Filter / Type Headers ----------
    with col_left:
        if current_mode == mode_deleted:
            st.markdown("### 🔍 Filtr po usuniętych paletach")
        else:
            st.markdown("### 🔍 Filtr po przyjętych paletach")

    with col_right:
        if current_mode == mode_deleted and mandant == "352" and len(deleted_df) > 0:
            st.markdown("### 📊 Suma usuniętych palet według typu")
        else:
            # to align right table header later
            st.write(" ")

    # ---------- Row 2: Article Filter / Pallet Types ----------
    with col_left:
        # filter source values — always current rows,
        # but logic is same: filter by ARTIKELNR
        source_df = deleted_df if current_mode == mode_deleted else filtered_df
        available_artikels = sorted(source_df["ARTIKELNR"].unique())

        df_show_base = filtered_df.copy()
        if available_artikels:
            selected_artikels_table = st.multiselect(
                "Artykuły z wybranych palet",
                options=available_artikels,
                default=[],
                key="table_artikel_filter"
            )

            if selected_artikels_table:
                df_show_base = df_show_base[
                    df_show_base["ARTIKELNR"].isin(selected_artikels_table)
                ].copy()
                st.info(f"Filtr: {len(selected_artikels_table)} artykułów")
        # if no available articles, df_show_base remains = filtered_df

    with col_right:
        if current_mode == mode_deleted and mandant == "352" and len(deleted_df) > 0:
            cartons_list, other_list = load_packaging_config()
            pallets_list = st.session_state.get("pallets_frames", [])

            deleted_df_classified = deleted_df.copy()
            deleted_df_classified["PALLET_TYPE"] = deleted_df_classified["ARTIKELNR"].apply(
                lambda x: classify_pallet(x, cartons_list, pallets_list, other_list)
            )

            pallet_stats = deleted_df_classified.groupby("PALLET_TYPE").agg(
                Palety=("LHMNR", lambda s: s.nunique())
            ).reset_index()

            # Horizontal view: Cartons | Other packaging | Pallets/frames (if any)
            cols_stats = st.columns(len(pallet_stats))
            for idx, row in pallet_stats.iterrows():
                with cols_stats[idx]:
                    st.metric(label=row["PALLET_TYPE"], value=f"{int(row['Palety']):,}")
        else:
            st.write(" ")

    # ---------- Row 3: Table Headers ----------
    with col_left:
        st.subheader(STR["table_result"])
    with col_right:
        if len(deleted_df) > 0:
            st.subheader(STR["table_summary"])
        else:
            st.write(" ")

    # ---------- Row 4: Tables (aligned by height) ----------


    # Column set depends on mode
    if current_mode == mode_deleted:
        # Deleted pallets:
        # show dates/times of receipt and removal + who/change
        cols_show_left = [
            "ARTIKELNR",
            "ARTBEZ1",
            "QUANTITY",
            "LHMNR",
            "IN_DATE",
            "IN_TIME",
            "OUT_DATE",
            "OUT_TIME",
            "CREATED_BY",
            "CHANGED_DATE",
            "CHANGED_TIME",
            "ZUSTAND",
            "PLATZ",
        ]
    else:
        # Received pallets: without IS_DELETED column
        cols_show_left = [
            "ARTIKELNR",
            "ARTBEZ1",
            "QUANTITY",
            "LHMNR",
            "PLATZ",
            "IN_DATE",
            "IN_TIME",
            "CREATED_BY",
        ]
        # OUT_DATE/OUT_TIME for received can be hidden if not needed


    with col_left:
        if not df_show_base.empty:
            # select date field for sorting
            sort_col = "OUT_DATE" if (current_mode == mode_deleted and "OUT_DATE" in df_show_base.columns) else "IN_DATE"

            # first sort by existing date, then select columns
            df_sorted = df_show_base.sort_values(by=sort_col, ascending=False)
            df_left = df_sorted[cols_show_left].reset_index(drop=True)

            # Rename columns for display using STR
            rename_map = {
                "ARTIKELNR": STR["col_article"],
                "ARTBEZ1": STR["col_description"],
                "QUANTITY": STR["col_qty_per_pallet"],
                "LHMNR": STR["col_pid"],
                "PLATZ": STR["col_place"],
                "IN_DATE": STR["col_in_date"],
                "IN_TIME": STR["col_in_time"],
                "OUT_DATE": STR["col_out_date"],
                "OUT_TIME": STR["col_out_time"],
                "CREATED_BY": STR["col_created_by"],
                "CHANGED_DATE": STR["col_changed_date"],
                "CHANGED_TIME": STR["col_changed_time"],
                "ZUSTAND": STR["col_status"],
            }
            st.dataframe(
                df_left.rename(columns=rename_map),
                width="stretch",
                height=350,
                hide_index=True
            )
        else:
            st.warning("Brak danych po filtrowaniu")


    with col_right:
        if len(deleted_df) > 0:
            summary = deleted_df.groupby(
                ["ARTIKELNR", "ARTBEZ1"],
                as_index=False
            ).agg(
                Deleted_Pallets=("LHMNR", lambda s: s.nunique()),
                Deleted_Qty=("QUANTITY", "sum")
            )
            summary["Deleted_Pallets"] = summary["Deleted_Pallets"].fillna(0).astype(int)
            summary["Deleted_Qty"] = summary["Deleted_Qty"].fillna(0)

            # Rename columns for summary table
            summary_display = summary.rename(columns={
                "ARTIKELNR": STR["col_article"],
                "ARTBEZ1": STR["col_description"],
                "Deleted_Pallets": STR["col_deleted_pallets"],
                "Deleted_Qty": STR["col_deleted_qty"]
            })
            st.dataframe(
                summary_display.head(10),
                width="stretch",
                hide_index=True
            )
        else:
            # Align no data message with left block height
            st.info("Brak usuniętych palet")

    # ---------- Bottom Row: Download Buttons ----------
    st.markdown("---")
    if len(deleted_df) > 0:
        render_downloads(deleted_df, summary, STR)


def render_downloads(deleted_df, summary_df, STR):
    """Только кнопка скачивания Excel-raportu"""
    cols_show = [
        "MANDANT",
        "ARTIKELNR",
        "ARTBEZ1",
        "QUANTITY",
        "LHMNR",
        "ZUSTAND",
        "PLATZ",
        "IN_DATE",
        "IN_TIME",
        "OUT_DATE",
        "OUT_TIME",
        "CREATED_BY",
        "CHANGED_DATE",
        "CHANGED_TIME",
    ]


    try:
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            deleted_df[cols_show].to_excel(
                writer, sheet_name="Deleted_Pallets", index=False
            )
            summary_df.to_excel(
                writer, sheet_name="Summary", index=False
            )

        # Одна кнопка — raport Excel
        st.download_button(
            STR["download_excel"],
            data=output.getvalue(),
            file_name="warehouse_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_excel_main",
        )
    except Exception:
        st.info(STR["install_openpyxl"])
