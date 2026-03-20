# modules/orders.py
# Order handling: files + manual entries, with delayed processing.
# Обработка заказов: файлы + ручной ввод, с отложенной обработкой.

import streamlit as st
import pandas as pd
import numpy as np
import traceback
import sys
import re

# Initialize cache for file-based orders in session state.
# Инициализация кэша для заказов из файлов в состоянии сессии.
if "orders_cache" not in st.session_state:
    st.session_state["orders_cache"] = {
        "files_keys": None,      # Unique identifiers for uploaded files / Уникальные идентификаторы загруженных файлов
        "orders_all": None,      # DataFrame with all order rows / DataFrame со всеми строками заказов
        "orders_agg": None,      # Aggregated orders by article / Агрегированные заказы по артикулу
    }



# ===== Settings for order structure recognition =====
# ===== Настройки для распознавания структуры заказа =====

# Set of known "anchor" articles used to identify the article column.
# Набор известных "якорных" артикулов, используемых для идентификации колонки артикула.
KNOWN_ARTS_SET = {
    "1",
    "2",
    "21",
    "22",
    "61",
    "MH-1875",
    "MN 5029",
    "MH-9036",
    "DAF H-PALETTEN",
    "8309024074",
    "8309023044",
    "0004 MAN",
    "MH-1872",
    "8309021164",
}

# List of potential headers for the article column.
# Список возможных заголовков для колонки артикула.
ARTICLE_HEADER_CANDIDATES = [
    "NR MATERIALU",
    "NR MATERIAU",
    "MATERIALNUMMER",
    "ARTIKELNR",
    "ARTIKEL",
]

def _looks_like_article(value: str) -> bool:
    # Checks if a value resembles an article number.
    # Проверяет, похоже ли значение на номер артикула.
    # Criteria: not empty, not '0', contains alphanumeric chars/dashes/spaces.
    # Критерии: не пустое, не '0', содержит буквенно-цифровые символы/тире/пробелы.
    v = str(value).strip()
    if not v:
        return False
    if v == "0":
        return False
    import re
    return bool(re.match(r"^[A-Za-z0-9\- ]+$", v))


def detect_order_structure(df_o):
    # Attempts to determine the structure of the order file.
    # Пытается определить структуру файла заказа.
    # Returns a dict with 'art_col' (index) and 'data_start_row' (index).
    # Возвращает словарь с 'art_col' (индекс) и 'data_start_row' (индекс).
    
    # Limit the check to the top 200 rows for performance.
    # Ограничиваем проверку первыми 200 строками для производительности.
    max_rows_to_check = min(200, df_o.shape[0])

    # --- Step 1: Search for a header row using known candidates ---
    # --- Шаг 1: Поиск строки заголовка с использованием известных кандидатов ---
    art_col_by_header = None
    header_row_idx = None

    for row_idx in range(max_rows_to_check):
        row_vals = df_o.iloc[row_idx, :]
        for col_idx, cell in enumerate(row_vals):
            text = str(cell).strip().upper()
            if text in ARTICLE_HEADER_CANDIDATES:
                art_col_by_header = col_idx
                header_row_idx = row_idx
                break
        if art_col_by_header is not None:
            break

    if art_col_by_header is not None:
        # Header found.
        # Заголовок найден.
        art_col = art_col_by_header
        data_start_row = header_row_idx + 1
        return {
            "art_col": art_col,
            "data_start_row": data_start_row,
        }

    # --- Step 2: Heuristic search by content (if no header found) ---
    # --- Шаг 2: Эвристический поиск по содержимому (если заголовок не найден) ---
    best_col = None
    best_score = -1
    best_first_row = None

    n_cols = df_o.shape[1]

    for col_idx in range(n_cols):
        col = df_o.iloc[:max_rows_to_check, col_idx]

        known_hits = 0
        article_like = 0
        first_article_row = None

        for row_idx, val in col.items():
            v = str(val).strip()
            if not v:
                continue

            v_upper = v.upper()

            # Check for known anchor articles.
            # Проверка на известные якорные артикулы.
            if v_upper in KNOWN_ARTS_SET:
                known_hits += 1
                if first_article_row is None:
                    first_article_row = row_idx

            # Check if value looks like an article.
            # Проверка, похоже ли значение на артикул.
            if _looks_like_article(v):
                article_like += 1
                if first_article_row is None:
                    first_article_row = row_idx

        # Score the column: matches with known articles are weighted higher.
        # Оценка колонки: совпадения с известными артикулами имеют больший вес.
        score = known_hits * 10 + article_like

        if score > best_score and article_like > 0:
            best_score = score
            best_col = col_idx
            best_first_row = first_article_row

    if best_col is None:
        # Fallback if nothing is found.
        # Резервный вариант, если ничего не найдено.
        return {
            "art_col": 0,
            "data_start_row": 2,
        }

    # Column found by content analysis.
    # Колонка найдена путем анализа содержимого.
    art_col = best_col
    data_start_row = best_first_row if best_first_row is not None else 2

    return {
        "art_col": art_col,
        "data_start_row": data_start_row,
    }




# ---------- Parsing a single order file ----------
# ---------- Парсинг одного файла заказа ----------

def parse_order_file_to_df(fobj):
    # Reads a single order file (XLSX/CSV) and extracts relevant columns.
    # Читает один файл заказа (XLSX/CSV) и извлекает соответствующие колонки.
    # Uses low-level XML parsing for XLSX to avoid 'wildcard' errors in openpyxl.
    # Использует низкоуровневый парсинг XML для XLSX, чтобы избежать ошибок 'wildcard' в openpyxl.
    
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    name = getattr(fobj, "name", "uploaded")
    df_o = None

    # Handle CSV/TXT files.
    # Обработка CSV/TXT файлов.
    if name.lower().endswith((".csv", ".txt")):
        fobj.seek(0)
        try:
            df_o = pd.read_csv(
                fobj,
                sep=";",
                dtype=str,
                encoding="utf-8",
                header=None,
            )
        except Exception as e:
            print("\n===== ORDER PARSE ERROR (CSV/TXT) =====", file=sys.stderr)
            traceback.print_exc()
            print("===== END ORDER PARSE ERROR =====\n", file=sys.stderr)
            st.error(f"Błąd czytania pliku zamówienia {name}: {e}")
            return None

    # Handle XLSX files using direct XML parsing.
    # Обработка XLSX файлов с использованием прямого парсинга XML.
    else:
        try:
            fobj.seek(0)
            file_bytes = fobj.read()
            fobj.seek(0)

            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                # Find the 'OrderMasterSheet' in workbook.xml.
                # Находим 'OrderMasterSheet' в workbook.xml.
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
                    # Fallback to the first sheet if specific name not found.
                    # Резервный вариант: первый лист, если конкретное имя не найдено.
                    first_sheet = wb_root.find("ns:sheets/ns:sheet", ns)
                    if first_sheet is None:
                        raise ValueError("Brak arkuszy w pliku XLSX")
                    sheet_id = first_sheet.attrib.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    )

                # Find the path to the sheet file in workbook.xml.rels.
                # Находим путь к файлу листа в workbook.xml.rels.
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

                # Parse the sheet XML.
                # Парсим XML листа.
                with zf.open(sheet_path) as sf:
                    sheet_tree = ET.parse(sf)
                    sheet_root = sheet_tree.getroot()

                # Load shared strings (text values).
                # Загружаем общие строки (текстовые значения).
                shared_strings = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    with zf.open("xl/sharedStrings.xml") as ssf:
                        ss_tree = ET.parse(ssf)
                        ss_root = ss_tree.getroot()
                    for si in ss_root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                        t = si.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                        shared_strings.append(t.text if t is not None else "")

                # Extract rows and cells.
                # Извлекаем строки и ячейки.
                rows_data = []
                for row_elem in sheet_root.findall(
                    ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"
                ):
                    row_values = []
                    last_col_idx = -1
                    for cell in row_elem.findall(
                        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"
                    ):
                        # Determine column index from cell reference (e.g., 'A1').
                        # Определяем индекс колонки из ссылки на ячейку (например, 'A1').
                        cell_ref = cell.attrib.get("r", "")
                        col_letters = "".join(ch for ch in cell_ref if ch.isalpha())
                        col_idx = 0
                        for ch in col_letters:
                            col_idx = col_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
                        col_idx -= 1  # 0-based

                        # Fill gaps for empty cells.
                        # Заполняем пропуски для пустых ячеек.
                        while last_col_idx + 1 < col_idx:
                            row_values.append("")
                            last_col_idx += 1

                        # Get cell value.
                        # Получаем значение ячейки.
                        v = cell.find(
                            "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
                        )
                        cell_type = cell.attrib.get("t")
                        if v is not None and v.text is not None:
                            if cell_type == "s":
                                # Shared string lookup.
                                # Поиск в общих строках.
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

                # Create DataFrame from extracted data.
                # Создаем DataFrame из извлеченных данных.
                max_cols = max(len(r) for r in rows_data)
                rows_padded = [r + [""] * (max_cols - len(r)) for r in rows_data]
                df_o = pd.DataFrame(rows_padded)

        except Exception as e:
            print("\n===== ORDER PARSE ERROR (XLSX ZIP/XML) =====", file=sys.stderr)
            traceback.print_exc()
            print("===== END ORDER PARSE ERROR =====\n", file=sys.stderr)
            st.error(f"Błąd czytania pliku zamówienia {name}: {e}")
            return None

    # --- Determine data structure ---
    # --- Определение структуры данных ---
    if df_o.shape[1] < 1:
        st.error(f"Plik {name} ma za mało kolumn (oczekiwane >= 1).")
        return None

    structure = detect_order_structure(df_o)
    art_col = structure["art_col"]
    data_start_row = structure["data_start_row"]

    # Slice the DataFrame to get the data section.
    # Срезаем DataFrame, чтобы получить секцию данных.
    df_data = df_o.iloc[data_start_row:, :].copy()

    # Extract the article column.
    # Извлекаем колонку артикула.
    artikel_col = df_data.iloc[:, art_col].astype(str)

    # Identify potential numeric columns to the right of the article column.
    # Идентифицируем потенциальные числовые колонки справа от колонки артикула.
    right_cols_indices = []
    max_right_span = 5

    for offset in range(1, max_right_span + 1):
        idx = art_col + offset
        if idx >= df_data.shape[1]:
            break

        col_raw = df_data.iloc[:, idx].astype(str)
        # Attempt to convert to numeric.
        # Попытка конвертировать в число.
        col_num = pd.to_numeric(col_raw.str.replace(",", "."), errors="coerce")
        non_null = col_num.dropna()

        # Keep column if it has at least one numeric value.
        # Оставляем колонку, если в ней есть хотя бы одно числовое значение.
        if len(non_null) < 1:
            continue

        right_cols_indices.append(idx)

    if not right_cols_indices:
        st.error(f"Plik {name}: brak liczbowych kolumn z ilościami po kolumnie artykułu.")
        return None

    # --- Heuristic Column Classification ---
    # --- Эвристическая классификация колонок ---
    # Try to identify Pallets, Qty, and Per (pieces per pallet) columns.
    # Пытаемся идентифицировать колонки Паллеты, Кол-во и Per (штук на паллете).
    
    right_part = df_data.iloc[:, right_cols_indices].copy()

    KNOWN_PER_VALUES = {10, 20, 11, 1, 22, 320, 27}

    pallets_col_idx = None
    per_col_idx = None
    qty_col_idx = None
    
    # Gather statistics for each column to aid classification.
    # Собираем статистику для каждой колонки, чтобы помочь в классификации.
    col_stats = {}
    for idx in right_cols_indices:
        raw = df_data.iloc[:, idx].astype(str).str.replace(",", ".")
        col = pd.to_numeric(raw, errors="coerce")

        non_null = col.dropna()
        if non_null.empty:
            continue

        max_val = non_null.max()
        min_val = non_null.min()
        unique_vals = set(int(v) for v in non_null.unique() if pd.notna(v))

        per_hits = unique_vals.intersection(KNOWN_PER_VALUES)
        zero_share = (col == 0).sum() / len(col)

        col_stats[idx] = {
            "max": max_val,
            "min": min_val,
            "unique": unique_vals,
            "per_hits_count": len(per_hits),
            "zero_share": zero_share,
        }

    # 1. Identify PER column (matches known values).
    # 1. Идентифицируем колонку PER (совпадает с известными значениями).
    if col_stats:
        per_candidate = max(
            col_stats.items(),
            key=lambda kv: kv[1]["per_hits_count"],
        )
        if per_candidate[1]["per_hits_count"] > 0:
            per_col_idx = per_candidate[0]

    # 2. Identify PALLETS column (small integers <= 500).
    # 2. Идентифицируем колонку PALLETS (малые целые числа <= 500).
    for idx, stats in col_stats.items():
        if idx == per_col_idx:
            continue
        if stats["max"] <= 500:
            pallets_col_idx = idx
            break

    # 3. Identify QTY column (remaining column).
    # 3. Идентифицируем колонку QTY (оставшаяся колонка).
    for idx in right_cols_indices:
        if idx == per_col_idx or idx == pallets_col_idx:
            continue
        if idx in col_stats:
            qty_col_idx = idx
            break

    # --- Sanity Check: Pallets vs Qty ---
    # --- Проверка здравого смысла: Паллеты vs Кол-во ---
    # Pallets count should generally be smaller than Quantity.
    # Количество паллет обычно должно быть меньше количества штук.
    if pallets_col_idx is not None and qty_col_idx is not None:
        p_vals = pd.to_numeric(
            df_data.iloc[:, pallets_col_idx].astype(str).str.replace(",", "."),
            errors="coerce"
        ).fillna(0)
        q_vals = pd.to_numeric(
            df_data.iloc[:, qty_col_idx].astype(str).str.replace(",", "."),
            errors="coerce"
        ).fillna(0)

        mask_check = (p_vals > 0) & (q_vals > 0)
        if mask_check.any():
            violations = (p_vals[mask_check] > q_vals[mask_check]).sum()
            valid_count = mask_check.sum()
            
            # Swap if heuristic failed.
            # Меняем местами, если эвристика ошиблась.
            if violations > valid_count * 0.5:
                pallets_col_idx, qty_col_idx = qty_col_idx, pallets_col_idx


    # Fallback for PER column if not identified.
    # Резервный вариант для колонки PER, если не идентифицирована.
    if per_col_idx is None and len(right_cols_indices) >= 2:
        candidate = right_cols_indices[-1]
        col = pd.to_numeric(
            df_data.iloc[:, candidate].astype(str).str.replace(",", "."),
            errors="coerce",
        )
        if col.dropna().max() <= 1000:
            per_col_idx = candidate

    # --- Construct Result DataFrame ---
    # --- Создание итогового DataFrame ---
    data = pd.DataFrame()
    data["ARTIKELNR_RAW"] = artikel_col

    if qty_col_idx is not None:
        data["QTY_RAW"] = df_data.iloc[:, qty_col_idx]
    else:
        data["QTY_RAW"] = ""

    if pallets_col_idx is not None:
        data["PALLETS_RAW"] = df_data.iloc[:, pallets_col_idx]
    else:
        data["PALLETS_RAW"] = ""

    if per_col_idx is not None:
        data["PER_RAW"] = df_data.iloc[:, per_col_idx]
    else:
        data["PER_RAW"] = ""

    # Normalize and clean data.
    # Нормализация и очистка данных.
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

    # Filter out rows with no pallets.
    # Отфильтровываем строки без паллет.
    res = res[res["ORDER_PALLETS"] > 0].copy()

    # Calculate QTY if missing but PER and PALLETS are present.
    # Вычисляем QTY, если отсутствует, но есть PER и PALLETS.
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

# ---------- Aggregation of multiple order files ----------
# ---------- Агрегация нескольких файлов заказов ----------

def natural_sort_key(text):
    # Helper for natural sorting (e.g., 1, 2, 10 instead of 1, 10, 2).
    # Помощник для естественной сортировки (например, 1, 2, 10 вместо 1, 10, 2).
    import re
    parts = re.split(r"(\d+)", str(text).upper())
    return [int(p) if p.isdigit() else p for p in parts]

def extract_date_from_filename(filename):
    # Attempts to extract a date from the filename.
    # Пытается извлечь дату из имени файла.
    # Supports formats: dd-mm-yyyy, yyyy-mm-dd, dd-mm-yy.
    # Поддерживает форматы: dd-mm-yyyy, yyyy-mm-dd, dd-mm-yy.
    s = str(filename)
    
    # 1. Format dd-mm-yyyy
    match_dmy = re.search(r"(\d{2})[-._](\d{2})[-._](\d{4})", s)
    if match_dmy:
        d, m, y = match_dmy.groups()
        try:
            return pd.Timestamp(year=int(y), month=int(m), day=int(d)).date()
        except ValueError:
            pass

    # 2. Format yyyy-mm-dd
    match_ymd = re.search(r"(\d{4})[-._](\d{2})[-._](\d{2})", s)
    if match_ymd:
        y, m, d = match_ymd.groups()
        try:
            return pd.Timestamp(year=int(y), month=int(m), day=int(d)).date()
        except ValueError:
            pass

    # 3. Format dd-mm-yy (assumes 20xx)
    match_dmy_short = re.search(r"(\d{2})[-._](\d{2})[-._](\d{2})", s)
    if match_dmy_short:
        d, m, y = match_dmy_short.groups()
        year_full = 2000 + int(y)
        try:
            return pd.Timestamp(year=year_full, month=int(m), day=int(d)).date()
        except ValueError:
            pass
            
    return None

def aggregate_uploaded_orders(uploaded_orders):
    # Processes uploaded order files and aggregates them.
    # Обрабатывает загруженные файлы заказов и агрегирует их.
    # Returns: orders_all (detailed), orders_agg (aggregated), valid_count.
    # Возвращает: orders_all (детальный), orders_agg (агрегированный), valid_count.
    
    orders_detail_map = {}

    if not uploaded_orders:
        # Reset cache if no files.
        # Сброс кэша, если файлов нет.
        st.session_state["orders_cache"] = {
            "files_keys": None,
            "orders_all": None,
            "orders_agg": None,
            "orders_detail_map": {},
            "valid_count": 0,
        }
        return None, None, 0

    # Generate a key to check if files have changed.
    # Генерируем ключ для проверки, изменились ли файлы.
    files_keys = tuple((getattr(f, "name", ""), getattr(f, "size", None)) for f in uploaded_orders)

    cache = st.session_state.get("orders_cache", {})
    if (
        cache.get("files_keys") == files_keys
        and cache.get("orders_agg") is not None
        and cache.get("orders_detail_map") is not None
        and "valid_count" in cache
        and cache.get("orders_all") is not None and "ORDER_DATE" in cache["orders_all"].columns
    ):
        # Return cached data if files match.
        # Возвращаем кэшированные данные, если файлы совпадают.
        return cache["orders_all"], cache["orders_agg"], cache["valid_count"]

    # Process files.
    # Обработка файлов.
    orders_list = []

    for f in uploaded_orders:
        name = getattr(f, "name", "uploaded")
        parsed = parse_order_file_to_df(f)
        if parsed is None:
            continue
        
        if parsed.empty:
            st.warning(f"Plik {name}: nie znaleziono zamówień (pusty wynik).")
            continue

        # Add metadata.
        # Добавляем метаданные.
        parsed = parsed.copy()
        parsed["SOURCE_FILE"] = name
        parsed["ORDER_DATE"] = extract_date_from_filename(name)

        # Build detail map for tooltips.
        # Строим карту деталей для подсказок.
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
            "valid_count": 0,
        }
        return None, None, 0

    # Combine all orders.
    # Объединяем все заказы.
    orders_all = pd.concat(orders_list, ignore_index=True)

    # Aggregate by article.
    # Агрегируем по артикулу.
    orders_agg = orders_all.groupby("ARTIKELNR", as_index=False).agg(
        ORDER_PALLETS=("ORDER_PALLETS", "sum"),
        ORDER_QTY=("ORDER_QTY", "sum"),
    )

    # Filter out zero pallets.
    # Отфильтровываем нулевые паллеты.
    orders_agg = orders_agg[orders_agg["ORDER_PALLETS"] > 0].copy()

    # Sort.
    # Сортировка.
    orders_agg["_sort_key"] = orders_agg["ARTIKELNR"].apply(natural_sort_key)
    orders_agg = orders_agg.sort_values("_sort_key").drop(columns=["_sort_key"]).reset_index(drop=True)

    valid_count = len(orders_list)

    # Update cache.
    # Обновляем кэш.
    st.session_state["orders_cache"] = {
        "files_keys": files_keys,
        "orders_all": orders_all,
        "orders_agg": orders_agg,
        "orders_detail_map": orders_detail_map,
        "valid_count": valid_count,
    }

    return orders_all, orders_agg, valid_count

def make_order_tooltip(art, orders_detail_map, manual_agg, STR):
    # Generates a tooltip string showing the source of orders for an article.
    # Генерирует строку подсказки, показывающую источник заказов для артикула.
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
                lines.append(f"{STR['manual_orders']} - {int(mq)}")

    if not lines:
        return STR.get("tooltip_no_info", "No info")

    return " ; ".join(lines)



# ---------- Manual Orders – quick add without table ----------
# ---------- Ручные заказы – быстрое добавление без таблицы ----------

def init_manual_orders():
    # Initializes session state for manual orders.
    # Инициализирует состояние сессии для ручных заказов.
    if "manual_orders_editor_df" not in st.session_state:
        st.session_state.manual_orders_editor_df = pd.DataFrame(
            {"ARTIKELNR": [""], "ORDER_PALLETS": [0], "ORDER_QTY": [0]}
        )
    if "manual_orders_committed_df" not in st.session_state:
        st.session_state.manual_orders_committed_df = pd.DataFrame(
            {"ARTIKELNR": [], "ORDER_PALLETS": [], "ORDER_QTY": []}
        )

def render_manual_orders_editor(artikel_options, STR):
    # Renders the interface for adding manual orders.
    # Рендерит интерфейс для добавления ручных заказов.
    init_manual_orders()

    if "manual_order_msg" in st.session_state:
        st.success(st.session_state.pop("manual_order_msg"))

    st.subheader(STR["manual_orders"])

    # --- Single Item Entry Form ---
    # --- Форма ввода одного элемента ---
    st.markdown(f"#### {STR['add_manual_item_header']}")

    # Use a form to batch input and prevent app rerun on every keystroke/selection change.
    # Используем форму для пакетного ввода и предотвращения перезапуска приложения при каждом нажатии клавиши/изменении выбора.
    with st.form("manual_add_form", clear_on_submit=False):
        col_a, col_p, col_q, col_btn = st.columns([3, 1, 1, 1])

        with col_a:
            options = [""] + artikel_options
            new_art = st.selectbox(
                STR["manual_input_artikelnr"],
                options=options,
                index=0,
                key="manual_artikel_select",
            )

        with col_p:
            new_pallets = st.number_input(
                STR["manual_input_pallets"],
                min_value=0,
                value=0,
                key="manual_pallets_input",
            )

        with col_q:
            new_qty = st.number_input(
                STR["manual_input_qty"],
                min_value=0,
                value=0,
                key="manual_qty_input",
            )

        with col_btn:
            st.write("")
            submitted = st.form_submit_button(STR["manual_add_row_btn"])

    if submitted:
        # Validate input.
        # Валидация ввода.
        if not new_art or not new_art.strip():
            st.warning(STR["manual_select_article_warning"])
        else:
            art_norm = new_art.strip().upper()

            if art_norm not in [a.strip().upper() for a in artikel_options]:
                st.warning(STR["manual_article_not_in_filter_warning"])

            if int(new_pallets) == 0 and int(new_qty) == 0:
                st.warning(STR["manual_quantity_warning"])
            else:
                # Add to committed DataFrame.
                # Добавляем в подтвержденный DataFrame.
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

                st.success(STR["manual_added_success"].format(art=art_norm))


    st.markdown("---")

    # --- Clear All Button ---
    # --- Кнопка очистить все ---
    if st.button(STR["manual_clear_all"], type="secondary", key="clear_manual_committed"):
        st.session_state.manual_orders_committed_df = pd.DataFrame(
            {"ARTIKELNR": [], "ORDER_PALLETS": [], "ORDER_QTY": []}
        )
        st.success(STR["manual_cleared_success"])

    # --- Display Committed Orders ---
    # --- Отображение подтвержденных заказов ---
    st.markdown(f"#### {STR['manual_added_header']}")

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

        # Add checkbox column for deletion.
        # Добавляем колонку с чекбоксом для удаления.
        committed_display["USUN"] = False

        edited = st.data_editor(
            committed_display,
            width="stretch",
            hide_index=True,
            key="manual_committed_editor",
            column_config={
                "ARTIKELNR": st.column_config.TextColumn(STR["manual_input_artikelnr"], disabled=True),
                "ORDER_PALLETS": st.column_config.NumberColumn(STR["manual_input_pallets"], disabled=True),
                "ORDER_QTY": st.column_config.NumberColumn(STR["manual_input_qty"], disabled=True),
                "USUN": st.column_config.CheckboxColumn(STR["col_remove"]),
            },
        )

        col_del_one, col_space = st.columns([1, 3])
        with col_del_one:
            def delete_selected_callback():
                # Callback to delete selected rows.
                # Обратный вызов для удаления выбранных строк.
                editor_state = st.session_state.get("manual_committed_editor", {})
                edited_rows = editor_state.get("edited_rows", {})
                indices_to_remove = [int(k) for k, v in edited_rows.items() if v.get("USUN") is True]
                
                if indices_to_remove:
                    df = st.session_state.manual_orders_committed_df
                    valid_indices = [i for i in indices_to_remove if i in df.index]
                    if valid_indices:
                        st.session_state.manual_orders_committed_df = df.drop(valid_indices).reset_index(drop=True)
                        st.session_state["manual_order_msg"] = STR["manual_deleted_success"]
            
            st.button(STR["manual_delete_selected"], key="manual_delete_selected_committed", on_click=delete_selected_callback)
    else:
        st.info(STR["no_manual_orders"])



# ---------- Main function for 'Orders' tab ----------
# ---------- Главная функция для вкладки 'Заказы' ----------

def render_orders_tab(artikel_options, filtered_pallets_df=None, selected_artikel=None, filtered_pallets_no_art_df=None, full_df=None, date_start=None, date_end=None, selected_mandant=None, show_comparison=True, STR=None):
    # Main function to render the Orders tab.
    # Главная функция для рендеринга вкладки Заказы.
    # Displays pallet list, order uploads, and comparison.
    # Отображает список паллет, загрузку заказов и сравнение.
    
    from utils import load_excluded_articles

    
    # --- 1. Pallet List Section ---
    # --- 1. Секция списка паллет ---
    st.subheader(STR["pallet_list_title"])
    
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
        
        # Format dates.
        # Форматирование дат.
        df_show["IN_DATE"] = df_show["IN_DATE"].dt.date
        df_show["OUT_DATE"] = df_show["OUT_DATE"].dt.date

        st.dataframe(df_show, width="stretch", hide_index=True)
        
        # Summary of visible pallets.
        # Сводка видимых паллет.
        st.markdown(f"#### {STR['pallet_list_summary']}")
        # observed=True is required when grouping by categorical columns to avoid expanding all categories.
        # observed=True требуется при группировке по категориальным колонкам, чтобы избежать развертывания всех категорий.
        df_list_agg = filtered_pallets_df.groupby(["ARTIKELNR", "ARTBEZ1"], as_index=False, observed=True).agg(
            Liczba_palet=("LHMNR", "nunique"),
            Suma_sztuk=("QUANTITY", "sum")
        ).rename(columns={"Liczba_palet": "Liczba palet", "Suma_sztuk": "Suma sztuk"}).sort_values("Liczba palet", ascending=False)
        st.dataframe(df_list_agg, width="stretch", hide_index=True)

        # Detailed daily analytics.
        # Подробная ежедневная аналитика.
        with st.expander(STR["daily_details_expander"], expanded=False):
            if not selected_artikel:
                st.info(STR["daily_details_info"])
            elif full_df is not None and selected_mandant and date_start and date_end:
                # Prepare data for daily breakdown.
                # Подготовка данных для ежедневной разбивки.
                
                mask_base = (full_df["MANDANT"].astype(str) == str(selected_mandant))
                mask_base &= full_df["ARTIKELNR"].isin([a.strip().upper() for a in selected_artikel])
                df_subset = full_df[mask_base]

                # Receipts.
                # Поступления.
                mask_in = df_subset["IN_DATE"].between(pd.Timestamp(date_start), pd.Timestamp(date_end))
                df_in = df_subset[mask_in].copy()

                if not df_in.empty:
                    # Group by article and date. observed=True handles categorical ARTIKELNR correctly.
                    # Группируем по артикулу и дате. observed=True корректно обрабатывает категориальный ARTIKELNR.
                    daily_accepted = df_in.groupby(["ARTIKELNR", "IN_DATE"], as_index=False, observed=True).agg(
                        Palety_przyjęte=("LHMNR", "nunique"),
                        Sztuki_przyjęte=("QUANTITY", "sum")
                    )
                    daily_accepted["IN_DATE"] = daily_accepted["IN_DATE"].dt.date
                    daily_accepted = daily_accepted.sort_values(["ARTIKELNR", "IN_DATE"], ascending=[True, False])
                    
                    st.subheader(STR["daily_receipts"])
                    st.dataframe(daily_accepted, width="stretch", hide_index=True)
                else:
                    st.info(STR["daily_no_receipts"])

                st.markdown("---")

                # Removals.
                # Удаления.
                mask_out = df_subset["OUT_DATE"].between(pd.Timestamp(date_start), pd.Timestamp(date_end))
                if "IS_DELETED" in df_subset.columns:
                    mask_deleted = df_subset["IS_DELETED"]
                else:
                    mask_deleted = df_subset["ZUSTAND"] != "401"
                
                df_out = df_subset[mask_out & mask_deleted].copy()

                if not df_out.empty:
                    # Group by article and date. observed=True handles categorical ARTIKELNR correctly.
                    # Группируем по артикулу и дате. observed=True корректно обрабатывает категориальный ARTIKELNR.
                    daily_deleted = df_out.groupby(["ARTIKELNR", "OUT_DATE"], as_index=False, observed=True).agg(
                        Palety_usunięte=("LHMNR", "nunique"),
                        Sztuki_usunięte=("QUANTITY", "sum")
                    )
                    daily_deleted["OUT_DATE"] = daily_deleted["OUT_DATE"].dt.date
                    daily_deleted = daily_deleted.sort_values(["ARTIKELNR", "OUT_DATE"], ascending=[True, False])
                    
                    st.subheader(STR["daily_removals"])
                    st.dataframe(daily_deleted, width="stretch", hide_index=True)
                else:
                    st.info(STR["daily_no_removals"])
            else:
                st.warning(STR["daily_no_data"])


    else:
        st.info(STR["no_pallets_in_filter"])


    st.markdown("---")

    # --- 2. Orders Section ---
    # --- 2. Секция заказов ---
    st.subheader(STR["orders_header"])

    if "orders_uploader_key" not in st.session_state:
        st.session_state["orders_uploader_key"] = 0

    # File uploader.
    # Загрузчик файлов.
    uploaded_orders = st.file_uploader(
        STR["upload_orders"],
        type=["xlsx", "csv", "txt"],
        accept_multiple_files=True,
        key=f"orders_uploader_{st.session_state['orders_uploader_key']}",
    )

    if uploaded_orders:
        if st.button(STR["clear_all_orders_btn"], key="clear_all_orders_btn"):
            st.session_state["orders_cache"] = {
                "files_keys": None,
                "orders_all": None,
                "orders_agg": None,
                "orders_detail_map": {},
                "valid_count": 0,
            }
            st.session_state["orders_uploader_key"] += 1
            st.rerun()

    # Process uploaded files.
    # Обработка загруженных файлов.
    orders_all, orders_agg_base, valid_files_count = aggregate_uploaded_orders(uploaded_orders)

    if uploaded_orders:
        st.caption(STR["loaded_files_info"].format(count=len(uploaded_orders), valid=valid_files_count))

    # Render manual orders editor.
    # Рендеринг редактора ручных заказов.
    render_manual_orders_editor(artikel_options, STR)

    # Check if any order data exists.
    # Проверка наличия данных заказов.
    manual_df = st.session_state.get("manual_orders_committed_df", pd.DataFrame(
        {"ARTIKELNR": [], "ORDER_PALLETS": [], "ORDER_QTY": []}
    ))

    if orders_agg_base is None and manual_df.empty:
        st.info(STR["no_orders_data"])
        return

    # Combine file orders and manual orders.
    # Объединение заказов из файлов и ручных заказов.
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

    if orders_agg_base is not None:
        orders_agg = orders_agg_base.copy()
    else:
        orders_agg = pd.DataFrame(columns=["ARTIKELNR", "ORDER_PALLETS", "ORDER_QTY"])

    if manual_agg is not None and not manual_agg.empty:
        orders_agg = orders_agg.merge(manual_agg, on="ARTIKELNR", how="outer")
    else:
        orders_agg["Manual_Pallets"] = 0
        orders_agg["Manual_Qty"] = 0

    # Normalize numeric columns.
    # Нормализация числовых колонок.
    for col in ["ORDER_PALLETS", "Manual_Pallets"]:
        orders_agg[col] = pd.to_numeric(orders_agg[col], errors="coerce").fillna(0).astype(int)
    for col in ["ORDER_QTY", "Manual_Qty"]:
        orders_agg[col] = pd.to_numeric(orders_agg[col], errors="coerce").fillna(0)

    orders_agg["Ordered_Pallets_Total"] = orders_agg["ORDER_PALLETS"] + orders_agg["Manual_Pallets"]
    orders_agg["Ordered_Qty_Total"] = orders_agg["ORDER_QTY"] + orders_agg["Manual_Qty"]

    # Calculate sources count.
    # Подсчет количества источников.
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

    orders_agg["SOURCES_CNT"] = orders_agg.apply(sources_count, axis=1)
    orders_agg["ORDER_TOOLTIP"] = orders_agg["ARTIKELNR"].apply(
        lambda a: make_order_tooltip(a, orders_detail_map, manual_agg, STR)
    )

    # Display aggregated orders table.
    # Отображение таблицы агрегированных заказов.
    st.subheader(f"📋 {STR['orders_table']}")
    display_cols = ["ARTIKELNR", "Ordered_Pallets_Total", "Ordered_Qty_Total", "SOURCES_CNT", "ORDER_TOOLTIP"]
    display_df = orders_agg[display_cols].copy()
    display_df.rename(columns={
        "ARTIKELNR": "ARTIKELNR",
        "Ordered_Pallets_Total": STR["col_ordered_pallets"],
        "Ordered_Qty_Total": STR["col_ordered_qty"],
        "ORDER_TOOLTIP": STR["col_source_details"],
        "SOURCES_CNT": STR["col_sources"],
    }, inplace=True)

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
    )

    # --- 3. Comparison Section ---
    # --- 3. Секция сравнения ---
    if show_comparison:
        df_for_comparison = filtered_pallets_no_art_df if filtered_pallets_no_art_df is not None else filtered_pallets_df

        if df_for_comparison is not None and not df_for_comparison.empty:
            st.markdown("---")
            st.subheader(f"⚖️ {STR['compare']}")

            deleted_pallets = df_for_comparison[df_for_comparison["IS_DELETED"]].copy()

            if not deleted_pallets.empty:
                # Aggregate deleted pallets.
                # Агрегация удаленных паллет.
                # observed=True ensures we only count existing categories.
                # observed=True гарантирует, что мы считаем только существующие категории.
                deleted_agg = deleted_pallets.groupby("ARTIKELNR", as_index=False, observed=True).agg(
                    Deleted_Pallets=("LHMNR", "nunique"),
                    Deleted_Qty=("QUANTITY", "sum"),
                )

                # Merge orders and deletions.
                # Объединение заказов и удалений.
                comparison_df = orders_agg[["ARTIKELNR", "Ordered_Pallets_Total", "Ordered_Qty_Total"]].merge(
                    deleted_agg, on="ARTIKELNR", how="outer"
                ).fillna(0)

                comparison_df["Różnica_Palety"] = (
                    comparison_df["Ordered_Pallets_Total"] - comparison_df["Deleted_Pallets"]
                )
                comparison_df["Różnica_Sztuki"] = (
                    comparison_df["Ordered_Qty_Total"] - comparison_df["Deleted_Qty"]
                )

                # Filter rows based on differences and exclusions.
                # Фильтрация строк на основе различий и исключений.
                excluded_exact, excluded_prefixes = load_excluded_articles()
                
                def should_show_row(row):
                    art = row["ARTIKELNR"].strip().upper()
                    if is_excluded_article(art, excluded_exact, excluded_prefixes):
                        # For excluded articles, show only if BOTH differences are non-zero.
                        # Для исключенных артикулов показывать только если ОБА различия не равны нулю.
                        return (row["Różnica_Palety"] != 0) and (row["Różnica_Sztuki"] != 0)
                    else:
                        # For regular articles, show if ANY difference exists.
                        # Для обычных артикулов показывать, если есть ХОТЯ БЫ ОДНО различие.
                        return (row["Różnica_Palety"] != 0) or (row["Różnica_Sztuki"] != 0)
                
                comparison_df = comparison_df[comparison_df.apply(should_show_row, axis=1)]


                # Generate explanation text.
                # Генерация текста пояснения.
                def explain_diff(row):
                    diff_pal = row["Różnica_Palety"]
                    diff_szt = row["Różnica_Sztuki"]

                    if diff_pal == 0 and diff_szt == 0:
                        return STR["diff_none"]
                    msgs = []

                    if diff_pal > 0:
                        msgs.append(STR["diff_pallets_less"].format(val=int(abs(diff_pal))))
                    elif diff_pal < 0:
                        msgs.append(STR["diff_pallets_more"].format(val=int(abs(diff_pal))))
                    else:
                        msgs.append(STR["diff_pallets_none"])

                    if diff_szt > 0:
                        msgs.append(STR["diff_qty_missing"].format(val=int(abs(diff_szt))))
                    elif diff_szt < 0:
                        msgs.append(STR["diff_qty_excess"].format(val=int(abs(diff_szt))))
                    else:
                        msgs.append(STR["diff_qty_none"])

                    return ", ".join(msgs)

                comparison_df["Wyjaśnienie różnicy"] = comparison_df.apply(explain_diff, axis=1)

                comparison_df = comparison_df.sort_values("Różnica_Palety", ascending=False).reset_index(drop=True)

                # --- Daily Breakdown Analysis ---
                # --- Анализ ежедневной разбивки ---
                is_date_range = date_start and date_end and (date_end.date() - date_start.date()).days > 0

                if is_date_range and orders_all is not None and "ORDER_DATE" in orders_all.columns and not orders_all.empty:
                    orders_valid = orders_all.dropna(subset=["ORDER_DATE"]).copy()
                    
                    # Warn about files without dates.
                    # Предупреждение о файлах без дат.
                    missing_date_mask = orders_all["ORDER_DATE"].isna()
                    if missing_date_mask.any():
                        missing_files = orders_all.loc[missing_date_mask, "SOURCE_FILE"].unique()
                        if len(missing_files) > 0:
                            st.warning(
                                STR["diff_days_warning"].format(count=len(missing_files), example=missing_files[0])
                            )

                    if not orders_valid.empty:
                        orders_daily = orders_valid.groupby(["ARTIKELNR", "ORDER_DATE"], as_index=False)["ORDER_PALLETS"].sum()
                        orders_daily.rename(columns={"ORDER_DATE": "DATE", "ORDER_PALLETS": "ORD"}, inplace=True)
                    else:
                        orders_daily = pd.DataFrame(columns=["ARTIKELNR", "DATE", "ORD"])
                    
                    if not deleted_pallets.empty:
                        del_daily = deleted_pallets.copy()
                        del_daily["DATE"] = del_daily["OUT_DATE"].dt.date
                        # Group by article and date. observed=True handles categorical ARTIKELNR correctly.
                        # Группируем по артикулу и дате. observed=True корректно обрабатывает категориальный ARTIKELNR.
                        del_daily_agg = del_daily.groupby(["ARTIKELNR", "DATE"], as_index=False, observed=True)["LHMNR"].nunique()
                        del_daily_agg.rename(columns={"LHMNR": "DEL"}, inplace=True)
                    else:
                        del_daily_agg = pd.DataFrame(columns=["ARTIKELNR", "DATE", "DEL"])

                    # Merge daily data and calculate differences.
                    # Объединение ежедневных данных и расчет различий.
                    if not orders_daily.empty or not del_daily_agg.empty:
                        daily_merged = pd.merge(orders_daily, del_daily_agg, on=["ARTIKELNR", "DATE"], how="outer").fillna(0)
                        daily_merged["DIFF"] = daily_merged["ORD"] - daily_merged["DEL"]
                        
                        daily_diffs = daily_merged[daily_merged["DIFF"] != 0].copy()
                        
                        if not daily_diffs.empty:
                            daily_diffs = daily_diffs.sort_values("DATE")
                            
                            def fmt_diff(row):
                                d_str = row["DATE"].strftime("%d.%m")
                                val = int(row["DIFF"])
                                sign = "+" if val > 0 else ""
                                return f"{d_str}: {sign}{val}"

                            daily_diffs["TXT"] = daily_diffs.apply(fmt_diff, axis=1)
                            
                            daily_map = daily_diffs.groupby("ARTIKELNR")["TXT"].apply(lambda x: "\n".join(x)).to_dict()
                            
                            comparison_df["Dni z różnicą"] = comparison_df["ARTIKELNR"].map(daily_map).fillna("-")
                        else:
                            comparison_df["Dni z różnicą"] = "-"
                    else:
                        comparison_df["Dni z różnicą"] = "-"
                elif is_date_range:
                    comparison_df["Dni z różnicą"] = "-"

                # Rename columns for display.
                # Переименование колонок для отображения.
                display_comparison_df = comparison_df.copy()
                display_comparison_df.rename(columns={
                    "Różnica_Palety": STR["col_diff_pallets"],
                    "Różnica_Sztuki": STR["col_diff_qty"],
                    "Wyjaśnienie różnicy": STR["col_diff_explanation"],
                    "Dni z różnicą": STR["col_diff_days"]
                }, inplace=True)

                st.dataframe(
                    display_comparison_df,
                    width="stretch",
                    hide_index=True,
                )

                # Display final metrics.
                # Отображение итоговых метрик.
                col1, col2, col3 = st.columns(3)
                col1.metric(STR["metric_articles_ordered"], f"{len(orders_agg[orders_agg['Ordered_Pallets_Total'] > 0])}")
                col2.metric(STR["metric_articles_removed"], f"{len(deleted_agg)}")
                col3.metric(STR["metric_articles_diff"], f"{len(comparison_df)}")
            else:
                st.info("Brak usuniętych palet w wybranym zakresie.")
