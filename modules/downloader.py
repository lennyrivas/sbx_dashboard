# modules/downloader.py
# Automatic data download from ihka.schaeflein.de using Selenium (Firefox).
# Автоматическая загрузка данных с ihka.schaeflein.de с использованием Selenium (Firefox).

import os
import time
import glob
import shutil
import io
import zipfile
from datetime import datetime
import streamlit as st

# Selenium imports
# Импорт библиотек Selenium
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

def run_ihka_downloader(status_container, STR):
    # Runs the automatic download process using Selenium.
    # Запускает процесс автоматической загрузки с использованием Selenium.
    #
    # Args:
    #     status_container: Streamlit container (st.empty or st.status) to display progress messages.
    #     status_container: Контейнер Streamlit (st.empty или st.status) для отображения сообщений о прогрессе.
    #     STR (dict): Dictionary of localized strings for UI messages.
    #     STR (dict): Словарь локализованных строк для сообщений интерфейса.
    #
    # Returns:
    #     str: Path to the downloaded file if successful, or None if an error occurs.
    #     str: Путь к загруженному файлу в случае успеха или None в случае ошибки.
    
    # --- Path Setup ---
    # --- Настройка путей ---
    
    # Get the current working directory.
    # Получаем текущую рабочую директорию.
    base_dir = os.getcwd()
    
    # Define the temporary download directory path.
    # Определяем путь к временной папке загрузок.
    download_dir = os.path.join(base_dir, "temp_downloads")
    
    # --- Cleanup/Create Download Directory ---
    # --- Очистка/Создание папки загрузок ---
    
    # If the directory exists, remove it to ensure a clean state.
    # Если папка существует, удаляем ее, чтобы обеспечить чистое состояние.
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    
    # Create the directory again.
    # Создаем папку заново.
    os.makedirs(download_dir)

    driver = None
    current_step = "Start"
    
    try:
        # --- 1. Initialization ---
        # --- 1. Инициализация ---
        
        # Update status message.
        # Обновляем сообщение о статусе.
        status_container.write(f"⏳ {STR['dl_step_init']}")
        
        # Configure Firefox options.
        # Настраиваем опции Firefox.
        options = Options()
        # options.add_argument("--headless")  # Uncomment to run without GUI (invisible browser).
        # options.add_argument("--headless")  # Раскомментируйте, чтобы запустить без GUI (невидимый браузер).
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        
        # Configure download preferences:
        # 2 = Use a custom download directory.
        # Don't show download manager.
        # Set the download directory to our temp folder.
        # Настраиваем предпочтения загрузки:
        # 2 = Использовать пользовательскую папку загрузки.
        # Не показывать менеджер загрузок.
        # Устанавливаем папку загрузки в нашу временную папку.
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", download_dir)
        
        # Disable Safe Browsing checks to prevent blocking of the file.
        # Отключаем проверки Safe Browsing, чтобы предотвратить блокировку файла.
        options.set_preference("browser.safebrowsing.enabled", False)
        options.set_preference("browser.safebrowsing.malware.enabled", False)
        
        # Define MIME types to automatically save without asking for confirmation.
        # Определяем MIME-типы для автоматического сохранения без запроса подтверждения.
        mime_types = [
            "text/csv", "application/csv", "text/plain", 
            "application/vnd.ms-excel", "application/octet-stream"
        ]
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", ",".join(mime_types))

        # --- Driver Setup ---
        # --- Настройка драйвера ---
        
        # Check if 'geckodriver.exe' exists locally (offline mode support).
        # Проверяем, существует ли 'geckodriver.exe' локально (поддержка офлайн-режима).
        gecko_path = os.path.join(os.getcwd(), "geckodriver.exe")
        if os.path.exists(gecko_path):
            service = FirefoxService(executable_path=gecko_path)
        else:
            # Fallback: Download and install geckodriver using webdriver_manager (requires internet).
            # Резервный вариант: Скачиваем и устанавливаем geckodriver с помощью webdriver_manager (требуется интернет).
            service = FirefoxService(GeckoDriverManager().install())
            
        # Initialize the Firefox driver.
        # Инициализируем драйвер Firefox.
        driver = webdriver.Firefox(service=service, options=options)
        
        # Set window size to ensure all elements are visible/clickable.
        # Устанавливаем размер окна, чтобы все элементы были видимы/кликабельны.
        driver.set_window_size(1920, 1080)
        
        # Initialize WebDriverWait with a 20-second timeout.
        # Инициализируем WebDriverWait с таймаутом 20 секунд.
        wait = WebDriverWait(driver, 20) 

        # --- 2. Login ---
        # --- 2. Логин ---
        
        current_step = STR['dl_step_login']
        status_container.write(f"🔐 {current_step}")
        
        # Navigate to the login page.
        # Переходим на страницу входа.
        driver.get("http://ihka.schaeflein.de/WebAccess/Auth/Login")
        
        # Wait for the username and password fields to be present.
        # Ждем появления полей имени пользователя и пароля.
        user_input = wait.until(EC.presence_of_element_located((By.NAME, "user")))
        pass_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        
        # Enter credentials.
        # Вводим учетные данные.
        user_input.clear()
        user_input.send_keys("Opakowania")
        pass_input.clear()
        pass_input.send_keys("Start123!")
        
        # Submit the form by pressing Enter.
        # Отправляем форму нажатием Enter.
        pass_input.send_keys(Keys.RETURN) 

        # --- 3. Navigation (Ihka -> LZB -> PIDs) ---
        # --- 3. Навигация (Ihka -> LZB -> PIDs) ---
        
        current_step = STR['dl_step_nav']
        status_container.write(f"🧭 {current_step}")
        
        # === FIX: IFRAME Handling ===
        # The application might be inside an iframe. We need to switch context.
        # Приложение может находиться внутри iframe. Нам нужно переключить контекст.
        try:
            iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
            driver.switch_to.frame(iframe)
        except Exception:
            # If the iframe is not found, assume we are in the main window context.
            # Если iframe не найден, предполагаем, что мы находимся в контексте главного окна.
            pass

        try:
            # Wait for the 'Ihka' tile/section to appear.
            # Ждем появления плитки/секции 'Ihka'.
            ihka_section = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-areakey='Ihka']")))
            
            # Use JavaScript to click the element. This is often more reliable than standard click() for overlay elements.
            # Используем JavaScript для клика по элементу. Это часто надежнее стандартного click() для элементов с наложением.
            driver.execute_script("arguments[0].click();", ihka_section)
            
            # Wait briefly for the page to react/reload.
            # Ждем немного, пока страница отреагирует/перезагрузится.
            time.sleep(3) 
        except Exception as e:
            raise Exception(f"Failed to click Ihka tile. URL: {driver.current_url}. Error: {e}")

        # --- Navigate to LZB Menu ---
        # --- Переход в меню LZB ---
        
        current_step = "Nawigacja: Wybór LZB"
        
        # === FIX: RE-ENTER IFRAME ===
        # The page might have reloaded after clicking the tile. We need to re-establish the iframe context.
        # Страница могла перезагрузиться после клика по плитке. Нужно заново установить контекст iframe.
        driver.switch_to.default_content()
        try:
            # Try to find the 'Ihka' iframe first.
            # Сначала пытаемся найти iframe 'Ihka'.
            iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='Ihka']")))
            driver.switch_to.frame(iframe)
        except Exception:
            # Fallback to 'WebAccess' iframe if 'Ihka' is not found.
            # Резервный вариант: iframe 'WebAccess', если 'Ihka' не найден.
            try:
                iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
                driver.switch_to.frame(iframe)
            except Exception:
                pass

        # Find and click the 'LZB' menu item using XPath text matching.
        # Находим и кликаем пункт меню 'LZB', используя поиск по тексту XPath.
        lzb_xpath = "//span[contains(@class, 'l-title') and contains(text(), 'LZB')]"
        lzb_element = wait.until(EC.element_to_be_clickable((By.XPATH, lzb_xpath)))
        lzb_element.click()
        
        # --- Select Report ---
        # --- Выбор отчета ---
        
        current_step = "Nawigacja: Wybór raportu PIDs"
        # Find and click the 'PIDs with IN and OUT date' report.
        # Находим и кликаем отчет 'PIDs with IN and OUT date'.
        pids_xpath = "//span[contains(@class, 'l-title') and contains(text(), 'PIDs with IN and OUT date')]"
        pids_element = wait.until(EC.element_to_be_clickable((By.XPATH, pids_xpath)))
        pids_element.click()

        # --- 4. Parameters ---
        # --- 4. Параметры ---
        
        current_step = STR['dl_step_params']
        status_container.write(f"⚙️ {current_step}")

        # Ensure we are still in the correct iframe context (in case of reload).
        # Убеждаемся, что мы все еще в правильном контексте iframe (на случай перезагрузки).
        driver.switch_to.default_content()
        try:
            iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='Ihka']")))
            driver.switch_to.frame(iframe)
        except Exception:
            try:
                iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
                driver.switch_to.frame(iframe)
            except Exception:
                pass
        
        # Wait for the parameter header to appear.
        # Ждем появления заголовка параметров.
        param_header = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "header[data-ts='slideupdownclick']")))
        
        # Check if the parameter section is collapsed (has class 'l-inactive').
        # Проверяем, свернута ли секция параметров (имеет класс 'l-inactive').
        param_article = param_header.find_element(By.XPATH, "./..")
        if "l-inactive" in param_article.get_attribute("class"):
            # Click to expand if collapsed.
            # Кликаем, чтобы развернуть, если свернуто.
            param_header.click()
            time.sleep(1)

        # --- Fill Input Fields ---
        # --- Заполнение полей ввода ---
        
        # DATEFROM: Set start date.
        # DATEFROM: Устанавливаем начальную дату.
        input_date_from = driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEFROM']")
        input_date_from.clear()
        input_date_from.send_keys("20.12.2016")

        # DATEUNTIL: Set end date to today.
        # DATEUNTIL: Устанавливаем конечную дату на сегодня.
        input_date_until = driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEUNTIL']")
        input_date_until.clear()
        today_str = datetime.now().strftime("%d.%m.%Y")
        input_date_until.send_keys(today_str)

        # MANDANT: Set client ID.
        # MANDANT: Устанавливаем ID клиента.
        input_mandant = driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='MANDANT']")
        input_mandant.clear()
        input_mandant.send_keys("352")

        # --- 5. Table Generation ---
        # --- 5. Генерация таблицы ---
        
        current_step = STR['dl_step_exec']
        status_container.write(f"🚀 {current_step}")
        
        # Click the "Execute Query" button.
        # Кликаем кнопку "Выполнить запрос".
        exec_btn = driver.find_element(By.CSS_SELECTOR, "section[data-ts='resulttypetable']")
        exec_btn.click()

        # Wait for the table headers to appear, indicating the report is generated.
        # Ждем появления заголовков таблицы, что указывает на то, что отчет сгенерирован.
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ts='columns']")))

        # --- 6. Downloading ---
        # --- 6. Скачивание ---
        
        current_step = STR['dl_step_download']
        status_container.write(f"⬇️ {current_step}")
        
        # Click the download CSV link.
        # Кликаем ссылку для скачивания CSV.
        download_link = driver.find_element(By.CSS_SELECTOR, "a[data-ts='downloadcsv']")
        download_link.click()

        # --- Wait for Download Completion ---
        # --- Ожидание завершения загрузки ---
        
        # Max wait time: 1200 seconds (20 minutes) for slow connections/large files.
        # Максимальное время ожидания: 1200 секунд (20 минут) для медленных соединений/больших файлов.
        downloaded_file = None
        stable_count = 0
        last_size = -1
        last_part_size = 0 
        
        # Placeholder for real-time progress updates in UI.
        # Плейсхолдер для обновления прогресса в реальном времени в UI.
        progress_placeholder = status_container.empty()
        
        for _ in range(1200):
            # 1. Check for .part files (Firefox temporary download files).
            # 1. Проверяем наличие файлов .part (временные файлы загрузки Firefox).
            part_files = glob.glob(os.path.join(download_dir, "*.part"))
            if part_files:
                try:
                    # Get the most recent .part file.
                    # Получаем самый свежий файл .part.
                    current_part = max(part_files, key=os.path.getmtime)
                    current_size = os.path.getsize(current_part)
                    size_mb = current_size / (1024 * 1024)
                    
                    # Calculate download speed.
                    # Вычисляем скорость загрузки.
                    speed_bytes = current_size - last_part_size
                    if speed_bytes < 0: speed_bytes = 0
                    
                    speed_str = f"{speed_bytes / (1024 * 1024):.1f} MB/s" if speed_bytes > 1024*1024 else f"{speed_bytes / 1024:.0f} KB/s"
                    
                    last_part_size = current_size
                    
                    # Update UI with progress.
                    # Обновляем UI с прогрессом.
                    progress_placeholder.markdown(f"⏳ **Pobieranie:** {size_mb:.2f} MB ({speed_str})")
                except Exception:
                    pass

                time.sleep(1)
                stable_count = 0 # Reset stability counter if .part file exists.
                continue
            
            last_part_size = 0
            # 2. Check for completed CSV files.
            # 2. Проверяем наличие завершенных CSV файлов.
            csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
            if csv_files:
                current_file = max(csv_files, key=os.path.getmtime)
                try:
                    current_size = os.path.getsize(current_file)
                    size_mb = current_size / (1024 * 1024)
                    
                    if current_size > 0:
                        # Check if file size is stable (not growing anymore).
                        # Проверяем, стабилен ли размер файла (больше не растет).
                        if current_size == last_size:
                            stable_count += 1
                            progress_placeholder.markdown(f"✅ **Pobrano:** {size_mb:.2f} MB (Weryfikacja...)")
                        else:
                            stable_count = 0
                            last_size = current_size
                            progress_placeholder.markdown(f"⏳ **Pobieranie:** {size_mb:.2f} MB")
                        
                        # If size is stable for 2 seconds and no .part files exist, download is done.
                        # Если размер стабилен в течение 2 секунд и нет файлов .part, загрузка завершена.
                        if stable_count >= 2:
                            downloaded_file = current_file
                            progress_placeholder.empty() # Clear progress bar.
                            break
                except Exception:
                    pass
            
            time.sleep(1)
            
        if not downloaded_file:
            raise Exception("Timeout: File was not downloaded.")

        status_container.write(f"✅ {STR['dl_success']}")
        return downloaded_file

    except WebDriverException as e:
        # Handle specific network/driver errors.
        # Обрабатываем специфические ошибки сети/драйвера.
        status_container.error(f"{STR['dl_network_error']}")
        return None
    except Exception as e:
        # Handle general errors.
        # Обрабатываем общие ошибки.
        status_container.error(f"{STR['dl_error']} [Etap: {current_step}] -> {str(e)}")
        return None
        
    finally:
        # Ensure the driver is closed to free resources.
        # Убеждаемся, что драйвер закрыт для освобождения ресурсов.
        if driver:
            driver.quit()

def cleanup_temp_downloads():
    # Removes the temporary download directory and its contents.
    # Удаляет временную папку загрузок и ее содержимое.
    base_dir = os.getcwd()
    download_dir = os.path.join(base_dir, "temp_downloads")
    if os.path.exists(download_dir):
        try:
            shutil.rmtree(download_dir)
        except Exception:
            pass

def create_standalone_package():
    # Creates a ZIP file containing a standalone Python script and batch files for offline downloading.
    # This allows users to run the downloader on a machine with internet access if the server is restricted.
    # Создает ZIP-файл, содержащий автономный скрипт Python и пакетные файлы для офлайн-загрузки.
    # Это позволяет пользователям запускать загрузчик на машине с доступом в Интернет, если сервер ограничен.
    
    # 1. Python script content (Logic similar to run_ihka_downloader but without Streamlit dependencies).
    # 1. Содержимое скрипта Python (Логика похожа на run_ihka_downloader, но без зависимостей Streamlit).
    py_code = r'''# -*- coding: utf-8 -*-
import os
import time
import glob
import shutil
import sys
from datetime import datetime

# 0. Include local libraries (if libs folder exists)
# 0. Подключение локальных библиотек (если существует папка libs)
local_libs = os.path.join(os.getcwd(), "libs")
if os.path.exists(local_libs):
    sys.path.insert(0, local_libs)

# Check libraries
# Проверка библиотек
try:
    from selenium import webdriver
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.firefox import GeckoDriverManager
except ImportError:
    print("Brak wymaganych bibliotek. Uruchom plik start.bat!")
    input("Naciśnij Enter...")
    sys.exit(1)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run():
    base_dir = os.getcwd()
    download_dir = os.path.join(base_dir, "downloads")
    
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir)

    log("Inicjalizacja przeglądarki Firefox...")
    
    options = Options()
    # options.add_argument("--headless") # Windowed mode so user sees what happens
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", download_dir)
    options.set_preference("browser.safebrowsing.enabled", False)
    options.set_preference("browser.safebrowsing.malware.enabled", False)
    mime_types = [
        "text/csv", "application/csv", "text/plain", 
        "application/vnd.ms-excel", "application/octet-stream"
    ]
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", ",".join(mime_types))

    # Offline geckodriver support
    if os.path.exists("geckodriver.exe"):
        service = FirefoxService(executable_path="geckodriver.exe")
    else:
        service = FirefoxService(GeckoDriverManager().install())
        
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_window_size(1920, 1080)
    wait = WebDriverWait(driver, 20)

    try:
        log("Logowanie do systemu...")
        driver.get("http://ihka.schaeflein.de/WebAccess/Auth/Login")
        
        wait.until(EC.presence_of_element_located((By.NAME, "user"))).send_keys("Opakowania")
        pass_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        pass_input.send_keys("Start123!")
        pass_input.send_keys(Keys.RETURN)

        log("Nawigacja do raportu...")
        
        # IFRAME FIX
        try:
            iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
            driver.switch_to.frame(iframe)
        except:
            pass

        try:
            ihka_section = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-areakey='Ihka']")))
            driver.execute_script("arguments[0].click();", ihka_section)
            time.sleep(3)
        except Exception as e:
            raise Exception(f"Nie udało się kliknąć w kafelek Ihka: {e}")

        # RE-ENTER IFRAME
        driver.switch_to.default_content()
        try:
            iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='Ihka']")))
            driver.switch_to.frame(iframe)
        except:
            try:
                iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
                driver.switch_to.frame(iframe)
            except:
                pass

        log("Wybieranie LZB...")
        lzb_xpath = "//span[contains(@class, 'l-title') and contains(text(), 'LZB')]"
        wait.until(EC.element_to_be_clickable((By.XPATH, lzb_xpath))).click()
        
        log("Wybieranie raportu PIDs...")
        pids_xpath = "//span[contains(@class, 'l-title') and contains(text(), 'PIDs with IN and OUT date')]"
        wait.until(EC.element_to_be_clickable((By.XPATH, pids_xpath))).click()

        log("Ustawianie parametrów...")
        driver.switch_to.default_content()
        try:
            iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='Ihka']")))
            driver.switch_to.frame(iframe)
        except:
            pass
        
        param_header = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "header[data-ts='slideupdownclick']")))
        param_article = param_header.find_element(By.XPATH, "./..")
        if "l-inactive" in param_article.get_attribute("class"):
            param_header.click()
            time.sleep(1)

        driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEFROM']").clear()
        driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEFROM']").send_keys("20.12.2016")
        
        driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEUNTIL']").clear()
        driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEUNTIL']").send_keys(datetime.now().strftime("%d.%m.%Y"))
        
        driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='MANDANT']").clear()
        driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='MANDANT']").send_keys("352")

        log("Generowanie tabeli...")
        driver.find_element(By.CSS_SELECTOR, "section[data-ts='resulttypetable']").click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ts='columns']")))

        log("Pobieranie pliku...")
        driver.find_element(By.CSS_SELECTOR, "a[data-ts='downloadcsv']").click()

        # Waiting for file
        downloaded_file = None
        last_size = -1
        stable_count = 0
        
        for _ in range(1200):
            part_files = glob.glob(os.path.join(download_dir, "*.part"))
            if part_files:
                time.sleep(1)
                stable_count = 0
                continue
            
            csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
            if csv_files:
                current_file = max(csv_files, key=os.path.getmtime)
                current_size = os.path.getsize(current_file)
                if current_size > 0:
                    if current_size == last_size:
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_size = current_size
                    
                    if stable_count >= 2:
                        downloaded_file = current_file
                        break
            time.sleep(1)
            
        if downloaded_file:
            log(f"SUKCES! Plik pobrany: {os.path.basename(downloaded_file)}")
            log(f"Pełna ścieżka: {downloaded_file}")
            # Open folder with file (Windows only)
            try:
                os.startfile(download_dir)
            except:
                pass
        else:
            log("Błąd: Timeout pobierania.")

    except Exception as e:
        log(f"Błąd: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    run()
    input("\nNaciśnij Enter, aby zakończyć...")
'''

    # 2. .bat file content (Launcher script)
    # 2. Содержимое файла .bat (Скрипт запуска)
    bat_code = r'''@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo  IHKA Downloader - Narzedzie Offline
echo ==========================================

set CONFIG_FILE=python_config.txt

REM 1. Check if path is saved
if exist %CONFIG_FILE% (
    set /p PY_EXE=<%CONFIG_FILE%
) else (
    goto :SETUP
)

REM 2. Verify if file still exists
if not exist "!PY_EXE!" (
    echo.
    echo [INFO] Zapisana sciezka do Python nie jest juz poprawna.
    goto :SETUP
)

goto :START

:SETUP
echo.
echo Ten skrypt wymaga Pythona (moze byc wersja przenosna).
echo.
echo Prosze podac pelna sciezke do pliku python.exe.
echo Mozesz przeciagnac plik python.exe na to okno i nacisnac Enter.
echo (Np. D:\PortablePython\python.exe)
echo.
set "USER_INPUT="
set /p USER_INPUT="Sciezka do python.exe: "

REM Remove quotes (if any)
set PY_EXE=!USER_INPUT:"=!

if "!PY_EXE!"=="" (
    echo.
    echo [BLAD] Nie podano sciezki.
    goto :SETUP
)

if not exist "!PY_EXE!" (
    echo.
    echo [BLAD] Plik nie istnieje: "!PY_EXE!"
    echo Sprobuj ponownie.
    goto :SETUP
)

REM Save to file
echo !PY_EXE!> %CONFIG_FILE%
echo.
echo Sciezka zapisana w %CONFIG_FILE%.

:START
echo.
echo Uzywany Python: "!PY_EXE!"
echo.

REM Check if PIP is available
"!PY_EXE!" -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] PIP nie zostal wykryty. Proba automatycznej instalacji (ensurepip)...
    "!PY_EXE!" -m ensurepip --default-pip >nul 2>&1
    
    if !errorlevel! neq 0 (
        echo.
        echo [BLAD] Nie udalo sie zainstalowac PIP automatycznie.
        echo.
        echo Twoja wersja przenosna Python nie ma modulu 'pip' ani 'ensurepip'.
        echo.
        echo ROZWIAZANIE:
        echo 1. Pobierz skrypt: https://bootstrap.pypa.io/get-pip.py
        echo 2. Umiesc go w folderze z python.exe
        echo 3. Uruchom: "!PY_EXE!" get-pip.py
        echo 4. WAZNE: W folderze Pythona edytuj plik 'python*._pth' i odkomentuj 'import site'.
        pause
        exit /b
    ) else (
        echo [SUKCES] PIP zostal zainstalowany.
    )
)

REM Check if libraries are already in 'libs' folder (offline/portable mode)
if exist "libs" (
    echo [INFO] Wykryto folder 'libs'. Pomijanie instalacji PIP.
) else (
    echo [1/2] Instalacja bibliotek (selenium)...
    "!PY_EXE!" -m pip install selenium webdriver-manager --no-warn-script-location >nul

    if !errorlevel! neq 0 (
        echo.
        echo [BLAD] Nie udalo sie zainstalowac bibliotek.
        echo Sprawdz czy Twoja wersja Python obsluguje PIP i ma dostep do internetu.
        echo.
        echo ALTERNATYWA: Mozesz utworzyc folder 'libs' i wgrac tam biblioteki recznie.
        pause
        exit /b
    )
)

echo [2/2] Uruchamianie skryptu...
"!PY_EXE!" download_ihka.py

echo.
echo Gotowe.
pause
'''

    # 3. prepare_libs.bat content (Helper to download libs for offline tool)
    # 3. Содержимое prepare_libs.bat (Помощник для загрузки библиотек для офлайн-инструмента)
    prep_code = r'''@echo off
echo Pobieranie bibliotek dla narzedzia offline...
if not exist libs mkdir libs
pip install selenium webdriver-manager --target=libs
echo Gotowe.
pause
'''

    # Create ZIP in memory
    # Создаем ZIP в памяти
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("download_ihka.py", py_code)
        zf.writestr("start.bat", bat_code)
        zf.writestr("prepare_libs.bat", prep_code)
    
    zip_buffer.seek(0)
    return zip_buffer