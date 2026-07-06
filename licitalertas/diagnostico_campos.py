# -*- coding: utf-8 -*-
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

URL = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"

def log(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}")

op = Options()
op.add_argument("--window-size=1920,1080")
op.add_argument("--no-sandbox")
op.add_argument("--disable-dev-shm-usage")
op.add_argument("--disable-blink-features=AutomationControlled")
op.add_experimental_option("excludeSwitches", ["enable-automation"])
op.add_experimental_option("useAutomationExtension", False)
op.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=op)
driver.maximize_window()

try:
    log("Abriendo buscador...")
    driver.get(URL)
    time.sleep(10)

    for p in driver.find_elements(By.XPATH, "//a | //span | //li"):
        try:
            if "Buscador de Procedimientos de Selecci" in p.text.strip():
                driver.execute_script("arguments[0].click();", p)
                break
        except:
            continue
    time.sleep(6)

    log("Clic en Busqueda Avanzada...")
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
        log("NO se encontro el boton de Busqueda Avanzada")
    time.sleep(6)
    driver.save_screenshot("diag_campos.png")

    log("--- INPUTS DE TEXTO VISIBLES (id | habilitado | texto vecino) ---")
    for inp in driver.find_elements(By.XPATH, "//input[@type='text']"):
        try:
            if not inp.is_displayed():
                continue
            iid = inp.get_attribute("id") or "(sin id)"
            hab = inp.is_enabled()
            vecino = ""
            try:
                celda = inp.find_element(By.XPATH, "./ancestor::td[1]/preceding-sibling::td[1]")
                vecino = celda.text.strip()[:40]
            except:
                pass
            print(f"  id={iid!r} | enabled={hab} | vecino={vecino!r}")
        except:
            continue
    log("=== FIN ===")
finally:
    time.sleep(2)
    driver.quit()