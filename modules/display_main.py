# modules/display_main.py
# Отображение таблиц с фильтрами и статистикой палет

import streamlit as st
import pandas as pd
import numpy as np
from modules.ui_strings import STR


def show_main_display(filtered_df, deleted_df, STR):
    """
    Основное отображение:
    - в режиме 'Usunięte palety' есть правый блок с типами паллет и сводкой,
      фильтр по artykułom относится к удалённым паллетам;
    - в режиме 'Przyjęte palety' справа только сводка по artykułom,
      а сверху слева заголовок/фильтр по przyjętym paletom.
    Также меняется набор отображаемых колонок.
    """

    # Определяем режим по локализованной строке
    mode_deleted = STR["mode_deleted"]
    mode_received = STR["mode_received"]

    # В main.py в filters.apply_filters используется тот же STR, поэтому
    # можно восстановить текущий режим из sidebar через session_state
    # или по признакам данных. Надёжнее — передавать mode явно,
    # но сейчас используем простую эвристику: если есть OUT_DATE != NaT,
    # значит был режим удалённых. Для наглядности добавим кнопку выбора.
    # Однако вы режим уже выбираете в sidebar, поэтому
    # лучше прокинуть mode из main.py сюда.
    # Здесь предполагаем, что main.py передаёт st.session_state["current_mode"].

    current_mode = st.session_state.get("current_mode", mode_deleted)

    # ---------------- Метрики ----------------
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

    # ---------------- Общий layout: две колонки ----------------
    col_left, col_right = st.columns([1, 1])

    mandant = filtered_df["MANDANT"].iloc[0] if not filtered_df.empty else "351"

    # ---------- Ряд 1: заголовки фильтров / типов ----------
    with col_left:
        if current_mode == mode_deleted:
            st.markdown("### 🔍 Filtr po usuniętych paletach")
        else:
            st.markdown("### 🔍 Filtr po przyjętych paletach")

    with col_right:
        if current_mode == mode_deleted and mandant == "352" and len(deleted_df) > 0:
            st.markdown("### 📊 Suma usuniętych palet według typu")
        else:
            # чтобы заголовок правой таблицы позже стоял на одной линии
            st.write(" ")

    # ---------- Ряд 2: фильтр по artykułom / типы паллет ----------
    with col_left:
        # источник значений для фильтра — всегда текущие строки,
        # но логика одинаковая: фильтр по ARTIKELNR
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
        # если нет доступных artykułów, df_show_base остаётся = filtered_df

    with col_right:
        if current_mode == mode_deleted and mandant == "352" and len(deleted_df) > 0:
            cartons_list = st.session_state.get("cartons", [])
            pallets_list = st.session_state.get("pallets_frames", [])
            other_list = st.session_state.get("other_packaging", [])

            deleted_df_classified = deleted_df.copy()
            deleted_df_classified["PALLET_TYPE"] = deleted_df_classified["ARTIKELNR"].apply(
                lambda x: classify_pallet(x, cartons_list, pallets_list, other_list)
            )

            pallet_stats = deleted_df_classified.groupby("PALLET_TYPE").agg(
                Palety=("LHMNR", lambda s: s.nunique())
            ).reset_index()

            # Горизонтальное представление: Kartony | Inne opakowania | Palety/ramy (если есть)
            cols_stats = st.columns(len(pallet_stats))
            for idx, row in pallet_stats.iterrows():
                with cols_stats[idx]:
                    st.metric(label=row["PALLET_TYPE"], value=f"{int(row['Palety']):,}")
        else:
            st.write(" ")

    # ---------- Ряд 3: заголовки таблиц ----------
    with col_left:
        st.subheader(STR["table_result"])
    with col_right:
        if len(deleted_df) > 0:
            st.subheader(STR["table_summary"])
        else:
            st.write(" ")

    # ---------- Ряд 4: сами таблицы (ровно по высоте) ----------


    # Набор колонок зависит от режима
    if current_mode == mode_deleted:
        # Usunięte palety:
        # показываем даты/время przyjęcia i usunięcia + kto/zmiana
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
        # Przyjęte palety: без kolumny IS_DELETED
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
        # OUT_DATE/OUT_TIME при przyjętych можно не показывать, если не нужны


    with col_left:
        if not df_show_base.empty:
            # выбираем поле даты для сортировки
            sort_col = "OUT_DATE" if (current_mode == mode_deleted and "OUT_DATE" in df_show_base.columns) else "IN_DATE"

            # сначала сортируем по существующей дате, потом выбираем колонки
            df_sorted = df_show_base.sort_values(by=sort_col, ascending=False)
            df_left = df_sorted[cols_show_left].reset_index(drop=True)

            st.dataframe(
                df_left,
                use_container_width=True,
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

            st.dataframe(
                summary.head(10),
                use_container_width=True,
                height=350,
                hide_index=True
            )
        else:
            # Сообщение об отсутствии данных выравниваем по высоте с левым блоком
            st.info("Brak usuniętych palet")

    # ---------- Нижний ряд: кнопки скачивания ----------
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
