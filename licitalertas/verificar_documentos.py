# -*- coding: utf-8 -*-
"""
verificar_documentos.py - VERIFICADOR ALEATORIO V2 (doble control)
V2 (05/07/2026): acepta ademas de PDF los formatos ZIP, RAR y DOCX/XLSX,
porque SEACE publica documentos en todos esos formatos (verificado con
descarga manual de un ZIP valido con 5 PDF adentro).
1) BOT: toma una muestra aleatoria de la tabla 'documentos' de Supabase
   y verifica que cada enlace Alfresco responda con un archivo valido.
2) TAREA MANUAL: elige OTRA muestra aleatoria (distinta cuando alcance)
   y la guarda en tarea_verificacion.txt para que Fer la revise a mano.
No usa Selenium ni Chrome. Corre en segundos.
La key se lee de la variable de entorno SUPABASE_KEY_LICITALERTAS.
"""

import os
import random
import requests
from datetime import datetime

# --- CONFIGURACION -----------------------------------------------------------
SUPABASE_URL = "https://hjbmcdxbiajmbczgyhxk.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY_LICITALERTAS", "")

MUESTRA_BOT = 10      # cuantos verifica el bot (o todos si hay menos)
MUESTRA_MANUAL = 3    # cuantos van a la tarea manual de Fer
TAMANO_MINIMO_KB = 10 # un documento real de bases pesa mas que esto

URL_ALFRESCO = "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode={}"

# Firmas estandar de archivo (primeros bytes) — verificables en cualquier
# referencia de "file signatures" / "magic numbers":
#   %PDF -> PDF | PK -> ZIP (incluye DOCX/XLSX, que son ZIP por dentro) | Rar! -> RAR
FIRMAS_VALIDAS = [
    (b"%PDF", "PDF"),
    (b"PK",   "ZIP/DOCX/XLSX"),
    (b"Rar!", "RAR"),
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def traer_documentos():
    """Trae todas las filas de la tabla documentos."""
    url = f"{SUPABASE_URL}/rest/v1/documentos?select=id,nomenclatura,etapa,nombre_doc,file_code"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        log(f"ERROR Supabase: status {resp.status_code} - {resp.text[:200]}")
        return None
    return resp.json()

def identificar_formato(contenido):
    """Devuelve el nombre del formato si la firma es valida, o None."""
    for firma, nombre in FIRMAS_VALIDAS:
        if contenido.startswith(firma):
            return nombre
    return None

def verificar_enlace(file_code):
    """Devuelve (ok, detalle). ok=True si responde 200, tiene firma de
    PDF/ZIP/RAR/DOCX y pesa suficiente."""
    url = URL_ALFRESCO.format(file_code)
    try:
        resp = requests.get(url, timeout=60)
    except Exception as e:
        return False, f"error de conexion: {e}"
    if resp.status_code != 200:
        return False, f"status {resp.status_code}"
    contenido = resp.content
    formato = identificar_formato(contenido)
    if formato is None:
        inicio = contenido[:8]
        return False, f"formato no reconocido (inicia con {inicio!r})"
    kb = len(contenido) / 1024
    if kb < TAMANO_MINIMO_KB:
        return False, f"{formato} sospechosamente chico ({kb:.0f} KB)"
    return True, f"{formato} valido, {kb:.0f} KB"

def main():
    log("=== LicitAlertas - Verificador Aleatorio de Documentos V2 ===")
    if not SUPABASE_KEY:
        log("ERROR: variable SUPABASE_KEY_LICITALERTAS no encontrada.")
        log("Abre un CMD nuevo o revisa Variables de entorno.")
        return

    docs = traer_documentos()
    if docs is None:
        return
    total = len(docs)
    log(f"Documentos en la base: {total}")
    if total == 0:
        log("La tabla esta vacia. Nada que verificar.")
        return

    # -- Muestra del BOT (aleatoria) ------------------------------------------
    n_bot = min(MUESTRA_BOT, total)
    muestra_bot = random.sample(docs, n_bot)
    ids_bot = {d["id"] for d in muestra_bot}

    log(f"BOT: verificando {n_bot} documento(s) al azar...")
    ok_count = 0
    fallos = []
    for d in muestra_bot:
        ok, detalle = verificar_enlace(d["file_code"])
        estado = "OK " if ok else "FALLO"
        log(f"  [{estado}] {d['nomenclatura']} | {d['nombre_doc'][:50]} | {detalle}")
        if ok:
            ok_count += 1
        else:
            fallos.append(d)

    log(f"BOT RESULTADO: {ok_count}/{n_bot} verificados correctamente.")
    if fallos:
        log("FALLOS DETECTADOS (revisar estos file_code):")
        for f in fallos:
            log(f"  id={f['id']} | {f['nomenclatura']} | {f['file_code']}")

    # -- Muestra MANUAL para Fer (distinta a la del bot cuando alcance) -------
    restantes = [d for d in docs if d["id"] not in ids_bot]
    fuente_manual = restantes if len(restantes) >= MUESTRA_MANUAL else docs
    n_manual = min(MUESTRA_MANUAL, len(fuente_manual))
    muestra_manual = random.sample(fuente_manual, n_manual)

    lineas = []
    lineas.append("TAREA DE VERIFICACION MANUAL - LicitAlertas")
    lineas.append(f"Generada: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lineas.append("")
    lineas.append("Instrucciones: abre cada enlace. El archivo puede ser PDF,")
    lineas.append("ZIP, RAR o Word. Verifica que corresponda a la convocatoria")
    lineas.append("indicada (entidad/objeto).")
    lineas.append("Responde en el chat: 'todos correctos' o cual fallo.")
    lineas.append("")
    for i, d in enumerate(muestra_manual, 1):
        lineas.append(f"{i}. Convocatoria: {d['nomenclatura']}")
        lineas.append(f"   Documento:    {d['nombre_doc']}")
        lineas.append(f"   Etapa:        {d['etapa']}")
        lineas.append(f"   Enlace:       {URL_ALFRESCO.format(d['file_code'])}")
        lineas.append("")

    with open("tarea_verificacion.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    log(f"TAREA MANUAL: {n_manual} documento(s) guardados en tarea_verificacion.txt")
    log("Abre ese archivo, revisa los enlaces y reporta el resultado.")
    log("Fin.")

if __name__ == "__main__":
    main()