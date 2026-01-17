# modules/data_loader.py
# Loading and normalization of the main CSV file.

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import time
import glob

def get_session_file_path(session_id):
    # Generates a safe file path for the session based on the ID.
    # Генерирует безопасный путь к файлу сессии на основе ID.
    safe_id = "".join([c for c in str(session_id) if c.isalnum() or c in "-_"])
    return f"session_state_{safe_id}.pkl"

def cleanup_old_sessions(max_age_hours=24):
    # Removes session files older than max_age_hours.
    # Удаляет файлы сессий старше max_age_hours.
    try:
        # Calculate the cutoff time (current time minus max age).
        # Вычисляем время отсечения (текущее время минус максимальный возраст).
        cutoff = time.time() - (max_age_hours * 3600)
        
        # Iterate over all session files matching the pattern.
        # Перебираем все файлы сессий, соответствующие шаблону.
        for f in glob.glob("session_state_*.pkl"):
            # If the file's modification time is older than the cutoff, delete it.
            # Если время изменения файла старше времени отсечения, удаляем его.
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
    except Exception:
        # Ignore errors during cleanup.
        # Игнорируем ошибки во время очистки.
        pass

def save_session_to_disk(df, session_id):
    # Saves the DataFrame to a file on disk (persistence after refresh).
    # Сохраняет DataFrame в файл на диске (сохранение после обновления страницы).
    
    # Clean old sessions while saving to maintain hygiene.
    # Очищаем старые сессии при сохранении для поддержания порядка.
    cleanup_old_sessions() 
    
    # Get the file path for the current session.
    # Получаем путь к файлу для текущей сессии.
    fpath = get_session_file_path(session_id)
    try:
        # Save the DataFrame using pickle.
        # Сохраняем DataFrame с помощью pickle.
        df.to_pickle(fpath)
    except Exception:
        pass

def load_session_from_disk(session_id):
    # Attempts to load the DataFrame from a session file.
    # Пытается загрузить DataFrame из файла сессии.
    fpath = get_session_file_path(session_id)
    
    # Check if the file exists.
    # Проверяем, существует ли файл.
    if os.path.exists(fpath):
        try:
            # Load the DataFrame from the pickle file.
            # Загружаем DataFrame из pickle-файла.
            return pd.read_pickle(fpath)
        except Exception:
            return None
    return None

def clear_session_state(session_id):
    # Removes the saved session file.
    # Удаляет сохраненный файл сессии.
    fpath = get_session_file_path(session_id)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
        except Exception:
            pass

@st.cache_data
def load_main_csv(uploaded_file, STR):
    # Loads the warehouse CSV file with column validation and data normalization.
    # Загружает CSV-файл склада с проверкой колонок и нормализацией данных.
    # Returns: df (normalized DataFrame) or None on error.
    # Возвращает: df (нормализованный DataFrame) или None в случае ошибки.
    
    if uploaded_file is None:
        return None
    
    # IMPORTANT: Reset file pointer to the beginning before reading.
    # This prevents errors when reusing the same file object (e.g., during cache refresh).
    # ВАЖНО: Сбрасываем указатель файла в начало перед чтением.
    # Это предотвращает ошибки при повторном использовании одного и того же объекта файла (например, при обновлении кэша).
    uploaded_file.seek(0)

    try:
        # Try reading the file with UTF-8 encoding first.
        # Сначала пытаемся прочитать файл в кодировке UTF-8.
        df_raw = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
    except Exception:
        try:
            # Fallback to Latin-1 if UTF-8 fails.
            # Если UTF-8 не сработал, пробуем Latin-1.
            uploaded_file.seek(0)
            df_raw = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='latin-1')
        except Exception as e:
            # Display error message if loading fails.
            # Отображаем сообщение об ошибке, если загрузка не удалась.
            st.error(f"{STR['err_file_load']}{e}")
            return None
    
    # Normalize column names: strip whitespace.
    # Нормализуем имена колонок: удаляем пробелы.
    df_raw.columns = [c.strip() for c in df_raw.columns]
    
    # Create a map of upper-case column names to actual names for case-insensitive lookup.
    # Создаем карту имен колонок в верхнем регистре к реальным именам для поиска без учета регистра.
    cols_map = {c.upper(): c for c in df_raw.columns}
    
    # List of required columns (German names from the source file).
    # Список обязательных колонок (немецкие имена из исходного файла).
    required_raw = [
        "MANDANT", "ARTIKELNR", "ARTBEZ1", "QUANTITY", "LHMNR", "ZUSTAND",
        "PLATZ", "CHARGE1", "ANGELEGT AM", "ANGELEGT UM", "ANGELEGT VON",
        "GEANDERT AM", "GEANDERT UM", "BEWEGUNG AM", "BEWEGUNG UM",
    ]
    
    # Check for missing columns.
    # Проверяем наличие отсутствующих колонок.
    missing = [r for r in required_raw if r not in cols_map]
    
    if missing:
        # Display error if required columns are missing.
        # Отображаем ошибку, если отсутствуют обязательные колонки.
        st.error(f"{STR['err_missing_cols']}{', '.join(missing)}")
        return None
    
    # Select only the required columns using the map and create a copy.
    # Выбираем только нужные колонки, используя карту, и создаем копию.
    df = df_raw[[cols_map[c] for c in required_raw]].copy()
    
    # Rename columns to standard names used in the required_raw list.
    # Переименовываем колонки в стандартные имена, используемые в списке required_raw.
    df.columns = required_raw
    
    # Rename German fields to internal program names (English).
    # Переименовываем немецкие поля во внутренние имена программы (английские).
    df = df.rename(
        columns={
            "ANGELEGT AM": "IN_DATE",
            "ANGELEGT UM": "IN_TIME",
            "BEWEGUNG AM": "OUT_DATE",
            "BEWEGUNG UM": "OUT_TIME",
            "GEANDERT AM": "CHANGED_DATE",
            "GEANDERT UM": "CHANGED_TIME",
            "ANGELEGT VON": "CREATED_BY",
        }
    )
    
    # Normalize data types.
    # Нормализуем типы данных.
    
    # ARTIKELNR: String, stripped, upper case.
    # ARTIKELNR: Строка, без пробелов, верхний регистр.
    df["ARTIKELNR"] = df["ARTIKELNR"].astype(str).str.strip().str.upper().astype("category")
    
    # ARTBEZ1: String, stripped.
    # ARTBEZ1: Строка, без пробелов.
    df["ARTBEZ1"] = df["ARTBEZ1"].astype(str).str.strip()
    
    # QUANTITY: Numeric, replace comma with dot, handle errors, fill NaN with 0.
    # QUANTITY: Число, заменяем запятую на точку, обрабатываем ошибки, заменяем NaN на 0.
    df["QUANTITY"] = pd.to_numeric(
        df["QUANTITY"].astype(str).str.replace(',', '.'), 
        errors='coerce'
    ).fillna(0)
    
    # LHMNR (PID): String, stripped.
    # LHMNR (PID): Строка, без пробелов.
    df["LHMNR"] = df["LHMNR"].astype(str).str.strip()
    
    # CHARGE1: String, stripped, fill NaN with empty string.
    # CHARGE1: Строка, без пробелов, заменяем NaN на пустую строку.
    df["CHARGE1"] = df["CHARGE1"].fillna("").astype(str).str.strip()
    
    # ZUSTAND: String, stripped.
    # ZUSTAND: Строка, без пробелов.
    df["ZUSTAND"] = df["ZUSTAND"].astype(str).str.strip().astype("category")
    
    # PLATZ: String, stripped.
    # PLATZ: Строка, без пробелов.
    df["PLATZ"] = df["PLATZ"].astype(str).str.strip()
    
    # CREATED_BY: String, stripped.
    # CREATED_BY: Строка, без пробелов.
    df["CREATED_BY"] = df["CREATED_BY"].astype(str).str.strip().astype("category")
    
    # MANDANT: Convert to category for memory saving.
    # MANDANT: Конвертируем в категорию для экономии памяти.
    df["MANDANT"] = df["MANDANT"].astype("category")

    # Convert date columns to datetime objects.
    # Конвертируем колонки дат в объекты datetime.
    df["IN_DATE"] = pd.to_datetime(df["IN_DATE"], dayfirst=True, errors='coerce')
    df["OUT_DATE"] = pd.to_datetime(df["OUT_DATE"], dayfirst=True, errors='coerce')
    df["CHANGED_DATE"] = pd.to_datetime(df["CHANGED_DATE"], dayfirst=True, errors="coerce")

    # Convert time columns to time objects.
    # Конвертируем колонки времени в объекты time.
    df["IN_TIME"] = pd.to_datetime(df["IN_TIME"], format="%H:%M:%S", errors="coerce").dt.time
    df["OUT_TIME"] = pd.to_datetime(df["OUT_TIME"], format="%H:%M:%S", errors="coerce").dt.time
    df["CHANGED_TIME"] = pd.to_datetime(
        df["CHANGED_TIME"], format="%H:%M:%S", errors="coerce"
    ).dt.time

    # Deletion logic: A pallet is considered deleted if ZUSTAND is not '401'.
    # Логика удаления: Паллета считается удаленной, если ZUSTAND не равен '401'.
    df["IS_DELETED"] = df["ZUSTAND"] != "401"
    
    # If pallet is in stock (401), clear OUT_DATE and OUT_TIME.
    # This prevents displaying the last modification date as the deletion date.
    # Если паллета на складе (401), очищаем OUT_DATE и OUT_TIME.
    # Это предотвращает отображение даты последнего изменения как даты удаления.
    mask_stock = df["ZUSTAND"] == "401"
    df.loc[mask_stock, "OUT_DATE"] = pd.NaT
    df.loc[mask_stock, "OUT_TIME"] = None

    return df
