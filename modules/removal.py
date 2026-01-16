# modules/removal.py
# Logic for the 'Pallet Removal' tab (PID Generator).
# Логика для вкладки 'Удаление паллет' (Генератор PID).

import streamlit as st
import pandas as pd
from datetime import datetime
from utils import load_packages_strategies, load_packaging_config

def get_platz_priority(platz):
    # Determines the priority of a storage location (PLATZ).
    # Определяет приоритет места хранения (PLATZ).
    # Priority levels:
    # 0: High priority (Reception/Blocking areas: WE, BL).
    # 1: Medium priority (Standard racks starting with 2 or 02).
    # 2: Low priority (Everything else).
    # Уровни приоритета:
    # 0: Высокий приоритет (Зоны приемки/блокировки: WE, BL).
    # 1: Средний приоритет (Стандартные стеллажи, начинающиеся с 2 или 02).
    # 2: Низкий приоритет (Все остальное).
    
    p = str(platz).strip().upper()
    if p.startswith(('WE', 'BL')): return 0
    if p.startswith(('2', '02')): return 1
    return 2

def render_removal_tab(df, STR):
    # Renders the main content of the 'Pallet Removal' tab.
    # Рендерит основное содержимое вкладки 'Удаление паллет'.
    
    # --- OPTIMIZATION: Initialize working stock base (only ZUSTAND 401) ---
    # --- ОПТИМИЗАЦИЯ: Инициализация рабочей базы остатков (только ZUSTAND 401) ---
    
    # Create a unique signature for the dataframe (e.g., shape) to detect if the source file has changed.
    # Создаем уникальную подпись для dataframe (например, размер), чтобы обнаружить изменение исходного файла.
    df_signature = df.shape
    
    # Initialize session state variables if they don't exist or if the data has changed.
    # Инициализируем переменные состояния сессии, если они не существуют или если данные изменились.
    if "removal_stock_df" not in st.session_state or st.session_state.get("removal_df_signature") != df_signature:
        # Create a lightweight copy containing only pallets currently in stock (ZUSTAND 401).
        # Создаем легкую копию, содержащую только паллеты, находящиеся на складе (ZUSTAND 401).
        stock_401 = df[df["ZUSTAND"] == "401"].copy()
        
        # Calculate location priority immediately (once and for all) to avoid re-calculation during interaction.
        # Вычисляем приоритет места сразу (один раз и навсегда), чтобы избежать пересчета во время взаимодействия.
        stock_401["PLATZ_PRIORITY"] = stock_401["PLATZ"].apply(get_platz_priority)
        
        # Store in session state.
        # Сохраняем в состоянии сессии.
        st.session_state["removal_stock_df"] = stock_401
        st.session_state["removal_df_signature"] = df_signature
        st.session_state["removed_pids"] = set()

    st.header(STR["removal_header"])
    st.info(STR["removal_info"])

    # 1. Check order availability.
    # 1. Проверка наличия заказов.
    if "orders_cache" not in st.session_state or st.session_state["orders_cache"].get("orders_all") is None:
        st.warning(STR["removal_warn_no_orders"])
        return

    orders_all = st.session_state["orders_cache"]["orders_all"]
    if orders_all.empty:
        st.warning(STR["removal_warn_empty_orders"])
        return

    # 2. File selection dropdown.
    # 2. Выпадающий список выбора файла.
    files = sorted(orders_all["SOURCE_FILE"].unique())
    selected_file = st.selectbox(STR["removal_select_file"], options=files)

    if selected_file:
        # Pass our optimized stock base from session state to the tool.
        # Передаем нашу оптимизированную базу остатков из состояния сессии в инструмент.
        render_removal_tool(st.session_state["removal_stock_df"], orders_all, selected_file, STR)


def render_removal_tool(stock_df, orders_all, filename, STR):
    # Core logic for the removal tool: matches orders with stock and suggests PIDs.
    # Основная логика инструмента удаления: сопоставляет заказы с остатками и предлагает PID.
    
    # CSS hack: wider tags in multiselect (attempt at 2-column layout / full width).
    # CSS хак: более широкие теги в мультивыборе (попытка макета в 2 колонки / полная ширина).
    # This improves readability of long PID strings in the selection box.
    # Это улучшает читаемость длинных строк PID в поле выбора.
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

    # Display success message (if exists in session from previous action).
    # Отображение сообщения об успехе (если оно существует в сессии от предыдущего действия).
    if "removal_msg" in st.session_state:
        st.success(st.session_state.pop("removal_msg"))

    # Filter order data for the selected file.
    # Фильтрация данных заказа для выбранного файла.
    order_data = orders_all[orders_all["SOURCE_FILE"] == filename].copy()
    
    # Preserve original order (sort by first occurrence in file).
    # Сохранение исходного порядка (сортировка по первому появлению в файле).
    order_data = order_data.reset_index()
    
    # Aggregate by article to get total quantities needed.
    # Агрегация по артикулу для получения общего необходимого количества.
    order_agg = order_data.groupby("ARTIKELNR", as_index=False).agg(
        Total_Qty=("ORDER_QTY", "sum"),
        Total_Pallets=("ORDER_PALLETS", "sum")
    )
    
    # Restore original order after aggregation.
    # Восстановление исходного порядка после агрегации.
    first_occurrence = order_data.groupby("ARTIKELNR")['index'].min()
    order_agg['orig_idx'] = order_agg['ARTIKELNR'].map(first_occurrence)
    order_agg = order_agg.sort_values('orig_idx').drop(columns=['orig_idx'])
    
    # Calculate average quantity per pallet (for structural matching).
    # Вычисление среднего количества на паллете (для структурного сопоставления).
    order_agg["Qty_Per_Pallet"] = order_agg.apply(
        lambda r: r["Total_Qty"] / r["Total_Pallets"] if r["Total_Pallets"] > 0 else 0, axis=1
    )

    # Use already filtered and optimized base (stock_df is passed from session state).
    # Используем уже отфильтрованную и оптимизированную базу (stock_df передается из состояния сессии).
    stock_active = stock_df.copy()

    final_pids = []

    st.markdown(STR["removal_list_header"])
    st.markdown("---")

    # Collecting data for summary table.
    # Сбор данных для сводной таблицы.
    summary_rows = []
    empty_pids_arts = []

    # Load strategy config (e.g., for articles with pallet priority).
    # Загрузка конфигурации стратегий (например, для артикулов с приоритетом паллет).
    strategies_config = load_packages_strategies()
    pallet_priority_prefixes = strategies_config.get("pallet_priority", {}).get("prefixes", ["202671"])

    # Load packaging config (for marking cartons).
    # Загрузка конфигурации упаковки (для маркировки картонов).
    kartony_prefixes_raw, _ = load_packaging_config()
    kartony_prefixes = [k for k in kartony_prefixes_raw if k and str(k).strip()]

    # Helper to format PLATZ (mask for 02...).
    # Помощник для форматирования PLATZ (маска для 02...).
    # Converts 021234567 -> 02-123-45-67 for better readability.
    # Конвертирует 021234567 -> 02-123-45-67 для лучшей читаемости.
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

    # Use form to minimize page reloads on every click.
    # Используем форму, чтобы минимизировать перезагрузки страницы при каждом клике.
    with st.form("removal_form"):
        # Split into two columns: Others (left) | Cartons (right).
        # Разделение на две колонки: Остальные (слева) | Картоны (справа).
        col_others, col_cartons = st.columns(2)
        with col_others:
            st.markdown(STR["removal_col_others"])
        with col_cartons:
            st.markdown(STR["removal_col_cartons"])

        # Iterate through each ordered article.
        # Перебираем каждый заказанный артикул.
        for index, row in order_agg.iterrows():
            art = row["ARTIKELNR"]
            qty_needed = row["Total_Qty"]
            pallets_needed = int(row["Total_Pallets"])
            qty_per_pal = row["Qty_Per_Pallet"]

            # Check if article is a carton.
            # Проверяем, является ли артикул картоном.
            is_carton = str(art).startswith(tuple(kartony_prefixes))

            # Get available pallets for this article from stock.
            # Получаем доступные паллеты для этого артикула со склада.
            art_stock = stock_active[stock_active["ARTIKELNR"] == art].copy()
            
            # Special logic for articles defined in packages_strategies.json (pallet count priority).
            # Специальная логика для артикулов, определенных в packages_strategies.json (приоритет количества паллет).
            is_pallet_priority = str(art).startswith(tuple(pallet_priority_prefixes))
            
            if is_carton:
                # For cartons, we don't suggest specific PIDs automatically (usually handled differently).
                # Для картонов мы не предлагаем конкретные PID автоматически (обычно обрабатываются иначе).
                suggested_pids = []
            elif is_pallet_priority:
                # Strategy: Pallet Priority.
                # Стратегия: Приоритет паллет.
                # Select pallets based on location priority and FIFO, ignoring quantity on pallet.
                # Выбираем паллеты на основе приоритета места и FIFO, игнорируя количество на паллете.
                df_special = art_stock.sort_values(
                    by=["PLATZ_PRIORITY", "IN_DATE"], 
                    ascending=[True, True]
                )
                suggested_pids = df_special["LHMNR"].head(pallets_needed).tolist()
            else:
                # --- STRATEGY 1: Structural matching (by quantity per pallet) ---
                # --- СТРАТЕГИЯ 1: Структурное сопоставление (по количеству на паллете) ---
                # Try to find pallets matching exactly "pieces per pallet" from order.
                # Пытаемся найти паллеты, точно соответствующие "штук на паллете" из заказа.
                art_stock["Qty_Diff"] = art_stock["QUANTITY"].apply(lambda q: abs(q - qty_per_pal))
                
                df_strat1 = art_stock.sort_values(
                    by=["Qty_Diff", "PLATZ_PRIORITY", "IN_DATE"], 
                    ascending=[True, True, True]
                )
                pids_strat1 = df_strat1["LHMNR"].head(pallets_needed).tolist()
                qty_strat1 = df_strat1[df_strat1["LHMNR"].isin(pids_strat1)]["QUANTITY"].sum()
                diff_strat1 = abs(qty_strat1 - qty_needed)

                # --- STRATEGY 2: Quantitative matching (FIFO / Location Priority) ---
                # --- СТРАТЕГИЯ 2: Количественное сопоставление (FIFO / Приоритет места) ---
                # Ignore pallet division, try to collect required quantity (e.g., 11 pallets of 1 piece instead of 1 of 11).
                # Игнорируем разделение на паллеты, пытаемся собрать необходимое количество (например, 11 паллет по 1 штуке вместо 1 по 11).
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
                        
                        # Remember best set (closest quantitatively).
                        # Запоминаем лучший набор (ближайший количественно).
                        if curr_diff < best_strat2_diff:
                            best_strat2_diff = curr_diff
                            pids_strat2 = list(temp_pids)
                        
                        # If collected enough, stop (don't take excess pallets).
                        # Если собрали достаточно, останавливаемся (не берем лишние паллеты).
                        if temp_qty >= qty_needed:
                            break
                
                # If strategy 2 selected nothing (e.g., no stock), set error to max.
                # Если стратегия 2 ничего не выбрала (например, нет остатков), устанавливаем ошибку на максимум.
                if not pids_strat2:
                    best_strat2_diff = qty_needed

                # --- DECISION ---
                # --- РЕШЕНИЕ ---
                # If Strategy 2 gives better quantitative match (smaller error), choose it.
                # Если Стратегия 2 дает лучшее количественное совпадение (меньшую ошибку), выбираем ее.
                # Otherwise (tie or Strategy 1 better) stick to order structure.
                # В противном случае (ничья или Стратегия 1 лучше) придерживаемся структуры заказа.
                if best_strat2_diff < diff_strat1:
                    suggested_pids = pids_strat2
                else:
                    suggested_pids = pids_strat1
            
            # Target column selection.
            # Выбор целевой колонки.
            target_col = col_cartons if is_carton else col_others

            # Display row in the appropriate column.
            # Отображение строки в соответствующей колонке.
            with target_col:
                # Compact layout: Info left (1), Selection right (2) - adapted for narrower column.
                # Компактный макет: Инфо слева (1), Выбор справа (2) - адаптировано для узкой колонки.
                col_info, col_select = st.columns([1, 2])
                
                # Map for multiselect display: PID (Qty) [Location].
                # Карта для отображения в мультивыборе: PID (Кол-во) [Место].
                # Format: PID | Qty pcs | Location
                pid_map = {
                    r["LHMNR"]: f"{r['LHMNR']} | {int(r['QUANTITY'])} szt. | {format_platz_display(r['PLATZ'])}" 
                    for _, r in art_stock.iterrows()
                }
                
                # Ensure suggested PIDs are in available options (sanity check).
                # Убеждаемся, что предложенные PID находятся в доступных опциях (проверка на здравый смысл).
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
                    
                    # Calculate selection stats.
                    # Вычисление статистики выбора.
                    sel_count = len(selected)
                    sel_qty = art_stock[art_stock["LHMNR"].isin(selected)]["QUANTITY"].sum()
                    
                    # Check compliance.
                    # Проверка соответствия.
                    match_pal = (sel_count == pallets_needed)
                    # Float tolerance for quantity comparison.
                    # Допуск float для сравнения количества.
                    match_qty = abs(sel_qty - qty_needed) < 0.1
                    
                    # Text coloring logic.
                    # Логика раскрашивания текста.
                    if is_pallet_priority:
                        color_class = "green" if match_pal else "red"
                    else:
                        color_class = "green" if match_qty else "red"
                    
                    summary_text = STR["removal_summary_text"].format(p1=int(pallets_needed), q1=int(qty_needed), p2=sel_count, q2=int(sel_qty))
                    st.markdown(f":{color_class}[{summary_text}]")
                
                final_pids.extend(selected)
                st.divider()

                # Collecting data for summary.
                # Сбор данных для сводки.
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
    # --- Секция сводки (вне формы) ---
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
            # Show only those with difference.
            # Показываем только те, где есть разница.
            df_diff = df_summary[df_summary["Różnica (szt)"] != 0]
            if not df_diff.empty:
                st.dataframe(df_diff, width="stretch", hide_index=True)
            else:
                st.success(STR["removal_no_diff"])
            st.caption(STR["removal_strategy_caption"])

    # --- Result Section ---
    # --- Секция результата ---
    st.markdown(STR["removal_result_header"])
    if final_pids:
        # Remove duplicates (just in case).
        # Удаление дубликатов (на всякий случай).
        final_pids = list(dict.fromkeys(final_pids))
        
        # Layout: Result (left, ~35%), Button (right).
        # Макет: Результат (слева, ~35%), Кнопка (справа).
        col_res, col_btn = st.columns([0.35, 0.65])
        
        with col_res:
            # Compact result in expander.
            # Компактный результат в экспандере.
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
            # Confirm removal button logic.
            # Логика кнопки подтверждения удаления.
            def confirm_removal():
                # Add selected PIDs to the removed set.
                # Добавляем выбранные PID в набор удаленных.
                st.session_state["removed_pids"].update(final_pids)
                # Remove them from the working stock dataframe.
                # Удаляем их из рабочего dataframe остатков.
                st.session_state["removal_stock_df"] = st.session_state["removal_stock_df"][~st.session_state["removal_stock_df"]["LHMNR"].isin(final_pids)]
                # Set success message.
                # Устанавливаем сообщение об успехе.
                st.session_state["removal_msg"] = STR["removal_msg_removed"].format(count=len(final_pids))

            st.button(STR["removal_btn_confirm"], type="primary", help=STR["removal_help_confirm"], on_click=confirm_removal)
            
        if submit_btn:
            st.toast(STR["removal_toast_generated"], icon="📋")
    else:
        st.info(STR["removal_no_selection"])