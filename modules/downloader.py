# modules/downloader.py
# Automatic data download from ihka.schaeflein.de using Selenium (Firefox).

import os
import time
import glob
import shutil
import io
import zipfile
from datetime import datetime
import streamlit as st

# Selenium imports
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
    """
    Runs the automatic download process.
    
    Args:
        status_container: st.empty() or st.status() to display progress.
        STR (dict): Dictionary of localized strings.
        
    Returns:
        str: Path to the downloaded file or None if error.
    """
    
    # Path setup
    base_dir = os.getcwd()
    download_dir = os.path.join(base_dir, "temp_downloads")
    
    # Clean/create download directory
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir)

    driver = None
    current_step = "Start"
    
    try:
        # --- 1. Initialization ---
        status_container.write(f"⏳ {STR['dl_step_init']}")
        
        options = Options()
        # options.add_argument("--headless")  # Run without GUI
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        
        # Firefox profile settings for automatic download
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", download_dir)
        
        # Disable Safe Browsing (might block download)
        options.set_preference("browser.safebrowsing.enabled", False)
        options.set_preference("browser.safebrowsing.malware.enabled", False)
        
        # Extended list of MIME types to avoid save confirmation dialog
        mime_types = [
            "text/csv", "application/csv", "text/plain", 
            "application/vnd.ms-excel", "application/octet-stream"
        ]
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", ",".join(mime_types))

        # Offline geckodriver support (if file exists in project folder)
        gecko_path = os.path.join(os.getcwd(), "geckodriver.exe")
        if os.path.exists(gecko_path):
            service = FirefoxService(executable_path=gecko_path)
        else:
            # Fallback: try to download (requires internet)
            service = FirefoxService(GeckoDriverManager().install())
            
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_window_size(1920, 1080)
        
        wait = WebDriverWait(driver, 20) # 20 seconds timeout

        # --- 2. Login ---
        current_step = STR['dl_step_login']
        status_container.write(f"🔐 {current_step}")
        driver.get("http://ihka.schaeflein.de/WebAccess/Auth/Login")
        
        # Wait for fields to load
        user_input = wait.until(EC.presence_of_element_located((By.NAME, "user")))
        pass_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        
        user_input.clear()
        user_input.send_keys("Opakowania")
        pass_input.clear()
        pass_input.send_keys("Start123!")
        pass_input.send_keys(Keys.RETURN) # Use Enter instead of click

        # --- 3. Navigation (Ihka -> LZB -> PIDs) ---
        current_step = STR['dl_step_nav']
        status_container.write(f"🧭 {current_step}")
        
        # Wait and click on Ihka block
        # Use CSS selector by data-areakey attribute
        
        # === FIX: IFRAME ===
        # Main page contains iframe with the app. Need to switch to it.
        try:
            iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
            driver.switch_to.frame(iframe)
        except Exception:
            # If no frame, try in main window (fallback)
            pass

        try:
            # Wait for Ihka tile to appear
            ihka_section = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-areakey='Ihka']")))
            
            # Use JS Click as the most reliable method for tiles with overlay
            driver.execute_script("arguments[0].click();", ihka_section)
            time.sleep(3) # Wait for page reaction
        except Exception as e:
            raise Exception(f"Nie udało się kliknąć w kafelek Ihka. URL: {driver.current_url}. Błąd: {e}")

        # Wait for menu load and click LZB
        # Search for span with text LZB. Use contains for reliability.
        current_step = "Nawigacja: Wybór LZB"
        
        # === FIX: RE-ENTER IFRAME ===
        # After clicking Ihka tile, page might have reloaded. Refresh frame context.
        driver.switch_to.default_content()
        try:
            # FIX: After entering Ihka, active frame is 'Ihka', 'WebAccess' is hidden.
            # Search for visible Ihka frame.
            iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='Ihka']")))
            driver.switch_to.frame(iframe)
        except Exception:
            # Fallback: If Ihka not visible, check WebAccess (e.g., transition error)
            try:
                iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
                driver.switch_to.frame(iframe)
            except Exception:
                pass

        lzb_xpath = "//span[contains(@class, 'l-title') and contains(text(), 'LZB')]"
        lzb_element = wait.until(EC.element_to_be_clickable((By.XPATH, lzb_xpath)))
        lzb_element.click()
        
        # Click PIDs with IN and OUT date
        current_step = "Nawigacja: Wybór raportu PIDs"
        pids_xpath = "//span[contains(@class, 'l-title') and contains(text(), 'PIDs with IN and OUT date')]"
        pids_element = wait.until(EC.element_to_be_clickable((By.XPATH, pids_xpath)))
        pids_element.click()

        # --- 4. Parameters ---
        current_step = STR['dl_step_params']
        status_container.write(f"⚙️ {current_step}")

        # Ensure we are still in the frame (in case of reload after clicking report)
        driver.switch_to.default_content()
        try:
            # Target Ihka frame again
            iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='Ihka']")))
            driver.switch_to.frame(iframe)
        except Exception:
            try:
                iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[data-area='WebAccess']")))
                driver.switch_to.frame(iframe)
            except Exception:
                pass
        
        # Wait for Parameter header
        param_header = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "header[data-ts='slideupdownclick']")))
        
        # Check if menu is collapsed (class l-inactive on parent article)
        # Find parent article
        param_article = param_header.find_element(By.XPATH, "./..")
        if "l-inactive" in param_article.get_attribute("class"):
            # If collapsed - click to expand
            param_header.click()
            time.sleep(1)

        # Fill fields
        # DATEFROM
        input_date_from = driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEFROM']")
        input_date_from.clear()
        input_date_from.send_keys("20.12.2016")

        # DATEUNTIL
        input_date_until = driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='DATEUNTIL']")
        input_date_until.clear()
        today_str = datetime.now().strftime("%d.%m.%Y")
        input_date_until.send_keys(today_str)

        # MANDANT
        input_mandant = driver.find_element(By.CSS_SELECTOR, "input[data-parameterkey='MANDANT']")
        input_mandant.clear()
        input_mandant.send_keys("352")

        # --- 5. Table Generation ---
        current_step = STR['dl_step_exec']
        status_container.write(f"🚀 {current_step}")
        
        # Button "Abfrage sofort ausführen"
        exec_btn = driver.find_element(By.CSS_SELECTOR, "section[data-ts='resulttypetable']")
        exec_btn.click()

        # Wait for table (headers)
        # <tr data-ts="columns">
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ts='columns']")))

        # --- 6. Downloading ---
        current_step = STR['dl_step_download']
        status_container.write(f"⬇️ {current_step}")
        
        # Download button
        download_link = driver.find_element(By.CSS_SELECTOR, "a[data-ts='downloadcsv']")
        download_link.click()

        # Wait for file in folder
        # Max 1200 seconds (20 minutes) wait (for slow connection)
        downloaded_file = None
        stable_count = 0
        last_size = -1
        last_part_size = 0 # For speed calculation
        
        # Placeholder for real-time download progress
        progress_placeholder = status_container.empty()
        
        for _ in range(1200):
            # 1. Check for .part files (Firefox downloading)
            part_files = glob.glob(os.path.join(download_dir, "*.part"))
            if part_files:
                # Display .part file size
                try:
                    current_part = max(part_files, key=os.path.getmtime)
                    current_size = os.path.getsize(current_part)
                    size_mb = current_size / (1024 * 1024)
                    
                    # Speed calculation
                    speed_bytes = current_size - last_part_size
                    if speed_bytes < 0: speed_bytes = 0
                    
                    speed_str = f"{speed_bytes / (1024 * 1024):.1f} MB/s" if speed_bytes > 1024*1024 else f"{speed_bytes / 1024:.0f} KB/s"
                    
                    last_part_size = current_size
                    
                    progress_placeholder.markdown(f"⏳ **Pobieranie:** {size_mb:.2f} MB ({speed_str})")
                except Exception:
                    pass

                time.sleep(1)
                stable_count = 0 # Reset stability counter
                continue
            
            last_part_size = 0
            
            # 2. Look for CSV files
            csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
            if csv_files:
                current_file = max(csv_files, key=os.path.getmtime)
                try:
                    current_size = os.path.getsize(current_file)
                    size_mb = current_size / (1024 * 1024)
                    
                    if current_size > 0:
                        # Check if size is stable (file stopped growing)
                        if current_size == last_size:
                            stable_count += 1
                            progress_placeholder.markdown(f"✅ **Pobrano:** {size_mb:.2f} MB (Weryfikacja...)")
                        else:
                            stable_count = 0
                            last_size = current_size
                            progress_placeholder.markdown(f"⏳ **Pobieranie:** {size_mb:.2f} MB")
                        
                        # If size unchanged for 2 seconds and no .part -> done
                        if stable_count >= 2:
                            downloaded_file = current_file
                            progress_placeholder.empty() # Clear progress bar
                            break
                except Exception:
                    pass
            
            time.sleep(1)
            
        if not downloaded_file:
            raise Exception("Timeout: Plik nie został pobrany.")

        status_container.write(f"✅ {STR['dl_success']}")
        return downloaded_file

    except WebDriverException as e:
        # Specific connection error (e.g., no internal network access)
        status_container.error(f"{STR['dl_network_error']}")
        return None
    except Exception as e:
        status_container.error(f"{STR['dl_error']} [Etap: {current_step}] -> {str(e)}")
        return None
        
    finally:
        if driver:
            driver.quit()

def cleanup_temp_downloads():
    """Cleans up temporary download folder."""
    base_dir = os.getcwd()
    download_dir = os.path.join(base_dir, "temp_downloads")
    if os.path.exists(download_dir):
        try:
            shutil.rmtree(download_dir)
        except Exception:
            pass

def create_standalone_package():
    """Creates a ZIP file with the offline download tool (.py script + .bat)."""
    
    # 1. Python script content (copy of run_ihka_downloader logic, but without Streamlit)
    py_code = r'''# -*- coding: utf-8 -*-
import os
import time
import glob
import shutil
import sys
from datetime import datetime

# 0. Include local libraries (if libs folder exists)
local_libs = os.path.join(os.getcwd(), "libs")
if os.path.exists(local_libs):
    sys.path.insert(0, local_libs)

# Check libraries
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

    # 2. .bat file content
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

    # 3. prepare_libs.bat content (for offline tool)
    prep_code = r'''@echo off
echo Pobieranie bibliotek dla narzedzia offline...
if not exist libs mkdir libs
pip install selenium webdriver-manager --target=libs
echo Gotowe.
pause
'''

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("download_ihka.py", py_code)
        zf.writestr("start.bat", bat_code)
        zf.writestr("prepare_libs.bat", prep_code)
    
    zip_buffer.seek(0)
    return zip_buffer