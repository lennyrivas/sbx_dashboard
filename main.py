# main.py
# Entry point for the Warehouse Dashboard application.
# Точка входа для приложения Warehouse Dashboard.

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


# --- Page Configuration ---
# --- Конфигурация страницы ---
# Sets the page title, layout, and initial sidebar state.
# Устанавливает заголовок страницы, макет и начальное состояние боковой панели.
st.set_page_config(
    page_title="Sprintbox — Raport palet",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Language Selection ---
# --- Выбор языка ---
# Initialize language in session state if not present.
# Инициализация языка в состоянии сессии, если он отсутствует.
if "lang" not in st.session_state:
    st.session_state["lang"] = "PL"

# Sidebar widget to select language.
# Виджет боковой панели для выбора языка.
lang_choice = st.sidebar.selectbox(
    "Language / Język", 
    ["PL", "EN"], 
    index=0 if st.session_state["lang"] == "PL" else 1
)
if lang_choice != st.session_state["lang"]:
    st.session_state["lang"] = lang_choice
    st.rerun()

# Load translations based on selected language.
# Загрузка переводов на основе выбранного языка.
STR = get_translations(st.session_state["lang"])
st.title(STR["title"])

# --- Session Management ---
# --- Управление сессией ---
# Generate or retrieve a unique session ID to handle data persistence.
# Генерация или получение уникального ID сессии для управления сохранением данных.
try:
    # Check query parameters for session_id.
    # Проверка параметров запроса на наличие session_id.
    if "session_id" not in st.query_params:
        st.query_params["session_id"] = str(uuid.uuid4())
    session_id = st.query_params["session_id"]
except AttributeError:
    # Fallback for older Streamlit versions.
    # Резервный вариант для старых версий Streamlit.
    params = st.experimental_get_query_params()
    if "session_id" not in params:
        session_id = str(uuid.uuid4())
        params["session_id"] = session_id
        st.experimental_set_query_params(**params)
    else:
        session_id = params["session_id"][0]

# --- Data Loading Section ---
# --- Секция загрузки данных ---

# 1. Auto-Download from IHKA.
# 1. Автозагрузка из IHKA.
st.sidebar.markdown(f"### {STR['import_data']}")

if st.sidebar.button(STR["btn_auto_download"], type="primary"):
    # Create a status container to show progress.
    # Создаем контейнер статуса для отображения прогресса.
    status_box = st.sidebar.status("Łączenie z IHKA...", expanded=True)
    
    # Run the downloader process.
    # Запускаем процесс загрузки.
    file_path = run_ihka_downloader(status_box, STR)
    
    if file_path:
        # If download successful, try to load the file.
        # Если загрузка прошла успешно, пытаемся загрузить файл.
        try:
            with open(file_path, "rb") as f:
                # Create in-memory bytes buffer.
                # Создаем буфер байтов в памяти.
                from io import BytesIO
                mem_file = BytesIO(f.read())
                # Set name attribute to full path (needed for caching mechanism).
                # Устанавливаем атрибут имени в полный путь (нужно для механизма кэширования).
                mem_file.name = file_path 
                
                # Parse CSV into DataFrame.
                # Парсим CSV в DataFrame.
                df = load_main_csv(mem_file, STR)
                if df is not None:
                    # Save to disk for persistence.
                    # Сохраняем на диск для персистентности.
                    save_session_to_disk(df, session_id)
                    st.session_state["restored_df"] = df
                    status_box.update(label="Done!", state="complete", expanded=False)
                    st.rerun()
                else:
                    status_box.update(label=STR["err_format"], state="error")
        except Exception as e:
            # Handle errors during processing.
            # Обработка ошибок во время обработки.
            st.sidebar.error(STR["err_process_download"])
            print(f"Auto-download error: {e}")
        finally:
            # Clean up temporary files.
            # Очистка временных файлов.
            cleanup_temp_downloads()
    else:
        status_box.update(label="Błąd", state="error")

# Link for manual download if auto-download fails.
# Ссылка для ручной загрузки, если автозагрузка не удалась.
st.sidebar.link_button(STR["btn_open_ihka"], "http://ihka.schaeflein.de/WebAccess/Auth/Login")

# 2. Offline Tool Download.
# 2. Скачивание офлайн-инструмента.
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {STR['offline_tool']}")
st.sidebar.caption(STR["offline_desc"])

# Generate and provide download button for the standalone script.
# Генерируем и предоставляем кнопку скачивания для автономного скрипта.
zip_file = create_standalone_package()
st.sidebar.download_button(
    label=STR["download_script"],
    data=zip_file,
    file_name="ihka_downloader_tool.zip",
    mime="application/zip"
)

st.sidebar.caption(STR["wifi_warning"])
st.sidebar.markdown("---")

# 3. Manual File Upload.
# 3. Ручная загрузка файла.
uploaded = st.sidebar.file_uploader(
    STR["upload_csv"],
    type=["csv", "txt"],
    key="main_csv",
)

df = None

# Priority 1: Load from uploaded file.
# Приоритет 1: Загрузка из загруженного файла.
if uploaded is not None:
    df = load_main_csv(uploaded, STR)
    if df is not None:
        # Save to disk.
        # Сохраняем на диск.
        save_session_to_disk(df, session_id)
        if "restored_df" in st.session_state:
            del st.session_state["restored_df"]

# Priority 2: Restore from session state or disk.
# Приоритет 2: Восстановление из состояния сессии или диска.
if df is None:
    if "restored_df" not in st.session_state:
        saved_df = load_session_from_disk(session_id)
        if saved_df is not None:
            st.session_state["restored_df"] = saved_df
    
    if "restored_df" in st.session_state:
        df = st.session_state["restored_df"]
        st.sidebar.warning(STR["restore_session"])
        # Button to clear session data.
        # Кнопка для очистки данных сессии.
        if st.sidebar.button(STR["clear_data"], key="clear_session_btn"):
            clear_session_state(session_id)
            del st.session_state["restored_df"]
            st.rerun()

# Stop execution if no data is available.
# Остановка выполнения, если данные недоступны.
if df is None:
    st.info(STR["no_file"])
    st.stop()

# --- Admin Login ---
# --- Вход администратора ---
# Sidebar form for admin authentication.
# Форма в боковой панели для аутентификации администратора.
with st.sidebar:
    st.markdown("---")
    with st.expander(STR["admin_login"]):
        with st.form("admin_login_form"):
            admin_password = st.text_input(STR["password"], type="password", key="admin_pass", label_visibility="collapsed", placeholder=STR["password"])
            st.form_submit_button(STR["login"], width="stretch")

# --- Tabs Configuration ---
# --- Конфигурация вкладок ---
tabs_labels = [
    STR["tab_analysis"],
    STR["tab_stock"],
    STR["tab_stats"],
    STR["tab_removal"],
]

# Check admin password.
# Проверка пароля администратора.
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

# --- Tab 1: Analysis (Orders vs Pallets) ---
# --- Вкладка 1: Анализ (Заказы vs Паллеты) ---
with tab_analysis:
    st.header(STR["analysis_header"])

    # Render filters specific to analysis.
    # Рендеринг фильтров, специфичных для анализа.
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

    # Load packaging config for metrics.
    # Загрузка конфигурации упаковки для метрик.
    kartony_prefixes, _ = load_packaging_config()

    # Display metrics based on mode (Received vs Deleted).
    # Отображение метрик в зависимости от режима (Принятые vs Удаленные).
    if mode == STR["mode_received"]:
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

    # Render the main orders table and comparison logic.
    # Рендеринг основной таблицы заказов и логики сравнения.
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

# --- Tab 2: Stock Levels ---
# --- Вкладка 2: Уровни запасов ---
with tab_stock:
    render_stock_tab(
        df,                # Full DataFrame / Полный DataFrame
        selected_mandant,  # Selected mandant / Выбранный мандант
        selected_artikel,  # Selected articles / Выбранные артикулы
        STR,
    )

# --- Tab 3: Statistics ---
# --- Вкладка 3: Статистика ---
with tab_stats:
    render_stats_tab(df, STR)

# --- Tab 4: Pallet Removal ---
# --- Вкладка 4: Удаление паллет ---
with tab_removal:
    render_removal_tab(df, STR)

# --- Tab 5: Settings (Admin Only) ---
# --- Вкладка 5: Настройки (Только админ) ---
if len(tabs) > 4:
    with tabs[4]:
        render_settings_tab(STR)
