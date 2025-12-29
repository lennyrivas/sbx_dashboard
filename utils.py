import json
import os
import streamlit as st

EXCLUDED_ARTICLES_FILE = "excluded_articles.json"
PACKAGING_CONFIG_FILE = "packaging_config.json"
ADMIN_STRATEGIES_FILE = "admin_strategies.json"

def load_excluded_articles():
    """Загружает список исключённых артикулов"""
    if os.path.isfile(EXCLUDED_ARTICLES_FILE):
        try:
            with open(EXCLUDED_ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("exact", []), data.get("prefixes", [])
        except Exception as e:
            st.error(f"Błąd ładowania excluded_articles.json: {e}")
            return [], []
    return [], []

def save_excluded_articles(exact_list, prefix_list):
    """Сохраняет исключённые артикулы"""
    try:
        with open(EXCLUDED_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump({"exact": exact_list, "prefixes": prefix_list}, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania excluded_articles.json: {e}")
        return False

def load_packaging_config():
    """Загружает конфигурацию упаковки (картоны)"""
    if os.path.isfile(PACKAGING_CONFIG_FILE):
        try:
            with open(PACKAGING_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("kartony_prefixes", []), data.get("other_packaging_prefixes", [])
        except Exception as e:
            st.error(f"Błąd ładowania packaging_config.json: {e}")
            return [], []
    return ["83090", "ZC", "568", "676", "826"], []

def save_packaging_config(kartony_prefixes, other_prefixes):
    """Сохраняет конфигурацию упаковки"""
    try:
        with open(PACKAGING_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "kartony_prefixes": kartony_prefixes, 
                "other_packaging_prefixes": other_prefixes
            }, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania packaging_config.json: {e}")
        return False

def load_admin_strategies():
    """
    Загружает конфигурацию стратегий для админ-панели (admin_strategies.json).
    Возвращает словарь с настройками.
    """
    default_strategies = {
        "pallet_priority": {"prefixes": ["202671"]}
    }
    if os.path.isfile(ADMIN_STRATEGIES_FILE):
        try:
            with open(ADMIN_STRATEGIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Błąd ładowania admin_strategies.json: {e}")
    return default_strategies

def classify_pallet(
    artikelnr: str,
    kartony_prefixes: list[str],
    pallets_frames_prefixes: list[str],   # можно оставить параметр, но не использовать
    other_packaging_prefixes: list[str],
) -> str:
    """
    Простая классификация:
    - "Kartony"      – если ARTIKELNR НАЧИНАЕТСЯ с одного из kartony_prefixes
    - "Inne opakowania" – всё остальное
    """

    art = str(artikelnr).strip().upper()

    # 1) Kartony – строго по НАЧАЛУ строки (prefix)
    for pref in kartony_prefixes:
        p = str(pref).strip().upper()
        if p and art.startswith(p):
            return "Kartony"

    # 2) Всё, что не попало в kartony, считаем "Inne opakowania"
    return "Inne opakowania"
