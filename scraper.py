import requests
import json
import os
import io
from datetime import datetime, timedelta

# Configuracion
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_USER       = os.environ.get("EMAIL_USER", "")
EMAIL_DESTINO    = os.environ.get("EMAIL_DESTINO", "")
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
SUPABASE_URL     = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY     = os.environ.get("SUPABASE_KEY", "")

GITHUB_REPO    = "fermardelgado/licitalertas"
EXCEL_PATH     = "seace_data.xls"
TAXONOMIA_PATH = "taxonomia.json"

# ─────────────────────────────────────────────
# DICCIONARIO REGION: palabras clave → región
# ─────────────────────────────────────────────
REGION_MAP = {
    "AMAZONAS":      "Amazonas",
    "ANCASH":        "Ancash",
    "APURIMAC":      "Apurímac",
    "APURÍMAC":      "Apurímac",
    "AREQUIPA":      "Arequipa",
    "AYACUCHO":      "Ayacucho",
    "CAJAMARCA":     "Cajamarca",
    "CALLAO":        "Callao",
    "CUSCO":         "Cusco",
    "CUZCO":         "Cusco",
    "HUANCAVELICA":  "Huancavelica",
    "HUANUCO":       "Huánuco",
    "HUÁNUCO":       "Huánuco",
    "ICA":           "Ica",
    "JUNIN":         "Junín",
    "JUNÍN":         "Junín",
    "LA LIBERTAD":   "La Libertad",
    "LAMBAYEQUE":    "Lambayeque",
    "LIMA":          "Lima",
    "LORETO":        "Loreto",
    "MADRE DE DIOS": "Madre de Dios",
    "MOQUEGUA":      "Moquegua",
    "PASCO":         "Pasco",
    "PIURA":         "Piura",
    "PUNO":          "Puno",
    "SAN MARTIN":    "San Martín",
    "SAN MARTÍN":    "San Martín",
    "TACNA":         "Tacna",
    "TUMBES":        "Tumbes",
    "UCAYALI":       "Ucayali",
    # Ciudades conocidas → región
    "TRUJILLO":      "La Libertad",
    "CHICLAYO":      "Lambayeque",
    "IQUITOS":       "Loreto",
    "HUARAZ":        "Ancash",
    "CHIMBOTE":      "Ancash",
    "PIURA":         "Piura",
    "SULLANA":       "Piura",
    "TARAPOTO":      "San Martín",
    "PUCALLPA":      "Ucayali",
    "PUERTO MALDONADO": "Madre de Dios",
    "MOQUEGUA":      "Moquegua",
    "ILO":           "Moquegua",
    "TACNA":         "Tacna",
    "TUMBES":        "Tumbes",
    "ABANCAY":       "Apurímac",
    "HUANCAYO":      "Junín",
    "CERRO DE PASCO":"Pasco",
    "HUANCAVELICA":  "Huancavelica",
    "AYACUCHO":      "Ayacucho",
    "CHACHAPOYAS":   "Amazonas",
}

# Entidades que son nacionales (no tienen región específica)
ENTIDADES_NACIONALES = [
    "MINISTERIO", "MINSA", "MINEDU", "MTC", "MEF", "MIDIS",
    "MINAM", "MINEM", "MININTER", "MINAGRI", "MINJUS", "MIMP",
    "PRODUCE", "MINCETUR", "MINCUL", "MINDEF",
    "EJERCITO PERUANO", "MARINA DE GUERRA", "FUERZA AEREA",
    "POLICIA NACIONAL", "SUNAT", "SUNAFIL", "SUNARP", "SIS",
    "ESSALUD", "OSINERGMIN", "OSIPTEL", "OSITRAN", "OEFA",
    "INDECOPI", "CONGRESO", "PODER JUDICIAL", "FISCALIA",
    "DEFENSORIA", "CONTRALORIA", "JNE", "ONPE", "RENIEC",
    "PCM", "PRESIDENCIA DEL CONSEJO",
    "PERU COMPRAS", "AGRO RURAL", "AGRORURAL",
    "PROVIAS", "FONDO", "PROGRAMA NACIONAL",
]

def inferir_region(entidad):
    """Infiere la región desde el nombre de la entidad."""
    entidad_up = entidad.upper()

    # Verificar si es entidad nacional
    for keyword in ENTIDADES_NACIONALES:
        if keyword in entidad_up:
            return "Nacional"

    # Buscar región por palabras clave (orden importa: primero las más largas)
    for keyword in sorted(REGION_MAP.keys(), key=len, reverse=True):
        if keyword in entidad_up:
            return REGION_MAP[keyword]

    return "Nacional"  # Default: si no se reconoce, se trata como nacional

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}")

def descargar_excel_github():
    log("Descargando Excel desde GitHub...")
    headers = {"Accept": "application/vnd.github.v3.raw"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{EXCEL_PATH}"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 200:
        log(f"Excel descargado: {len(resp.content)} bytes")
        return resp.content
    else:
        log(f"Error descargando Excel: {resp.status_code}")
        return None

def cargar_taxonomia():
    try:
        with open(TAXONOMIA_PATH, "r", encoding="utf-8") as f:
            tax = json.load(f)
            log(f"Taxonomia cargada: {len(tax)} categorias")
            return tax
    except Exception as e:
        log(f"No se pudo cargar {TAXONOMIA_PATH}: {e}")
        return {}

def detectar_categorias(texto, taxonomia):
    texto_up = texto.upper()
    encontradas = []
    for cat_id, cat in taxonomia.items():
        for palabra in cat.get("palabras_clave", []):
            if palabra.upper() in texto_up:
                encontradas.append(cat_id)
                break
    return encontradas

# Mapeo de objeto SEACE → nuestro estándar
OBJETO_MAP = {
    "BIEN":      "BIEN",
    "BIENES":    "BIEN",
    "SERVICIO":  "SERVICIO",
    "SERVICIOS": "SERVICIO",
    "OBRA":      "OBRA",
    "OBRAS":     "OBRA",
    "CONSULTORIA DE OBRAS": "SERVICIO",
    "CONSULTORIA EN GENERAL": "SERVICIO",
}

def normalizar_objeto(objeto_raw):
    """Convierte el texto del Excel al estándar BIEN/SERVICIO/OBRA."""
    return OBJETO_MAP.get(objeto_raw.upper().strip(), "SERVICIO")

def procesar_excel(contenido, taxonomia):
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=contenido)
        ws = wb.sheet_by_index(0)
        log(f"Excel abierto: {ws.nrows} filas, {ws.ncols} columnas")

        convocatorias = []
        for i in range(1, ws.nrows):
            try:
                fila = [str(ws.cell_value(i, j)).strip() for j in range(ws.ncols)]
                if not fila[0] or fila[0] == "":
                    continue

                entidad     = fila[1] if len(fila) > 1 else ""
                fecha_pub   = fila[2] if len(fila) > 2 else ""
                nomenclat   = fila[3] if len(fila) > 3 else ""
                objeto_raw  = fila[5] if len(fila) > 5 else ""
                descripcion = fila[6] if len(fila) > 6 else ""
                monto_str   = fila[7] if len(fila) > 7 else "0"

                try:
                    monto = float(str(monto_str).replace(",", "").replace("---", "0") or 0)
                except:
                    monto = 0.0

                fecha_venc = ""
                if fecha_pub:
                    try:
                        partes = fecha_pub.split(" ")[0]
                        if "/" in partes:
                            dt = datetime.strptime(partes, "%d/%m/%Y")
                        else:
                            dt = datetime.strptime(partes, "%Y-%m-%d")
                        fecha_venc = (dt + timedelta(days=30)).strftime("%Y-%m-%d")
                    except:
                        fecha_venc = ""

                titulo   = descripcion[:100] if descripcion else objeto_raw
                texto_cat = f"{descripcion} {objeto_raw} {entidad}"
                categorias = detectar_categorias(texto_cat, taxonomia)
                region   = inferir_region(entidad)
                objeto   = normalizar_objeto(objeto_raw)

                conv = {
                    "id":                nomenclat or str(i),
                    "nomenclatura":      nomenclat or f"SIN-NOMENCLATURA-{i}",
                    "titulo":            titulo,
                    "descripcion":       descripcion,
                    "entidad":           entidad,
                    "tipo":              objeto,          # BIEN / SERVICIO / OBRA
                    "tipo_raw":          objeto_raw,      # texto original del SEACE
                    "monto":             monto,
                    "region":            region,          # inferida
                    "categorias":        categorias,
                    "fecha_publicacion": fecha_pub,
                    "fecha_vencimiento": fecha_venc,
                    "url_seace":         "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml",
                }
                convocatorias.append(conv)
            except Exception:
                continue

        log(f"Convocatorias procesadas: {len(convocatorias)}")

        # Log de distribución de regiones para verificar
        from collections import Counter
        regiones = Counter(c["region"] for c in convocatorias)
        log(f"Distribución de regiones: {dict(regiones.most_common(10))}")

        return convocatorias
    except Exception as e:
        log(f"Error procesando Excel: {e}")
        return []

def datos_respaldo():
    hoy = datetime.now()
    f = lambda d: (hoy + timedelta(days=d)).strftime("%Y-%m-%d")
    return [
        {"id":"F001","nomenclatura":"F001","titulo":"Adquisicion de equipos de computo","descripcion":"","entidad":"Municipalidad de Lima","tipo":"BIEN","tipo_raw":"Bien","monto":85000,"region":"Lima","categorias":[],"fecha_vencimiento":f(2),"url_seace":"https://seace.gob.pe"},
        {"id":"F002","nomenclatura":"F002","titulo":"Servicio de limpieza de locales","descripcion":"","entidad":"Ministerio de Educacion","tipo":"SERVICIO","tipo_raw":"Servicio","monto":42000,"region":"Nacional","categorias":[],"fecha_vencimiento":f(15),"url_seace":"https://seace.gob.pe"},
        {"id":"F003","nomenclatura":"F003","titulo":"Suministro de materiales de construccion","descripcion":"","entidad":"Gobierno Regional Cusco","tipo":"BIEN","tipo_raw":"Bien","monto":320000,"region":"Cusco","categorias":[],"fecha_vencimiento":f(7),"url_seace":"https://seace.gob.pe"},
    ]

def dias_restantes(fecha_str):
    if not fecha_str:
        return 999
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            return (datetime.strptime(str(fecha_str)[:10], fmt) - hoy).days
        except:
            continue
    return 999

def urgencia(dias):
    if dias < 0:   return "vencido"
    if dias <= 3:  return "urgente"
    if dias <= 10: return "proximo"
    return "normal"

# ─────────────────────────────────────────────
# USUARIOS DESDE SUPABASE
# ─────────────────────────────────────────────
def cargar_usuarios():
    """Lee perfiles de usuario desde Supabase (nuevo) o usuarios.json (fallback)."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            # Traer usuarios activos
            res_u = supabase.table("usuarios").select("id,nombre,email").eq("activo", True).execute()
            usuarios_raw = res_u.data or []

            if not usuarios_raw:
                log("No hay usuarios activos en Supabase.")
                return []

            ids = [u["id"] for u in usuarios_raw]

            # Traer preferencias en paralelo
            res_obj = supabase.table("usuario_objetos").select("usuario_id,objeto").in_("usuario_id", ids).execute()
            res_reg = supabase.table("usuario_regiones").select("usuario_id,region").in_("usuario_id", ids).execute()
            res_cat = supabase.table("usuario_categorias").select("usuario_id,categoria_id").in_("usuario_id", ids).execute()
            res_mon = supabase.table("usuario_montos").select("usuario_id,tope_id").in_("usuario_id", ids).execute()

            # Traer topes para mapear tope_id → monto_min/monto_max
            res_top = supabase.table("config_topes").select("id,monto_min,monto_max").eq("activo", True).execute()
            topes_map = {t["id"]: t for t in (res_top.data or [])}

            # Indexar por usuario_id
            def agrupar(rows, key, val):
                d = {}
                for r in rows:
                    d.setdefault(r[key], []).append(r[val])
                return d

            obj_map = agrupar(res_obj.data or [], "usuario_id", "objeto")
            reg_map = agrupar(res_reg.data or [], "usuario_id", "region")
            cat_map = agrupar(res_cat.data or [], "usuario_id", "categoria_id")
            mon_map = agrupar(res_mon.data or [], "usuario_id", "tope_id")

            usuarios = []
            for u in usuarios_raw:
                uid = u["id"]
                tope_ids = mon_map.get(uid, [])

                # Calcular monto_min y monto_max desde los topes seleccionados
                if tope_ids:
                    montos = [topes_map[tid] for tid in tope_ids if tid in topes_map]
                    monto_min = min(t["monto_min"] for t in montos) if montos else 0
                    monto_max_vals = [t["monto_max"] for t in montos if t["monto_max"] is not None]
                    monto_max = max(monto_max_vals) if monto_max_vals else 999_999_999_999
                else:
                    monto_min = 0
                    monto_max = 999_999_999_999

                usuarios.append({
                    "id":         uid,
                    "nombre":     u["nombre"],
                    "email":      u["email"],
                    "objetos":    obj_map.get(uid, []),    # ["BIEN","SERVICIO"]
                    "regiones":   reg_map.get(uid, []),    # ["Lima","Nacional"]
                    "categorias": cat_map.get(uid, []),    # ["mobiliario","climatizacion"]
                    "monto_min":  monto_min,
                    "monto_max":  monto_max,
                })

            log(f"Usuarios cargados desde Supabase: {len(usuarios)}")
            return usuarios

        except Exception as e:
            log(f"Error cargando usuarios desde Supabase: {e}. Usando fallback JSON.")

    # Fallback: usuarios.json
    try:
        with open("usuarios.json", "r", encoding="utf-8") as f:
            usuarios = json.load(f)
            log(f"Usuarios cargados desde JSON: {len(usuarios)}")
            return usuarios
    except Exception as e:
        log(f"No se pudo cargar usuarios.json: {e}")
        return []

# ─────────────────────────────────────────────
# FILTRO POR PERFIL DE USUARIO
# ─────────────────────────────────────────────
def coincide_con_usuario(c, usuario):
    # 1. Filtro por objeto (BIEN / SERVICIO / OBRA)
    objetos = usuario.get("objetos", [])
    if objetos:
        if c.get("tipo", "") not in objetos:
            return False

    # 2. Filtro por región (incluye "Nacional" siempre si está en la lista)
    regiones = usuario.get("regiones", [])
    if regiones:
        region_conv = c.get("region", "")
        # Nacional aparece para todos si el usuario marcó "Nacional"
        if region_conv == "Nacional":
            if "Nacional" not in regiones:
                return False
        else:
            if region_conv not in regiones and "Nacional" not in regiones:
                return False

    # 3. Filtro por categoría
    categorias_usuario = usuario.get("categorias", [])
    if categorias_usuario:
        if not any(cat in c.get("categorias", []) for cat in categorias_usuario):
            return False

    # 4. Filtro por monto
    monto = c.get("monto", 0)
    if monto < usuario.get("monto_min", 0):
        return False
    if monto > usuario.get("monto_max", 999_999_999_999):
        return False

    return True

def filtrar_para_usuario(convocatorias, usuario):
    return [c for c in convocatorias if coincide_con_usuario(c, usuario)]

def guardar_en_supabase(convocatorias):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log("SUPABASE_URL o SUPABASE_KEY no configurados, se omite guardado.")
        return
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        log(f"Error conectando a Supabase: {e}")
        return

    guardadas = 0
    errores = 0
    for c in convocatorias:
        try:
            fecha_pub = None
            if c.get("fecha_publicacion"):
                try:
                    partes = str(c["fecha_publicacion"]).split(" ")[0]
                    if "/" in partes:
                        fecha_pub = datetime.strptime(partes, "%d/%m/%Y").strftime("%Y-%m-%d")
                    else:
                        fecha_pub = partes
                except:
                    fecha_pub = None

            registro = {
                "nomenclatura":      c["nomenclatura"],
                "entidad":           c.get("entidad", ""),
                "titulo":            c.get("titulo", ""),
                "descripcion":       c.get("descripcion", ""),
                "categorias":        c.get("categorias", []),
                "monto":             c.get("monto", 0),
                "region":            c.get("region", ""),
                "fecha_publicacion": fecha_pub,
                "fecha_vencimiento": c.get("fecha_vencimiento") or None,
                "url_seace":         c.get("url_seace", ""),
                "actualizado_en":    datetime.now().isoformat(),
            }
            supabase.table("convocatorias").upsert(registro, on_conflict="nomenclatura").execute()
            guardadas += 1
        except Exception as e:
            errores += 1
            if errores <= 3:
                log(f"Error guardando '{c.get('nomenclatura','?')}': {e}")

    log(f"Supabase: {guardadas} guardadas, {errores} errores")

def generar_html(convocatorias, fecha, fuente):
    activas  = [c for c in convocatorias if c["urg"] != "vencido"]
    urgentes = [c for c in activas if c["urg"] == "urgente"]
    proximas = [c for c in activas if c["urg"] == "proximo"]
    normales = [c for c in activas if c["urg"] == "normal"]

    def fila(c, color):
        dias  = c["dias"]
        label = "HOY" if dias == 0 else f"{dias} dias"
        region_badge = f'<span style="font-size:10px;color:#888"> | {c.get("region","")}</span>'
        return (
            f'<tr style="border-bottom:1px solid #f0f4f8">'
            f'<td style="padding:8px;font-size:13px">{str(c["titulo"])[:70]}{region_badge}</td>'
            f'<td style="padding:8px;font-size:12px;color:#666">{c["entidad"][:40]}</td>'
            f'<td style="padding:8px;font-size:12px;color:#666">S/. {c["monto"]:,.0f}</td>'
            f'<td style="padding:8px;text-align:center">'
            f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{label}</span>'
            f'</td></tr>'
        )

    def tabla(titulo, items, color):
        if not items:
            return ""
        filas = "".join([fila(c, color) for c in items])
        return (
            f'<h3 style="color:{color};margin:20px 0 8px">{titulo} ({len(items)})</h3>'
            f'<table style="width:100%;border-collapse:collapse;background:white;border-radius:8px">'
            f'<thead><tr style="background:#f7fafc">'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">TITULO</th>'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">ENTIDAD</th>'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">MONTO</th>'
            f'<th style="padding:8px;text-align:center;font-size:11px;color:#999">VENCE</th>'
            f'</tr></thead><tbody>{filas}</tbody></table>'
        )

    badge       = "SEACE REAL" if fuente != "Respaldo" else "RESPALDO"
    color_badge = "#38a169"   if fuente != "Respaldo" else "#e53e3e"

    return f'''<html><body style="font-family:Arial,sans-serif;background:#f0f4f8;padding:20px">
    <div style="max-width:860px;margin:0 auto">
    <div style="background:linear-gradient(135deg,#1a365d,#2b6cb0);color:white;padding:20px 30px;border-radius:12px 12px 0 0">
    <h1 style="margin:0;font-size:20px">LicitAlertas — Reporte Diario</h1>
    <p style="margin:4px 0 0;opacity:0.85">{fecha} | {len(activas)} convocatorias activas |
    <span style="background:{color_badge};padding:2px 8px;border-radius:10px;font-size:11px">{badge}</span></p>
    </div>
    <div style="background:white;padding:20px 30px;border-radius:0 0 12px 12px">
    {tabla("URGENTES — Vencen en 3 dias o menos", urgentes, "#e53e3e")}
    {tabla("PROXIMAS — Vencen en 10 dias o menos", proximas, "#d69e2e")}
    {tabla("NORMALES", normales[:20], "#38a169")}
    </div></div></body></html>'''

def enviar_email_a(destino, convocatorias, fecha, fuente, nombre_usuario=""):
    if not SENDGRID_API_KEY or not EMAIL_USER or not destino:
        log("Credenciales SendGrid o destino no configurados.")
        return
    activas = [c for c in convocatorias if c["urg"] != "vencido"]
    if not activas:
        log(f"Sin coincidencias para {destino}, no se envia email.")
        return
    urgentes = len([c for c in activas if c["urg"] == "urgente"])
    asunto = (
        f"LicitAlertas {fecha} — {urgentes} URGENTES | {len(activas)} convocatorias [{fuente}]"
        if urgentes > 0
        else f"LicitAlertas {fecha} — {len(activas)} convocatorias [{fuente}]"
    )
    html = generar_html(convocatorias, fecha, fuente)
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": destino}]}],
            "from": {"email": EMAIL_USER},
            "subject": asunto,
            "content": [{"type": "text/html", "value": html}],
        }
    )
    if resp.status_code == 202:
        log(f"Email enviado a {destino} ({nombre_usuario}) — {len(activas)} convocatorias")
    else:
        log(f"Error email a {destino}: {resp.status_code} {resp.text}")

def main():
    fecha = datetime.now().strftime("%d/%m/%Y")
    log("Iniciando LicitAlertas...")

    taxonomia = cargar_taxonomia()

    fuente    = "SEACE Excel"
    contenido = descargar_excel_github()

    if contenido:
        convocatorias = procesar_excel(contenido, taxonomia)
    else:
        convocatorias = []

    if not convocatorias:
        log("Sin datos del Excel, usando respaldo.")
        convocatorias = datos_respaldo()
        fuente = "Respaldo"

    for c in convocatorias:
        c["dias"] = dias_restantes(c.get("fecha_vencimiento", ""))
        c["urg"]  = urgencia(c["dias"])

    output = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fuente":        fuente,
        "total":         len(convocatorias),
        "convocatorias": convocatorias,
    }
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"datos.json guardado: {len(convocatorias)} convocatorias — fuente: {fuente}")

    if fuente != "Respaldo":
        guardar_en_supabase(convocatorias)

    usuarios = cargar_usuarios()

    if usuarios:
        for usuario in usuarios:
            filtradas = filtrar_para_usuario(convocatorias, usuario)
            log(f"Usuario {usuario['nombre']}: {len(filtradas)} coincidencias")
            enviar_email_a(usuario.get("email"), filtradas, fecha, fuente, usuario.get("nombre", ""))
    elif EMAIL_DESTINO:
        log("Sin usuarios en Supabase, usando EMAIL_DESTINO como respaldo.")
        enviar_email_a(EMAIL_DESTINO, convocatorias, fecha, fuente)
    else:
        log("No hay usuarios ni EMAIL_DESTINO. No se envio ningun email.")

    log("Proceso completado.")

if __name__ == "__main__":
    main()
