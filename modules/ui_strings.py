# modules/ui_strings.py
# Все UI строки в одном месте для локализации

STR = {
    "title": "Warehouse — Raport palet",
    "upload_csv": "Wybierz plik raportu (CSV, separator ';')",
    "no_file": "Proszę załadować plik CSV, aby kontynuować.",
    "filters": "Filtry",
    "mandant": "Mandant",
    "artikel": "Artykuł (ARTIKELNR)",
    "mode": "Tryb kontroli",
    "mode_deleted": "Usunięte palety (OUT_DATE)",
    "mode_received": "Przyjęte palety (IN_DATE)",
    "date_mode": "Tryb daty",
    "single": "Pojedyncza data",
    "range": "Zakres",
    "from": "Od",
    "to": "Do",
    "table_result": "Lista palet — wynik filtra",
    "table_summary": "Suma usuniętych palet według artykułu",
    "orders_tab": "Zamówienia",
    "upload_orders": "Załaduj pliki zamówień (.csv lub .xlsx) — można wiele",
    "orders_help": "Program odczyta kolumny z plików zamówień i zbierze liczbę palet i ilość sztuk.",
    "orders_table": "Podsumowanie zamówień (agregat)",
    "compare": "Porównanie zamówień z usunięciami",
    "hide_zero_diff": "Ukryj pozycje bez rozbieżności",
    "download_csv": "Pobierz CSV (usunięte palety)",
    "download_excel": "Pobierz Excel (raport)",
    "install_openpyxl": "Zainstaluj openpyxl, aby pobierać Excel",
    "manual_orders": "Dodatkowe zamówienia (ręczne wpisy)",
    "notes": "Uwagi",
    "delete_selected": "Usuń zaznaczone",
    "add_manual": "Dodaj ręczne zamówienie",
    "invalid_artikel": "Nieprawidłowy ARTIKELNR. Wybierz z listy dostępnych artykułów.",
    "select_artikel": "Wybierz ARTIKELNR...",
    "delete": "Usuń",
    "debug_filters": "🔍 Debug filtrów",
    "debug_info": "🔍 Debug info",
    "settings": "Ustawienia",
    "settings_cartons": "Kartony (wyjątki)",
    "settings_pallets": "Palety/ramy",
    "settings_other": "Inne opakowania",
    "add_prefix": "Dodaj prefix",
    "remove_prefix": "Usuń prefix",
    "stock_tab": "Stan magazynowy",
    "stock_table_pids": "Stan magazynowy (z PID)",
    "stock_table_agg": "Stan magazynowy (agregat)",
    "stock_warning": "UWAGA: Pamiętaj, że aktualne stany magazynowe są poprawne tylko na moment załadowania pliku z danymi. Jeśli zakres dat wybrany przy generowaniu pliku był zbyt krótki, nie wszystkie palety mogą być widoczne. Dla pełnej i prawidłowej kontroli stanów magazynowych, plik w schaeflein.ihka.de powinien być generowany z datami od 01.01.2016 do dzisiaj.",
    "metric_total_pallets": "Łączna liczba palet",
    "metric_cartons":"Kartony",	#Метрика.
    "metric_other_pkg":"Inne opakowania",	#Метрика.
    "checkbox_cartons_only":"Pokaż tylko kartony",	#Чекбокс фильтрации.
    "stock_date_title":"Analiza stanów magazynowych na datę",	#Заголовок для выбора даты.
    "stock_date_label":"Wybierz datę/zakres (historia)",	#Лейбл виджета выбора даты.
    "stock_date_range_label":"Zakres dat dla analizy historycznej"	#Лейбл для графика (будущее).
}
