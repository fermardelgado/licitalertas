import os
import json
import requests
from datetime import datetime, timedelta

SENDGRID_API_KEY  = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_USER        = os.environ.get("EMAIL_USER", "")
EMAIL_DESTINO     = os.environ.get("EMAIL_DESTINO", "")
BRIGHTDATA_HOST   = os.environ.get("BRIGHTDATA_HOST", "")
BRIGHTDATA_PORT   = os.environ.get("BRIGHTDATA_PORT", "")
BRIGHTDATA_USER   = os.environ.get("BRIGHTDATA_USER", "")
BRIGHTDATA_PASS   = os.environ.get("BRIGHTDATA_PASS", "")


# ─── PROXY ───────────────────────────────────────────────────────────────────

def get_proxies():
    if not BRIGHTDATA_HOST:
        return None
    proxy_url = f"http://{BRIGHTDATA_USER}:{BRIGHTDATA_PASS}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}"
    return {"http": proxy_url, "https": proxy_url}


# ─── OBTENER DATOS DESDE API OCDS ────────────────────────────────────────────

def obtener_convocatorias():
    print("Consultando API OCDS de OECE via proxy...")
    proxies = get_proxies()
    if proxies:
        print(f"Proxy configurado: {BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}")
    else:
        print("Sin proxy — intentando conexion directa")

    convocatorias = []

    url = "https://contratacionesabiertas.oece.gob.pe/api/v1/releases"
    params = {
        "page": 1,
        "order": "desc",
    }

    pagina = 1
    max_paginas = 5

    while pagina <= max_paginas:
        params["page"] = pagina
        try:
            print(f"  Pagina {pagina}...")
            resp = requests.get(
                url,
                params=params,
                proxies=proxies,
                timeout=30,
                verify=False
            )
            print(f"  Status: {resp.status_code}")

            if resp.status_code != 200:
                print(f"  Error HTTP: {resp.text[:200]}")
                break

            data = resp.json()
            releases = data.get("releases", [])
            print(f"  Registros: {len(releases)}")

            if not releases:
                break

            for r in releases:
                conv = extraer_de_release(r)
                if conv:
                    convocatorias.append(conv)

            if data.get("next"):
                pagina += 1
            else:
                break

        except Exception as e:
            print(f"  Error en pagina {pagina}: {e}")
            break

    print(f"Total convocatorias: {len(convocatorias)}")
    return convocatorias


def extraer_de_release(release):
    try:
        tender = release.get("tender", {})
        if not tender:
            return None

        fecha_cierre = tender.get("tenderPeriod", {}).get("endDate", "")
        if fecha_cierre:
            fecha_cierre = fecha_cierre[:10]

        monto = 0.0
        valor = tender.get("value", {})
        if valor:
            try:
                monto = float(valor.get("amount", 0) or 0)
            except:
                monto = 0.0

        entidad = ""
        buyer = release.get("buyer", {})
        if buyer:
            entidad = buyer.get("name", "")

        region = "Lima"
        addr = buyer.get("address", {})
        if addr:
            region = addr.get("region", addr.get("locality", "Lima")) or "Lima"

        return {
            "id":                release.get("ocid", "")[-20:],
            "titulo":            tender.get("title", "Sin titulo") or "Sin titulo",
            "entidad":           entidad,
            "tipo":              tender.get("procurementMethodDetails", ""),
            "monto":             monto,
            "region":            region,
            "fecha_vencimiento": fecha_cierre,
            "url_seace":         f"https://contratacionesabiertas.oece.gob.pe/proceso/{release.get('ocid','')}",
        }
    except Exception as e:
        print(f"  Error extrayendo release: {e}")
        return None


# ─── DATOS DE RESPALDO ───────────────────────────────────────────────────────

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


# ─── URGENCIA Y EMAIL ────────────────────────────────────────────────────────

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
    urgentes = [c for c in convocatorias if c["urg"] == "urgente"]
    proximas  = [c for c in convocatorias if c["urg"] == "proximo"]
    normales  = [c for c in convocatorias if c["urg"] == "normal"]

    def fila(c, color):
        dias = c["dias"]
        label = "HOY" if dias == 0 else f"{dias} dias"
        return (
            f'<tr>'
            f'<td style="padding:8px;font-size:13px">{str(c["titulo"])[:70]}</td>'
            f'<td style="padding:8px;font-size:12px;color:#666">{c["entidad"]}</td>'
            f'<td style="padding:8px;font-size:12px;color:#666">S/. {c["monto"]:,.0f}</td>'
            f'<td style="padding:8px;font-size:12px;color:#666">{c["region"]}</td>'
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
            f'<table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden">'
            f'<thead><tr style="background:#f7fafc">'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">TITULO</th>'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">ENTIDAD</th>'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">MONTO</th>'
            f'<th style="padding:8px;text-align:left;font-size:11px;color:#999">REGION</th>'
            f'<th style="padding:8px;text-align:center;font-size:11px;color:#999">VENCE</th>'
            f'</tr></thead><tbody>{filas}</tbody></table>'
        )

    badge = "SEACE REAL" if fuente != "Respaldo" else "RESPALDO"
    color_badge = "#38a169" if fuente != "Respaldo" else "#e53e3e"

    return f'''<html><body style="font-family:Arial,sans-serif;background:#f0f4f8;padding:20px">
    <div style="max-width:860px;margin:0 auto">
    <div style="background:linear-gradient(135deg,#1a365d,#2b6cb0);color:white;padding:20px 30px;border-radius:12px 12px 0 0">
    <h1 style="margin:0;font-size:20px">LicitAlertas — Reporte Diario</h1>
    <p style="margin:4px 0 0;opacity:0.85">{fecha} | {len(convocatorias)} convocatorias | {len(urgentes)} urgentes |
    <span style="background:{color_badge};padding:2px 8px;border-radius:10px;font-size:11px">{badge}</span></p>
    </div>
    <div style="background:white;padding:20px 30px;border-radius:0 0 12px 12px">
    {tabla("URGENTES — Vencen en 3 dias o menos", urgentes, "#e53e3e")}
    {tabla("PROXIMAS — Vencen en 10 dias o menos", proximas, "#d69e2e")}
    {tabla("NORMALES", normales[:20], "#38a169")}
    </div></div></body></html>'''


def enviar_email(convocatorias, fecha, fuente):
    if not SENDGRID_API_KEY or not EMAIL_USER or not EMAIL_DESTINO:
        print("Credenciales SendGrid no configuradas.")
        return
    urgentes = len([c for c in convocatorias if c["urg"] == "urgente"])
    asunto = f"LicitAlertas {fecha} — {urgentes} URGENTES | {len(convocatorias)} convocatorias [{fuente}]" if urgentes > 0 \
             else f"LicitAlertas {fecha} — {len(convocatorias)} convocatorias [{fuente}]"
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
        print(f"Email enviado a {EMAIL_DESTINO}")
    else:
        print(f"Error email: {resp.status_code} {resp.text}")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    fecha = datetime.now().strftime("%d/%m/%Y")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Iniciando LicitAlertas...")

    convocatorias = obtener_convocatorias()
    fuente = "API OECE"

    if not convocatorias:
        print("Usando datos de respaldo.")
        convocatorias = datos_respaldo()
        fuente = "Respaldo"

    for c in convocatorias:
        c["dias"] = dias_restantes(c.get("fecha_vencimiento", ""))
        c["urg"]  = urgencia(c["dias"])
        print(f"DEBUG: {c['titulo'][:40]} | vence: {c['fecha_vencimiento']} | dias: {c['dias']} | urg: {c['urg']}")

    # convocatorias = [c for c in convocatorias if c["urg"] != "vencido"]

    output = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fuente": fuente,
        "total": len(convocatorias),
        "convocatorias": convocatorias,
    }
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"datos.json guardado: {len(convocatorias)} convocatorias — fuente: {fuente}")

    enviar_email(convocatorias, fecha, fuente)
    print("Proceso completado.")


if __name__ == "__main__":
    main()
