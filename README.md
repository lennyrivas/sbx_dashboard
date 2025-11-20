# sbx_dashboard

## Opis
Zaawansowany system do analizy i raportowania ruchów palet na magazynie. Automatyzuje proces sprawdzania przyjęć, usunięć i porównania z zamówieniami.

## Funkcjonalności

### 🔍 Analiza Danych
- Wczytywanie raportów CSV z systemu WMS
- Filtrowanie według mandanta, artykułu, zakresu dat
- Rozróżnienie przyjęć i usunięć palet
- Automatyczna walidacja danych

### 📊 Raportowanie
- Tabela szczegółowych ruchów palet
- Podsumowanie usunięć według artykułu
- Porównanie zamówień z faktycznymi usunięciami
- Wykrywanie rozbieżności

### 📦 Zarządzanie Zamówieniami
- Import plików zamówień (CSV/XLSX)
- Ręczne dodawanie zamówień
- Agregacja zamówień z wielu źródeł
- System podpowiedzi i walidacji

### 📈 Statystyki
- Metryki podstawowe (liczba palet, sztuk, artykułów)
- Trendy dzienne i tygodniowe
- Top 10 najczęściej używanych artykułów
- Eksport raportów do Excel

### ⚙️ Automatyzacja
- Interfejs przystosowany dla użytkowników nietechnicznych
- Automatyczne wykrywanie formatów plików
- Konfigurowalne filtry i ustawienia

## Technologie
- **Python** - logika biznesowa
- **Streamlit** - interfejs użytkownika
- **Pandas** - przetwarzanie danych
- **OpenPyXL** - obsługa Excel
- **Streamlit AgGrid** - zaawansowane tabele

## Instalacja
```bash
pip install streamlit pandas numpy openpyxl streamlit-aggrid
streamlit run warehouse_dashboard.py
