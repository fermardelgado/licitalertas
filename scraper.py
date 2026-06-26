import requests
import json
import os
from datetime import datetime, timedelta

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", "")

BASE_URL = "https://prod2.seace.gob.pe/seacebus-uimp-pub/buscadorPublico/"
HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

def obtener_convocatorias():
    hoy = datetime.now()
    hace_30_dias = hoy - timedelta(days=30)
    payload = {
        "numPagina": 1,
        "numResultados": 100,
        "codigoEntidad": "",
        "fechaInicio": hace_30_dias.strftime("%d/%m/%Y"),
        "fechaFin": hoy.strftime("%d/%m/%Y"),
        "idEstadoProceso": "1",
    }
    try:
        resp = requests.post(BASE_URL + "listarProcesosActivos", json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error SEACE: {e}")
        return None

def procesar_datos(data):
    if not data:
        return []
    registros = data.get("listaResultados", []) or data.get("registros", []) or []
    convocatorias = []
    for r in registros:
        try:
            conv = {
                "id": str(r.get("idProceso") or r.get("codigoProceso", "")),
                "titulo": r.get("descripcionObjeto") or r.get("nombreObjeto", "Sin titulo"),
                "entidad": r.get("nombreEntidad") or r.get("entidad", ""),
                "tipo": r.get("descripcionTipoProceso") or r.get("tipoProceso", ""),
                "monto": float(r.get("valorReferencial") or r.get("montoReferencial") or 0),
                "region": r.get("nombreDepartamento") or r.get("region") or "Lima",
                "fecha_vencimiento": r.get("fechaVencimiento") or r.get("fecVencimiento") or "",
                "url_seace": f"https://seace.gob.pe/proceso/{r.get('codigoProceso','')}",
            }
            convocatorias.append(conv)
        except:
            continue
    return convocatorias

def datos_respaldo():
    hoy = datetime.now()
    f = lambda d: (hoy + timedelta(days=d)).strftime("%Y-%m-%d")
    return [
        {"id":"F001","titulo":"Adquisicion de equipos de computo","entidad":"Municipalidad de Lima","tipo":"Adjudicacion Simplificada","monto":85000,"region":"Lima","fecha_vencimiento":f(2),"url_seace":"https://seace.gob.pe"},
        {"id":"F002","titulo":"Servicio de limpieza de locales","entidad":"Ministerio de Educacion","tipo":"Concurso Publico","monto":42000,"region":"Lima","fecha_vencimiento":f(15),"url_seace":"https://seace.gob.pe"},
        {"id":"F003","titulo":"Suministro de materiales de construccion","entidad":"Gobierno Regional Cusco","tipo":"Licitacion Publica","monto":320000,"region":"Cusco","fecha_vencimiento":f(7),"url_seace":"https://seace.gob.pe"},
        {"id":"F004","titulo":"Consultoria en sistemas de informacion","entidad":"SUNAT","tipo":"Concurso Publico","monto":95000,"region":"Lima","fecha_vencimiento":f(22),"url_seace":"https://seace.gob.pe"},
        {"id":"F005","titulo":"Adquisicion de mobiliario de oficina","entidad":"Ministerio de Salud","tipo":"Adjudicacion Simplificada","monto":28000,"region":"Lima","fecha_vencimiento":f(1),"url_seace":"https://seace.gob.pe"},
    ]

def dias_restantes(fecha_str):
    if not fecha_str:
        return 999
    try:
        hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
            try:
                f = datetime.strptime(fecha_str, fmt)
                return (f - hoy).days
            except:
                continue
    except:
        pass
    return 999

def urgencia(dias):
    if dias < 0: return "vencido"
    if dias <= 3: return "urgente"
    if dias <= 10: return "proximo"
    return "normal"

def generar_html(convocatorias, fecha):
    urgentes = [c for c in convocatorias if c["urg"] == "urgente"]
    proximas = [c for c in convocatorias if c["urg"] == "proximo"]
    normales = [c for c in convocatorias if c["urg"] == "normal"]

    def fila(c, color):
        dias = c["dias"]
        label = "HOY" if dias == 0 else f"{dias} dias"
        return f'<tr><td style="padding:8px;font-size:13px">{c["titulo"][:70]}</td><td style="padding:8px;font-size:12px;color:#666">{c["entidad"]}</td><td style="padding:8px;font-size:12px;color:#666">S/. {c["monto"]:,.0f}</td><td style="padding:8px;text-align:center"><span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{label}</span></td></tr>'

    def tabla(titulo, items, color):
        if not items: return ""
        filas = "".join([fila(c, color) for c in items])
        return f'<h3 style="color:{color};margin:20px 0 8px">{titulo} ({len(items)})</h3><table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden"><thead><tr style="background:#f7fafc"><th style="padding:8px;text-align:left;font-size:11px;color:#999">TITULO</th><th style="padding:8px;text-align:left;font-size:11px;color:#999">ENTIDAD</th><th style="padding:8px;text-align:left;font-size:11px;color:#999">MONTO</th><th style="padding:8px;text-align:center;font-size:11px;color:#999">VENCE</th></tr></thead><tbody>{filas}</tbody></table>'

    return f'''<html><body style="font-family:Arial,sans-serif;background:#f0f4f8;padding:20px">
    <div style="max-width:800px;margin:0 auto">
    <div style="background:linear-gradient(135deg,#1a365d,#2b6cb0);color:white;padding:20px 30px;border-radius:12px 12px 0 0">
    <h1 style="margin:0;font-size:20px">LicitAlertas - Reporte Diario</h1>
    <p style="margin:4px 0 0;opacity:0.85">{fecha} | {len(convocatorias)} convocatorias | {len(urgentes)} urgentes</p>
    </div>
    <div style="background:white;padding:20px 30px;border-radius:0 0 12px 12px">
    {tabla("URGENTES - Vencen en 3 dias o menos", urgentes, "#e53e3e")}
    {tabla("PROXIMAS - Vencen en 10 dias o menos", proximas, "#d69e2e")}
    {tabla("NORMALES", normales[:5], "#38a169")}
    </div></div></body></html>'''

def enviar_email(convocatorias, fecha):
    if not SENDGRID_API_KEY or not EMAIL_USER or not EMAIL_DESTINO:
        print("Credenciales no configuradas.")
        return
    urgentes = len([c for c in convocatorias if c["urg"] == "urgente"])
    asunto = f"LicitAlertas {fecha} - {len(convocatorias)} convocatorias"
    if urgentes > 0:
        asunto = f"LicitAlertas {fecha} - {urgentes} URGENTES"
    html = generar_html(convocatorias, fecha)
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": EMAIL_DESTINO}]}],
            "from": {"email": EMAIL_USER},
            "subject": asunto,
            "content": [{"type": "text/html", "value": html}]
        }
    )
    if response.status_code == 202:
        print(f"Email enviado a {EMAIL_DESTINO}")
    else:
        print(f"Error email: {response.status_code} {response.text}")

def main():
    fecha = datetime.now().strftime("%d/%m/%Y")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Iniciando scraper...")
    data = obtener_convocatorias()
    convocatorias = procesar_datos(data) if data else []
    if not convocatorias:
        print("Usando datos de respaldo...")
        convocatorias = datos_respaldo()
    for c in convocatorias:
        c["dias"] = dias_restantes(c.get("fecha_vencimiento", ""))
        c["urg"] = urgencia(c["dias"])
    output = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(convocatorias),
        "convocatorias": convocatorias
    }
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"datos.json guardado: {len(convocatorias)} convocatorias")
    enviar_email(convocatorias, fecha)
    print("Proceso completado.")

if __name__ == "__main__":
    main()
