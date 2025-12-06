import json
import os
import streamlit as st

EXCLUDED_ARTICLES_FILE = "excluded_articles.json"
PACKAGING_CONFIG_FILE = "packaging_config.json"

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
