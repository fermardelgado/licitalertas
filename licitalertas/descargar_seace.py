import os
import time
import base64
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIGURACION ────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN_LICITALERTAS", "")
GITHUB_REPO  = "fermardelgado/licitalertas"
GITHUB_PATH  = "seace_data.xlsx"
CARPETA_DESCARGA = os.path.join(os.path.expanduser("~"), "Downloads", "seace")

os.makedirs(CARPETA_DESCARGA, exist_ok=True)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def iniciar_chrome():
    opciones = Options()
    opciones.add_experimental_option("prefs", {
        "download.default_directory": CARPETA_DESCARGA,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opciones
    )
    driver.maximize_window()
    return driver

def descargar_excel():
    log("Iniciando Chrome...")
    driver = iniciar_chrome()
    wait = WebDriverWait(driver, 40)

    try:
        log("Abriendo SEACE...")
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(10)

        log("Seleccionando pestaña Buscador de Procedimientos...")
        pestanas = driver.find_elements(By.XPATH, "//a | //span | //li")
        for p in pestanas:
            try:
                texto = p.text.strip()
                if "Buscador de Procedimientos de Selecci" in texto:
                    driver.execute_script("arguments[0].click();", p)
                    log("Pestaña clickeada")
                    break
            except:
                continue
        time.sleep(6)

        log("Verificando año 2026...")
        try:
            anio_selects = driver.find_elements(By.XPATH, "//select")
            for s in anio_selects:
                try:
                    sid = s.get_attribute("id") or ""
                    if "Anio" in sid or "anio" in sid:
                        Select(s).select_by_visible_text("2026")
                        log("Año 2026 seleccionado")
                        break
                except:
                    continue
        except Exception as e:
            log(f"Error año: {e}")
        time.sleep(3)

        log("Haciendo clic en Buscar...")
        try:
            botones = driver.find_elements(By.XPATH, "//button | //input[@type='submit']")
            for b in botones:
                try:
                    texto = b.text or b.get_attribute("value") or ""
                    if "Buscar" in texto and b.is_displayed():
                        driver.execute_script("arguments[0].click();", b)
                        log("Buscar clickeado")
                        break
                except:
                    continue
        except Exception as e:
            log(f"Error buscar: {e}")

        log("Esperando resultados (20 seg)...")
        time.sleep(20)

        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "No se encontraron" in body_text:
                log("ADVERTENCIA: SEACE dice 'No se encontraron datos'")
                driver.save_screenshot(os.path.join(CARPETA_DESCARGA, "sin_resultados.png"))
            else:
                log("Resultados cargados correctamente")
        except:
            pass

        log("Buscando botón Exportar a Excel...")
        exportar = None
        elementos = driver.find_elements(By.XPATH, "//button | //a | //input | //span")
        for e in elementos:
            try:
                texto = e.text or e.get_attribute("value") or e.get_attribute("title") or ""
                if ("Exportar" in texto or "Descargar" in texto or "Excel" in texto) and e.is_displayed():
                    exportar = e
                    log(f"Botón exportar encontrado: '{texto}'")
                    break
            except:
                continue

        if not exportar:
            log("ERROR: No se encontró botón Exportar")
            driver.save_screenshot(os.path.join(CARPETA_DESCARGA, "error.png"))
            return None

        for f in os.listdir(CARPETA_DESCARGA):
            if f.endswith(".xls") or f.endswith(".xlsx"):
                os.remove(os.path.join(CARPETA_DESCARGA, f))

        driver.execute_script("arguments[0].click();", exportar)
        log("Clic en Exportar realizado")

        log("Esperando descarga...")
        tiempo_espera = 0
        archivo_excel = None
        while tiempo_espera < 60:
            archivos = [f for f in os.listdir(CARPETA_DESCARGA)
                       if (f.endswith(".xlsx") or f.endswith(".xls")) and not f.startswith("~")]
            if archivos:
                archivos.sort(key=lambda x: os.path.getmtime(os.path.join(CARPETA_DESCARGA, x)), reverse=True)
                archivo_excel = os.path.join(CARPETA_DESCARGA, archivos[0])
                log(f"Archivo descargado: {archivos[0]}")
                break
            time.sleep(2)
            tiempo_espera += 2

        if not archivo_excel:
            log("ERROR: No se descargó el archivo.")
            driver.save_screenshot(os.path.join(CARPETA_DESCARGA, "error_descarga.png"))
            return None

        return archivo_excel

    except Exception as e:
        log(f"ERROR general: {e}")
        return None
    finally:
        time.sleep(2)
        driver.quit()

def subir_a_github(ruta_archivo):
    if not GITHUB_TOKEN:
        log("ERROR: GITHUB_TOKEN_LICITALERTAS no está configurado como variable de entorno.")
        return False

    log("Subiendo Excel a GitHub...")
    with open(ruta_archivo, "rb") as f:
        contenido = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    resp = requests.get(url, headers=headers)
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    payload = {
        "message": f"Actualización SEACE {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": contenido,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in [200, 201]:
        log("✅ Excel subido a GitHub correctamente.")
        return True
    else:
        log(f"ERROR subiendo a GitHub: {resp.status_code} {resp.text[:200]}")
        return False

def main():
    log("=== LicitAlertas — Descargador SEACE ===")
    archivo = descargar_excel()
    if archivo:
        subir_a_github(archivo)
        log("=== Proceso completado ===")
    else:
        log("=== Proceso fallido — revisa screenshots en Downloads/seace/ ===")

if __name__ == "__main__":
    main()