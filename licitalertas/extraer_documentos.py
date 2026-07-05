# -*- coding: utf-8 -*-
"""
extraer_documentos.py — PLAN C + SUPABASE
Igual que la version que ya funciono, mas el envio (upsert) de los
documentos extraidos a la tabla 'documentos' de Supabase.
La key se lee de la variable de entorno SUPABASE_KEY_LICITALERTAS.
"""

import os
import re
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIGURACION ───────────────────────────────────────────────────────────
MAX_CONVOCATORIAS = 3   # subir a 5 cuando la prueba pase
ANIO = "2026"
URL_BUSCADOR = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"

SUPABASE_URL = "https://hjbmcdxbiajmbczgyhxk.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY_LICITALERTAS", "")

REGEX_DOC = re.compile(r"descargaDocGeneral\('([0-9a-fA-F-]{36})'\s*,\s*'[^']*'\s*,\s*'([^']+)'\)")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def iniciar_chrome():
    opciones = Options()
    opciones.add_argument("--window-size=1920,1080")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)
    opciones.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opciones
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    driver.maximize_window()
    return driver

def abrir_buscador_y_buscar(driver):
    log("Abriendo buscador publico SEACE...")
    driver.get(URL_BUSCADOR)
    time.sleep(10)

    log("Seleccionando pestana Buscador de Procedimientos...")
    pestanas = driver.find_elements(By.XPATH, "//a | //span | //li")
    for p in pestanas:
        try:
            texto = p.text.strip()
            if "Buscador de Procedimientos de Selecci" in texto:
                driver.execute_script("arguments[0].click();", p)
                log("Pestana clickeada")
                break
        except:
            continue
    time.sleep(6)

    log(f"Verificando anio {ANIO}...")
    try:
        for s in driver.find_elements(By.XPATH, "//select"):
            try:
                sid = s.get_attribute("id") or ""
                if "Anio" in sid or "anio" in sid:
                    Select(s).select_by_visible_text(ANIO)
                    log(f"Anio {ANIO} seleccionado")
                    break
            except:
                continue
    except Exception as e:
        log(f"Error anio: {e}")
    time.sleep(3)

    log("Haciendo clic en Buscar...")
    for b in driver.find_elements(By.XPATH, "//button | //input[@type='submit']"):
        try:
            texto = b.text or b.get_attribute("value") or ""
            if "Buscar" in texto and b.is_displayed():
                driver.execute_script("arguments[0].click();", b)
                log("Buscar clickeado")
                break
        except:
            continue

    log("Esperando resultados (20 seg)...")
    time.sleep(20)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "No se encontraron" in body_text:
        log("ADVERTENCIA: SEACE dice 'No se encontraron datos'")
        driver.save_screenshot("planc_sin_resultados.png")
        return False
    log("Resultados cargados correctamente")
    return True

def obtener_filas_resultados(driver):
    filas = driver.find_elements(By.CSS_SELECTOR, "tbody[id$='_data'] > tr[data-ri]")
    filas_utiles = []
    for f in filas:
        try:
            celdas = f.find_elements(By.TAG_NAME, "td")
            if len(celdas) >= 8 and f.is_displayed():
                filas_utiles.append(f)
        except:
            continue
    return filas_utiles

def extraer_nomenclatura(fila):
    try:
        celdas = fila.find_elements(By.TAG_NAME, "td")
        return celdas[3].text.strip()
    except:
        return "DESCONOCIDA"

def clic_icono_ficha(driver, fila):
    try:
        celdas = fila.find_elements(By.TAG_NAME, "td")
        acciones = celdas[-1]
        enlaces = acciones.find_elements(By.TAG_NAME, "a")
        if not enlaces:
            enlaces = acciones.find_elements(By.TAG_NAME, "img")
        if not enlaces:
            return False
        driver.execute_script("arguments[0].click();", enlaces[-1])
        return True
    except Exception as e:
        log(f"Error clic ficha: {e}")
        return False

def extraer_documentos_de_ficha(driver):
    docs = []
    for intento in range(1, 4):
        time.sleep(8)
        filas = driver.find_elements(By.CSS_SELECTOR, "tbody[id$='dtDocumentos_data'] > tr")
        html = driver.page_source
        pares = REGEX_DOC.findall(html)
        if pares:
            etapas = []
            for f in filas:
                try:
                    celdas = f.find_elements(By.TAG_NAME, "td")
                    etapas.append(celdas[1].text.strip() if len(celdas) > 1 else "")
                except:
                    etapas.append("")
            for i, (file_code, nombre_doc) in enumerate(pares):
                etapa = etapas[i] if i < len(etapas) else ""
                docs.append({"file_code": file_code, "nombre_doc": nombre_doc, "etapa": etapa})
            return docs
        log(f"  Ficha aun sin documentos (intento {intento}/3)...")
    return docs

def volver_al_buscador(driver):
    driver.back()
    time.sleep(10)
    filas = obtener_filas_resultados(driver)
    if not filas:
        log("La tabla no sobrevivio al back; repitiendo busqueda...")
        abrir_buscador_y_buscar(driver)

def subir_a_supabase(registros):
    """Upsert de documentos a Supabase (on_conflict nomenclatura,file_code)."""
    if not SUPABASE_KEY:
        log("ERROR: variable SUPABASE_KEY_LICITALERTAS no encontrada.")
        log("Cierra y abre un CMD nuevo, o revisa Variables de entorno.")
        return False
    if not registros:
        log("Nada que subir a Supabase.")
        return False

    url = f"{SUPABASE_URL}/rest/v1/documentos?on_conflict=nomenclatura,file_code"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    resp = requests.post(url, headers=headers, json=registros, timeout=30)
    if resp.status_code in (200, 201, 204):
        log(f"SUPABASE OK: {len(registros)} documento(s) enviados (status {resp.status_code}).")
        return True
    log(f"ERROR Supabase: status {resp.status_code} - {resp.text[:300]}")
    return False

def main():
    log("=== LicitAlertas — Extractor de Documentos (PLAN C + SUPABASE) ===")
    if not SUPABASE_KEY:
        log("ADVERTENCIA: no veo SUPABASE_KEY_LICITALERTAS. Extraere igual, pero no subire nada.")
    driver = iniciar_chrome()
    resultados = []
    try:
        if not abrir_buscador_y_buscar(driver):
            return

        procesadas = 0
        while procesadas < MAX_CONVOCATORIAS:
            filas = obtener_filas_resultados(driver)
            if procesadas >= len(filas):
                log("No hay mas filas disponibles en esta pagina.")
                break

            fila = filas[procesadas]
            nomenclatura = extraer_nomenclatura(fila)
            log(f"[{procesadas + 1}/{MAX_CONVOCATORIAS}] Abriendo ficha de: {nomenclatura}")

            if not clic_icono_ficha(driver, fila):
                log("  No se pudo clickear el icono de ficha. Saltando.")
                procesadas += 1
                continue

            docs = extraer_documentos_de_ficha(driver)
            url_ficha = driver.current_url
            log(f"  URL ficha: {url_ficha}")
            log(f"  Documentos encontrados: {len(docs)}")
            for d in docs:
                log(f"    [{d['etapa']}] {d['nombre_doc']} -> {d['file_code']}")

            resultados.append({
                "nomenclatura": nomenclatura,
                "url_ficha": url_ficha,
                "documentos": docs,
            })

            volver_al_buscador(driver)
            procesadas += 1

        log("=== RESUMEN ===")
        registros = []
        total_docs = 0
        for r in resultados:
            log(f"{r['nomenclatura']}: {len(r['documentos'])} documento(s)")
            total_docs += len(r["documentos"])
            for d in r["documentos"]:
                registros.append({
                    "nomenclatura": r["nomenclatura"],
                    "etapa": d["etapa"],
                    "nombre_doc": d["nombre_doc"],
                    "file_code": d["file_code"],
                })
        log(f"TOTAL: {len(resultados)} convocatorias, {total_docs} documentos")

        if total_docs > 0:
            log("Subiendo a Supabase...")
            if subir_a_supabase(registros):
                log("EXITO COMPLETO: extraccion + Supabase funcionando.")
        else:
            log("Sin documentos extraidos. Revisa capturas planc_*.png si existen.")

    except Exception as e:
        log(f"ERROR general: {e}")
        try:
            driver.save_screenshot("planc_error.png")
            log("Captura guardada: planc_error.png")
        except:
            pass
    finally:
        time.sleep(2)
        driver.quit()
        log("Fin.")

if __name__ == "__main__":
    main()