import json
import os
import io
import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

EXCLUDED_ARTICLES_FILE = "excluded_articles.json"
PACKAGING_CONFIG_FILE = "packaging_config.json"
PACKAGES_STRATEGIES_FILE = "packages_strategies.json"

# --- GOOGLE DRIVE HELPER FUNCTIONS ---

def get_drive_service():
    """Autoryzacja i tworzenie klienta Google Drive API (OAuth 2.0)"""
    try:
        # 1. Próba OAuth 2.0 (Zalecane dla kont osobistych/Gmail)
        if "google_oauth" in st.secrets:
            oauth_config = st.secrets["google_oauth"]
            
            creds = Credentials(
                token=None,  # Access token zostanie pobrany automatycznie przy użyciu refresh_token
                refresh_token=oauth_config["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=oauth_config["client_id"],
                client_secret=oauth_config["client_secret"],
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            # Odśwież token jeśli wygasł (lub jest None)
            if not creds.valid:
                creds.refresh(Request())
                
            return build('drive', 'v3', credentials=creds)

        # 2. Fallback: Service Account (dla firmowych Workspace, jeśli działa)
        if "gcp_service_account" in st.secrets:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
            
        return None
    except Exception as e:
        st.error(f"Błąd połączenia z Google Drive: {e}")
        return None

def _load_json_from_drive(filename):
    """Pobiera plik JSON z Google Drive z folderu zdefiniowanego w secrets"""
    service = get_drive_service()
    if not service:
        return None

    folder_id = st.secrets.get("drive", {}).get("folder_id")
    if not folder_id:
        st.error("Brak 'folder_id' w st.secrets[drive]")
        return None

    # Szukamy pliku w folderze
    query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        return None # Plik nie istnieje

    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    fh.seek(0)
    try:
        return json.load(fh)
    except json.JSONDecodeError:
        return None

def _save_json_to_drive(filename, data):
    """Zapisuje (aktualizuje lub tworzy) plik JSON na Google Drive"""
    service = get_drive_service()
    if not service:
        return False

    folder_id = st.secrets.get("drive", {}).get("folder_id")
    
    # Szukamy czy plik już istnieje
    query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    # Przygotowanie treści
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    fh = io.BytesIO(json_str.encode('utf-8'))
    media = MediaIoBaseUpload(fh, mimetype='application/json')

    if items:
        # Aktualizacja istniejącego
        file_id = items[0]['id']
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        # Tworzenie nowego
        file_metadata = {'name': filename, 'parents': [folder_id]}
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    return True

# --- LOADERS / SAVERS (Abstraction Layer) ---

def load_excluded_articles():
    """Загружает список исключённых артикулов"""
    # Próba z Drive
    data = _load_json_from_drive(EXCLUDED_ARTICLES_FILE)
    if data:
        return data.get("exact", []), data.get("prefixes", [])
    
    # Fallback na lokalny plik (jeśli brak neta/konfiguracji)
    if os.path.isfile(EXCLUDED_ARTICLES_FILE):
        try:
            with open(EXCLUDED_ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("exact", []), data.get("prefixes", [])
        except Exception:
            pass
            
    return [], []

def save_excluded_articles(exact_list, prefix_list):
    """Сохраняет исключённые артикулы"""
    data = {
        "_description": "Plik zawiera listę artykułów wykluczonych z porównań (dokładne dopasowanie oraz prefiksy).",
        "exact": exact_list, 
        "prefixes": prefix_list
    }
    
    # Próba zapisu na Drive
    if _save_json_to_drive(EXCLUDED_ARTICLES_FILE, data):
        return True
        
    # Fallback lokalny
    try:
        with open(EXCLUDED_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania excluded_articles.json: {e}")
        return False

def load_packaging_config():
    """Загружает конфигурацию упаковки (картоны)"""
    data = _load_json_from_drive(PACKAGING_CONFIG_FILE)
    if data:
        return data.get("kartony_prefixes", []), data.get("other_packaging_prefixes", [])

    if os.path.isfile(PACKAGING_CONFIG_FILE):
        try:
            with open(PACKAGING_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("kartony_prefixes", []), data.get("other_packaging_prefixes", [])
        except Exception:
            pass
            
    return ["83090", "ZC", "568", "676", "826"], []

def save_packaging_config(kartony_prefixes, other_prefixes):
    """Сохраняет конфигурацию упаковки"""
    data = {
        "_description": "Konfiguracja prefiksów dla kartonów i innych opakowań (używane głównie dla Mandanta 352).",
        "kartony_prefixes": kartony_prefixes, 
        "other_packaging_prefixes": other_prefixes
    }

    if _save_json_to_drive(PACKAGING_CONFIG_FILE, data):
        return True

    try:
        with open(PACKAGING_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Błąd zapisywania packaging_config.json: {e}")
        return False

def load_packages_strategies():
    """
    Загружает конфигурацию стратегий для админ-панели (packages_strategies.json).
    Возвращает словарь с настройками.
    """
    default_strategies = {
        "pallet_priority": {"prefixes": ["202671"]}
    }
    
    data = _load_json_from_drive(PACKAGES_STRATEGIES_FILE)
    if data:
        return data

    if os.path.isfile(PACKAGES_STRATEGIES_FILE):
        try:
            with open(PACKAGES_STRATEGIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_strategies

def save_packages_strategies(pallet_priority_prefixes):
    """Сохраняет стратегии (packages_strategies.json)"""
    current = load_packages_strategies()
    
    # Aktualizacja prefiksów
    if "pallet_priority" not in current:
        current["pallet_priority"] = {"description": "", "prefixes": [], "examples": []}
    
    current["pallet_priority"]["prefixes"] = pallet_priority_prefixes
    current["_description"] = "Konfiguracja strategii dobierania palet w narzędziu usuwania (np. priorytet liczby palet nad ilością sztuk)."

    if _save_json_to_drive(PACKAGES_STRATEGIES_FILE, current):
        return True

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
