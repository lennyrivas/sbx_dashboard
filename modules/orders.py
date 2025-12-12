# modules/orders.py
# Obsługa zamówień: pliki + ręczne wpisy, z opóźnionym przetwarzaniem

import streamlit as st
import pandas as pd
import numpy as np
import traceback
import sys
from modules.ui_strings import STR

# Cache na zamówienia z plików
if "orders_cache" not in st.session_state:
    st.session_state["orders_cache"] = {
        "files_keys": None,      # identyfikatory plików
        "orders_all": None,
        "orders_agg": None,
    }

# ---------- Parsowanie pojedynczego pliku zamówień ----------

def parse_order_file_to_df(fobj):
    """
    Czyta pojedynczy plik zamówień (XLSX w formacie z OrderMasterSheet)
    BEZ użycia pandas.read_excel / openpyxl, żeby uniknąć błędu wildcard.

    Oczekiwana struktura arkusza OrderMasterSheet:
    - kolumna A: Materialnummer / Nr materiau (ARTIKELNR)
    - kolumna B: Artikelgesamtmenge / Ilość sztuk (całkowita ilość)
    - kolumna C: liczba palet (brak nagłówka)
    - kolumna D: szt./wiązka
    Reszta kolumn ignorowana.

    Zwraca DataFrame z kolumnami:
      ARTIKELNR (upper), ORDER_PALLETS (int), ORDER_QTY (float)
    """
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    name = getattr(fobj, "name", "uploaded")

    # CSV / TXT – на будущее
    if name.lower().endswith((".csv", ".txt")):
        try:
            df_o = pd.read_csv(
                fobj,
                sep=";",
                dtype=str,
                encoding="utf-8",
                header=0,
            )
        except Exception as e:
            print("\n===== ORDER PARSE ERROR (CSV/TXT) =====", file=sys.stderr)
            traceback.print_exc()
            print("===== END ORDER PARSE ERROR =====\n", file=sys.stderr)
            st.error(f"Błąd czytania pliku zamówienia {name}: {e}")
            return None
        return None

    # ---- XLSX: низкоуровневое чтение XML ----
    try:
        fobj.seek(0)
        file_bytes = fobj.read()
        fobj.seek(0)

        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            # workbook.xml – szukamy arkusza z zamówieniem
            with zf.open("xl/workbook.xml") as wb:
                wb_tree = ET.parse(wb)
                wb_root = wb_tree.getroot()
            ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

            sheet_id = None
            for sheet in wb_root.findall("ns:sheets/ns:sheet", ns):
                sheet_name = sheet.attrib.get("name", "")
                r_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                if sheet_name in ("OrderMasterSheet", "Order_Master_Sheet"):
                    sheet_id = r_id
                    break
            if sheet_id is None:
                first_sheet = wb_root.find("ns:sheets/ns:sheet", ns)
                if first_sheet is None:
                    raise ValueError("Brak arkuszy w pliku XLSX")
                sheet_id = first_sheet.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )

            # workbook.xml.rels – ścieżka do pliku arkusza
            with zf.open("xl/_rels/workbook.xml.rels") as rels:
                rels_tree = ET.parse(rels)
                rels_root = rels_tree.getroot()
            rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

            sheet_path = None
            for rel in rels_root.findall("rel:Relationship", rel_ns):
                if rel.attrib.get("Id") == sheet_id:
                    sheet_path = rel.attrib.get("Target")
                    break
            if sheet_path is None:
                raise ValueError("Nie można znaleźć arkusza dla zamówień (rels).")

            if not sheet_path.startswith("xl/"):
                sheet_path = "xl/" + sheet_path

            # XML wybranego arkusza
            with zf.open(sheet_path) as sf:
                sheet_tree = ET.parse(sf)
                sheet_root = sheet_tree.getroot()

            # sharedStrings – teksty
            shared_strings = []
            if "xl/sharedStrings.xml" in zf.namelist():
                with zf.open("xl/sharedStrings.xml") as ssf:
                    ss_tree = ET.parse(ssf)
                    ss_root = ss_tree.getroot()
                for si in ss_root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    t = si.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    shared_strings.append(t.text if t is not None else "")

            # wiersze + komórki
            rows_data = []
            for row_elem in sheet_root.findall(
                ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"
            ):
                row_values = []
                last_col_idx = -1
                for cell in row_elem.findall(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"
                ):
                    cell_ref = cell.attrib.get("r", "")
                    col_letters = "".join(ch for ch in cell_ref if ch.isalpha())
                    col_idx = 0
                    for ch in col_letters:
                        col_idx = col_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
                    col_idx -= 1  # 0-based

                    while last_col_idx + 1 < col_idx:
                        row_values.append("")
                        last_col_idx += 1

                    v = cell.find(
                        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
                    )
                    cell_type = cell.attrib.get("t")
                    if v is not None and v.text is not None:
                        if cell_type == "s":
                            idx = int(v.text)
                            value = shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
                        else:
                            value = v.text
                    else:
                        value = ""

                    row_values.append(str(value))
                    last_col_idx = col_idx

                if row_values:
                    rows_data.append(row_values)

            if not rows_data:
                raise ValueError("Brak danych w arkuszu zamówień.")

            max_cols = max(len(r) for r in rows_data)
            rows_padded = [r + [""] * (max_cols - len(r)) for r in rows_data]
            df_o = pd.DataFrame(rows_padded)

    except Exception as e:
        print("\n===== ORDER PARSE ERROR (XLSX ZIP/XML) =====", file=sys.stderr)
        traceback.print_exc()
        print("===== END ORDER PARSE ERROR =====\n", file=sys.stderr)
        st.error(f"Błąd czytania pliku zamówienia {name}: {e}")
        return None

    # Проверка структуры
    if df_o.shape[1] < 4:
        st.error(f"Plik {name} ma za mało kolumn (oczekiwane >= 4).")
        return None

    df4 = df_o.iloc[:, :4].copy()

    if df4.shape[0] <= 2:
        st.error(f"Plik {name} ma za mało wierszy z danymi.")
        return None

    data = df4.iloc[2:].copy()
    data.columns = ["ARTIKELNR_RAW", "QTY_RAW", "PALLETS_RAW", "PER_RAW"]

    res = pd.DataFrame()
    res["ARTIKELNR"] = data["ARTIKELNR_RAW"].astype(str).str.strip().str.upper()

    res["ORDER_QTY"] = pd.to_numeric(
        data["QTY_RAW"].astype(str).str.replace(",", "."),
        errors="coerce",
    ).fillna(0)

    res["ORDER_PALLETS"] = pd.to_numeric(
        data["PALLETS_RAW"].astype(str).str.replace(",", "."),
        errors="coerce",
    ).fillna(0).astype(int)

    res = res[res["ORDER_PALLETS"] > 0].copy()

    per_vals = pd.to_numeric(
        data["PER_RAW"].astype(str).str.replace(",", "."),
        errors="coerce",
    ).fillna(0)

    missing = (res["ORDER_QTY"] == 0) & (per_vals > 0)
    if missing.any():
        res.loc[missing, "ORDER_QTY"] = (
            res.loc[missing, "ORDER_PALLETS"] * per_vals.loc[missing]
        )

    res["ARTIKELNR"] = res["ARTIKELNR"].astype(str).str.strip()
    res = res[res["ARTIKELNR"] != ""].copy()

    return res

# ---------- Agregacja wielu plików zamówień ----------

def natural_sort_key(text):
    import re
    parts = re.split(r"(\d+)", str(text).upper())
    return [int(p) if p.isdigit() else p for p in parts]

def aggregate_uploaded_orders(uploaded_orders):
    """
    Przyjmuje listę plików ze st.file_uploader,
    zwraca:
      - orders_all: wszystkie wiersze z plików (ARTIKELNR, ORDER_PALLETS, ORDER_QTY, SOURCE_FILE)
      - orders_agg: agregat po ARTIKELNR z podsumowaniem ilości

    Buduje też mapę szczegółów po artykule: ile sztuk z każdego pliku,
    która później jest użyta do tooltipów w tabeli agregatu.
    """
    # mapa szczegółów: ARTIKELNR -> { filename: qty_sum }
    orders_detail_map = {}

    if not uploaded_orders:
        st.session_state["orders_cache"] = {
            "files_keys": None,
            "orders_all": None,
            "orders_agg": None,
            "orders_detail_map": {},
        }
        return None, None

    # prosty identyfikator zestawu plików: nazwy + rozmiar
    files_keys = tuple((getattr(f, "name", ""), getattr(f, "size", None)) for f in uploaded_orders)

    cache = st.session_state.get("orders_cache", {})
    if (
        cache.get("files_keys") == files_keys
        and cache.get("orders_agg") is not None
        and cache.get("orders_detail_map") is not None
    ):
        # użyj już policzonych danych – bez ponownego parsowania
        return cache["orders_all"], cache["orders_agg"]

    # jeśli pliki się zmieniły – licz od nowa
    orders_list = []

    for f in uploaded_orders:
        name = getattr(f, "name", "uploaded")
        parsed = parse_order_file_to_df(f)
        if parsed is None or parsed.empty:
            continue

        # dodaj info o źródle do wierszy
        parsed = parsed.copy()
        parsed["SOURCE_FILE"] = name

        # budowa mapy szczegółów: suma sztuk z każdego pliku dla danego artykułu
        grouped = parsed.groupby("ARTIKELNR", as_index=False).agg(
            ORDER_PALLETS=("ORDER_PALLETS", "sum"),
            ORDER_QTY=("ORDER_QTY", "sum"),
        )
        for _, row in grouped.iterrows():
            art = str(row["ARTIKELNR"]).strip().upper()
            qty = float(row["ORDER_QTY"])
            if art not in orders_detail_map:
                orders_detail_map[art] = {}
            orders_detail_map[art][name] = orders_detail_map[art].get(name, 0) + qty

        orders_list.append(parsed)

    if not orders_list:
        st.session_state["orders_cache"] = {
            "files_keys": files_keys,
            "orders_all": None,
            "orders_agg": None,
            "orders_detail_map": {},
        }
        return None, None

    # wszystkie wiersze z plików
    orders_all = pd.concat(orders_list, ignore_index=True)

    # agregat po ARTIKELNR (tylko z plików, bez ręcznych)
    orders_agg = orders_all.groupby("ARTIKELNR", as_index=False).agg(
        ORDER_PALLETS=("ORDER_PALLETS", "sum"),
        ORDER_QTY=("ORDER_QTY", "sum"),
    )

    # tylko artykuły z paletami > 0
    orders_agg = orders_agg[orders_agg["ORDER_PALLETS"] > 0].copy()

    # naturalna sortowanie po ARTIKELNR
    orders_agg["_sort_key"] = orders_agg["ARTIKELNR"].apply(natural_sort_key)
    orders_agg = orders_agg.sort_values("_sort_key").drop(columns=["_sort_key"]).reset_index(drop=True)

    # zapisz do cache
    st.session_state["orders_cache"] = {
        "files_keys": files_keys,
        "orders_all": orders_all,
        "orders_agg": orders_agg,
        "orders_detail_map": orders_detail_map,
    }

    return orders_all, orders_agg

def make_order_tooltip(art, orders_detail_map, manual_agg):
    lines = []
    a = str(art).strip().upper()

    if a in orders_detail_map:
        for fname, qty in orders_detail_map[a].items():
            if qty != 0:
                lines.append(f"{fname} - {int(qty)} szt.")

    if manual_agg is not None and not manual_agg.empty:
        man_row = manual_agg[manual_agg["ARTIKELNR"] == a]
        if not man_row.empty:
            mq = float(man_row["Manual_Qty"].iloc[0])
            if mq != 0:
                lines.append(f"Dodatkowe zamówienia - {int(mq)} szt.")

    if not lines:
        return "Brak informacji z plików zamówień"

    return " ; ".join(lines)



# ---------- Ręczne zamówienia – быстрый дозаказ без таблицы ----------

def init_manual_orders():
    """
    Bufor edytora (manual_orders_editor_df) zawsze ma przynajmniej jeden pusty wiersz.
    Committed – to już dodane do agregatu zamówień.
    """
    if "manual_orders_editor_df" not in st.session_state:
        st.session_state.manual_orders_editor_df = pd.DataFrame(
            {"ARTIKELNR": [""], "ORDER_PALLETS": [0], "ORDER_QTY": [0]}
        )
    if "manual_orders_committed_df" not in st.session_state:
        st.session_state.manual_orders_committed_df = pd.DataFrame(
            {"ARTIKELNR": [], "ORDER_PALLETS": [], "ORDER_QTY": []}
        )

def render_manual_orders_editor(artikel_options):
    """
    Prosty formularz do ręcznych zamówień:
      - wprowadzanie jednej pozycji na raz,
      - bufor jest niewidoczny – od razu dodajemy do agregatu,
      - lista już dodanych ręcznych zamówień na dole.
    """
    init_manual_orders()

    st.subheader(STR["manual_orders"])

    # 1) Formularz jednej pozycji
    st.markdown("#### Dodaj pojedynczy artykuł do ręcznych zamówień")

    col_a, col_p, col_q, col_btn = st.columns([3, 1, 1, 1])

    with col_a:
        options = [""] + artikel_options
        new_art = st.selectbox(
            "ARTIKELNR",
            options=options,
            index=0,
            key="manual_artikel_select",
        )

    with col_p:
        new_pallets = st.number_input(
            "Palety",
            min_value=0,
            value=0,
            key="manual_pallets_input",
        )

    with col_q:
        new_qty = st.number_input(
            "Ilość sztuk",
            min_value=0,
            value=0,
            key="manual_qty_input",
        )

    with col_btn:
        st.write("")
        if st.button("Dodaj wiersz", key="manual_add_row_btn"):
            # 1) Проверка артикула
            if not new_art or not new_art.strip():
                st.warning("Wybierz ARTIKELNR przed dodaniem.")
            else:
                art_norm = new_art.strip().upper()

                # Pozwalamy na wpisanie ręczne artykułu spoza filtrów:
                # jeśli nie ma go w artikel_options, tylko ostrzegamy.
                if art_norm not in [a.strip().upper() for a in artikel_options]:
                    st.warning("Ten ARTIKELNR nie jest na liście filtrowanej, ale zostanie dodany ręcznie.")

                # 2) Проверка ilości
                if int(new_pallets) == 0 and int(new_qty) == 0:
                    st.warning("Podaj liczbę palet lub ilość sztuk przed dodaniem wiersza.")
                else:
                    # 3) Od razu dodajemy do manual_orders_committed_df
                    new_row = pd.DataFrame(
                        {
                            "ARTIKELNR": [art_norm],
                            "ORDER_PALLETS": [int(new_pallets)],
                            "ORDER_QTY": [int(new_qty)],
                        }
                    )

                    st.session_state.manual_orders_committed_df = pd.concat(
                        [st.session_state.manual_orders_committed_df, new_row],
                        ignore_index=True,
                    )

                    st.success(f"Dodano artykuł {art_norm} do ręcznych zamówień.")


    st.markdown("---")

    # 2) Кнопка очистки всех ручных заказов (при необходимости)
    if st.button("🗑 Usuń wszystkie ręczne zamówienia", type="secondary", key="clear_manual_committed"):
        st.session_state.manual_orders_committed_df = pd.DataFrame(
            {"ARTIKELNR": [], "ORDER_PALLETS": [], "ORDER_QTY": []}
        )
        st.success("Wyczyszczono wszystkie ręczne zamówienia.")

    st.markdown("#### Ręczne zamówienia dodane do agregatu")

    committed = st.session_state.manual_orders_committed_df

    if not committed.empty:
        committed_display = committed.copy()
        committed_display["ARTIKELNR"] = committed_display["ARTIKELNR"].astype(str).str.strip().str.upper()
        committed_display["ORDER_PALLETS"] = pd.to_numeric(
            committed_display["ORDER_PALLETS"], errors="coerce"
        ).fillna(0).astype(int)
        committed_display["ORDER_QTY"] = pd.to_numeric(
            committed_display["ORDER_QTY"], errors="coerce"
        ).fillna(0)

        # добавляем колонку с выбором для удаления
        committed_display["USUN"] = False

        edited = st.data_editor(
            committed_display,
            use_container_width=True,
            hide_index=True,
            key="manual_committed_editor",
            column_config={
                "ARTIKELNR": st.column_config.TextColumn("ARTIKELNR", disabled=True),
                "ORDER_PALLETS": st.column_config.NumberColumn("Palety", disabled=True),
                "ORDER_QTY": st.column_config.NumberColumn("Ilość sztuk", disabled=True),
                "USUN": st.column_config.CheckboxColumn("Usuń"),
            },
        )

        col_del_one, col_space = st.columns([1, 3])
        with col_del_one:
            if st.button("🗑 Usuń zaznaczone wiersze", key="manual_delete_selected_committed"):
                mask_to_keep = ~edited["USUN"].fillna(False)
                st.session_state.manual_orders_committed_df = committed[mask_to_keep].reset_index(drop=True)
                st.success("Usunięto zaznaczone wiersze z ręcznych zamówień.")
    else:
        st.info("Brak ręcznych zamówień w agregacie.")



# ---------- Główna funkcja zakładki 'Zamówienia' ----------

def render_orders_tab(artikel_options, filtered_pallets_df=None, selected_artikel=None):
    """
    Główna funkcja dla analizy palet + zamówień.
    """
    from utils import load_excluded_articles  # ← ТОЛЬКО 4 пробела!

    
    # 1) ПЕРВЫЙ БЛОК: Таблица паллет + их сумма по артикулу
    st.subheader("📋 Lista palet")
    
    if filtered_pallets_df is not None and not filtered_pallets_df.empty:
        cols_show = [
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
        ]

        df_show = filtered_pallets_df[cols_show].sort_values(by="OUT_DATE", ascending=False).reset_index(drop=True)
        
        st.dataframe(df_show, use_container_width=True, hide_index=True)
        
        # Расширенная аналитика по дням (в expanders)
        with st.expander("📊 Szczegóły przyjęć i usunięć według dnia", expanded=False):
            # 1. Принятые паллеты по дням
            accepted_pallets = filtered_pallets_df[~filtered_pallets_df["IS_DELETED"]].copy()
            
            if not accepted_pallets.empty and selected_artikel:
                daily_accepted = accepted_pallets.groupby(["ARTIKELNR", "IN_DATE"], as_index=False).agg(
                    Palety_przyjęte=("LHMNR", "nunique"),
                    Sztuki_przyjęte=("QUANTITY", "sum")
                )
                daily_accepted["IN_DATE"] = daily_accepted["IN_DATE"].dt.date
                daily_accepted = daily_accepted[daily_accepted["ARTIKELNR"].isin(selected_artikel)]
                daily_accepted = daily_accepted.sort_values(["ARTIKELNR", "IN_DATE"], ascending=[True, False])
                
                st.subheader("📥 Przyjęcia według dnia")
                st.dataframe(daily_accepted, use_container_width=True, hide_index=True)
            elif selected_artikel:
                st.info("Brak przyjętych palet dla wybranego artykułu.")
            
            # 2. Удалённые паллеты по дням
            deleted_pallets_daily = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]].copy()
            
            if not deleted_pallets_daily.empty and selected_artikel:
                daily_deleted = deleted_pallets_daily.groupby(["ARTIKELNR", "OUT_DATE"], as_index=False).agg(
                    Palety_usunięte=("LHMNR", "nunique"),
                    Sztuki_usunięte=("QUANTITY", "sum")
                )
                daily_deleted["OUT_DATE"] = daily_deleted["OUT_DATE"].dt.date
                daily_deleted = daily_deleted[daily_deleted["ARTIKELNR"].isin(selected_artikel)]
                daily_deleted = daily_deleted.sort_values(["ARTIKELNR", "OUT_DATE"], ascending=[True, False])
                
                st.markdown("---")
                st.subheader("🗑️ Usunięcia według dnia")
                st.dataframe(daily_deleted, use_container_width=True, hide_index=True)
            elif selected_artikel:
                st.info("Brak usuniętych palet dla wybranego artykułu.")
            
            if not selected_artikel:
                st.info("Wybierz artykuł w filtrach, aby zobaczyć szczegółową tabelę po dniach.")


    else:
        st.info("Brak palet w wybranym zakresie filtrów.")


    st.markdown("---")

    # 2) ВТОРОЙ БЛОК: Zamówienia (pliki + ręczne)
    st.subheader("📦 Zamówienia")

    # Загрузка файлов заказов
    uploaded_orders = st.file_uploader(
        STR["upload_orders"],
        type=["xlsx", "csv", "txt"],
        accept_multiple_files=True,
        key="orders_uploader",
    )

    orders_all, orders_agg_base = aggregate_uploaded_orders(uploaded_orders)

    # Ręczne zamówienia
    render_manual_orders_editor(artikel_options)

    # Проверка наличия данных заказов
    manual_df = st.session_state.get("manual_orders_committed_df", pd.DataFrame(
        {"ARTIKELNR": [], "ORDER_PALLETS": [], "ORDER_QTY": []}
    ))

    if orders_agg_base is None and manual_df.empty:
        st.info("Brak danych z plików zamówień ani z ręcznych zamówień.")
        return

    # Агрегация файлов + ręczne
    manual_agg = None
    if not manual_df.empty:
        m = manual_df.copy()
        m["ARTIKELNR"] = m["ARTIKELNR"].astype(str).str.strip().str.upper()
        m["ORDER_PALLETS"] = pd.to_numeric(m["ORDER_PALLETS"], errors="coerce").fillna(0).astype(int)
        m["ORDER_QTY"] = pd.to_numeric(m["ORDER_QTY"], errors="coerce").fillna(0)

        manual_agg = m.groupby("ARTIKELNR", as_index=False).agg(
            Manual_Pallets=("ORDER_PALLETS", "sum"),
            Manual_Qty=("ORDER_QTY", "sum"),
        )

    # Finalny agregat
    if orders_agg_base is not None:
        orders_agg = orders_agg_base.copy()
    else:
        orders_agg = pd.DataFrame(columns=["ARTIKELNR", "ORDER_PALLETS", "ORDER_QTY"])

    if manual_agg is not None and not manual_agg.empty:
        orders_agg = orders_agg.merge(manual_agg, on="ARTIKELNR", how="outer")
    else:
        orders_agg["Manual_Pallets"] = 0
        orders_agg["Manual_Qty"] = 0

    # Нормализация
    for col in ["ORDER_PALLETS", "Manual_Pallets"]:
        orders_agg[col] = pd.to_numeric(orders_agg[col], errors="coerce").fillna(0).astype(int)
    for col in ["ORDER_QTY", "Manual_Qty"]:
        orders_agg[col] = pd.to_numeric(orders_agg[col], errors="coerce").fillna(0)

    orders_agg["Ordered_Pallets_Total"] = orders_agg["ORDER_PALLETS"] + orders_agg["Manual_Pallets"]
    orders_agg["Ordered_Qty_Total"] = orders_agg["ORDER_QTY"] + orders_agg["Manual_Qty"]

    # Źródła
    cache = st.session_state.get("orders_cache", {})
    orders_detail_map = cache.get("orders_detail_map", {})

    def sources_count(row):
        art = str(row["ARTIKELNR"]).strip().upper()
        files_sources = sum(1 for _, qty in orders_detail_map.get(art, {}).items() if qty != 0)
        manual_source = 1 if row.get("Manual_Qty", 0) > 0 else 0
        return files_sources + manual_source

    def is_excluded_article(art, excluded_exact, excluded_prefixes):
        art = str(art).strip().upper()
        if art in [e.upper() for e in excluded_exact]:
            return True
        for p in excluded_prefixes:
            if art.startswith(p.upper()):
                return True
        return False

    orders_agg["Źródła"] = orders_agg.apply(sources_count, axis=1)
    orders_agg["ORDER_TOOLTIP"] = orders_agg["ARTIKELNR"].apply(
        lambda a: make_order_tooltip(a, orders_detail_map, manual_agg)
    )

    # Таблица заказов
    st.subheader("📋 Podsumowanie zamówień (agregat)")
    display_cols = ["ARTIKELNR", "Ordered_Pallets_Total", "Ordered_Qty_Total", "Źródła", "ORDER_TOOLTIP"]
    display_df = orders_agg[display_cols].copy()
    display_df.rename(columns={
        "ARTIKELNR": "ARTIKELNR",
        "Ordered_Pallets_Total": "Zamówione_palety",
        "Ordered_Qty_Total": "Zamówione_sztuki",
        "ORDER_TOOLTIP": "Szczegóły_źródeł",
    }, inplace=True)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # 3) СРАВНЕНИЕ (если есть палеты)
    if filtered_pallets_df is not None and not filtered_pallets_df.empty:
        st.markdown("---")
        st.subheader("⚖️ Porównanie zamówień z usuniętymi paletami")

        deleted_pallets = filtered_pallets_df[filtered_pallets_df["IS_DELETED"]].copy()

        if not deleted_pallets.empty:
            deleted_agg = deleted_pallets.groupby("ARTIKELNR", as_index=False).agg(
                Deleted_Pallets=("LHMNR", "nunique"),
                Deleted_Qty=("QUANTITY", "sum"),
            )

            comparison_df = orders_agg[["ARTIKELNR", "Ordered_Pallets_Total", "Ordered_Qty_Total"]].merge(
                deleted_agg, on="ARTIKELNR", how="outer"
            ).fillna(0)

            comparison_df["Różnica_Palety"] = (
                comparison_df["Ordered_Pallets_Total"] - comparison_df["Deleted_Pallets"]
            )
            comparison_df["Różnica_Sztuki"] = (
                comparison_df["Ordered_Qty_Total"] - comparison_df["Deleted_Qty"]
            )

            # Фильтрация строк без разницы
            # Загрузка исключений
            excluded_exact, excluded_prefixes = load_excluded_articles()
            
            def should_show_row(row):
                art = row["ARTIKELNR"].strip().upper()
                if is_excluded_article(art, excluded_exact, excluded_prefixes):
                    # Исключения: показываем ТОЛЬКО если ОБЕ разницы НЕ ноль
                    return (row["Różnica_Palety"] != 0) and (row["Różnica_Sztuki"] != 0)
                else:
                    # Обычные: показываем если ХОТЬ ОДНА разница
                    return (row["Różnica_Palety"] != 0) or (row["Różnica_Sztuki"] != 0)
            
            comparison_df = comparison_df[comparison_df.apply(should_show_row, axis=1)]


            # Добавляем колонку с пояснением
            def explain_diff(row):
                diff_pal = row["Różnica_Palety"]
                diff_szt = row["Różnica_Sztuki"]

                if diff_pal == 0 and diff_szt == 0:
                    return "Brak różnicy"
                msgs = []

                if diff_pal > 0:
                    msgs.append(f"Usunięto {int(abs(diff_pal))} palet mniej")
                elif diff_pal < 0:
                    msgs.append(f"Usunięto {int(abs(diff_pal))} palet więcej")
                else:
                    msgs.append("Brak różnicy w liczbie palet")

                if diff_szt > 0:
                    msgs.append(f"zabrakło {int(abs(diff_szt))} sztuk")
                elif diff_szt < 0:
                    msgs.append(f"jest {int(abs(diff_szt))} sztuk za dużo")
                else:
                    msgs.append("brak różnicy w ilości sztuk")

                return ", ".join(msgs)

            comparison_df["Wyjaśnienie różnicy"] = comparison_df.apply(explain_diff, axis=1)

            comparison_df = comparison_df.sort_values("Różnica_Palety", ascending=False).reset_index(drop=True)

            st.dataframe(
                comparison_df,
                use_container_width=True,
                hide_index=True,
            )

            # Итоговая статистика сравнения
            col1, col2, col3 = st.columns(3)
            col1.metric("Artykuły z zamówieniami", f"{len(orders_agg[orders_agg['Ordered_Pallets_Total'] > 0])}")
            col2.metric("Artykuły usunięte", f"{len(deleted_agg)}")
            col3.metric("Artykuły z rozbieżnością", f"{len(comparison_df)}")
        else:
            st.info("Brak usuniętych palet w wybranym zakresie.")
