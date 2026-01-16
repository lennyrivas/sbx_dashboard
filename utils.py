# utils.py
# Utility functions for configuration management and helper logic.
# Вспомогательные функции для управления конфигурацией и служебной логики.

import json
import os
import streamlit as st

EXCLUDED_ARTICLES_FILE = "excluded_articles.json"
PACKAGING_CONFIG_FILE = "packaging_config.json"
PACKAGES_STRATEGIES_FILE = "packages_strategies.json"

# --- LOADERS / SAVERS (Abstraction Layer) ---

def load_excluded_articles():
    # Loads the list of excluded articles from the local JSON file.
    # Загружает список исключенных артикулов из локального JSON-файла.
    # Returns: Tuple (exact_matches_list, prefixes_list).
    if os.path.isfile(EXCLUDED_ARTICLES_FILE):
        try:
            with open(EXCLUDED_ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("exact", []), data.get("prefixes", [])
        except Exception:
            pass
            
    return [], []

def save_excluded_articles(exact_list, prefix_list):
    # Saves the list of excluded articles to the local JSON file.
    # Сохраняет список исключенных артикулов в локальный JSON-файл.
    data = {
        "_description": "Plik zawiera listę artykułów wykluczonych z porównań (dokładne dopasowanie oraz prefiksy).",
        "exact": exact_list, 
        "prefixes": prefix_list
    }
    
    try:
        with open(EXCLUDED_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania excluded_articles.json: {e}")
        return False

def load_packaging_config():
    # Loads packaging configuration (cartons vs others) from JSON.
    # Загружает конфигурацию упаковки (картоны vs остальные) из JSON.
    # Returns: Tuple (cartons_prefixes, other_prefixes).
    if os.path.isfile(PACKAGING_CONFIG_FILE):
        try:
            with open(PACKAGING_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("kartony_prefixes", []), data.get("other_packaging_prefixes", [])
        except Exception:
            pass
            
    return ["83090", "ZC", "568", "676", "826"], []

def save_packaging_config(kartony_prefixes, other_prefixes):
    # Saves packaging configuration to JSON.
    # Сохраняет конфигурацию упаковки в JSON.
    data = {
        "_description": "Konfiguracja prefiksów dla kartonów i innych opakowań (używane głównie dla Mandanta 352).",
        "kartony_prefixes": kartony_prefixes, 
        "other_packaging_prefixes": other_prefixes
    }

    try:
        with open(PACKAGING_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania packaging_config.json: {e}")
        return False

def load_packages_strategies():
    # Loads packaging strategies (e.g., pallet priority) from JSON.
    # Загружает стратегии упаковки (например, приоритет паллет) из JSON.
    default_strategies = {
        "pallet_priority": {"prefixes": ["202671"]}
    }
    
    if os.path.isfile(PACKAGES_STRATEGIES_FILE):
        try:
            with open(PACKAGES_STRATEGIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_strategies

def save_packages_strategies(pallet_priority_prefixes):
    # Saves packaging strategies to JSON.
    # Сохраняет стратегии упаковки в JSON.
    current = load_packages_strategies()
    
    # Update prefixes for pallet priority strategy.
    if "pallet_priority" not in current:
        current["pallet_priority"] = {"description": "", "prefixes": [], "examples": []}
    
    current["pallet_priority"]["prefixes"] = pallet_priority_prefixes
    current["_description"] = "Konfiguracja strategii dobierania palet w narzędziu usuwania (np. priorytet liczby palet nad ilością sztuk)."

    try:
        with open(PACKAGES_STRATEGIES_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania packages_strategies.json: {e}")
        return False

def classify_pallet(
    artikelnr: str,
    kartony_prefixes: list[str],
    pallets_frames_prefixes: list[str],   # можно оставить параметр, но не использовать
    other_packaging_prefixes: list[str],
) -> str:
    # Classifies a pallet based on its article number.
    # Классифицирует паллету на основе номера артикула.
    #
    # Logic:
    # - "Kartony" (Cartons): If ARTIKELNR starts with any prefix in kartony_prefixes.
    # - "Inne opakowania" (Other): Everything else.
    #
    # Логика:
    # - "Kartony" (Картоны): Если ARTIKELNR начинается с любого префикса из kartony_prefixes.
    # - "Inne opakowania" (Другие): Все остальное.

    art = str(artikelnr).strip().upper()

    # 1. Check for Cartons (strict prefix match).
    for pref in kartony_prefixes:
        p = str(pref).strip().upper()
        if p and art.startswith(p):
            return "Kartony"

    # 2. Default to Other.
    return "Inne opakowania"
