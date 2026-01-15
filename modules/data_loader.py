# modules/data_loader.py
# Загрузка и нормализация основного CSV файла

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import time
import glob

def get_session_file_path(session_id):
    """Generuje bezpieczną ścieżkę do pliku sesji na podstawie ID"""
    # Usuwamy znaki, które mogłyby być niebezpieczne w nazwie pliku
    safe_id = "".join([c for c in str(session_id) if c.isalnum() or c in "-_"])
    return f"session_state_{safe_id}.pkl"

def cleanup_old_sessions(max_age_hours=24):
    """Usuwa pliki sesji starsze niż max_age_hours"""
    try:
        cutoff = time.time() - (max_age_hours * 3600)
        for f in glob.glob("session_state_*.pkl"):
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
    except Exception:
        pass

def save_session_to_disk(df, session_id):
    """Zapisuje DataFrame do pliku na dysku (trwałość po odświeżeniu)"""
    cleanup_old_sessions() # Przy okazji zapisu czyścimy stare sesje
    fpath = get_session_file_path(session_id)
    try:
        df.to_pickle(fpath)
    except Exception:
        pass

def load_session_from_disk(session_id):
    """Próbuje wczytać DataFrame z pliku sesji"""
    fpath = get_session_file_path(session_id)
    if os.path.exists(fpath):
        try:
            return pd.read_pickle(fpath)
        except Exception:
            return None
    return None

def clear_session_state(session_id):
    """Usuwa zapisany plik sesji"""
    fpath = get_session_file_path(session_id)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
        except Exception:
            pass

@st.cache_data
def load_main_csv(uploaded_file):
    """
    Загружает CSV файл склада с проверкой колонок и нормализацией данных
    Возвращает: df (нормализованный DataFrame) или None при ошибке
    """
    if uploaded_file is None:
        return None
    
    # WAŻNE: Resetujemy wskaźnik pliku na początek przed odczytem.
    # Zapobiega to błędom przy ponownym użyciu tego samego obiektu pliku (np. przy odświeżeniu cache).
    uploaded_file.seek(0)

    try:
        # Попытка UTF-8
        if uploaded_file.name.lower().endswith(('.csv', '.txt')):
            df_raw = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
        else:
            df_raw = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
    except Exception:
        try:
            uploaded_file.seek(0)
            df_raw = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='latin-1')
        except Exception as e:
            st.error(f"Błąd wczytywania pliku: {e}")
            return None
    
    # Нормализация колонок
    df_raw.columns = [c.strip() for c in df_raw.columns]
    cols_map = {c.upper(): c for c in df_raw.columns}
    
    # Обязательные колонки (Немецкие имена из исходного файла)
    required_raw = [
        "MANDANT", "ARTIKELNR", "ARTBEZ1", "QUANTITY", "LHMNR", "ZUSTAND",
        "PLATZ", "CHARGE1", "ANGELEGT AM", "ANGELEGT UM", "ANGELEGT VON",
        "GEANDERT AM", "GEANDERT UM", "BEWEGUNG AM", "BEWEGUNG UM",
    ]
    
    missing = [r for r in required_raw if r not in cols_map]
    
    if missing:
        st.error(f"Plik nie zawiera wymaganych kolumn: {', '.join(missing)}")
        return None
    
    # Выбираем только нужные колонки и переименовываем
    df = df_raw[[cols_map[c] for c in required_raw]].copy()
    df.columns = required_raw
    
    # Переименовываем немецкие поля в программные имена
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
    
    # Нормализация типов данных
    df["ARTIKELNR"] = df["ARTIKELNR"].astype(str).str.strip().str.upper()
    df["ARTBEZ1"] = df["ARTBEZ1"].astype(str).str.strip()
    df["QUANTITY"] = pd.to_numeric(
        df["QUANTITY"].astype(str).str.replace(',', '.'), 
        errors='coerce'
    ).fillna(0)
    
    df["LHMNR"] = df["LHMNR"].astype(str).str.strip()
    df["CHARGE1"] = df["CHARGE1"].fillna("").astype(str).str.strip()
    df["ZUSTAND"] = df["ZUSTAND"].astype(str).str.strip()
    df["PLATZ"] = df["PLATZ"].astype(str).str.strip()
    df["CREATED_BY"] = df["CREATED_BY"].astype(str).str.strip()

    df["IN_DATE"] = pd.to_datetime(df["IN_DATE"], dayfirst=True, errors='coerce')
    df["OUT_DATE"] = pd.to_datetime(df["OUT_DATE"], dayfirst=True, errors='coerce')
    df["CHANGED_DATE"] = pd.to_datetime(df["CHANGED_DATE"], dayfirst=True, errors="coerce")

    df["IN_TIME"] = pd.to_datetime(df["IN_TIME"], format="%H:%M:%S", errors="coerce").dt.time
    df["OUT_TIME"] = pd.to_datetime(df["OUT_TIME"], format="%H:%M:%S", errors="coerce").dt.time
    df["CHANGED_TIME"] = pd.to_datetime(
        df["CHANGED_TIME"], format="%H:%M:%S", errors="coerce"
    ).dt.time

    # Логика удаления: ZUSTAND != 401
    df["IS_DELETED"] = df["ZUSTAND"] != "401"
    
    # Если паллета на складе (401), очищаем OUT_DATE и OUT_TIME
    # Это предотвращает отображение даты последнего изменения как даты удаления
    mask_stock = df["ZUSTAND"] == "401"
    df.loc[mask_stock, "OUT_DATE"] = pd.NaT
    df.loc[mask_stock, "OUT_TIME"] = None

    return df
