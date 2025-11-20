# warehouse_dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

st.set_page_config(page_title="Warehouse — Raport palet", layout="wide", initial_sidebar_state="expanded")

# --------------------
# Dark theme CSS
# --------------------
st.markdown(
    """
    <style>
      :root { color-scheme: dark; }
      .stApp { background-color: #0f1115; color: #d7dde5; }
      [data-testid="stSidebar"] { background-color: #0b0c0e; color: #d7dde5; }
      .stButton>button, .stDownloadButton>button { border-radius: 6px; }
      .ag-theme-streamlit { --ag-background-color: #0f1115; --ag-odd-row-background-color: #111318; --ag-row-hover-color: #1a222a; --ag-header-background-color: #0c1013; --ag-foreground-color: #d7dde5; color: #d7dde5; }
      .small-note { color:#9fb0c8; font-size:0.9em; }
      .delete-btn { background-color: #ff4b4b; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; }
      .delete-btn:hover { background-color: #ff3333; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------
# Polish UI strings
# --------------------
STR = {
    "title": "Warehouse — Raport palet",
    "upload_csv": "Wybierz plik raportu (CSV, separator ';')",
    "no_file": "Proszę załadować plik CSV, aby kontynuować.",
    "filters": "Filtry",
    "mandant": "Mandant",
    "artikel": "Artykuł (ARTIKELNR)",
    "mode": "Tryb kontroli",
    "mode_deleted": "Usunięte palety (OUT_DATE)",
    "mode_received": "Przyjęte palety (IN_DATE)",
    "date_mode": "Tryb daty",
    "single": "Pojedyncza data",
    "range": "Zakres",
    "from": "Od",
    "to": "Do",
    "table_result": "Lista palet — wynik filtra",
    "table_summary": "Suma usuniętych palet według artykułu",
    "orders_tab": "Zamówienia",
    "upload_orders": "Załaduj pliki zamówień (.csv или .xlsx) — можно wiele",
    "orders_help": "Program odczyta kolumny z plików zamówień i zbierze liczbę palet i ilość sztuk.",
    "orders_table": "Podsumowanie zamówień (agregat)",
    "compare": "Porównanie zamówień z usunięciami",
    "hide_zero_diff": "Ukryj pozycje bez rozbieżności",
    "download_csv": "Pobierz CSV (usunięte palety)",
    "download_excel": "Pobierz Excel (raport)",
    "install_openpyxl": "Zainstaluj openpyxl, aby pobierać Excel",
    "manual_orders": "Dodatkowe zamówienia (ręczne wpisy)",
    "notes": "Uwagi",
    "delete_selected": "Usuń zaznaczone",
    "add_manual": "Dodaj ręczne zamówienie",
    "invalid_artikel": "Nieprawidłowy ARTIKELNR. Wybierz z listy dostępnych artykułów.",
    "select_artikel": "Wybierz ARTIKELNR...",
    "delete": "Usuń"
}

# --------------------
# Helpers
# --------------------
def norm_art(a):
    return str(a).strip().upper()

def to_csv_bytes(df_in: pd.DataFrame, sep=";"):
    return df_in.to_csv(index=False, sep=sep).encode("utf-8-sig")

def to_excel_bytes(d1: pd.DataFrame, d2: pd.DataFrame):
    with BytesIO() as b:
        with pd.ExcelWriter(b, engine="openpyxl") as writer:
            d1.to_excel(writer, sheet_name="Deleted_Pallets", index=False)
            d2.to_excel(writer, sheet_name="Summary", index=False)
        return b.getvalue()

# --------------------
# Title and tabs
# --------------------
st.title(STR["title"])
tab_main, tab_stats, tab_settings = st.tabs(["Sprawdzanie palet", "Statystyki", "Ustawienia"])

# --------------------
# Main tab
# --------------------
with tab_main:
    st.header("Sprawdzanie palet")
    st.sidebar.header(STR["filters"])

    # Main file upload (CSV)
    uploaded = st.file_uploader(STR["upload_csv"], type=["csv", "txt"], key="main_csv", help="Plik CSV z raportem magazynowym; separator ';'")

    # Sidebar minimal filters
    available_mandants = ["351", "352"]
    selected_mandant = st.sidebar.selectbox(STR["mandant"], options=available_mandants, index=0)
    # article selection will be populated after load

    mode = st.sidebar.radio(STR["mode"], (STR["mode_deleted"], STR["mode_received"]))

    st.sidebar.markdown(STR["date_mode"])
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_mode = st.sidebar.radio("", (STR["single"], STR["range"]), label_visibility="collapsed")
    if date_mode == STR["single"]:
        sel_date = st.sidebar.date_input(STR["single"], value=yesterday, key="date_single")
        date_start = datetime.combine(sel_date, datetime.min.time())
        date_end = datetime.combine(sel_date, datetime.max.time())
    else:
        start = st.sidebar.date_input(STR["from"], value=yesterday - timedelta(days=6), key="date_from")
        end = st.sidebar.date_input(STR["to"], value=yesterday, key="date_to")
        # FIX: Проверка на наличие значений
        if start and end:
            date_start = datetime.combine(start, datetime.min.time())
            date_end = datetime.combine(end, datetime.max.time())
        else:
            # Значения по умолчанию, если даты не выбраны
            date_start = datetime.combine(yesterday - timedelta(days=6), datetime.min.time())
            date_end = datetime.combine(yesterday, datetime.max.time())

    if uploaded is None:
        st.info(STR["no_file"])
        st.stop()

    # --------------------
    # Read main CSV (semicolon)
    # --------------------
    try:
        if uploaded.name.lower().endswith(".csv") or uploaded.name.lower().endswith(".txt"):
            df_raw = pd.read_csv(uploaded, sep=';', dtype=str, encoding='utf-8')
        else:
            # try reading as csv anyway
            df_raw = pd.read_csv(uploaded, sep=';', dtype=str, encoding='utf-8')
    except Exception:
        try:
            uploaded.seek(0)
            df_raw = pd.read_csv(uploaded, sep=';', dtype=str, encoding='latin-1')
        except Exception as e:
            st.error(f"Błąd wczytywania pliku: {e}")
            st.stop()

    df_raw.columns = [c.strip() for c in df_raw.columns]
    cols_map = {c.upper(): c for c in df_raw.columns}
    required = ["MANDANT","ARTIKELNR","ARTBEZ1","QUANTITY","LHMNR","ZUSTAND","PLATZ","IN_DATE","OUT_DATE"]
    missing = [r for r in required if r not in cols_map]
    if missing:
        st.error(f"Plik nie zawiera wymaganych kolumn: {', '.join(missing)}")
        st.stop()

    df = df_raw[[cols_map[c] for c in required]].copy()
    df.columns = required

    # Keep only mandants 351/352 but allow user to select which one to view
    df = df[df["MANDANT"].astype(str).isin(["351","352"])].copy()

    # Normalize and parse types
    df["ARTIKELNR"] = df["ARTIKELNR"].astype(str).str.strip().str.upper()
    df["ARTBEZ1"] = df["ARTBEZ1"].astype(str).str.strip()
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    df["IN_DATE"] = pd.to_datetime(df["IN_DATE"], dayfirst=True, errors='coerce')
    df["OUT_DATE"] = pd.to_datetime(df["OUT_DATE"], dayfirst=True, errors='coerce')
    df["LHMNR"] = df["LHMNR"].astype(str)

    # populate artikel selector based on selected mandant
    artikel_options = sorted(df[df["MANDANT"].astype(str) == selected_mandant]["ARTIKELNR"].dropna().unique().tolist())
    selected_artikel = st.sidebar.multiselect(STR["artikel"], options=artikel_options, default=[])

    # --------------------
    # Filtering by chosen controls
    # --------------------
    date_field = "OUT_DATE" if mode == STR["mode_deleted"] else "IN_DATE"

    mask = (df["MANDANT"].astype(str) == selected_mandant)
    if selected_artikel:
        mask &= df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])
    # date filter: allow NaT to be excluded
    mask &= df[date_field].between(pd.Timestamp(date_start), pd.Timestamp(date_end))
    filtered = df[mask].copy()

    # Deleted definition: PLATZ startswith WA -> deleted; else available
    filtered["IS_DELETED"] = filtered["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA")
    deleted_df = filtered[filtered["IS_DELETED"]].copy()

    # --------------------
    # Metrics
    # --------------------
    col1, col2, col3 = st.columns([1,1,2])
    col1.metric("Wybrane wiersze", f"{len(filtered):,}")
    col2.metric("Usunięte palety (wg PLATZ)", f"{len(deleted_df):,}")
    total_qty = deleted_df["QUANTITY"].sum()
    col3.metric("Suma sztuk na wybranych paletach", f"{int(total_qty) if not np.isnan(total_qty) else 0:,}")

    # --------------------
    # Show filtered pallets (aggrid)
    # --------------------
    st.subheader(STR["table_result"])
    cols_show = ["MANDANT","ARTIKELNR","ARTBEZ1","QUANTITY","LHMNR","ZUSTAND","PLATZ","IN_DATE","OUT_DATE","IS_DELETED"]
    df_show = filtered[cols_show].sort_values(by="OUT_DATE", ascending=False).reset_index(drop=True)

    gb1 = GridOptionsBuilder.from_dataframe(df_show)
    gb1.configure_default_column(filter=True, sortable=True, resizable=True)
    gb1.configure_column("IN_DATE", type=["dateColumnFilter","customDateTimeFormat"], custom_format_string='dd.MM.yyyy HH:mm', pivot=False)
    gb1.configure_column("OUT_DATE", type=["dateColumnFilter","customDateTimeFormat"], custom_format_string='dd.MM.yyyy HH:mm', pivot=False)
    gb1.configure_column("IS_DELETED", header_name="Usunięte", width=100)
    grid1 = AgGrid(df_show, gridOptions=gb1.build(), theme="streamlit", update_mode=GridUpdateMode.NO_UPDATE, fit_columns_on_grid_load=False)

    # # --------------------
    # # Summary of deleted by article (aggrid)
    # # --------------------
    # st.subheader(STR["table_summary"])
    # summary = deleted_df.groupby(["ARTIKELNR","ARTBEZ1"], as_index=False).agg(
    #     Deleted_Pallets=("LHMNR", lambda s: s.nunique()),
    #     Deleted_Qty=("QUANTITY","sum")
    # )
    # summary["Deleted_Pallets"] = summary["Deleted_Pallets"].fillna(0).astype(int)
    # summary["Deleted_Qty"] = summary["Deleted_Qty"].fillna(0)

    # # FIX 1: Добавляем tooltip с информацией о файлах заказов
    # # Сначала создадим orders_detail_map для использования в tooltip
    # orders_detail_map = {}
    
    # # Функция для создания tooltip для таблицы summary
    # def make_summary_tooltip(art):
    #     art_norm = norm_art(art)
    #     if art_norm in orders_detail_map:
    #         files_info = []
    #         for fname, pallets in orders_detail_map[art_norm].items():
    #             if pallets > 0:
    #                 files_info.append(f"{fname}: {pallets} palet")
    #         if files_info:
    #             return "\n".join(files_info)
    #     return "Brak zamówień dla tego artykułu"

    # # Добавляем столбец с tooltip
    # summary["ORDER_TOOLTIP"] = summary["ARTIKELNR"].apply(make_summary_tooltip)

    # gb2 = GridOptionsBuilder.from_dataframe(summary[["ARTIKELNR", "ARTBEZ1", "Deleted_Pallets", "Deleted_Qty", "ORDER_TOOLTIP"]])
    # gb2.configure_default_column(filter=True, sortable=True, resizable=True)
    # gb2.configure_column("ARTIKELNR", header_name="ARTIKELNR", tooltipField="ORDER_TOOLTIP")
    # gb2.configure_column("ARTBEZ1", tooltipField="ORDER_TOOLTIP")
    # gb2.configure_column("Deleted_Pallets", tooltipField="ORDER_TOOLTIP")
    # gb2.configure_column("Deleted_Qty", tooltipField="ORDER_TOOLTIP")
    # gb2.configure_column("ORDER_TOOLTIP", hide=True)
    # AgGrid(summary[["ARTIKELNR", "ARTBEZ1", "Deleted_Pallets", "Deleted_Qty", "ORDER_TOOLTIP"]], 
    #        gridOptions=gb2.build(), theme="streamlit", update_mode=GridUpdateMode.NO_UPDATE, height=260)

    # # --------------------
    # # Downloads
    # # --------------------
    # c1, c2 = st.columns([1,1])
    # c1.download_button(STR["download_csv"], data=to_csv_bytes(deleted_df[cols_show]), file_name="deleted_pallets.csv", mime="text/csv")
    # try:
    #     c2.download_button(STR["download_excel"], data=to_excel_bytes(deleted_df[cols_show], summary), file_name="warehouse_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    # except Exception:
    #     c2.info(STR["install_openpyxl"])

    # st.markdown("---")

        # --------------------
    # Summary of deleted by article (aggrid)
    # --------------------
    st.subheader(STR["table_summary"])
    summary = deleted_df.groupby(["ARTIKELNR","ARTBEZ1"], as_index=False).agg(
        Deleted_Pallets=("LHMNR", lambda s: s.nunique()),
        Deleted_Qty=("QUANTITY","sum")
    )
    summary["Deleted_Pallets"] = summary["Deleted_Pallets"].fillna(0).astype(int)
    summary["Deleted_Qty"] = summary["Deleted_Qty"].fillna(0)

    # FIX 1: Добавляем tooltip с информацией о файлах заказов
    # Сначала создадим orders_detail_map для использования в tooltip
    orders_detail_map = {}
    
    # Функция для создания tooltip для таблицы summary
    def make_summary_tooltip(art):
        art_norm = norm_art(art)
        if art_norm in orders_detail_map:
            files_info = []
            for fname, pallets in orders_detail_map[art_norm].items():
                if pallets > 0:
                    files_info.append(f"{fname}: {pallets} palet")
            if files_info:
                return "\n".join(files_info)
        return "Brak zamówień dla tego artykułu"

    # Добавляем столбец с tooltip
    summary["ORDER_TOOLTIP"] = summary["ARTIKELNR"].apply(make_summary_tooltip)

    gb2 = GridOptionsBuilder.from_dataframe(summary[["ARTIKELNR", "ARTBEZ1", "Deleted_Pallets", "Deleted_Qty", "ORDER_TOOLTIP"]])
    gb2.configure_default_column(filter=True, sortable=True, resizable=True)
    gb2.configure_column("ARTIKELNR", header_name="ARTIKELNR", tooltipField="ORDER_TOOLTIP")
    gb2.configure_column("ARTBEZ1", tooltipField="ORDER_TOOLTIP")
    gb2.configure_column("Deleted_Pallets", tooltipField="ORDER_TOOLTIP")
    gb2.configure_column("Deleted_Qty", tooltipField="ORDER_TOOLTIP")
    gb2.configure_column("ORDER_TOOLTIP", hide=True)
    AgGrid(summary[["ARTIKELNR", "ARTBEZ1", "Deleted_Pallets", "Deleted_Qty", "ORDER_TOOLTIP"]], 
           gridOptions=gb2.build(), theme="streamlit", update_mode=GridUpdateMode.NO_UPDATE, height=260)

    # # --------------------
    # # NEW: Detailed deletion by date for selected articles
    # # --------------------
    # if selected_artikel:
    #     st.subheader("Szczegóły usunięć według daty dla wybranych artykułów")
        
    #     # Фильтруем удаленные паллеты по выбранным артикулам
    #     detailed_deleted = deleted_df[deleted_df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])].copy()
        
    #     if not detailed_deleted.empty:
    #         # Группируем по дате и артикулу
    #         date_details = detailed_deleted.groupby(["OUT_DATE", "ARTIKELNR", "ARTBEZ1"]).agg(
    #             Palety=("LHMNR", lambda s: s.nunique()),
    #             Sztuki=("QUANTITY", "sum")
    #         ).reset_index()
            
    #         # Сортируем по дате (новые сверху)
    #         date_details = date_details.sort_values("OUT_DATE", ascending=False)
            
    #         # Форматируем дату для отображения
    #         date_details["Data"] = date_details["OUT_DATE"].dt.strftime("%d.%m.%Y")
            
    #         # Показываем детальную таблицу
    #         gb_details = GridOptionsBuilder.from_dataframe(date_details[["Data", "ARTIKELNR", "ARTBEZ1", "Palety", "Sztuki"]])
    #         gb_details.configure_default_column(filter=True, sortable=True, resizable=True)
    #         gb_details.configure_column("Data", header_name="Data usunięcia", width=120)
    #         gb_details.configure_column("ARTIKELNR", header_name="ARTIKELNR", width=150)
    #         gb_details.configure_column("ARTBEZ1", header_name="Nazwa artykułu")
    #         gb_details.configure_column("Palety", header_name="Liczba palet", width=110)
    #         gb_details.configure_column("Sztuki", header_name="Liczba sztuk", width=110)
            
    #         AgGrid(date_details[["Data", "ARTIKELNR", "ARTBEZ1", "Palety", "Sztuki"]],
    #                gridOptions=gb_details.build(), 
    #                theme="streamlit", 
    #                update_mode=GridUpdateMode.NO_UPDATE, 
    #                height=300)
            
    #         # Показываем сводку по выбранным артикулам
    #         st.markdown("**Podsumowanie dla wybranych artykułów:**")
    #         selected_summary = summary[summary["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])]
            
    #         if not selected_summary.empty:
    #             cols = st.columns(len(selected_summary))
    #             for idx, (_, row) in enumerate(selected_summary.iterrows()):
    #                 with cols[idx]:
    #                     st.metric(
    #                         label=f"{row['ARTIKELNR']}",
    #                         value=f"{row['Deleted_Pallets']} palet",
    #                         delta=f"{int(row['Deleted_Qty'])} sztuk"
    #                     )
    #         else:
    #             st.info("Brak danych usunięć dla wybranych artykułów w podanym zakresie dat.")
    #     else:
    #         st.info("Brak usunięć dla wybranych artykułów w podanym zakresie dat.")
    # else:
    #     st.info("Wybierz artykuły w filtrach po lewej stronie, aby zobaczyć szczegóły usunięć według daty.")

        # --------------------
    # NEW: Detailed operations by date for selected articles (dynamic based on mode)
    # --------------------
    if selected_artikel:
        if mode == STR["mode_deleted"]:
            st.subheader("Szczegóły usunięć według daty dla wybranych artykułów")
            date_field = "OUT_DATE"
            date_column_name = "Data usunięcia"
            pallets_column_name = "Liczba palet (usunięte)"
            qty_column_name = "Liczba sztuk (usunięte)"
        else:
            st.subheader("Szczegóły przyjęć według daty dla wybranych artykułów")
            date_field = "IN_DATE"
            date_column_name = "Data przyjęcia"
            pallets_column_name = "Liczba palet (przyjęte)"
            qty_column_name = "Liczba sztuk (przyjęte)"
        
        # Фильтруем данные по выбранным артикулам и соответствующему полю даты
        if mode == STR["mode_deleted"]:
            detailed_data = deleted_df[deleted_df["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])].copy()
        else:
            # Для приема используем все отфильтрованные данные (не только удаленные)
            detailed_data = filtered[filtered["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])].copy()
        
        if not detailed_data.empty:
            # Группируем по дате и артикулу
            date_details = detailed_data.groupby([date_field, "ARTIKELNR", "ARTBEZ1"]).agg(
                Palety=("LHMNR", lambda s: s.nunique()),
                Sztuki=("QUANTITY", "sum")
            ).reset_index()
            
            # Сортируем по дате (новые сверху) - используем исходный datetime для правильной сортировки
            date_details = date_details.sort_values(date_field, ascending=False)
            
            # Создаем отдельную колонку для отображения даты (только для отображения)
            date_details["Data_display"] = date_details[date_field].dt.strftime("%d.%m.%Y")
            
            # Показываем детальную таблицу
            gb_details = GridOptionsBuilder.from_dataframe(date_details[["Data_display", "ARTIKELNR", "ARTBEZ1", "Palety", "Sztuki"]])
            gb_details.configure_default_column(filter=True, sortable=True, resizable=True)
            gb_details.configure_column("Data_display", header_name=date_column_name, width=120, sortable=True)
            gb_details.configure_column("ARTIKELNR", header_name="ARTIKELNR", width=150)
            gb_details.configure_column("ARTBEZ1", header_name="Nazwa artykułu")
            gb_details.configure_column("Palety", header_name=pallets_column_name, width=130)
            gb_details.configure_column("Sztuki", header_name=qty_column_name, width=130)
            
            # Используем AgGrid с правильной сортировкой по дате
            grid_options = gb_details.build()
            
            # Добавляем кастомную сортировку для даты
            grid_options['columnDefs'][0]['comparator'] = JsCode("""
                function(valueA, valueB, nodeA, nodeB, isDescending) {
                    // Используем исходные даты для сортировки, а не отображаемые строки
                    const dateA = new Date(nodeA.data[""" + f'"{date_field}"' + """]);
                    const dateB = new Date(nodeB.data[""" + f'"{date_field}"' + """]);
                    return dateA - dateB;
                }
            """)
            
            AgGrid(date_details[["Data_display", "ARTIKELNR", "ARTBEZ1", "Palety", "Sztuki", date_field]],
                   gridOptions=grid_options, 
                   theme="streamlit", 
                   update_mode=GridUpdateMode.NO_UPDATE, 
                   height=300,
                   allow_unsafe_jscode=True)
            
            # Показываем сводку по выбранным артикулам
            if mode == STR["mode_deleted"]:
                st.markdown("**Podsumowanie usunięć dla wybranych artykułów:**")
                # Для удалений используем существующую summary
                selected_summary = summary[summary["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])]
            else:
                st.markdown("**Podsumowanie przyjęć dla wybranych artykułów:**")
                # Для приемов создаем новую summary
                received_summary = filtered[filtered["ARTIKELNR"].isin([s.strip().upper() for s in selected_artikel])].groupby(
                    ["ARTIKELNR", "ARTBEZ1"], as_index=False).agg(
                    Received_Pallets=("LHMNR", lambda s: s.nunique()),
                    Received_Qty=("QUANTITY", "sum")
                )
                selected_summary = received_summary
            
            if not selected_summary.empty:
                cols = st.columns(len(selected_summary))
                for idx, (_, row) in enumerate(selected_summary.iterrows()):
                    with cols[idx]:
                        if mode == STR["mode_deleted"]:
                            st.metric(
                                label=f"{row['ARTIKELNR']}",
                                value=f"{row['Deleted_Pallets']} palet",
                                delta=f"{int(row['Deleted_Qty'])} sztuk"
                            )
                        else:
                            st.metric(
                                label=f"{row['ARTIKELNR']}",
                                value=f"{int(row['Received_Pallets'])} palet",
                                delta=f"{int(row['Received_Qty'])} sztuk"
                            )
            else:
                st.info("Brak danych dla wybranych artykułów w podanym zakresie dat.")
        else:
            st.info("Brak danych dla wyбранych artykułów w podanym zakresie dat.")
    else:
        st.info("Wybierz artykuły w filtrach po lewej stronie, aby zobaczyć szczegóły według daty.")

    # --------------------
    # Downloads
    # --------------------
    c1, c2 = st.columns([1,1])
    c1.download_button(STR["download_csv"], data=to_csv_bytes(deleted_df[cols_show]), file_name="deleted_pallets.csv", mime="text/csv")
    try:
        c2.download_button(STR["download_excel"], data=to_excel_bytes(deleted_df[cols_show], summary), file_name="warehouse_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception:
        c2.info(STR["install_openpyxl"])

    st.markdown("---")

    # --------------------
    # Orders: upload multiple order files and manual entries
    # --------------------
    st.header(STR["orders_tab"])
    st.markdown(STR["orders_help"])
    uploaded_orders = st.file_uploader(STR["upload_orders"], type=["xlsx","csv","txt"], accept_multiple_files=True, key="orders_uploader")

    # Manual orders editor
    st.subheader(STR["manual_orders"])
    
    # FIX 2 & 3: Используем session_state для хранения ручных заказов с валидацией
    if 'manual_orders_data' not in st.session_state:
        st.session_state.manual_orders_data = pd.DataFrame({
            "ARTIKELNR": [], 
            "ORDER_PALLETS": [], 
            "ORDER_QTY": []
        })

    # Функция для добавления нового ручного заказа
    def add_manual_order():
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            # FIX 2: Выпадающий список с автодополнением для ARTIKELNR
            new_artikel = st.selectbox(
                STR["select_artikel"],
                options=[""] + artikel_options,
                key="new_artikel_select",
                index=0
            )
        
        with col2:
            new_pallets = st.number_input("Palety", min_value=0, value=0, key="new_pallets")
        
        with col3:
            new_qty = st.number_input("Ilość", min_value=0, value=0, key="new_qty")
        
        with col4:
            st.write("")  # Пустое пространство для выравнивания
            if st.button(STR["add_manual"], key="add_manual_btn"):
                if new_artikel and new_artikel.strip():
                    # FIX 3: Валидация ARTIKELNR
                    if new_artikel in artikel_options:
                        new_row = pd.DataFrame({
                            "ARTIKELNR": [new_artikel],
                            "ORDER_PALLETS": [int(new_pallets)],
                            "ORDER_QTY": [int(new_qty)]
                        })
                        st.session_state.manual_orders_data = pd.concat([
                            st.session_state.manual_orders_data, 
                            new_row
                        ], ignore_index=True)
                        st.rerun()
                    else:
                        st.error(STR["invalid_artikel"])
                else:
                    st.error("ARTIKELNR nie może być pusty")

    add_manual_order()

    # FIX 4: Отображаем таблицу с возможностью удаления
    if not st.session_state.manual_orders_data.empty:
        st.markdown("#### Aktualne ręczne zamówienia")
        
        # Добавляем чекбоксы для выбора строк
        manual_df_display = st.session_state.manual_orders_data.copy()
        manual_df_display["Wybierz"] = False
        
        # Отображаем таблицу с чекбоксами
        edited_manual = st.data_editor(
            manual_df_display,
            column_config={
                "Wybierz": st.column_config.CheckboxColumn("Zaznacz do usunięcia"),
                "ARTIKELNR": st.column_config.TextColumn("ARTIKELNR", width="medium"),
                "ORDER_PALLETS": st.column_config.NumberColumn("Palety", width="small"),
                "ORDER_QTY": st.column_config.NumberColumn("Ilość", width="small")
            },
            hide_index=True,
            use_container_width=True,
            key="manual_orders_editor"
        )
        
        # Кнопка удаления выбранных строк
        if st.button(STR["delete_selected"], type="secondary"):
            selected_indices = edited_manual[edited_manual["Wybierz"]].index
            if len(selected_indices) > 0:
                st.session_state.manual_orders_data = st.session_state.manual_orders_data.drop(selected_indices).reset_index(drop=True)
                st.rerun()
            else:
                st.warning("Nie zaznaczono żadnych wierszy do usunięcia")
    else:
        st.info("Brak ręcznych zamówień")

    # Parse uploaded orders
    orders_list = []
    orders_detail_map = {}  # ARTIKEL -> {filename: pallets_sum}

    def parse_order_file_to_df(fobj):
        """Parse order file and return DataFrame with columns ARTIKELNR (upper), ORDER_PALLETS (int), ORDER_QTY (numeric)"""
        try:
            name = getattr(fobj, "name", "uploaded")
            if name.lower().endswith(".csv") or name.lower().endswith(".txt"):
                df_o = pd.read_csv(fobj, sep=';', dtype=str, encoding='utf-8', header=0)
            else:
                # XLSX
                xl = pd.ExcelFile(fobj)
                sheet = "Order_Master_Sheet" if "Order_Master_Sheet" in xl.sheet_names else xl.sheet_names[0]
                try:
                    df_o = xl.parse(sheet_name=sheet, header=0, skiprows=1, dtype=str)
                except Exception:
                    # fallback first sheet without skip
                    df_o = xl.parse(sheet_name=sheet, header=0, dtype=str)
            df_o.columns = [c.strip() for c in df_o.columns]
        except Exception as e:
            st.error(f"Błąd czytania pliku zamówienia {name}: {e}")
            return None, name

        cols_lower = [str(c).lower() for c in df_o.columns]
        # find ARTIKELNR column
        art_col = None
        for i,c in enumerate(cols_lower):
            if "nr materiału" in c or "nr materialu" in c or "nr" == c.strip():
                art_col = df_o.columns[i]; break
        if art_col is None:
            # fallback second column
            if df_o.shape[1] >= 2:
                art_col = df_o.columns[1]
            else:
                art_col = df_o.columns[0]

        # find ilość sztuk (total ordered qty)
        total_col = None
        total_idx = None
        for i,c in enumerate(cols_lower):
            if "ilość sztuk" in c or "ilość" in c:
                total_col = df_o.columns[i]; total_idx = i; break

        pallets_col = None
        if total_idx is not None and total_idx + 1 < len(df_o.columns):
            pallets_col = df_o.columns[total_idx + 1]

        # szt./wiązka
        per_col = None
        for i,c in enumerate(cols_lower):
            if "szt./wiązka" in c or "szt./wią" in c or c.strip() == "szt":
                per_col = df_o.columns[i]; break

        res = pd.DataFrame()
        res["ARTIKELNR"] = df_o[art_col].astype(str).str.strip().str.upper()
        if pallets_col is not None:
            res["ORDER_PALLETS"] = pd.to_numeric(df_o[pallets_col].astype(str).str.replace(',','.'), errors='coerce').fillna(0).astype(int)
        else:
            # try to infer from ORDER_QTY / per_col
            res["ORDER_PALLETS"] = 0

        if total_col is not None:
            res["ORDER_QTY"] = pd.to_numeric(df_o[total_col].astype(str).str.replace(',','.'), errors='coerce').fillna(0)
            # if pallets not present but per_col present - compute pallets = ORDER_QTY / per_col
            if pallets_col is None and per_col is not None:
                pervals = pd.to_numeric(df_o[per_col].astype(str).str.replace(',','.'), errors='coerce').fillna(0)
                with np.errstate(divide='ignore', invalid='ignore'):
                    inferred_pallets = (res["ORDER_QTY"] / pervals).fillna(0)
                res["ORDER_PALLETS"] = inferred_pallets.round().astype(int)
        else:
            # if no total_col, try per_col and pallets_col
            if per_col is not None and pallets_col is not None:
                pervals = pd.to_numeric(df_o[per_col].astype(str).str.replace(',','.'), errors='coerce').fillna(0)
                pallets = pd.to_numeric(df_o[pallets_col].astype(str).str.replace(',','.'), errors='coerce').fillna(0)
                res["ORDER_QTY"] = (pervals * pallets)
            else:
                res["ORDER_QTY"] = 0

        return res, getattr(fobj, "name", "uploaded")

    if uploaded_orders:
        for f in uploaded_orders:
            parsed, fname = parse_order_file_to_df(f)
            if parsed is None:
                continue
            parsed["SOURCE_FILE"] = fname
            orders_list.append(parsed)
            # build detail map
            grouped = parsed.groupby("ARTIKELNR").agg(ORDER_PALLETS=("ORDER_PALLETS","sum"), ORDER_QTY=("ORDER_QTY","sum")).reset_index()
            for _, row in grouped.iterrows():
                art = row["ARTIKELNR"]
                pallets = int(row["ORDER_PALLETS"])
                # add to map
                if art not in orders_detail_map:
                    orders_detail_map[art] = {}
                orders_detail_map[art][fname] = orders_detail_map[art].get(fname, 0) + pallets

    # aggregate uploaded orders
    orders_agg = None
    if orders_list:
        orders_all = pd.concat(orders_list, ignore_index=True)
        orders_agg = orders_all.groupby("ARTIKELNR", as_index=False).agg(
            Ordered_Pallets=("ORDER_PALLETS","sum"),
            Ordered_Qty=("ORDER_QTY","sum")
        )
    else:
        orders_agg = pd.DataFrame(columns=["ARTIKELNR","Ordered_Pallets","Ordered_Qty"])

    # incorporate manual orders
    manual_df = st.session_state.manual_orders_data.copy()
    if manual_df is not None and not manual_df.empty:
        # normalize column names if user used different ones
        m = manual_df.copy()
        if "ARTIKELNR" not in m.columns and "ARTIKEL" in m.columns:
            m.rename(columns={"ARTIKEL": "ARTIKELNR"}, inplace=True)
        required_manual_cols = ["ARTIKELNR","ORDER_PALLETS","ORDER_QTY"]
        for c in required_manual_cols:
            if c not in m.columns:
                m[c] = 0
        
        # FIX 2: Сохраняем ARTIKELNR как строку без преобразования в float
        m["ARTIKELNR"] = m["ARTIKELNR"].astype(str).str.strip().str.upper()
        m["ORDER_PALLETS"] = pd.to_numeric(m["ORDER_PALLETS"], errors='coerce').fillna(0).astype(int)
        m["ORDER_QTY"] = pd.to_numeric(m["ORDER_QTY"], errors='coerce').fillna(0)

        manual_agg = m.groupby("ARTIKELNR", as_index=False).agg(
            Manual_Pallets=("ORDER_PALLETS","sum"),
            Manual_Qty=("ORDER_QTY","sum")
        )
        # merge with orders_agg
        if not orders_agg.empty:
            orders_agg = orders_agg.merge(manual_agg, on="ARTIKELNR", how="outer").fillna(0)
        else:
            orders_agg = manual_agg.rename(columns={
                "Manual_Pallets": "Ordered_Pallets",
                "Manual_Qty": "Ordered_Qty"
            })
            orders_agg["Manual_Pallets"] = orders_agg["Ordered_Pallets"]
            orders_agg["Manual_Qty"] = orders_agg["Ordered_Qty"]
    else:
        orders_agg["Manual_Pallets"] = 0
        orders_agg["Manual_Qty"] = 0

    # final ordered totals
    if "Manual_Pallets" not in orders_agg.columns:
        orders_agg["Manual_Pallets"] = 0
    if "Manual_Qty" not in orders_agg.columns:
        orders_agg["Manual_Qty"] = 0
    orders_agg["Ordered_Pallets_Total"] = orders_agg["Ordered_Pallets"].fillna(0).astype(int) + orders_agg["Manual_Pallets"].fillna(0).astype(int)
    orders_agg["Ordered_Qty_Total"] = orders_agg["Ordered_Qty"].fillna(0) + orders_agg["Manual_Qty"].fillna(0)

    # # build tooltip text for orders (files + manual)
    # def make_order_tooltip(art):
    #     lines = []
    #     a = str(art).strip().upper()
    #     if a in orders_detail_map:
    #         for fname, pallets in orders_detail_map[a].items():
    #             if pallets > 0:
    #                 lines.append(f"{fname}: {pallets} palet")
    #     # include manual if present
    #     if 'manual_agg' in locals() and not manual_agg.empty:
    #         try:
    #             man_row = manual_agg[manual_agg["ARTIKELNR"]==a]
    #             if not man_row.empty:
    #                 mp = int(man_row["Manual_Pallets"].iat[0])
    #                 if mp != 0:
    #                     lines.append(f"Dodatkowo (ręczne): {mp} palet")
    #         except Exception:
    #             pass
    #     if not lines:
    #         return "Brak informacji z plików zamówień"
    #     return "\n".join(lines)

    # orders_agg["ARTIKELNR"] = orders_agg["ARTIKELNR"].astype(str).str.strip().str.upper()
    # orders_agg["ORDER_TOOLTIP"] = orders_agg["ARTIKELNR"].apply(make_order_tooltip)

    # st.markdown("### " + STR["orders_table"])
    
    # # Добавляем чекбокс для скрытия нулевых заказов
    # hide_zero_orders = st.checkbox("Ukryj artykuły bez zamówień", value=True, key="hide_zero_orders")
    
    # # FIX 4: Отображаем агрегированные заказы с возможностью удаления
    # if not orders_agg.empty:
    #     orders_display = orders_agg[["ARTIKELNR","Ordered_Pallets_Total","Ordered_Qty_Total","ORDER_TOOLTIP"]].copy()
    #     orders_display["Wybierz"] = False
    #     orders_display.rename(columns={
    #         "ARTIKELNR":"ARTIKELNR",
    #         "Ordered_Pallets_Total":"Zamówione_palety",
    #         "Ordered_Qty_Total":"Zamówione_sztuki"
    #     }, inplace=True)

    #     # Фильтруем нулевые заказы если чекбокс активен
    #     if hide_zero_orders:
    #         orders_display = orders_display[
    #             (orders_display["Zamówione_palety"] > 0) | 
    #             (orders_display["Zamówione_sztuki"] > 0)
    #         ]

    #     # Используем data_editor вместо AgGrid для возможности удаления
    #     if not orders_display.empty:
    #         edited_orders = st.data_editor(
    #             orders_display,
    #             column_config={
    #                 "Wybierz": st.column_config.CheckboxColumn("Zaznacz do usunięcia"),
    #                 "ARTIKELNR": st.column_config.TextColumn("ARTIKELNR", width="medium"),
    #                 "Zamówione_palety": st.column_config.NumberColumn("Zamówione palety", width="small"),
    #                 "Zamówione_sztuki": st.column_config.NumberColumn("Zamówione sztuki", width="small"),
    #                 "ORDER_TOOLTIP": st.column_config.TextColumn("Tooltip", disabled=True)
    #             },
    #             hide_index=True,
    #             use_container_width=True,
    #             key="orders_aggregation_editor"
    #         )

    #         # Кнопка удаления выбранных заказов
    #         if st.button(STR["delete_selected"] + " (agregat)", type="secondary"):
    #             selected_indices = edited_orders[edited_orders["Wybierz"]].index
    #             if len(selected_indices) > 0:
    #                 # Удаляем выбранные артикулы из orders_agg
    #                 selected_arts = edited_orders.loc[selected_indices, "ARTIKELNR"].tolist()
    #                 orders_agg = orders_agg[~orders_agg["ARTIKELNR"].isin(selected_arts)].reset_index(drop=True)
    #                 st.rerun()
    #             else:
    #                 st.warning("Nie zaznaczono żadnych wierszy do usunięcia")
    #     else:
    #         st.info("Brak zamówień po zastosowaniu filtra (ukryto artykuły bez zamówień)")
    # else:
    #     st.info("Brak danych zamówień")

    #     # build tooltip text for orders (files + manual)
    # def make_order_tooltip(art):
    #     lines = []
    #     a = str(art).strip().upper()
    #     if a in orders_detail_map:
    #         for fname, pallets in orders_detail_map[a].items():
    #             if pallets > 0:
    #                 # Улучшаем читаемость: добавляем эмодзи и отступы
    #                 lines.append(f"📄 {fname}: {pallets} palet")
    #     # include manual if present
    #     if 'manual_agg' in locals() and not manual_agg.empty:
    #         try:
    #             man_row = manual_agg[manual_agg["ARTIKELNR"]==a]
    #             if not man_row.empty:
    #                 mp = int(man_row["Manual_Pallets"].iat[0])
    #                 mq = int(man_row["Manual_Qty"].iat[0])
    #                 if mp != 0:
    #                     lines.append(f"✏️ Dodatkowo (ręczne): {mp} palet / {mq} szt.")
    #         except Exception:
    #             pass
    #     if not lines:
    #         return "Brak informacji z plików zamówień"
        
    #     # Добавляем разделитель между файлами и улучшаем форматирование
    #     return "┌─ Pliki zamówień ─┐\n" + "\n".join(lines) + "\n└──────────────────┘"

        # build tooltip text for orders (files + manual)
    def make_order_tooltip(art):
        lines = []
        a = str(art).strip().upper()
        if a in orders_detail_map:
            for fname, pallets in orders_detail_map[a].items():
                if pallets > 0:
                    # Улучшаем читаемость: добавляем эмодзи и отступы
                    lines.append(f"📄 {fname}: {pallets} palet")
        
        # Всегда проверяем ручные заказы, даже если они уже были добавлены
        if 'manual_agg' in locals() and not manual_agg.empty:
            try:
                man_row = manual_agg[manual_agg["ARTIKELNR"]==a]
                if not man_row.empty:
                    mp = int(man_row["Manual_Pallets"].iat[0])
                    mq = int(man_row["Manual_Qty"].iat[0])
                    if mp != 0:
                        # Проверяем, нет ли уже этой информации в lines
                        manual_exists = any("✏️" in line for line in lines)
                        if not manual_exists:
                            lines.append(f"✏️ Dodatkowo (ręczne): {mp} palet / {mq} szt.")
            except Exception:
                pass
                
        if not lines:
            return "Brak informacji z plików zamówień"
        
        # Добавляем разделитель между файлами и улучшаем форматирование
        return "┌─ Pliki zamówień ─┐\n" + "\n".join(lines) + "\n└──────────────────┘"

    orders_agg["ARTIKELNR"] = orders_agg["ARTIKELNR"].astype(str).str.strip().str.upper()
    orders_agg["ORDER_TOOLTIP"] = orders_agg["ARTIKELNR"].apply(make_order_tooltip)

    st.markdown("### " + STR["orders_table"])
    
    # Добавляем чекбокс для скрытия нулевых заказов
    hide_zero_orders = st.checkbox("Ukryj artykuły bez zamówień", value=True, key="hide_zero_orders")
    
    # FIX 4: Отображаем агрегированные заказы с возможностью удаления
    if not orders_agg.empty:
        orders_display = orders_agg[["ARTIKELNR","Ordered_Pallets_Total","Ordered_Qty_Total","ORDER_TOOLTIP"]].copy()
        orders_display["Wybierz"] = False
        orders_display.rename(columns={
            "ARTIKELNR":"ARTIKELNR",
            "Ordered_Pallets_Total":"Zamówione_palety",
            "Ordered_Qty_Total":"Zamówione_sztuki"
        }, inplace=True)

        # Фильтруем нулевые заказы если чекбокс активен
        if hide_zero_orders:
            orders_display = orders_display[
                (orders_display["Zamówione_palety"] > 0) | 
                (orders_display["Zamówione_sztuki"] > 0)
            ]

        # Используем data_editor вместо AgGrid для возможности удаления
        if not orders_display.empty:
            # Создаем улучшенный tooltip для отображения
            def format_tooltip_display(tooltip_text):
                # Для отображения в таблице используем сокращенную версию
                if "Brak informacji" in tooltip_text:
                    return "Brak zamówień"
                # Считаем количество файлов
                file_count = tooltip_text.count("📄")
                manual_count = tooltip_text.count("✏️")
                result = f"Plików: {file_count}"
                if manual_count > 0:
                    result += f" + {manual_count} ręczne"
                return result

            orders_display["Tooltip_display"] = orders_display["ORDER_TOOLTIP"].apply(format_tooltip_display)

            edited_orders = st.data_editor(
                orders_display[["Wybierz", "ARTIKELNR", "Zamówione_palety", "Zamówione_sztuki", "Tooltip_display"]],
                column_config={
                    "Wybierz": st.column_config.CheckboxColumn("Zaznacz do usunięcia"),
                    "ARTIKELNR": st.column_config.TextColumn("ARTIKELNR", width="medium"),
                    "Zamówione_palety": st.column_config.NumberColumn("Zamówione palety", width="small"),
                    "Zamówione_sztuki": st.column_config.NumberColumn("Zamówione sztuki", width="small"),
                    "Tooltip_display": st.column_config.TextColumn("Źródła", width="medium", help="Kliknij lub najedź aby zobaczyć szczegóły")
                },
                hide_index=True,
                use_container_width=True,
                key="orders_aggregation_editor"
            )

            # # Добавляем расширенную информацию под таблицей
            # st.markdown("#### 📋 Szczegóły źródeł zamówień")
            # for _, row in orders_display.iterrows():
            #     if row["Zamówione_palety"] > 0 or row["Zamówione_sztuki"] > 0:
            #         with st.expander(f"🔍 {row['ARTIKELNR']} - szczegóły źródeł"):
            #             # Парсим tooltip для красивого отображения
            #             tooltip_text = row["ORDER_TOOLTIP"]
            #             if "Brak informacji" not in tooltip_text:
            #                 # Убираем рамки для чистого отображения
            #                 clean_text = tooltip_text.replace("┌─ Pliki zamówień ─┐\n", "").replace("\n└──────────────────┘", "")
            #                 lines = clean_text.split("\n")
            #                 for line in lines:
            #                     if line.strip():
            #                         st.write(line)
            #             else:
            #                 st.write("Brak szczegółowych informacji o źródłach")

            # # Кнопка удаления выбранных заказов
            # if st.button(STR["delete_selected"] + " (agregat)", type="secondary"):
            #     selected_indices = edited_orders[edited_orders["Wybierz"]].index
            #     if len(selected_indices) > 0:
            #         # Удаляем выбранные артикулы из orders_agg
            #         selected_arts = edited_orders.loc[selected_indices, "ARTIKELNR"].tolist()
            #         orders_agg = orders_agg[~orders_agg["ARTIKELNR"].isin(selected_arts)].reset_index(drop=True)
            #         st.rerun()
            #     else:
            #         st.warning("Nie zaznaczono żadnych wierszy do usunięcia")

            # # Добавляем расширенную информацию под таблицей (свернуто по умолчанию)
            # with st.expander("📋 Szczegóły źródeł zamówień", expanded=False):
            #     st.markdown("**Lista źródeł zamówień dla każdego artykułu:**")
                
            #     # Используем компактный формат с колонками
            #     cols = st.columns(2)
            #     col_idx = 0
                
            #     for idx, (_, row) in enumerate(orders_display.iterrows()):
            #         if row["Zamówione_palety"] > 0 or row["Zamówione_sztuki"] > 0:
            #             with cols[col_idx]:
            #                 with st.expander(f"**{row['ARTIKELNR']}** ({row['Zamówione_palety']} palet)", expanded=False):
            #                     tooltip_text = row["ORDER_TOOLTIP"]
            #                     if "Brak informacji" not in tooltip_text:
            #                         clean_text = tooltip_text.replace("┌─ Pliki zamówień ─┐\n", "").replace("\n└──────────────────┘", "")
            #                         lines = clean_text.split("\n")
            #                         for line in lines:
            #                             if line.strip():
            #                                 st.write(f"• {line}")
            #                     else:
            #                         st.write("• Brak szczegółowych informacji")
                        
            #             col_idx = (col_idx + 1) % 2  # Чередуем колонки

            # Добавляем расширенную информацию под таблицей (свернуто по умолчанию)
            with st.expander("📋 Szczegóły źródeł zamówień", expanded=False):
                st.markdown("**Lista źródeł zamówień dla każdego artykułu:**")
                
                # Сортируем артикулы по номеру (по возрастанию)
                sorted_orders = orders_display.sort_values("ARTIKELNR").reset_index(drop=True)
                
                # Разделяем на две колонки (пополам)
                half_idx = len(sorted_orders) // 2 + len(sorted_orders) % 2
                col1_arts = sorted_orders.iloc[:half_idx]
                col2_arts = sorted_orders.iloc[half_idx:]
                
                cols = st.columns(2)
                
                # Первая колонка
                with cols[0]:
                    for _, row in col1_arts.iterrows():
                        if row["Zamówione_palety"] > 0 or row["Zamówione_sztuki"] > 0:
                            with st.expander(f"**{row['ARTIKELNR']}** ({row['Zamówione_palety']} palet)", expanded=False):
                                tooltip_text = row["ORDER_TOOLTIP"]
                                if "Brak informacji" not in tooltip_text:
                                    clean_text = tooltip_text.replace("┌─ Pliki zamówień ─┐\n", "").replace("\n└──────────────────┘", "")
                                    lines = clean_text.split("\n")
                                    
                                    # Добавляем информацию о ручных заказах если есть
                                    art_norm = row['ARTIKELNR'].strip().upper()
                                    manual_info_added = False
                                    
                                    for line in lines:
                                        if line.strip():
                                            if "✏️" in line:
                                                st.write(f"• 🖊️ **{line.replace('✏️ ', '')}**")
                                                manual_info_added = True
                                            else:
                                                st.write(f"• {line}")
                                    
                                    # Если нет информации о ручных заказах, но они есть в данных
                                    if not manual_info_added and 'manual_agg' in locals():
                                        try:
                                            man_row = manual_agg[manual_agg["ARTIKELNR"] == art_norm]
                                            if not man_row.empty:
                                                mp = int(man_row["Manual_Pallets"].iat[0])
                                                mq = int(man_row["Manual_Qty"].iat[0])
                                                if mp > 0:
                                                    st.write(f"• 🖊️ **Dodatkowo (ręczne): {mp} palet / {mq} szt.**")
                                        except Exception:
                                            pass
                                else:
                                    # Если нет информации из файлов, проверяем ручные заказы
                                    art_norm = row['ARTIKELNR'].strip().upper()
                                    if 'manual_agg' in locals():
                                        try:
                                            man_row = manual_agg[manual_agg["ARTIKELNR"] == art_norm]
                                            if not man_row.empty:
                                                mp = int(man_row["Manual_Pallets"].iat[0])
                                                mq = int(man_row["Manual_Qty"].iat[0])
                                                if mp > 0:
                                                    st.write(f"• 🖊️ **Dodatkowo (ręczne): {mp} palet / {mq} szt.**")
                                            else:
                                                st.write("• Brak szczegółowych informacji")
                                        except Exception:
                                            st.write("• Brak szczegółowych informacji")
                                    else:
                                        st.write("• Brak szczegółowych informacji")
                
                # Вторая колонка
                with cols[1]:
                    for _, row in col2_arts.iterrows():
                        if row["Zamówione_palety"] > 0 or row["Zamówione_sztuki"] > 0:
                            with st.expander(f"**{row['ARTIKELNR']}** ({row['Zamówione_palety']} palet)", expanded=False):
                                tooltip_text = row["ORDER_TOOLTIP"]
                                if "Brak informacji" not in tooltip_text:
                                    clean_text = tooltip_text.replace("┌─ Pliki zamówień ─┐\n", "").replace("\n└──────────────────┘", "")
                                    lines = clean_text.split("\n")
                                    
                                    # Добавляем информацию о ручных заказах если есть
                                    art_norm = row['ARTIKELNR'].strip().upper()
                                    manual_info_added = False
                                    
                                    for line in lines:
                                        if line.strip():
                                            if "✏️" in line:
                                                st.write(f"• 🖊️ **{line.replace('✏️ ', '')}**")
                                                manual_info_added = True
                                            else:
                                                st.write(f"• {line}")
                                    
                                    # Если нет информации о ручных заказах, но они есть в данных
                                    if not manual_info_added and 'manual_agg' in locals():
                                        try:
                                            man_row = manual_agg[manual_agg["ARTIKELNR"] == art_norm]
                                            if not man_row.empty:
                                                mp = int(man_row["Manual_Pallets"].iat[0])
                                                mq = int(man_row["Manual_Qty"].iat[0])
                                                if mp > 0:
                                                    st.write(f"• 🖊️ **Dodatkowo (ręczne): {mp} palet / {mq} szt.**")
                                        except Exception:
                                            pass
                                else:
                                    # Если нет информации из файлов, проверяем ручные заказы
                                    art_norm = row['ARTIKELNR'].strip().upper()
                                    if 'manual_agg' in locals():
                                        try:
                                            man_row = manual_agg[manual_agg["ARTIKELNR"] == art_norm]
                                            if not man_row.empty:
                                                mp = int(man_row["Manual_Pallets"].iat[0])
                                                mq = int(man_row["Manual_Qty"].iat[0])
                                                if mp > 0:
                                                    st.write(f"• 🖊️ **Dodatkowo (ręczne): {mp} palet / {mq} szt.**")
                                            else:
                                                st.write("• Brak szczegółowych informacji")
                                        except Exception:
                                            st.write("• Brak szczegółowych informacji")
                                    else:
                                        st.write("• Brak szczegółowych informacji")

            # Кнопка удаления выбранных заказов
            if st.button(STR["delete_selected"] + " (agregat)", type="secondary"):
                selected_indices = edited_orders[edited_orders["Wybierz"]].index
                if len(selected_indices) > 0:
                    # Удаляем выбранные артикулы из orders_agg
                    selected_arts = edited_orders.loc[selected_indices, "ARTIKELNR"].tolist()
                    orders_agg = orders_agg[~orders_agg["ARTIKELNR"].isin(selected_arts)].reset_index(drop=True)
                    st.rerun()
                else:
                    st.warning("Nie zaznaczono żadnych wierszy do usunięcia")
        else:
            st.info("Brak zamówień po zastosowaniu filtra (ukryto artykuły bez zamówień)")
    else:
        st.info("Brak danych zamówień")

    st.markdown("---")

    # --------------------
    # Comparison: merge orders and deleted aggregates
    # --------------------
    # prepare deleted aggregation (for selected filtered set)
    del_agg = deleted_df.copy()
    del_agg["ARTIKELNR"] = del_agg["ARTIKELNR"].astype(str).str.upper()
    del_agg_summary = del_agg.groupby("ARTIKELNR", as_index=False).agg(
        Deleted_Pallets=("LHMNR", lambda s: s.nunique()),
        Deleted_Qty=("QUANTITY","sum")
    )
    if del_agg_summary.empty:
        del_agg_summary = pd.DataFrame(columns=["ARTIKELNR","Deleted_Pallets","Deleted_Qty"])

    # orders_agg may have ARTIKELNR not present in deleted and vice versa
    cmp = pd.merge(orders_agg.rename(columns={"ARTIKELNR":"ARTIKELNR"}), del_agg_summary, on="ARTIKELNR", how="outer").fillna(0)

    # enforce types
    cmp["Ordered_Pallets_Total"] = cmp["Ordered_Pallets_Total"].fillna(0).astype(int)
    cmp["Ordered_Qty_Total"] = cmp["Ordered_Qty_Total"].fillna(0).astype(float)
    cmp["Deleted_Pallets"] = cmp["Deleted_Pallets"].fillna(0).astype(int)
    cmp["Deleted_Qty"] = cmp["Deleted_Qty"].fillna(0).astype(float)

    # ========== ИСПРАВЛЕННАЯ ЛОГИКА ДЛЯ СПЕЦИАЛЬНЫХ АРТИКУЛОВ ==========
    
    # compute typical qty per article from filtered dataset
    try:
        if not filtered.empty:
            qty_mode = filtered.groupby("ARTIKELNR")["QUANTITY"].agg(
                lambda s: (s.mode().iat[0] if not s.mode().empty else (s.median() if len(s)>0 else np.nan))
            )
            qty_mode = qty_mode.to_dict()
        else:
            qty_mode = {}
    except Exception:
        qty_mode = {}

    # SPECIAL ARTICLES CONFIGURATION - CORRECTED LOGIC
    special_articles_config = {
        "202671+9687": {
            "system_pallet_qty": 4,
            "order_pallet_qty": 1,
            "compare_by": "pallets"  # Compare pallets directly for 202671+ articles
        },
        "202671+9691": {
            "system_pallet_qty": 2, 
            "order_pallet_qty": 1,
            "compare_by": "pallets"  # Compare pallets directly for 202671+ articles
        },
        "202671+9695": {
            "system_pallet_qty": 3,
            "order_pallet_qty": 1, 
            "compare_by": "pallets"  # Compare pallets directly for 202671+ articles
        },
        "DAF R-PALETTEN": {
            "system_pallet_qty": 1,
            "order_pallet_qty": 11,
            "compare_by": "qty"  # Compare quantities for DAF R-PALETTEN
        },
        "DAF K5": {
            "system_pallet_qty": 6,
            "order_pallet_qty": 1,
            "compare_by": "qty"  # Compare quantities for DAF K5
        }
    }

    def determine_primary(row):
        art = str(row["ARTIKELNR"]).upper()
        ordered_pallets = int(row["Ordered_Pallets_Total"])
        ordered_qty = float(row["Ordered_Qty_Total"])
        deleted_pallets = int(row["Deleted_Pallets"])
        deleted_qty = float(row["Deleted_Qty"])

        # Check if article is in special configuration
        if art in special_articles_config:
            config = special_articles_config[art]
            primary = config["compare_by"]  # Use the configured comparison method
        else:
            # For normal articles, use existing logic
            sys_q = qty_mode.get(art, np.nan)
            if not pd.isna(sys_q) and int(sys_q) == 1:
                primary = "qty"
            else:
                primary = "pallets"
            
        return pd.Series({
            "ARTIKELNR": art,
            "Ordered_Pallets": ordered_pallets,
            "Ordered_Qty": ordered_qty,
            "Deleted_Pallets": deleted_pallets,
            "Deleted_Qty": deleted_qty,
            "Primary": primary
        })

    # UPDATED tooltip function for special articles
    def row_tooltip(r):
        art = str(r["ARTIKELNR"]).upper()
        
        # Check if it's a special article
        if art in special_articles_config:
            config = special_articles_config[art]
            if r["Primary"] == "pallets":
                if r["Diff_Pallets"] < 0:
                    return f"SPECJALNY ARTYKUŁ - Usunięto więcej palet: {abs(int(r['Diff_Pallets']))} pal. (System: {config['system_pallet_qty']} szt/pal, Zamówienie: {config['order_pallet_qty']} szt/pal)"
                elif r["Diff_Pallets"] > 0:
                    return f"SPECJALNY ARTYKUŁ - Brakuje palet: {int(r['Diff_Pallets'])} pal. (System: {config['system_pallet_qty']} szt/pal, Zamówienie: {config['order_pallet_qty']} szt/pal)"
                else:
                    return f"SPECJALNY ARTYKUŁ - Ilość palet się zgadza (System: {config['system_pallet_qty']} szt/pal, Zamówienie: {config['order_pallet_qty']} szt/pal)"
            else:  # qty comparison
                if r["Diff_Qty"] < 0:
                    return f"SPECJALNY ARTYKUŁ - Usunięto więcej sztuk: {abs(int(r['Diff_Qty']))} szt. (System: {config['system_pallet_qty']} szt/pal, Zamówienie: {config['order_pallet_qty']} szt/pal)"
                elif r["Diff_Qty"] > 0:
                    return f"SPECJALNY ARTYKUŁ - Brakuje sztuk: {int(r['Diff_Qty'])} szt. (System: {config['system_pallet_qty']} szt/pal, Zamówienie: {config['order_pallet_qty']} szt/pal)"
                else:
                    return f"SPECJALNY ARTYKUŁ - Ilość sztuk się zgadza (System: {config['system_pallet_qty']} szt/pal, Zamówienie: {config['order_pallet_qty']} szt/pal)"
        else:
            # Normal articles - existing logic
            if r["Primary"] == "qty":
                if r["Diff_Qty"] < 0:
                    return f"Usunięto więcej (wg szt.): {abs(int(r['Diff_Qty']))} szt."
                elif r["Diff_Qty"] > 0:
                    return f"Brakuje (wg szt.): {int(r['Diff_Qty'])} szt."
                else:
                    return "Brak rozbieżności"
            else:
                if r["Diff_Pallets"] < 0:
                    return f"Usunięto więcej o {abs(int(r['Diff_Pallets']))} palet ({abs(int(r['Diff_Qty']))} szt.)"
                elif r["Diff_Pallets"] > 0:
                    return f"Brakuje {int(r['Diff_Pallets'])} palet ({int(r['Diff_Qty'])} szt.)"
                else:
                    if r["Diff_Qty"] != 0:
                        return f"Brak różnicy w paletach, ale różnica w szt.: {int(r['Diff_Qty'])}"
                    return "Brak rozbieżności"

    if not cmp.empty:
        cmp_expanded = cmp.apply(determine_primary, axis=1)
        cmp_expanded["Diff_Pallets"] = cmp_expanded["Ordered_Pallets"] - cmp_expanded["Deleted_Pallets"]
        cmp_expanded["Diff_Qty"] = cmp_expanded["Ordered_Qty"] - cmp_expanded["Deleted_Qty"]

        cmp_expanded["ROW_TOOLTIP"] = cmp_expanded.apply(row_tooltip, axis=1)

        # hide zero-diff option
        hide_zero = st.checkbox(STR["hide_zero_diff"], value=True)
        display_cmp = cmp_expanded.copy()
        if hide_zero:
            display_cmp = display_cmp[~((display_cmp["Diff_Pallets"] == 0) & (display_cmp["Diff_Qty"] == 0))]

        # prepare ORDER_TOOLTIP from orders_agg to show per-row file breakdown
        orders_toolmap = orders_agg.set_index("ARTIKELNR")["ORDER_TOOLTIP"].to_dict() if not orders_agg.empty else {}
        display_cmp["ORDER_TOOLTIP"] = display_cmp["ARTIKELNR"].apply(lambda a: orders_toolmap.get(a, "Brak danych z zamówień"))

        if display_cmp.empty:
            st.success("Brak rozbieżności dla wybranych filtrów.")
        else:
            st.markdown("### " + STR["compare"])

            # Build aggrid with conditional row style using JS
            gbc = GridOptionsBuilder.from_dataframe(display_cmp[["ARTIKELNR","Ordered_Pallets","Ordered_Qty","Deleted_Pallets","Deleted_Qty","Diff_Pallets","Diff_Qty","Primary","ROW_TOOLTIP","ORDER_TOOLTIP"]])
            gbc.configure_default_column(filter=True, sortable=True, resizable=True)
            gbc.configure_column("ARTIKELNR", header_name="ARTIKELNR", tooltipField="ORDER_TOOLTIP")
            gbc.configure_column("Ordered_Pallets", header_name="Ordered_pallets")
            gbc.configure_column("Ordered_Qty", header_name="Ordered_qty")
            gbc.configure_column("Deleted_Pallets", header_name="Deleted_pallets")
            gbc.configure_column("Deleted_Qty", header_name="Deleted_qty")
            gbc.configure_column("Diff_Pallets", header_name="Diff_pallets", tooltipField="ROW_TOOLTIP")
            gbc.configure_column("Diff_Qty", header_name="Diff_qty", tooltipField="ROW_TOOLTIP")
            gbc.configure_column("Primary", header_name="Primary")
            gbc.configure_column("ROW_TOOLTIP", hide=True)
            gbc.configure_column("ORDER_TOOLTIP", hide=True)

            gridOptions = gbc.build()

            # Add getRowStyle JS to highlight rows with differences subtly
            js_get_row_style = JsCode("""
            function(params) {
                if (!params.data) { return null; }
                if (params.data.Diff_Pallets !== 0 || params.data.Diff_Qty !== 0) {
                    return { 'background': '#22252b' };
                }
                return null;
            }
            """)
            gridOptions['getRowStyle'] = js_get_row_style

            AgGrid(display_cmp[["ARTIKELNR","Ordered_Pallets","Ordered_Qty","Deleted_Pallets","Deleted_Qty","Diff_Pallets","Diff_Qty","Primary","ORDER_TOOLTIP","ROW_TOOLTIP"]],
                   gridOptions=gridOptions,
                   theme="streamlit",
                   update_mode=GridUpdateMode.NO_UPDATE,
                   allow_unsafe_jscode=True,
                   height=420)

            # Show per-article PID lists and hints
            st.markdown("#### Szczegóły pozycji z rozbieżnościami")
            for _, r in display_cmp.iterrows():
                art = r["ARTIKELNR"]
                dp = int(r["Diff_Pallets"])
                dq = int(r["Diff_Qty"])
                primary = r["Primary"]
                st.markdown(f"**{art}** — Ordered: {int(r['Ordered_Pallets'])} palet / {int(r['Ordered_Qty'])} szt.   |   Deleted: {int(r['Deleted_Pallets'])} palet / {int(r['Deleted_Qty'])} szt.  — primary: {primary}")
                # list deleted PIDs
                pids = deleted_df[deleted_df["ARTIKELNR"].astype(str).str.upper() == art]["LHMNR"].unique().tolist()
                if pids:
                    st.text(f"Usunięte PID: {', '.join(map(str,pids[:50]))}" + ("" if len(pids) <= 50 else f"  (+{len(pids)-50} więcej)"))
                # show available (not deleted) PIDs for this art
                not_deleted = filtered[(filtered["ARTIKELNR"].astype(str).str.upper() == art) & (~filtered["IS_DELETED"])]["LHMNR"].unique().tolist()
                if not_deleted:
                    st.text(f"Dostępne (nie usunięte) PID: {', '.join(map(str,not_deleted[:50]))}" + ("" if len(not_deleted) <= 50 else f"  (+{len(not_deleted)-50} więcej)"))
                st.markdown("---")

# --------------------
# Tab: Statistics (placeholder)
# --------------------
with tab_stats:
    st.header("📊 Statystyki")
    
    # --------------------
    # Filters for statistics
    # --------------------
    st.subheader("Filtry statystyk")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Date range selection
        stat_date_mode = st.radio(
            "Tryb daty", 
            ["Ostatnie 30 dni", "Ostatnie 7 dni", "Niestandardowy"], 
            horizontal=True,
            key="stat_date_mode_radio"  # UNIQUE KEY
        )
        
        today = datetime.now().date()
        if stat_date_mode == "Ostatnie 30 dni":
            stat_start = today - timedelta(days=30)
            stat_end = today
            st.caption(f"Zakres: {stat_start.strftime('%d.%m.%Y')} - {stat_end.strftime('%d.%m.%Y')}")
        elif stat_date_mode == "Ostatnie 7 dni":
            stat_start = today - timedelta(days=7)
            stat_end = today
            st.caption(f"Zakres: {stat_start.strftime('%d.%m.%Y')} - {stat_end.strftime('%d.%m.%Y')}")
        else:
            stat_start = st.date_input("Okres od", value=today - timedelta(days=30), key="stat_start_date")
            stat_end = st.date_input("Okres do", value=today, key="stat_end_date")
    
    with col2:
        # Mandant filter
        stat_mandant = st.selectbox("Mandant", ["Wszystkie", "351", "352"], key="stat_mandant_select")
    
    with col3:
        # Operation type
        stat_operation = st.radio(
            "Typ operacji", 
            ["Usunięcia", "Przyjęcia", "Oba"], 
            horizontal=True,
            key="stat_operation_radio"  # UNIQUE KEY
        )
    
    # Convert dates to datetime
    if isinstance(stat_start, date):
        stat_start_dt = datetime.combine(stat_start, datetime.min.time())
    else:
        stat_start_dt = datetime.combine(stat_start, datetime.min.time())
        
    if isinstance(stat_end, date):
        stat_end_dt = datetime.combine(stat_end, datetime.max.time())
    else:
        stat_end_dt = datetime.combine(stat_end, datetime.max.time())
    
    # --------------------
    # Prepare data for statistics - CORRECTED LOGIC
    # --------------------
    if 'df' in locals() and not df.empty:
        # Filter data based on selections - CORRECTED
        if stat_operation == "Usunięcia":
            # For deletions: use OUT_DATE and only deleted pallets
            stats_mask = (
                (df["OUT_DATE"] >= pd.Timestamp(stat_start_dt)) & 
                (df["OUT_DATE"] <= pd.Timestamp(stat_end_dt)) &
                (df["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA"))
            )
        elif stat_operation == "Przyjęcia":
            # For receipts: use IN_DATE and all pallets (not just deleted)
            stats_mask = (
                (df["IN_DATE"] >= pd.Timestamp(stat_start_dt)) & 
                (df["IN_DATE"] <= pd.Timestamp(stat_end_dt))
            )
        else:  # "Oba"
            # For both: use appropriate date fields for each operation
            stats_mask = (
                ((df["OUT_DATE"] >= pd.Timestamp(stat_start_dt)) & 
                 (df["OUT_DATE"] <= pd.Timestamp(stat_end_dt)) &
                 (df["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA"))) |
                ((df["IN_DATE"] >= pd.Timestamp(stat_start_dt)) & 
                 (df["IN_DATE"] <= pd.Timestamp(stat_end_dt)))
            )
        
        # Apply mandant filter
        if stat_mandant != "Wszystkie":
            stats_mask &= (df["MANDANT"] == stat_mandant)
        
        stats_df = df[stats_mask].copy()
        
        # Display information about the current filter
        st.info(f"""
        **Aktywne filtry:**
        - Okres: {stat_start.strftime('%d.%m.%Y')} - {stat_end.strftime('%d.%m.%Y')}
        - Mandant: {stat_mandant}
        - Operacja: {stat_operation}
        - Znaleziono rekordów: {len(stats_df):,}
        """)
        
        if not stats_df.empty:
            # --------------------
            # 1. General Metrics - CORRECTED FOR OPERATION TYPES
            # --------------------
            st.subheader("📈 Podstawowe wskaźniki")
            
            if stat_operation == "Usunięcia":
                # For deletions: count deleted pallets and their quantities
                operation_df = stats_df[stats_df["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA")]
                operation_name = "usuniętych"
            elif stat_operation == "Przyjęcia":
                # For receipts: count all pallets in the date range
                operation_df = stats_df
                operation_name = "przyjętych"
            else:  # "Oba"
                # For both: separate calculations
                received_df = stats_df[~stats_df["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA")]
                deleted_df_stats = stats_df[stats_df["PLATZ"].fillna("").astype(str).str.upper().str.startswith("WA")]
                operation_name = "przyjętych i usuniętych"
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if stat_operation == "Oba":
                    total_pallets = len(stats_df)
                    received_pallets = len(received_df)
                    deleted_pallets = len(deleted_df_stats)
                    st.metric("Łączna liczba palet", f"{total_pallets:,}", 
                             delta=f"P: {received_pallets}, U: {deleted_pallets}")
                else:
                    total_pallets = len(operation_df)
                    st.metric(f"Liczba {operation_name} palet", f"{total_pallets:,}")
            
            with col2:
                if stat_operation == "Oba":
                    total_qty = stats_df["QUANTITY"].sum()
                    received_qty = received_df["QUANTITY"].sum()
                    deleted_qty = deleted_df_stats["QUANTITY"].sum()
                    st.metric("Łączna liczba sztuk", f"{int(total_qty):,}",
                             delta=f"P: {int(received_qty):,}, U: {int(deleted_qty):,}")
                else:
                    total_qty = operation_df["QUANTITY"].sum()
                    st.metric(f"Liczba {operation_name} sztuk", f"{int(total_qty):,}")
            
            with col3:
                unique_articles = stats_df["ARTIKELNR"].nunique()
                st.metric("Unikalne artykuły", f"{unique_articles}")
            
            with col4:
                if stat_operation == "Oba":
                    avg_per_pallet = total_qty / total_pallets if total_pallets > 0 else 0
                else:
                    avg_per_pallet = total_qty / total_pallets if total_pallets > 0 else 0
                st.metric("Średnio sztuk na palecie", f"{avg_per_pallet:.1f}")
            
            # Most frequently used articles - CORRECTED
            st.subheader("🏆 Najczęściej używane artykuły")
            
            if stat_operation == "Oba":
                # Separate analysis for received and deleted
                col1, col2 = st.columns(2)
                
                with col1:
                    top_received = received_df.groupby("ARTIKELNR").agg({
                        'LHMNR': 'nunique',
                        'QUANTITY': 'sum',
                        'ARTBEZ1': 'first'
                    }).nlargest(10, 'LHMNR')
                    
                    if not top_received.empty:
                        st.write("**Top 10 przyjmowanych artykułów:**")
                        for idx, (art, row) in enumerate(top_received.iterrows(), 1):
                            art_name = row['ARTBEZ1'] if pd.notna(row['ARTBEZ1']) else "Brak nazwy"
                            st.write(f"{idx}. **{art}** - {int(row['LHMNR'])} palet, {int(row['QUANTITY']):,} sztuk")
                
                with col2:
                    top_deleted = deleted_df_stats.groupby("ARTIKELNR").agg({
                        'LHMNR': 'nunique',
                        'QUANTITY': 'sum',
                        'ARTBEZ1': 'first'
                    }).nlargest(10, 'LHMNR')
                    
                    if not top_deleted.empty:
                        st.write("**Top 10 usuwanych artykułów:**")
                        for idx, (art, row) in enumerate(top_deleted.iterrows(), 1):
                            art_name = row['ARTBEZ1'] if pd.notna(row['ARTBEZ1']) else "Brak nazwy"
                            st.write(f"{idx}. **{art}** - {int(row['LHMNR'])} palet, {int(row['QUANTITY']):,} sztuk")
            
            else:
                # Single operation analysis
                top_articles = operation_df.groupby("ARTIKELNR").agg({
                    'LHMNR': 'nunique',
                    'QUANTITY': 'sum',
                    'ARTBEZ1': 'first'
                }).nlargest(10, 'LHMNR')
                
                if not top_articles.empty:
                    op_name = "usuwanych" if stat_operation == "Usunięcia" else "przyjmowanych"
                    st.write(f"**Top 10 {op_name} artykułów:**")
                    
                    for idx, (art, row) in enumerate(top_articles.iterrows(), 1):
                        art_name = row['ARTBEZ1'] if pd.notna(row['ARTBEZ1']) else "Brak nazwy"
                        st.write(f"{idx}. **{art}** - {int(row['LHMNR'])} palet, {int(row['QUANTITY']):,} sztuk")
                        st.caption(f"   {art_name}")
            
            # --------------------
            # 2. Trends and Time Series - CORRECTED DATE FIELDS
            # --------------------
            st.subheader("📊 Trendy i szeregi czasowe")
            
            if stat_operation == "Oba":
                # Separate received and deleted for comparison
                received_daily = received_df.groupby(
                    received_df["IN_DATE"].dt.date
                ).agg({'LHMNR': 'nunique'}).rename(columns={'LHMNR': 'Przyjęte'})
                
                deleted_daily = deleted_df_stats.groupby(
                    deleted_df_stats["OUT_DATE"].dt.date
                ).agg({'LHMNR': 'nunique'}).rename(columns={'LHMNR': 'Usunięte'})
                
                # Merge and fill missing dates
                daily_stats = pd.concat([received_daily, deleted_daily], axis=1).fillna(0)
                
            else:
                # Single operation
                date_field = "OUT_DATE" if stat_operation == "Usunięcia" else "IN_DATE"
                daily_stats = operation_df.groupby(operation_df[date_field].dt.date).agg({
                    'LHMNR': 'nunique',
                    'QUANTITY': 'sum'
                }).rename(columns={'LHMNR': 'Palety', 'QUANTITY': 'Sztuki'})
            
            if not daily_stats.empty:
                # Ensure all dates in range are present
                date_range = pd.date_range(start=stat_start, end=stat_end, freq='D')
                daily_stats = daily_stats.reindex(date_range, fill_value=0)
                
                tab1, tab2, tab3 = st.tabs(["Dzienne palety", "Dzienne sztuki", "Porównanie"])
                
                with tab1:
                    if stat_operation == "Oba":
                        st.line_chart(daily_stats[['Przyjęte', 'Usunięte']])
                        st.caption("Dzienna liczba palet - przyjęte vs usunięte")
                    else:
                        st.line_chart(daily_stats[['Palety']])
                        op_name = "usuniętych" if stat_operation == "Usunięcia" else "przyjętych"
                        st.caption(f"Dzienna liczba {op_name} palet")
                
                with tab2:
                    if stat_operation == "Oba":
                        # For both operations, show quantity comparison
                        received_qty_daily = received_df.groupby(
                            received_df["IN_DATE"].dt.date
                        ).agg({'QUANTITY': 'sum'}).rename(columns={'QUANTITY': 'Przyjęte_sztuki'})
                        
                        deleted_qty_daily = deleted_df_stats.groupby(
                            deleted_df_stats["OUT_DATE"].dt.date
                        ).agg({'QUANTITY': 'sum'}).rename(columns={'QUANTITY': 'Usunięte_sztuki'})
                        
                        qty_daily_stats = pd.concat([received_qty_daily, deleted_qty_daily], axis=1).fillna(0)
                        qty_daily_stats = qty_daily_stats.reindex(date_range, fill_value=0)
                        
                        st.line_chart(qty_daily_stats[['Przyjęte_sztuki', 'Usunięte_sztuki']])
                        st.caption("Dzienna liczba sztuk - przyjęte vs usunięte")
                    else:
                        st.line_chart(daily_stats[['Sztuki']])
                        op_name = "usuniętych" if stat_operation == "Usunięcia" else "przyjętych"
                        st.caption(f"Dzienna liczba {op_name} sztuk")
                
                with tab3:
                    if stat_operation == "Oba":
                        st.area_chart(daily_stats[['Przyjęte', 'Usunięte']])
                        st.caption("Porównanie przyjęć i usunięć - wykres obszarowy")
                    else:
                        st.info("Tryb porównania dostępny tylko przy wybranym 'Oba'")
            
            # --------------------
            # 3. Export to Excel - UPDATED
            # --------------------
            st.subheader("📥 Eksport raportu")
            
            def create_excel_report():
                """Create a comprehensive Excel report with formatting"""
                output = BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Sheet 1: Summary
                    if stat_operation == "Oba":
                        summary_data = {
                            'Wskaźnik': ['Łączna liczba palet', 'Przyjęte palety', 'Usunięte palety', 
                                        'Łączna liczba sztuk', 'Przyjęte sztuki', 'Usunięte sztuki',
                                        'Unikalne artykuły', 'Średnio sztuk na palecie'],
                            'Wartość': [total_pallets, len(received_df), len(deleted_df_stats),
                                       int(total_qty), int(received_qty), int(deleted_qty),
                                       unique_articles, f"{avg_per_pallet:.1f}"],
                        }
                    else:
                        summary_data = {
                            'Wskaźnik': [f'Liczba {operation_name} palet', f'Liczba {operation_name} sztuk', 
                                        'Unikalne artykuły', 'Średnio sztuk na palecie'],
                            'Wartość': [total_pallets, int(total_qty), unique_articles, f"{avg_per_pallet:.1f}"],
                        }
                    
                    summary_data['Okres'] = [f"{stat_start.strftime('%d.%m.%Y')} - {stat_end.strftime('%d.%m.%Y')}"] * len(summary_data['Wskaźnik'])
                    summary_data['Mandant'] = [stat_mandant] * len(summary_data['Wskaźnik'])
                    summary_data['Typ operacji'] = [stat_operation] * len(summary_data['Wskaźnik'])
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Podsumowanie', index=False)
                    
                    # Sheet 2: Daily statistics
                    daily_stats.reset_index().rename(columns={'index': 'Data'}).to_excel(
                        writer, sheet_name='Dzienne statystyki', index=False
                    )
                    
                    # Sheet 3: Top articles
                    if stat_operation == "Oba":
                        with pd.ExcelWriter(output, engine='openpyxl', mode='a') as writer:
                            top_received.reset_index().to_excel(writer, sheet_name='Top przyjęte', index=False)
                            top_deleted.reset_index().to_excel(writer, sheet_name='Top usunięte', index=False)
                    else:
                        top_articles.reset_index().to_excel(writer, sheet_name='Top artykuły', index=False)
                    
                    # Sheet 4: Raw data
                    stats_df[['MANDANT', 'ARTIKELNR', 'ARTBEZ1', 'QUANTITY', 'LHMNR', 'PLATZ', 'IN_DATE', 'OUT_DATE']].to_excel(
                        writer, sheet_name='Dane surowe', index=False
                    )
                
                return output.getvalue()
            
            # Download button
            excel_data = create_excel_report()
            st.download_button(
                label="📥 Pobierz pełny raport Excel",
                data=excel_data,
                file_name=f"raport_statystyk_{stat_operation}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="stat_export_button"  # UNIQUE KEY
            )
            
            st.caption("Raport zawiera: podsumowanie, statystyki dzienne, top artykuły i dane surowe")
            
        else:
            st.warning("Brak danych dla wyбранych filtrów.")
    else:
        st.info("Załaduj plik CSV w głównej zakładce, aby zobaczyć statystyki.")

# --------------------
# Tab: Settings (placeholder)
# --------------------
with tab_settings:
    st.header("Ustawienia")
    st.info("Ustawienia aplikacji i integracje (w przygotowaniu).")

# End of file