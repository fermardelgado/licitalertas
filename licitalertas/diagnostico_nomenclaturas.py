# -*- coding: utf-8 -*-
"""
diagnostico_nomenclaturas.py - SOLO LECTURA
Compara las nomenclaturas que Selenium ve en la pagina 1 del buscador SEACE
contra ejemplos de la tabla convocatorias de Supabase.
No escribe nada en ningun lado. No abre fichas.
"""

import os
import requests
import time
from datetime import datetime, date
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

ANIO = "2026"
URL_BUSCADOR = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
SUPABASE_URL = "https://hjbmcdxbiajmbczgyhxk.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY_LICITALERTAS", "")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def mostrar_crudo(texto):
    """Muestra el texto con marcadores para ver espacios y saltos ocultos."""
    return repr(texto)

def main():
    log("=== DIAGNOSTICO DE NOMENCLATURAS (solo lectura) ===")

    # 1) Ejemplos de Supabase
    if not SUPABASE_KEY:
        log("ERROR: no veo SUPABASE_KEY_LICITALERTAS. Abortando.")
        return
    hoy = date.today().isoformat()
    url = (f"{SUPABASE_URL}/rest/v1/convocatorias"
           f"?select=nomenclatura&fecha_vencimiento=gte.{hoy}&limit=5")
    r = requests.get(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }, timeout=30)
    if r.status_code != 200:
        log(f"ERROR Supabase: {r.status_code} - {r.text[:200]}")
        return
    ejemplos_bd = [x.get("nomenclatura", "") for x in r.json()]
    log("--- 5 EJEMPLOS DE SUPABASE (formato crudo) ---")
    for e in ejemplos_bd:
        print("  BD:", mostrar_crudo(e))

    # 2) Lo que ve Selenium en la pagina 1
    opciones = Options()
    opciones.add_argument("--window-size=1920,1080")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)
    opciones.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opciones)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    driver.maximize_window()

    try:
        log("Abriendo buscador publico SEACE...")
        driver.get(URL_BUSCADOR)
        time.sleep(10)

        for p in driver.find_elements(By.XPATH, "//a | //span | //li"):
            try:
                if "Buscador de Procedimientos de Selecci" in p.text.strip():
                    driver.execute_script("arguments[0].click();", p)
                    break
            except:
                continue
        time.sleep(6)

        for s in driver.find_elements(By.XPATH, "//select"):
            try:
                sid = s.get_attribute("id") or ""
                if "Anio" in sid or "anio" in sid:
                    Select(s).select_by_visible_text(ANIO)
                    break
            except:
                continue
        time.sleep(3)

        for b in driver.find_elements(By.XPATH, "//button | //input[@type='submit']"):
            try:
                texto = b.text or b.get_attribute("value") or ""
                if "Buscar" in texto and b.is_displayed():
                    driver.execute_script("arguments[0].click();", b)
                    break
            except:
                continue

        log("Esperando resultados (20 seg)...")
        time.sleep(20)

        filas = driver.find_elements(By.CSS_SELECTOR, "tbody[id$='_data'] > tr[data-ri]")
        log(f"Filas encontradas en pagina 1: {len(filas)}")
        log("--- CELDAS DE LAS PRIMERAS 5 FILAS (todas las columnas, crudo) ---")
        for idx, f in enumerate(filas[:5]):
            try:
                celdas = f.find_elements(By.TAG_NAME, "td")
                print(f"  FILA {idx + 1} ({len(celdas)} celdas):")
                for c_idx, c in enumerate(celdas):
                    txt = c.text.strip()
                    if txt:
                        print(f"    celda[{c_idx}]: {mostrar_crudo(txt)}")
            except Exception as e:
                print(f"  FILA {idx + 1}: error {e}")

        log("=== FIN DIAGNOSTICO ===")

    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()