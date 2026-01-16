# modules/display_main.py
# Display of tables with filters and pallet statistics.
# Отображение таблиц с фильтрами и статистикой паллет.

import streamlit as st
import pandas as pd
import numpy as np
from utils import classify_pallet, load_packaging_config


def show_main_display(filtered_df, deleted_df, STR):
    # Main function to render the display area.
    # It handles metrics, filters, and data tables for both 'Deleted' and 'Received' modes.
    # Главная функция для отрисовки области отображения.
    # Обрабатывает метрики, фильтры и таблицы данных для режимов "Удаленные" и "Принятые".

    # Retrieve localized strings for modes.
    # Получаем локализованные строки для режимов.
    mode_deleted = STR["mode_deleted"]
    mode_received = STR["mode_received"]

    # Determine the current mode from session state, defaulting to 'Deleted'.
    # This allows persistence of the mode selection across reruns.
    # Определяем текущий режим из состояния сессии, по умолчанию "Удаленные".
    # Это позволяет сохранять выбор режима между перезагрузками.
    current_mode = st.session_state.get("current_mode", mode_deleted)

    # ---------------- Metrics Section ----------------
    # ---------------- Секция метрик ----------------
    
    # Create three columns for top-level metrics.
    # Создаем три колонки для метрик верхнего уровня.
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        # Display count of selected rows in the filtered DataFrame.
        # Отображаем количество выбранных строк в отфильтрованном DataFrame.
        st.metric("Wybrane wiersze", f"{len(filtered_df):,}")
    with col2:
        # Display count of deleted pallets (unique PIDs).
        # Отображаем количество удаленных паллет (уникальные PID).
        st.metric("Usunięte palety (wg PLATZ)", f"{len(deleted_df):,}")
    
    # Calculate total quantity of items on deleted pallets.
    # Вычисляем общее количество штук на удаленных паллетах.
    total_qty = deleted_df["QUANTITY"].sum() if len(deleted_df) else 0
    
    with col3:
        # Display the total quantity metric.
        # Отображаем метрику общего количества.
        st.metric(
            "Suma sztuk na wybranych paletach",
            f"{int(total_qty):,}" if not np.isnan(total_qty) else "0"
        )

    # ---------------- Layout Setup ----------------
    # ---------------- Настройка макета ----------------
    
    # Split the main area into two equal columns.
    # Разделяем основную область на две равные колонки.
    col_left, col_right = st.columns([1, 1])

    # Determine the Mandant (client ID) from the data, default to "351" if empty.
    # Определяем Mandant (ID клиента) из данных, по умолчанию "351", если пусто.
    mandant = filtered_df["MANDANT"].iloc[0] if not filtered_df.empty else "351"

    # ---------- Row 1: Headers ----------
    # ---------- Ряд 1: Заголовки ----------
    
    with col_left:
        # Display header based on the current mode.
        # Отображаем заголовок в зависимости от текущего режима.
        if current_mode == mode_deleted:
            st.markdown("### 🔍 Filtr po usuniętych paletach")
        else:
            st.markdown("### 🔍 Filtr po przyjętych paletach")

    with col_right:
        # Display summary header only for Mandant 352 in 'Deleted' mode if data exists.
        # Отображаем заголовок сводки только для Mandant 352 в режиме "Удаленные", если есть данные.
        if current_mode == mode_deleted and mandant == "352" and len(deleted_df) > 0:
            st.markdown("### 📊 Suma usuniętych palet według typu")
        else:
            # Placeholder to align layout.
            # Заполнитель для выравнивания макета.
            st.write(" ")

    # ---------- Row 2: Filters and Statistics ----------
    # ---------- Ряд 2: Фильтры и статистика ----------
    
    with col_left:
        # Determine the source DataFrame for article filtering.
        # Определяем исходный DataFrame для фильтрации по артикулам.
        source_df = deleted_df if current_mode == mode_deleted else filtered_df
        
        # Get list of unique articles available in the current view.
        # Получаем список уникальных артикулов, доступных в текущем виде.
        available_artikels = sorted(source_df["ARTIKELNR"].unique())

        df_show_base = filtered_df.copy()
        
        # Render article multiselect filter if articles are available.
        # Рендерим мультивыбор фильтра артикулов, если артикулы доступны.
        if available_artikels:
            selected_artikels_table = st.multiselect(
                "Artykuły z wybranych palet",
                options=available_artikels,
                default=[],
                key="table_artikel_filter"
            )

            # Apply article filter if selection is made.
            # Применяем фильтр по артикулам, если сделан выбор.
            if selected_artikels_table:
                df_show_base = df_show_base[
                    df_show_base["ARTIKELNR"].isin(selected_artikels_table)
                ].copy()
                st.info(f"Filtr: {len(selected_artikels_table)} artykułów")

    with col_right:
        # Render pallet type statistics (Cartons vs Pallets) for Mandant 352.
        # Рендерим статистику по типам паллет (Картоны vs Паллеты) для Mandant 352.
        if current_mode == mode_deleted and mandant == "352" and len(deleted_df) > 0:
            # Load packaging configuration.
            # Загружаем конфигурацию упаковки.
            cartons_list, other_list = load_packaging_config()
            pallets_list = st.session_state.get("pallets_frames", [])

            # Classify each pallet.
            # Классифицируем каждую паллету.
            deleted_df_classified = deleted_df.copy()
            deleted_df_classified["PALLET_TYPE"] = deleted_df_classified["ARTIKELNR"].apply(
                lambda x: classify_pallet(x, cartons_list, pallets_list, other_list)
            )

            # Aggregate counts by pallet type.
            # Агрегируем количество по типу паллеты.
            pallet_stats = deleted_df_classified.groupby("PALLET_TYPE").agg(
                Palety=("LHMNR", lambda s: s.nunique())
            ).reset_index()

            # Display metrics horizontally.
            # Отображаем метрики горизонтально.
            cols_stats = st.columns(len(pallet_stats))
            for idx, row in pallet_stats.iterrows():
                with cols_stats[idx]:
                    st.metric(label=row["PALLET_TYPE"], value=f"{int(row['Palety']):,}")
        else:
            st.write(" ")

    # ---------- Row 3: Table Titles ----------
    # ---------- Ряд 3: Заголовки таблиц ----------
    
    with col_left:
        st.subheader(STR["table_result"])
    with col_right:
        if len(deleted_df) > 0:
            st.subheader(STR["table_summary"])
        else:
            st.write(" ")

    # ---------- Row 4: Data Tables ----------
    # ---------- Ряд 4: Таблицы данных ----------

    # Define columns to display based on the mode.
    # Определяем колонки для отображения в зависимости от режима.
    if current_mode == mode_deleted:
        # Columns for 'Deleted' mode (includes deletion info).
        # Колонки для режима "Удаленные" (включая информацию об удалении).
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
        # Columns for 'Received' mode (excludes deletion info).
        # Колонки для режима "Принятые" (исключая информацию об удалении).
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


    with col_left:
        if not df_show_base.empty:
            # Determine sorting column (OUT_DATE for deleted, IN_DATE for received).
            # Определяем колонку сортировки (OUT_DATE для удаленных, IN_DATE для принятых).
            sort_col = "OUT_DATE" if (current_mode == mode_deleted and "OUT_DATE" in df_show_base.columns) else "IN_DATE"

            # Sort data and select columns.
            # Сортируем данные и выбираем колонки.
            df_sorted = df_show_base.sort_values(by=sort_col, ascending=False)
            df_left = df_sorted[cols_show_left].reset_index(drop=True)

            # Map internal column names to localized names.
            # Сопоставляем внутренние имена колонок с локализованными.
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
            
            # Display the main data table.
            # Отображаем основную таблицу данных.
            st.dataframe(
                df_left.rename(columns=rename_map),
                width="stretch",
                height=350,
                hide_index=True
            )
        else:
            st.warning("Brak danych po filtrowaniu")


    with col_right:
        # Display summary table if there are deleted pallets.
        # Отображаем сводную таблицу, если есть удаленные паллеты.
        if len(deleted_df) > 0:
            # Group by article to calculate totals.
            # Группируем по артикулу для подсчета итогов.
            summary = deleted_df.groupby(
                ["ARTIKELNR", "ARTBEZ1"],
                as_index=False
            ).agg(
                Deleted_Pallets=("LHMNR", lambda s: s.nunique()),
                Deleted_Qty=("QUANTITY", "sum")
            )
            
            # Fill NaNs and ensure correct types.
            # Заполняем NaN и обеспечиваем правильные типы.
            summary["Deleted_Pallets"] = summary["Deleted_Pallets"].fillna(0).astype(int)
            summary["Deleted_Qty"] = summary["Deleted_Qty"].fillna(0)

            # Rename columns for display.
            # Переименовываем колонки для отображения.
            summary_display = summary.rename(columns={
                "ARTIKELNR": STR["col_article"],
                "ARTBEZ1": STR["col_description"],
                "Deleted_Pallets": STR["col_deleted_pallets"],
                "Deleted_Qty": STR["col_deleted_qty"]
            })
            
            # Display the summary table.
            # Отображаем сводную таблицу.
            st.dataframe(
                summary_display.head(10),
                width="stretch",
                hide_index=True
            )
        else:
            # Display info message if no deleted pallets.
            # Отображаем информационное сообщение, если нет удаленных паллет.
            st.info("Brak usuniętych palet")

    # ---------- Bottom Row: Download Buttons ----------
    # ---------- Нижний ряд: Кнопки скачивания ----------
    st.markdown("---")
    if len(deleted_df) > 0:
        render_downloads(deleted_df, summary, STR)


def render_downloads(deleted_df, summary_df, STR):
    # Renders the download button for the Excel report.
    # Рендерит кнопку скачивания для отчета Excel.
    
    # Define columns to include in the export.
    # Определяем колонки для включения в экспорт.
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
        # Create an in-memory buffer for the Excel file.
        # Создаем буфер в памяти для файла Excel.
        output = io.BytesIO()
        
        # Write data to Excel using openpyxl engine.
        # Записываем данные в Excel, используя движок openpyxl.
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            deleted_df[cols_show].to_excel(
                writer, sheet_name="Deleted_Pallets", index=False
            )
            summary_df.to_excel(
                writer, sheet_name="Summary", index=False
            )

        # Render the download button.
        # Рендерим кнопку скачивания.
        st.download_button(
            STR["download_excel"],
            data=output.getvalue(),
            file_name="warehouse_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_excel_main",
        )
    except Exception:
        # Show info message if openpyxl is missing or error occurs.
        # Показываем сообщение, если openpyxl отсутствует или произошла ошибка.
        st.info(STR["install_openpyxl"])
