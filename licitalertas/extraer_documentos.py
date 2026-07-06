# -*- coding: utf-8 -*-
"""
extraer_documentos.py - OPCION B2.2 (busqueda por Sigla Nomenclatura)
Fix B2.2 con datos verificados el 05/07/2026 via diagnostico_campos.py:
- El boton Busqueda Avanzada es un <legend> (texto corto, clic dirigido).
- El campo es id=tbBuscador:idFormBuscarProceso:siglasEntidad.
Base: version PLAN C + SUPABASE que ya funciono (Chrome, ficha y upsert intactos).
Cambio validado manualmente el 05/07: en vez de paginar el listado nacional,
se busca CADA pendiente por su nomenclatura en Busqueda Avanzada > Sigla Nomenclatura.
Si hay varias filas (republicaciones), se abre la fila 1 (la mas reciente).
La key se lee de la variable de entorno SUPABASE_KEY_LICITALERTAS.
"""

import os
import re
import time
import requests
from datetime import datetime, date
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACION -----------------------------------------------------------
MAX_POR_CORRIDA = 25   # primera prueba: 25. Luego subir a 50.
ANIO = "2026"
URL_BUSCADOR = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"

SUPABASE_URL = "https://hjbmcdxbiajmbczgyhxk.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY_LICITALERTAS", "")

REGEX_DOC = re.compile(r"descargaDocGeneral\('([0-9a-fA-F-]{36})'\s*,\s*'[^']*'\s*,\s*'([^']+)'\)")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- SUPABASE ----------------------------------------------------------------
def headers_supabase():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

def obtener_pendientes():
    """Devuelve lista de nomenclaturas vigentes que aun no tienen documentos."""
    hoy = date.today().isoformat()

    url1 = (f"{SUPABASE_URL}/rest/v1/convocatorias"
            f"?select=nomenclatura&fecha_vencimiento=gte.{hoy}&limit=1000")
    r1 = requests.get(url1, headers=headers_supabase(), timeout=30)
    if r1.status_code != 200:
        log(f"ERROR consultando convocatorias: {r1.status_code} - {r1.text[:200]}")
        return None
    vigentes = set(x["nomenclatura"] for x in r1.json() if x.get("nomenclatura"))
    log(f"Convocatorias vigentes (venc >= {hoy}): {len(vigentes)}")

    url2 = f"{SUPABASE_URL}/rest/v1/documentos?select=nomenclatura&limit=10000"
    r2 = requests.get(url2, headers=headers_supabase(), timeout=30)
    if r2.status_code != 200:
        log(f"ERROR consultando documentos: {r2.status_code} - {r2.text[:200]}")
        return None
    con_docs = set(x["nomenclatura"] for x in r2.json() if x.get("nomenclatura"))
    log(f"Nomenclaturas que ya tienen documentos: {len(con_docs)}")

    pendientes = sorted(vigentes - con_docs)
    log(f"PENDIENTES a procesar: {len(pendientes)}")
    return pendientes

def subir_a_supabase(nomenclatura, docs):
    """Upsert de los documentos de UNA convocatoria."""
    if not docs:
        log("  Sin documentos que subir para esta convocatoria.")
        return False
    registros = []
    for d in docs:
        registros.append({
            "nomenclatura": nomenclatura,
            "etapa": d["etapa"],
            "nombre_doc": d["nombre_doc"],
            "file_code": d["file_code"],
        })
    url = f"{SUPABASE_URL}/rest/v1/documentos?on_conflict=nomenclatura,file_code"
    resp = requests.post(url, headers=headers_supabase(), json=registros, timeout=30)
    if resp.status_code in (200, 201, 204):
        log(f"  SUPABASE OK: {len(registros)} documento(s) (status {resp.status_code}).")
        return True
    log(f"  ERROR Supabase: {resp.status_code} - {resp.text[:300]}")
    return False

# --- SELENIUM: BASE PLAN C (INTACTO) -------------------------------------------
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

def abrir_buscador(driver):
    """Abre el buscador, selecciona pestana y anio. NO hace clic en Buscar."""
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
    return True

ID_CAMPO_SIGLA = "tbBuscador:idFormBuscarProceso:siglasEntidad"  # verificado 05/07/2026

def abrir_busqueda_avanzada(driver):
    """Clic en 'Busqueda Avanzada' (es un <legend>) y verificacion del campo."""
    log("Abriendo Busqueda Avanzada...")
    clickeado = False
    for c in driver.find_elements(By.XPATH, "//legend | //a | //button | //span | //label"):
        try:
            texto = c.text.strip()
            if "squeda Avanzada" in texto and len(texto) < 30 and c.is_displayed():
                driver.execute_script("arguments[0].click();", c)
                log(f"Clickeado: <{c.tag_name}> '{texto}'")
                clickeado = True
                break
        except:
            continue
    if not clickeado:
        log("ERROR: no se encontro el boton de Busqueda Avanzada.")
        driver.save_screenshot("b2_sin_boton.png")
        return False
    time.sleep(5)
    inp = campo_sigla(driver)
    if inp is not None:
        log("Campo Sigla Nomenclatura localizado y usable.")
        return True
    log("ERROR: no encuentro un campo Sigla Nomenclatura usable.")
    driver.save_screenshot("b2_sin_campo.png")
    log("Captura guardada: b2_sin_campo.png")
    return False

def elemento_usable(inp):
    """True solo si el input esta visible, habilitado y no es readonly."""
    try:
        if not inp.is_displayed():
            return False
        if not inp.is_enabled():
            return False
        if inp.get_attribute("readonly"):
            return False
        return True
    except:
        return False

def campo_sigla(driver):
    """Localiza el input de Sigla Nomenclatura por su id exacto (verificado)."""
    try:
        inp = driver.find_element(By.ID, ID_CAMPO_SIGLA)
        if elemento_usable(inp):
            return inp
    except:
        pass
    return None

def buscar_por_nomenclatura(driver, nomenclatura):
    """Escribe la nomenclatura en Sigla, clic Buscar, espera. True si hay resultados."""
    inp = campo_sigla(driver)
    if inp is None:
        log("  CAMPO SIGLA NO ENCONTRADO.")
        driver.save_screenshot("b2_sin_campo.png")
        return None
    escrito = False
    try:
        inp.clear()
        inp.send_keys(nomenclatura)
        escrito = True
    except Exception as e:
        log(f"  send_keys fallo ({type(e).__name__}); usando JavaScript...")
    if not escrito:
        try:
            driver.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                inp, nomenclatura,
            )
            escrito = True
        except Exception as e:
            log(f"  Escritura JS tambien fallo: {e}")
            driver.save_screenshot("b2_error_escritura.png")
            return None
    time.sleep(1)

    for b in driver.find_elements(By.XPATH, "//button | //input[@type='submit']"):
        try:
            texto = b.text or b.get_attribute("value") or ""
            if "Buscar" in texto and b.is_displayed():
                driver.execute_script("arguments[0].click();", b)
                break
        except:
            continue

    time.sleep(12)
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "No se encontraron" in body_text:
        return False
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
    """Back desde la ficha. Si el formulario no sobrevive, lo rearma."""
    driver.back()
    time.sleep(10)
    if campo_sigla(driver) is not None:
        return True
    log("  El formulario no sobrevivio al back; rearmando buscador...")
    if not abrir_buscador(driver):
        return False
    return abrir_busqueda_avanzada(driver)

# --- MAIN ----------------------------------------------------------------------
def main():
    log("=== LicitAlertas - Extractor de Documentos (OPCION B2.2) ===")
    if not SUPABASE_KEY:
        log("ERROR: variable SUPABASE_KEY_LICITALERTAS no encontrada.")
        log("Cierra y abre un CMD nuevo, o revisa Variables de entorno. Abortando.")
        return

    pendientes = obtener_pendientes()
    if pendientes is None:
        log("Abortando por error de consulta a Supabase.")
        return
    if not pendientes:
        log("No hay pendientes. Nada que hacer.")
        return

    lote = pendientes[:MAX_POR_CORRIDA]
    log(f"Lote de esta corrida: {len(lote)} convocatorias.")

    driver = iniciar_chrome()
    ok = 0
    no_encontradas = []
    con_error = []
    try:
        if not abrir_buscador(driver):
            return
        if not abrir_busqueda_avanzada(driver):
            return

        for idx, nomenclatura in enumerate(lote, start=1):
            log(f"[{idx}/{len(lote)}] Buscando: {nomenclatura}")
            resultado = buscar_por_nomenclatura(driver, nomenclatura)

            if resultado is None:
                log("  Formulario roto. Rearmando y reintentando una vez...")
                if not (abrir_buscador(driver) and abrir_busqueda_avanzada(driver)):
                    log("  No se pudo rearmar. Terminando corrida.")
                    break
                resultado = buscar_por_nomenclatura(driver, nomenclatura)
                if resultado is None:
                    con_error.append(nomenclatura)
                    continue

            if resultado is False:
                log("  SEACE: No se encontraron datos.")
                no_encontradas.append(nomenclatura)
                continue

            filas = obtener_filas_resultados(driver)
            if not filas:
                log("  Sin filas utiles pese a haber resultados.")
                con_error.append(nomenclatura)
                continue

            log(f"  Filas encontradas: {len(filas)}. Abriendo la fila 1 (mas reciente).")
            if not clic_icono_ficha(driver, filas[0]):
                log("  No se pudo clickear el icono de ficha.")
                con_error.append(nomenclatura)
                continue

            docs = extraer_documentos_de_ficha(driver)
            log(f"  Documentos encontrados: {len(docs)}")
            for d in docs:
                log(f"    [{d['etapa']}] {d['nombre_doc']} -> {d['file_code']}")

            if docs and subir_a_supabase(nomenclatura, docs):
                ok += 1
            else:
                con_error.append(nomenclatura)

            if not volver_al_buscador(driver):
                log("No se pudo regresar al buscador. Terminando corrida.")
                break

            time.sleep(5)  # pausa anti-bloqueo

        log("=== RESUMEN DE CORRIDA ===")
        log(f"Subidas OK: {ok}")
        log(f"No encontradas en SEACE: {len(no_encontradas)}")
        for n in no_encontradas:
            log(f"  NO ENCONTRADA: {n}")
        log(f"Con error: {len(con_error)}")
        for n in con_error:
            log(f"  ERROR: {n}")

    except Exception as e:
        log(f"ERROR general: {e}")
        try:
            driver.save_screenshot("b2_error.png")
            log("Captura guardada: b2_error.png")
        except:
            pass
    finally:
        time.sleep(2)
        driver.quit()
        log("Fin.")

if __name__ == "__main__":
    main()