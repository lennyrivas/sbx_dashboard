# modules/data_loader.py
# Загрузка и нормализация основного CSV файла

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def load_main_csv(uploaded_file):
    """
    Загружает CSV файл склада с проверкой колонок и нормализацией данных
    Возвращает: df (нормализованный DataFrame) или None при ошибке
    """
    if uploaded_file is None:
        return None
    
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
    
    # Обязательные колонки
    required = ["MANDANT", "ARTIKELNR", "ARTBEZ1", "QUANTITY", "LHMNR", 
                "ZUSTAND", "PLATZ", "IN_DATE", "OUT_DATE"]
    missing = [r for r in required if r not in cols_map]
    
    if missing:
        st.error(f"Plik nie zawiera wymaganych kolumn: {', '.join(missing)}")
        return None
    
    # Выбираем только нужные колонки и переименовываем
    df = df_raw[[cols_map[c] for c in required]].copy()
    df.columns = required
    
    # Фильтр только mandants 351/352
    df = df[df["MANDANT"].astype(str).isin(["351", "352"])].copy()
    
    # Нормализация типов данных
    df["ARTIKELNR"] = df["ARTIKELNR"].astype(str).str.strip().str.upper()
    df["ARTBEZ1"] = df["ARTBEZ1"].astype(str).str.strip()
    df["QUANTITY"] = pd.to_numeric(
        df["QUANTITY"].astype(str).str.replace(',', '.'), 
        errors='coerce'
    ).fillna(0)
    df["IN_DATE"] = pd.to_datetime(df["IN_DATE"], dayfirst=True, errors='coerce')
    df["OUT_DATE"] = pd.to_datetime(df["OUT_DATE"], dayfirst=True, errors='coerce')
    df["LHMNR"] = df["LHMNR"].astype(str)
    
    return df
