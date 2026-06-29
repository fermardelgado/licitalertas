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

GITHUB_REPO = "fermardelgado/licitalertas"
EXCEL_PATH  = "seace_data.xls"

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

def procesar_excel(contenido):
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

                entidad    = fila[1] if len(fila) > 1 else ""
                fecha_pub  = fila[2] if len(fila) > 2 else ""
                nomenclat  = fila[3] if len(fila) > 3 else ""
                objeto     = fila[5] if len(fila) > 5 else ""
                descripcion = fila[6] if len(fila) > 6 else ""
                monto_str  = fila[7] if len(fila) > 7 else "0"
                moneda     = fila[8] if len(fila) > 8 else "Soles"

                try:
                    monto = float(str(monto_str).replace(",", "").replace("---", "0") or 0)
                except:
                    monto = 0.0

                # Fecha de publicacion como proxy de vencimiento (estimado +30 dias)
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

                conv = {
                    "id":               nomenclat or str(i),
                    "titulo":           descripcion[:100] if descripcion else objeto,
                    "entidad":          entidad,
                    "tipo":             objeto,
                    "monto":            monto,
                    "region":           "Lima",
                    "fecha_publicacion": fecha_pub,
                    "fecha_vencimiento": fecha_venc,
                    "url_seace":        f"https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml",
                }
                convocatorias.append(conv)
            except Exception as e:
                continue

        log(f"Convocatorias procesadas: {len(convocatorias)}")
        return convocatorias
    except Exception as e:
        log(f"Error procesando Excel: {e}")
        return []

def datos_respaldo():
    hoy = datetime.now()
    f = lambda d: (hoy + timedelta(days=d)).strftime("%Y-%m-%d")
    return [
        {"id":"F001","titulo":"Adquisicion de equipos de computo","entidad":"Municipalidad de Lima","tipo":"Adjudicacion Simplificada","monto":85000,"region":"Lima","fecha_vencimiento":f(2),"url_seace":"https://seace.gob.pe"},
        {"id":"F002","titulo":"Servicio de limpieza de locales","entidad":"Ministerio de Educacion","tipo":"Concurso Publico","monto":42000,"region":"Lima","fecha_vencimiento":f(15),"url_seace":"https://seace.gob.pe"},
        {"id":"F003","titulo":"Suministro de materiales de construccion","entidad":"Gobierno Regional Cusco","tipo":"Licitacion Publica","monto":320000,"region":"Cusco","fecha_vencimiento":f(7),"url_seace":"https://seace.gob.pe"},
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
    if dias < 0:  return "vencido"
    if dias <= 3:  return "urgente"
    if dias <= 10: return "proximo"
    return "normal"

def generar_html(convocatorias, fecha, fuente):
    activas = [c for c in convocatorias if c["urg"] != "vencido"]
    urgentes = [c for c in activas if c["urg"] == "urgente"]
    proximas  = [c for c in activas if c["urg"] == "proximo"]
    normales  = [c for c in activas if c["urg"] == "normal"]

    def fila(c, color):
        dias = c["dias"]
        label = "HOY" if dias == 0 else f"{dias} dias"
        return (
            f'<tr style="border-bottom:1px solid #f0f4f8">'
            f'<td style="padding:8px;font-size:13px">{str(c["titulo"])[:70]}</td>'
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

    badge = "SEACE REAL" if fuente != "Respaldo" else "RESPALDO"
    color_badge = "#38a169" if fuente != "Respaldo" else "#e53e3e"

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

def enviar_email(convocatorias, fecha, fuente):
    if not SENDGRID_API_KEY or not EMAIL_USER or not EMAIL_DESTINO:
        log("Credenciales SendGrid no configuradas.")
        return
    activas = [c for c in convocatorias if c["urg"] != "vencido"]
    urgentes = len([c for c in activas if c["urg"] == "urgente"])
    asunto = f"LicitAlertas {fecha} — {urgentes} URGENTES | {len(activas)} convocatorias [{fuente}]" if urgentes > 0 \
             else f"LicitAlertas {fecha} — {len(activas)} convocatorias [{fuente}]"
    html = generar_html(convocatorias, fecha, fuente)
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": EMAIL_DESTINO}]}],
            "from": {"email": EMAIL_USER},
            "subject": asunto,
            "content": [{"type": "text/html", "value": html}],
        }
    )
    if resp.status_code == 202:
        log(f"Email enviado a {EMAIL_DESTINO}")
    else:
        log(f"Error email: {resp.status_code} {resp.text}")

def main():
    fecha = datetime.now().strftime("%d/%m/%Y")
    log("Iniciando LicitAlertas...")

    fuente = "SEACE Excel"
    contenido = descargar_excel_github()

    if contenido:
        convocatorias = procesar_excel(contenido)
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
        "fuente": fuente,
        "total": len(convocatorias),
        "convocatorias": convocatorias,
    }
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"datos.json guardado: {len(convocatorias)} convocatorias — fuente: {fuente}")

    enviar_email(convocatorias, fecha, fuente)
    log("Proceso completado.")

if __name__ == "__main__":
    main()
